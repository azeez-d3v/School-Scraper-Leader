import streamlit as st
from datetime import datetime
from pathlib import Path
import asyncio
import os
import json
import logging
import re
import tempfile
import time
import pandas as pd
from urllib.parse import urlparse
from langchain_community.document_loaders import PyPDFLoader

# Local imports
from lib.school_data import SchoolData
from lib.parse import parse_with_langchain
from lib.utils import extract_body_content, clean_body_content
from lib.models import SchoolInfo
from services.session_manager import SessionManager
from services.playwright_manager import PlaywrightManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("streamlit_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create output directories
OUTPUT_DIR = Path("output")
RAW_DATA_DIR = OUTPUT_DIR / "raw_data"
PARSED_DATA_DIR = OUTPUT_DIR / "parsed_data"

for directory in [OUTPUT_DIR, RAW_DATA_DIR, PARSED_DATA_DIR]:
    directory.mkdir(exist_ok=True)

class StreamlitSchoolScraper:
    """Main class to handle scraping of school data with Streamlit integration"""

    def __init__(self):
        self.session_manager = SessionManager()
        self.playwright_manager = None  # Initialize only when needed
        self.schools_data = SchoolData.get_schools_list()
        
    async def initialize_playwright(self):
        """Initialize playwright manager if needed"""
        if self.playwright_manager is None:
            self.playwright_manager = PlaywrightManager()
            try:
                await self.playwright_manager.initialize()
                return True
            except Exception as e:
                logger.error(f"Failed to initialize Playwright. Using session_manager as fallback: {e}")
                return False
        return True
        
    async def extract_content_from_url(self, url: str, method: str = "Request", progress_callback=None):
        """Extract content from a URL using either RequestSession or Playwright"""
        logger.info(f"Extracting content from URL: {url} using method: {method}")
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
                        
                        # Return the extracted text
                        if progress_callback:
                            progress_callback()
                            
                        # Clean up the temporary file
                        os.unlink(temp_pdf_path)
                        
                        return f"[PDF CONTENT FROM: {url}]\n\n{pdf_text}"
                        
                    except Exception as e:
                        # Clean up the temporary file if an error occurred
                        try:
                            os.unlink(temp_pdf_path)
                        except:
                            pass
                        
                        logger.error(f"Error processing PDF {url}: {str(e)}", exc_info=True)
                        return f"Error processing PDF: {str(e)}"
            
            # Non-PDF content handling continues as before
            if method.lower() == "playwright":
                # Initialize playwright if needed
                await self.initialize_playwright()
                
                logger.info(f"Using Playwright for URL: {url}")
                content = await self.playwright_manager.get_page_content(url)
                if not content:
                    logger.warning(f"Playwright returned empty content for {url}")
                    return ""
            else:  # Default to request
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
                from lib.models import SchoolInfo
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
            from lib.models import SchoolInfo
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
        if self.playwright_manager is not None:
            await self.playwright_manager.close()


# Utility function to handle asyncio within Streamlit
async def process_schools_async(schools_to_process, scraper, progress_bar, status_text):
    """Process selected schools asynchronously"""
    results = []
    
    for school in schools_to_process:
        # First extract the content
        raw_data_info = await scraper.process_school(school, progress_bar, status_text)
        
        # Then parse the data
        parsed_data = await scraper.parse_school_data(raw_data_info, status_text)
        results.append(parsed_data)
        
    return results


def run_async(coro):
    """Run an async function from sync code"""
    try:
        return asyncio.run(coro)
    except Exception as e:
        st.error(f"Error in async operation: {e}")
        raise e


# Main Streamlit app
def main():
    st.set_page_config(
        page_title="AI School Web Scraper",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 AI School Web Scraper")
    st.markdown("""
    This application scrapes school websites, extracts relevant information using AI, and presents the results.
    The process involves:
    1. Fetching HTML content from school websites
    2. Saving the content as text files
    3. Using Gemini AI to parse structured information
    """)
    
    # Initialize the scraper on first run
    if 'scraper' not in st.session_state:
        st.session_state.scraper = StreamlitSchoolScraper()
        
    # Get schools list
    schools_data = st.session_state.scraper.schools_data
    
    # Sidebar for configuration and controls
    with st.sidebar:
        st.header("Configuration")
        
        # School selection
        st.subheader("Select Schools to Scrape")
        
        # Create checkboxes for each school
        selected_schools = []
        for school in schools_data:
            school_name = school.get("name")
            if st.checkbox(school_name, value=True):
                selected_schools.append(school)
        
        # Start scraping button
        st.subheader("Actions")
        start_button = st.button("Start Scraping", disabled=len(selected_schools) == 0)
    
    # Main area for displaying results
    if start_button and selected_schools:
        # Create a progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("Initializing scraper...")
        
        # Process the selected schools
        try:
            status_text.text("Starting scraping process...")
            
            # Run the async processing
            with st.spinner("Scraping and processing school data..."):
                results = run_async(process_schools_async(
                    selected_schools,
                    st.session_state.scraper,
                    progress_bar,
                    status_text
                ))
            
            # Display results
            progress_bar.progress(1.0)
            status_text.text("Processing complete!")
            
            # Show tabs for each school
            if len(results) > 0:
                school_tabs = st.tabs([result["name"] for result in results])
                
                for i, (tab, result) in enumerate(zip(school_tabs, results)):
                    with tab:
                        st.header(result["name"])
                        st.markdown(f"[Visit Website]({result.get('link', '#')})")
                        
                        # Display information in expandable sections
                        # School Fees
                        if result.get("school_fee") and result["school_fee"] != "No information available":
                            with st.expander("Tuition Fees", expanded=True):
                                fee_data = result["school_fee"]
                                if isinstance(fee_data, dict) and "academic_year" in fee_data:
                                    # Structured format
                                    st.subheader(f"Academic Year: {fee_data.get('academic_year', '')}")
                                    
                                    # Display tuition by level in a table if available
                                    if "tuition_by_level" in fee_data and fee_data["tuition_by_level"]:
                                        st.markdown("### Tuition by Grade Level")
                                        for level, details in fee_data["tuition_by_level"].items():
                                            st.markdown(f"**{level}**")
                                            if isinstance(details, dict):
                                                for key, value in details.items():
                                                    if key != "description":
                                                        st.markdown(f"- {key.capitalize()}: {value}")
                                                if "description" in details:
                                                    st.markdown(details["description"])
                                            else:
                                                st.markdown(str(details))
                                    
                                    # Display other fees
                                    if "other_fees" in fee_data and fee_data["other_fees"]:
                                        st.markdown("### Other Fees")
                                        for fee in fee_data["other_fees"]:
                                            if isinstance(fee, dict):
                                                fee_name = fee.get("name", "")
                                                fee_amount = fee.get("amount", "")
                                                fee_desc = fee.get("description", "")
                                                
                                                st.markdown(f"**{fee_name}**: {fee_amount}")
                                                if fee_desc:
                                                    st.markdown(fee_desc)
                                            else:
                                                st.markdown(str(fee))
                                    
                                    # Display due dates
                                    if "due_dates" in fee_data and fee_data["due_dates"]:
                                        st.markdown("### Payment Due Dates")
                                        for date_info in fee_data["due_dates"]:
                                            if isinstance(date_info, dict):
                                                period = date_info.get("period", "")
                                                date = date_info.get("date", "")
                                                st.markdown(f"**{period}**: {date}")
                                            else:
                                                st.markdown(str(date_info))
                                else:
                                    # Legacy format
                                    st.markdown(str(fee_data))
                                
                        # Programs
                        if result.get("programs") and result["programs"] != "No information available":
                            with st.expander("Programs Offered", expanded=True):
                                programs = result["programs"]
                                if isinstance(programs, list):
                                    for program in programs:
                                        if isinstance(program, dict):
                                            program_name = program.get("name", "")
                                            grade_level = program.get("grade_level", "")
                                            description = program.get("description", "")
                                            
                                            header = program_name
                                            if grade_level:
                                                header += f" ({grade_level})"
                                            
                                            st.markdown(f"**{header}**")
                                            if description:
                                                st.markdown(description)
                                        else:
                                            st.markdown(f"- {program}")
                                else:
                                    st.markdown(programs)
                                
                        # Enrollment Information
                        if result.get("enrollment") and result["enrollment"] != "No information available":
                            with st.expander("Enrollment Information", expanded=True):
                                enrollment_data = result["enrollment"]
                                
                                if isinstance(enrollment_data, dict):
                                    # Requirements
                                    if "requirements" in enrollment_data and enrollment_data["requirements"]:
                                        st.markdown("### Enrollment Requirements")
                                        requirements = enrollment_data["requirements"]
                                        for req in requirements:
                                            st.markdown(f"- {req}")
                                    
                                    # Required Documents
                                    if "documents" in enrollment_data and enrollment_data["documents"]:
                                        st.markdown("### Required Documents")
                                        documents = enrollment_data["documents"]
                                        for doc in documents:
                                            st.markdown(f"- {doc}")
                                    
                                    # Process Steps
                                    if "process_steps" in enrollment_data and enrollment_data["process_steps"]:
                                        st.markdown("### Application Process")
                                        steps = enrollment_data["process_steps"]
                                        for step in steps:
                                            if isinstance(step, dict):
                                                step_num = step.get("step", "")
                                                desc = step.get("description", "")
                                                if step_num:
                                                    st.markdown(f"**Step {step_num}**: {desc}")
                                                else:
                                                    st.markdown(f"- {desc}")
                                            else:
                                                st.markdown(f"- {step}")
                                else:
                                    st.markdown(enrollment_data)
                                
                        # Events
                        if result.get("events") and result["events"] != "No information available":
                            with st.expander("Upcoming Events", expanded=False):
                                events = result["events"]
                                if isinstance(events, list):
                                    for event in events:
                                        if isinstance(event, dict):
                                            event_name = event.get("name", "")
                                            event_date = event.get("date", "")
                                            event_desc = event.get("description", "")
                                            
                                            header = event_name
                                            if event_date:
                                                header += f" ({event_date})"
                                            
                                            st.markdown(f"**{header}**")
                                            if event_desc:
                                                st.markdown(event_desc)
                                        else:
                                            st.markdown(f"- {event}")
                                else:
                                    st.markdown(events)
                                
                        # Scholarships
                        if result.get("scholarships") and result["scholarships"] != "No information available":
                            with st.expander("Scholarships & Discounts", expanded=False):
                                scholarships = result["scholarships"]
                                if isinstance(scholarships, list):
                                    for scholarship in scholarships:
                                        if isinstance(scholarship, dict):
                                            name = scholarship.get("name", "")
                                            eligibility = scholarship.get("eligibility", "")
                                            amount = scholarship.get("amount", "")
                                            description = scholarship.get("description", "")
                                            
                                            st.markdown(f"**{name}**")
                                            if amount:
                                                st.markdown(f"*Amount:* {amount}")
                                            if eligibility:
                                                st.markdown(f"*Eligibility:* {eligibility}")
                                            if description:
                                                st.markdown(description)
                                        else:
                                            st.markdown(f"- {scholarship}")
                                else:
                                    st.markdown(scholarships)
                                
                        # Contact Information
                        if result.get("contact") and result["contact"] != "No information available":
                            with st.expander("Contact Information", expanded=True):
                                contact_data = result["contact"]
                                if isinstance(contact_data, dict):
                                    if "address" in contact_data and contact_data["address"]:
                                        st.markdown(f"**Address:** {contact_data['address']}")
                                    
                                    if "phone_numbers" in contact_data and contact_data["phone_numbers"]:
                                        st.markdown("**Phone Numbers:**")
                                        for phone in contact_data["phone_numbers"]:
                                            st.markdown(f"- {phone}")
                                    
                                    if "email" in contact_data and contact_data["email"]:
                                        st.markdown(f"**Email:** {contact_data['email']}")
                                    
                                    if "website" in contact_data and contact_data["website"]:
                                        st.markdown(f"**Website:** [{contact_data['website']}]({contact_data['website']})")
                                    
                                    if "social_media" in contact_data and contact_data["social_media"]:
                                        st.markdown("**Social Media:**")
                                        for platform, url in contact_data["social_media"].items():
                                            st.markdown(f"- {platform.capitalize()}: [{url}]({url})")
                                else:
                                    st.markdown(contact_data)
                                
                        # Notes
                        if result.get("notes") and result["notes"] != "No information available" and "Error" not in result.get("notes", ""):
                            with st.expander("Notes", expanded=False):
                                st.markdown(result["notes"])
                        
                        # Option to download the JSON file
                        json_data = json.dumps(result, indent=2)
                        st.download_button(
                            label="Download JSON data",
                            data=json_data,
                            file_name=f"{result['name'].replace(' ', '_')}_data.json",
                            mime="application/json"
                        )
                        
                        # Show raw data file path
                        raw_file_path = RAW_DATA_DIR / f"{result['name'].replace(' ', '_')}_raw.txt"
                        if raw_file_path.exists():
                            with st.expander("Raw Data", expanded=False):
                                with open(raw_file_path, "r", encoding="utf-8") as f:
                                    raw_data = f.read()
                                st.text_area("Raw Content (First 2000 chars)", raw_data[:2000], height=200)
                                st.text(f"Full raw data saved at: {raw_file_path}")
            
            # Add comparison view
            if len(results) > 1:
                st.header("School Comparison")
                
                # Create a DataFrame for comparison
                comparison_data = []
                for result in results:
                    row = {
                        "School": result["name"],
                        "Has Tuition Info": result.get("school_fee") != "No information available",
                        "Has Program Info": result.get("program") != "No information available",
                        "Has Enrollment Info": result.get("enrollment_process") != "No information available",
                        "Has Events Info": result.get("events") != "No information available",
                        "Has Scholarship Info": result.get("discounts_scholarships") != "No information available",
                        "Has Contact Info": result.get("contact_info") != "No information available"
                    }
                    comparison_data.append(row)
                
                comparison_df = pd.DataFrame(comparison_data)
                st.dataframe(comparison_df, use_container_width=True)
                
                # Option to download all data as a zip file
                st.text("Download all school data as a single zip file (feature to be implemented)")
            
        except Exception as e:
            st.error(f"An error occurred during the scraping process: {str(e)}")
            logger.error(f"Error in Streamlit app: {e}", exc_info=True)
        finally:
            # Close resources
            run_async(st.session_state.scraper.close())
            
    else:
        # Show instructions when no scraping is in progress
        st.info("Select schools from the sidebar and click 'Start Scraping' to begin the process.")
        
        # Show any existing results
        if os.path.exists(PARSED_DATA_DIR):
            parsed_files = list(PARSED_DATA_DIR.glob("*_parsed.json"))
            if parsed_files:
                st.header("Previously Scraped Schools")
                
                for file_path in parsed_files:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            school_data = json.load(f)
                            
                        st.subheader(school_data.get("name", "Unknown School"))
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if school_data.get("link"):
                                st.markdown(f"[Visit Website]({school_data['link']})")
                            
                            if school_data.get("contact_info") and school_data["contact_info"] != "No information available":
                                with st.expander("Contact Information"):
                                    st.markdown(school_data["contact_info"])
                        
                        with col2:
                            if school_data.get("school_fee") and school_data["school_fee"] != "No information available":
                                with st.expander("Has Tuition Information"):
                                    st.markdown("✅")
                            
                            if school_data.get("program") and school_data["program"] != "No information available":
                                with st.expander("Has Program Information"):
                                    st.markdown("✅")
                        
                        # Option to view full data
                        with st.expander("View Full Data"):
                            st.json(school_data)
                        
                        st.markdown("---")
                    except Exception as e:
                        st.warning(f"Could not load data from {file_path.name}: {str(e)}")


if __name__ == "__main__":
    main()