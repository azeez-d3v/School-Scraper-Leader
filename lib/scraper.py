import asyncio
import os
import json
import logging
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from langchain_community.document_loaders import PyPDFLoader

from lib.school_data import SchoolData
from lib.parse import parse_with_langchain
from lib.utils import extract_body_content, clean_body_content, extract_urls
from lib.models import SchoolInfo
from services.session_manager import SessionManager

# Configure logging
logger = logging.getLogger(__name__)

# Create output directories
OUTPUT_DIR = Path("output")
RAW_DATA_DIR = OUTPUT_DIR / "raw_data"
PARSED_DATA_DIR = OUTPUT_DIR / "parsed_data"

for directory in [OUTPUT_DIR, RAW_DATA_DIR, PARSED_DATA_DIR]:
    directory.mkdir(exist_ok=True)

class SchoolScraper:
    """Main class to handle scraping of school data"""   
    def __init__(self):
        self.session_manager = SessionManager()
        self.school_links = SchoolData.get_school_links()
        # Convert links to school data format for compatibility with existing code
        self.schools_data = self._initialize_school_data_from_links()
        
    def _initialize_school_data_from_links(self):
        """
        Initialize school data from the links provided by get_school_links()
        Creates a basic structure for each school based on its domain.
        """
        schools_data = []
        
        for url in self.school_links:
            # Extract domain name to use as school name
            domain = urlparse(url).netloc
            name = domain.replace("www.", "")
            
            # Create a simple name from the domain
            # Example: www.ismanila.org -> International School Manila
            if "ismanila" in name:
                school_name = "International School Manila"
            elif "britishschoolmanila" in name:
                school_name = "British School Manila"
            elif "reedleyschool" in name:
                school_name = "Reedley International School"
            elif "southville" in name:
                school_name = "Southville International School and Colleges"
            elif "singaporeschools" in name:
                school_name = "Singapore School Manila"
            elif "faith.edu" in name:
                school_name = "Faith Academy"
            elif "jca.edu" in name:
                school_name = "Jubilee Christian Academy"
            elif "vcis.edu" in name:
                school_name = "Victory Christian International School"
            else:
                # If it's a new domain not in our mapping, create a generic name
                school_name = " ".join(word.capitalize() for word in name.split('.')[0].split('-'))
                
            # Create the school data structure with basic info
            school_data = {
                "method": "Request",  # Default to using Request method
                "name": school_name,
                "link": url,
                "school_fee": "",
                "program": [],
                "Enrollment Process and Requirements": [],
                "Upcoming Events": [],
                "Discounts and Scholarship": [],
                "Contact Information ": []
            }
            schools_data.append(school_data)
            logger.info(f"Initialized school data for {school_name} with URL: {url}")
            
        return schools_data
        
    async def extract_content_from_url(self, url: str, method: str = "Request", progress_callback=None):
        """Extract content from a URL using SessionManager"""
        logger.info(f"Extracting content from URL: {url}")
        try:
            # Check if the URL is a PDF (either by extension or content type)
            is_pdf = url.lower().endswith('.pdf')
            content = ""
            
            if is_pdf:
                logger.info(f"Detected PDF URL: {url}")
                # Create a temporary file to store the PDF
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                    try:
                        # Download the PDF using the session manager
                        response = await self.session_manager.get(url)
                        
                        # Check if we got a valid response
                        if response.status_code >= 400:
                            logger.warning(f"HTTP error {response.status_code} for PDF {url}")
                            return f"Error downloading PDF: HTTP status {response.status_code}"
                        
                        # For PDF downloads we need to access the binary content
                        if hasattr(response.original, 'content'):
                            pdf_content = response.original.content
                        else:
                            logger.warning(f"Could not access binary content for PDF {url}")
                            return "Error: Could not download PDF content"
                        
                        # Check if the PDF content is empty
                        if not pdf_content or len(pdf_content) < 100:  # Consider very small files (< 100 bytes) as potentially empty
                            logger.warning(f"Empty or very small PDF content detected for {url} ({len(pdf_content) if pdf_content else 0} bytes)")
                            return f"PDF appears to be empty or unavailable: {url}"
                        
                        # Write the PDF content to the temporary file
                        temp_pdf.write(pdf_content)
                        temp_pdf_path = temp_pdf.name
                        
                        logger.info(f"PDF downloaded to temporary file: {temp_pdf_path}")
                        
                        try:
                            # Use PyPDFLoader to extract text from the PDF
                            loader = PyPDFLoader(temp_pdf_path)
                            pages = loader.load_and_split()
                            
                            # Combine all pages' text content
                            pdf_text = "\n\n".join([page.page_content for page in pages])
                            
                            # Check if the extracted text is empty
                            if not pdf_text or len(pdf_text.strip()) == 0:
                                logger.warning(f"No text content extracted from PDF {url}")
                                return f"PDF found but no text content could be extracted: {url}"
                                
                            logger.info(f"Successfully extracted text from PDF, length: {len(pdf_text)} characters")
                            
                            # Return the extracted text with PDF metadata
                            extracted_content = f"[PDF CONTENT FROM: {url}]\n\n{pdf_text}"
                            
                        except Exception as pdf_error:
                            # Handle specifically the EmptyFileError
                            if "Cannot read an empty file" in str(pdf_error):
                                logger.warning(f"PDF file is empty: {url}")
                                return f"Error processing PDF: File is empty or corrupted"
                            else:
                                # Re-raise the exception to be caught by the outer exception handler
                                raise pdf_error
                        
                        # Update progress if callback provided
                        if progress_callback:
                            progress_callback()
                            
                        # Clean up the temporary file - GRACEFULLY HANDLE DELETION ERRORS
                        try:
                            os.unlink(temp_pdf_path)
                        except Exception as e:
                            logger.warning(f"Could not delete temporary PDF file {temp_pdf_path}: {str(e)}")
                            # The file will be cleaned up by the OS eventually
                        
                        return extracted_content
                        
                    except Exception as e:
                        # Clean up the temporary file if an error occurred
                        try:
                            os.unlink(temp_pdf_path)
                        except Exception as cleanup_error:
                            logger.warning(f"Could not delete temporary PDF file {temp_pdf_path} during error handling: {str(cleanup_error)}")
                        
                        logger.error(f"Error processing PDF {url}: {str(e)}", exc_info=True)
                        return f"Error processing PDF: {str(e)}"
            
            # Non-PDF content handling with Request
            logger.info(f"Using RequestSession for URL: {url}")
            response = await self.session_manager.get(url)
            
            # Check if we got a valid response
            if response.status_code >= 400:
                logger.warning(f"HTTP error {response.status_code} for {url}")
                return ""
            
            # Check if response is actually a PDF (content type check)
            if hasattr(response.original, 'headers') and 'content-type' in response.original.headers:
                content_type = response.original.headers['content-type'].lower()
                if 'application/pdf' in content_type:
                    logger.info(f"Detected PDF content type for {url}")
                    # Call this method again but with the is_pdf flag
                    url_obj = urlparse(url)
                    pdf_filename = os.path.basename(url_obj.path)
                    if not pdf_filename.lower().endswith('.pdf'):
                        # Modify URL to have .pdf extension for our detection
                        if '?' in url:
                            url = url.split('?')[0] + '.pdf'
                        else:
                            url = url + '.pdf'
                    return await self.extract_content_from_url(url, method, progress_callback)
            
            content = response.text
            
            if not content:
                logger.warning(f"Empty content received for {url}")
                return ""
                
            logger.info(f"Successfully got content from {url} ({len(content)} bytes)")
            
            # Extract body content
            body_content = extract_body_content(content)
            if not body_content:
                logger.warning(f"Could not extract body content from {url}")
                return ""
                
            # Clean content
            cleaned_content = clean_body_content(body_content)
            if not cleaned_content:
                logger.warning(f"Content cleaning resulted in empty content for {url}")
                return ""
                
            logger.info(f"Successfully extracted and cleaned content from {url} ({len(cleaned_content)} bytes)")
            
            # Update progress if callback provided
            if progress_callback:
                progress_callback()
                
            return cleaned_content
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}", exc_info=True)
            return ""  
          
    async def process_school(self, school_data, progress_bar=None, status_text=None):
        """Process a single school's data and extract content from all URLs"""
        school_name = school_data.get("name", "Unknown School")
        
        if status_text:
            status_text.text(f"Processing school: {school_name}")
            
        logger.info(f"Processing school: {school_name}")
        
        method = school_data.get("method", "Request")
        school_link = school_data.get("link", "")
        
        # Prepare a raw content file for this school
        raw_file_path = RAW_DATA_DIR / f"{school_name.replace(' ', '_')}_raw.txt"
        
        # Use the URL extractor API to get relevant links
        if status_text:
            status_text.text(f"Extracting URLs from {school_name} website...")
            
        logger.info(f"Extracting URLs from {school_link} using API")
        all_urls = await extract_urls(school_link)
        
        # Organize extracted URLs by category
        extracted_links = self._categorize_urls(all_urls, school_link, school_name)
        
        # Log the extracted links
        logger.info(f"Extracted links for {school_name}: {extracted_links}")
        
        # Collect all links to scrape
        all_links = []
        
        # School fee link(s)
        fee_links = extracted_links.get("school_fee", [])
        if not fee_links and "school_fee" in school_data and school_data["school_fee"]:
            # Fall back to hardcoded links if API didn't find any
            fee_links = school_data.get("school_fee", [])
            logger.info(f"Falling back to hardcoded school fee links for {school_name}")
            
        if isinstance(fee_links, str) and fee_links:
            all_links.append(("school_fee", fee_links))
        elif isinstance(fee_links, list):
            for link in fee_links:
                if link:
                    all_links.append(("school_fee", link))
        
        # Program links
        program_links = extracted_links.get("program", [])
        if not program_links and "program" in school_data and school_data["program"]:
            # Fall back to hardcoded links if API didn't find any
            program_links = school_data.get("program", [])
            logger.info(f"Falling back to hardcoded program links for {school_name}")
            
        for link in program_links:
            if link:
                all_links.append(("program", link))
        
        # Enrollment links
        enrollment_links = extracted_links.get("enrollment", [])
        if not enrollment_links and "Enrollment Process and Requirements" in school_data and school_data["Enrollment Process and Requirements"]:
            # Fall back to hardcoded links if API didn't find any
            enrollment_links = school_data.get("Enrollment Process and Requirements", [])
            logger.info(f"Falling back to hardcoded enrollment links for {school_name}")
            
        for link in enrollment_links:
            if link:
                all_links.append(("enrollment", link))
        
        # Events links
        event_links = extracted_links.get("events", [])
        if not event_links and "Upcoming Events" in school_data and school_data["Upcoming Events"]:
            # Fall back to hardcoded links if API didn't find any
            event_links = school_data.get("Upcoming Events", [])
            logger.info(f"Falling back to hardcoded event links for {school_name}")
            
        for link in event_links:
            if link:
                all_links.append(("events", link))
        
        # Scholarship links
        scholarship_links = extracted_links.get("scholarships", [])
        if not scholarship_links and "Discounts and Scholarship" in school_data and school_data["Discounts and Scholarship"]:
            # Fall back to hardcoded links if API didn't find any
            scholarship_links = school_data.get("Discounts and Scholarship", [])
            logger.info(f"Falling back to hardcoded scholarship links for {school_name}")
            
        for link in scholarship_links:
            if link:
                all_links.append(("scholarships", link))
        
        # Contact links
        contact_links = extracted_links.get("contact", [])
        if not contact_links and "Contact Information " in school_data and school_data["Contact Information "]:
            # Fall back to hardcoded links if API didn't find any
            contact_links = school_data.get("Contact Information ", [])
            logger.info(f"Falling back to hardcoded contact links for {school_name}")
            
        for link in contact_links:
            if link:
                all_links.append(("contact", link))
                  # Calculate total number of links for progress
        total_links = len(all_links) + 1  # +1 for main page
        progress_step = 1.0 / total_links if total_links > 0 else 1.0
        progress_value = 0.0
        
        # Log the final set of links that will be scraped
        logger.info(f"Final links to scrape for {school_name}:")
        for category, link in all_links:
            logger.info(f"  - {category}: {link}")
        logger.info(f"Total links to scrape: {total_links} (including main page)")
                
        with open(raw_file_path, "w", encoding="utf-8") as f:
            # Write school main information
            f.write(f"School: {school_name}\n")
            f.write(f"Main URL: {school_link}\n")
            f.write("=" * 80 + "\n\n")
            
            # Process main school link
            if status_text:
                status_text.text(f"Fetching main page for: {school_name}")
                
            # Make sure to use the school's specified method for the main page
            main_content = await self.extract_content_from_url(school_link, method)
            f.write("MAIN PAGE CONTENT:\n")
            f.write(main_content)
            f.write("\n\n" + "=" * 20 + "PAGE" + "=" * 20 + "\n\n")
              # Update progress
            progress_value += progress_step
            if progress_bar:
                progress_bar.progress(progress_value)
            
            # Process all links in parallel
            if status_text:
                status_text.text(f"Fetching data from {len(all_links)} links for {school_name} in parallel...")
                
            logger.info(f"Processing {len(all_links)} links for {school_name} in parallel")
            
            # Set a reasonable concurrency limit to avoid overwhelming the server
            # Adjust this value based on server capacity and rate limiting considerations
            concurrency_limit = 5
            
            # Process links in batches to control concurrency
            results = []
            for i in range(0, len(all_links), concurrency_limit):
                batch = all_links[i:i + concurrency_limit]
                batch_tasks = [self._process_single_link(link_info, method, f, status_text) for link_info in batch]
                batch_results = await asyncio.gather(*batch_tasks)
                results.extend(batch_results)
                
                # Add a small delay between batches
                if i + concurrency_limit < len(all_links):
                    await asyncio.sleep(2)
            
            # Write all results to the file
            for result in results:
                if result["success"]:
                    category = result["category"]
                    link = result["link"]
                    content = result["content"]
                    
                    # Write content to the raw data file, including PDF content
                    f.write(f"{category.upper()} PAGE CONTENT ({link}):\n")
                    # Check if this is PDF content and ensure it's written correctly
                    if content.startswith("[PDF CONTENT FROM:"):
                        # Ensure PDF content is correctly written as is
                        logger.info(f"Writing PDF content for {link} to raw data file")
                        f.write(content)
                    else:
                        f.write(content)
                    f.write("\n\n" + "=" * 20 + "PAGE" + "=" * 20 + "\n\n")
                else:
                    # Write error information to the raw data file for troubleshooting
                    f.write(f"ERROR processing {result['category']} link {result['link']}: {result.get('error', 'Unknown error')}\n\n")
                
                # Update progress
                progress_value += progress_step
                if progress_bar:
                    progress_bar.progress(min(progress_value, 1.0))
        
        logger.info(f"Completed raw data extraction for {school_name}")
        if status_text:
            status_text.text(f"Completed data extraction for {school_name}")
            
        return {
            "school_name": school_name,
            "raw_file_path": str(raw_file_path)
        }
    
    async def parse_school_data(self, raw_data_info, status_text=None):
        """Parse the raw school data using the AI model and structure it according to our model"""
        school_name = raw_data_info["school_name"]
        raw_file_path = raw_data_info["raw_file_path"]
        
        if status_text:
            status_text.text(f"Parsing data for {school_name}")
            
        logger.info(f"Parsing data for {school_name}")
        
        try:
            # Read the raw data file
            with open(raw_file_path, "r", encoding="utf-8") as f:
                raw_content = f.read()
              # Define the parsing description
            parse_description = (
                f"Extract comprehensive information about {school_name} including: "
                "1. Tuition fees, payment schedules, and financial details. "
                "2. Academic programs, curriculum offerings, and educational approaches. "
                "3. Enrollment requirements, application process, and documentation needed. "
                "4. Upcoming events and school calendar information. "
                "5. Scholarships, discounts, and financial aid opportunities. "
                "6. Campus facilities, infrastructure, laboratories, libraries, sports facilities, and resources. "
                "7. Faculty information, staff credentials, notable teachers, and organizational structure. "
                "8. School achievements, awards, accreditations, and recognitions. "
                "9. Marketing approach, taglines, value propositions, and key messaging. "
                "10. Technology infrastructure, digital platforms, and learning management systems. "
                "11. Student life details, clubs, activities, testimonials, and campus culture. "
                "12. Contact information and communication channels. "
                "Pay special attention to unique features, differentiators, or specialized offerings that make this school stand out."
            )
            
            # Parse the content with structured output format
            parsed_result = parse_with_langchain(
                raw_content, 
                parse_description, 
                school_name=school_name
            )
            
            # Get the school's link from our school data
            school_link = next((school for school in self.schools_data if school.get("name") == school_name), {}).get("link", "")
            
            # If parsed_result is a dict, it's already in the new format
            if isinstance(parsed_result, dict):
                # Make sure the link is set
                parsed_result["link"] = school_link
            else:
                # Legacy format - create a basic structure
                school_info = SchoolInfo(
                    name=school_name,
                    link=school_link
                )
                parsed_result = school_info.to_dict()
            
            # Save parsed data to a JSON file
            parsed_file_path = PARSED_DATA_DIR / f"{school_name.replace(' ', '_')}_parsed.json"
            with open(parsed_file_path, "w", encoding="utf-8") as f:
                json.dump(parsed_result, f, indent=2)
            
            logger.info(f"Completed parsing data for {school_name}")
            if status_text:
                status_text.text(f"Completed parsing data for {school_name}")
                
            return parsed_result
            
        except Exception as e:
            logger.error(f"Error parsing data for {school_name}: {e}", exc_info=True)
            # Return a basic structure with error information
            if status_text:
                status_text.text(f"Error parsing data for {school_name}: {str(e)}")
                
            # Create a failsafe response with error information
            error_info = SchoolInfo(
                name=school_name,
                link=next((school for school in self.schools_data if school.get("name") == school_name), {}).get("link", "")
            )
            error_info.notes = f"Error during parsing: {str(e)}"
            
            return error_info.to_dict()
    def _extract_section(self, text: str, section_header: str) -> str:
        """Helper method to extract a section from the parsed text"""
        try:
            # Try exact header match first
            section_pattern = re.escape(section_header)
            headers = [
                "Tuition Fees:", "Programs Offered:", "Enrollment Requirements:", 
                "Enrollment Process:", "Upcoming Events:", "Scholarships/Discounts:", 
                "Facilities:", "Faculty Information:", "Achievements:", "Marketing Content:",
                "Technical Data:", "Student Life:", "Contact Information:", "Notes:"
            ]
            
            # Create pattern to find the end of this section (start of next section)
            escaped_headers = [re.escape(header) for header in headers if header != section_header]
            end_pattern = '|'.join(escaped_headers)
            
            start_match = re.search(f"{section_pattern}\\s*(.*?)(?=(?:{end_pattern})|$)", 
                                   text, re.DOTALL)
            
            if not start_match:
                # Try case-insensitive match
                start_match = re.search(f"{section_pattern}\\s*(.*?)(?=(?:{end_pattern})|$)", 
                                      text, re.DOTALL | re.IGNORECASE)
                
            if not start_match:
                # Try matching with just the key part of the section header
                key_part = section_header.split(":")[0]
                section_pattern = re.escape(key_part)
                start_match = re.search(f"{section_pattern}[:\s]+(.*?)(?=(?:{end_pattern})|$)", 
                                      text, re.DOTALL | re.IGNORECASE)
            
            if start_match:
                section_text = start_match.group(1).strip()
                # Clean up the extraction
                section_text = re.sub(r'\*\*|\*|-\*', '', section_text)
                section_text = re.sub(r'^\s*[-•*]\s*', '', section_text, flags=re.MULTILINE)
                
                if not section_text or section_text.lower() in ["no data available", "no information available", "n/a"]:
                    return "No information available"
                return section_text
            else:
                return "No information available"
                
        except Exception as e:
            logger.error(f"Error extracting section {section_header}: {e}")
            return "No information available"
    
    async def close(self):
        """Close resources"""
        pass
    
    def _categorize_urls(self, urls, base_url, school_name):
        """
        Categorize the extracted URLs into different sections of school information.
        
        Args:
            urls (list): List of URLs extracted from the school website
            base_url (str): The base URL of the school website
            school_name (str): The name of the school
            
        Returns:
            dict: A dictionary mapping categories to lists of URLs
        """
        # Initialize categories
        categories = {
            "school_fee": [],
            "program": [],
            "enrollment": [],
            "events": [],
            "scholarships": [],
            "contact": []
        }
        
        # Keywords for categorization
        keywords = {
            "school_fee": ["fee", "cost", "tuition", "payment", "financial", "finances"],
            "program": ["program", "course", "curriculum", "academic", "study", "learning"],
            "enrollment": ["enrollment", "admission", "apply", "application", "register", "how to", "requirements"],
            "events": ["event", "calendar", "schedule", "upcoming", "news"],
            "scholarships": ["scholarship", "grant", "financial aid", "discount", "merit", "award", "bursary"],
            "contact": ["contact", "location", "address", "phone", "email", "inquiry", "faq"]
        }
        
        logger.info(f"Categorizing {len(urls)} URLs for {school_name}")
        
        # Process each URL
        for url in urls:
            # Skip if URL is empty or None
            if not url:
                continue
                
            # Skip if URL is not from the same domain
            if not (base_url in url or urlparse(url).netloc == urlparse(base_url).netloc):
                continue
                
            # Convert to lowercase for easier matching
            url_lower = url.lower()
            
            # Check each category
            for category, keywords_list in keywords.items():
                for keyword in keywords_list:
                    if keyword in url_lower:
                        categories[category].append(url)
                        # Log the categorization
                        logger.info(f"Categorized URL as {category}: {url}")
                        break
        
        # Remove duplicates from each category
        for category in categories:
            categories[category] = list(set(categories[category]))
            logger.info(f"Found {len(categories[category])} URLs for {category} category")
        
        return categories
    
    async def _process_single_link(self, link_info, method, file_handle, status_text=None):
        """Process a single link and return the content and progress update
        
        Args:
            link_info: Tuple of (category, link)
            method: Scraping method to use
            file_handle: File handle to write to (don't write directly, return content)
            status_text: Streamlit status text object
            
        Returns:
            Dictionary with content, category, link and success status
        """
        category, link = link_info
        
        try:
            if status_text:
                status_text.text(f"Fetching {category} data from {link}")
                
            logger.info(f"Extracting {category} data from {link} using method: {method}")
            
            # Pass the school's method to ensure correct scraping technique is used
            content = await self.extract_content_from_url(link, method)
            
            if content:
                return {
                    "success": True,
                    "category": category,
                    "link": link,
                    "content": content
                }
            else:
                return {
                    "success": False,
                    "category": category,
                    "link": link,
                    "error": "No content extracted"
                }
                
        except Exception as e:
            logger.error(f"Error processing {category} link {link}: {e}")
            return {
                "success": False,
                "category": category,
                "link": link,
                "error": str(e)
            }