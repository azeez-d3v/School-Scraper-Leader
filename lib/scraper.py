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
from lib.utils import extract_body_content, clean_body_content
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
        self.schools_data = SchoolData.get_schools_list()
        
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
                        
                        # Write the PDF content to the temporary file
                        temp_pdf.write(pdf_content)
                        temp_pdf_path = temp_pdf.name
                        
                        logger.info(f"PDF downloaded to temporary file: {temp_pdf_path}")
                        
                        # Use PyPDFLoader to extract text from the PDF
                        loader = PyPDFLoader(temp_pdf_path)
                        pages = loader.load_and_split()
                        
                        # Combine all pages' text content
                        pdf_text = "\n\n".join([page.page_content for page in pages])
                        
                        logger.info(f"Successfully extracted text from PDF, length: {len(pdf_text)} characters")
                        
                        # Return the extracted text with PDF metadata
                        extracted_content = f"[PDF CONTENT FROM: {url}]\n\n{pdf_text}"
                        
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
        
        # Collect all links to scrape
        all_links = []
        
        # School fee link(s)
        fee_links = school_data.get("school_fee", [])
        if isinstance(fee_links, str) and fee_links:
            all_links.append(("school_fee", fee_links))
        elif isinstance(fee_links, list):
            for link in fee_links:
                if link:
                    all_links.append(("school_fee", link))
        
        # Program links
        for link in school_data.get("program", []):
            if link:
                all_links.append(("program", link))
        
        # Enrollment links
        for link in school_data.get("Enrollment Process and Requirements", []):
            if link:
                all_links.append(("enrollment", link))
        
        # Events links
        for link in school_data.get("Upcoming Events", []):
            if link:
                all_links.append(("events", link))
        
        # Scholarship links
        for link in school_data.get("Discounts and Scholarship", []):
            if link:
                all_links.append(("scholarships", link))
        
        # Contact links
        for link in school_data.get("Contact Information ", []):
            if link:
                all_links.append(("contact", link))
                
        # Calculate total number of links for progress
        total_links = len(all_links) + 1  # +1 for main page
        progress_step = 1.0 / total_links if total_links > 0 else 1.0
        progress_value = 0.0
                
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
            
            # Process each link
            for category, link in all_links:
                try:
                    if status_text:
                        status_text.text(f"Fetching {category} data from {link}")
                        
                    logger.info(f"Extracting {category} data from {link} using method: {method}")
                    
                    # Pass the school's method to ensure correct scraping technique is used
                    content = await self.extract_content_from_url(link, method)
                    
                    if content:
                        f.write(f"{category.upper()} PAGE CONTENT ({link}):\n")
                        f.write(content)
                        f.write("\n\n" + "=" * 20 + "PAGE" + "=" * 20 + "\n\n")
                    
                    # Update progress
                    progress_value += progress_step
                    if progress_bar:
                        progress_bar.progress(min(progress_value, 1.0))
                    
                    # Add a small delay to avoid overloading servers
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing {category} link {link} for {school_name}: {e}")
        
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
                f"Extract information about {school_name} including tuition fees, "
                "programs offered, enrollment requirements and process, upcoming events, "
                "scholarships/discounts, and contact information. "
                "Make sure to include specific details about tuition costs, program offerings, "
                "and all application requirements."
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
                "Contact Information:", "Notes:"
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