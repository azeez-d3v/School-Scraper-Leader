import streamlit as st
from datetime import datetime
import asyncio
import os
import json
import logging
import pandas as pd
import numpy as np
import re
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
import io

# Local imports
from lib.scraper import SchoolScraper, RAW_DATA_DIR, PARSED_DATA_DIR

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
    
    # Initialize the scraper on first run
    if 'scraper' not in st.session_state:
        st.session_state.scraper = SchoolScraper()
        
    # Get schools list
    schools_data = st.session_state.scraper.schools_data
    
    # Create main tabs for app sections
    main_tabs = st.tabs(["Home", "Scrape Schools", "Results", "Summary", "Export Data", "About"])
    
    # Home Tab
    with main_tabs[0]:
        st.header("Welcome to AI School Web Scraper")
        st.markdown("""
        This application scrapes school websites, extracts relevant information using AI, and presents the results.
        The process involves:
        1. Fetching HTML content from school websites
        2. Saving the content as text files
        3. Using Gemini AI to parse structured information
        
        Go to the "Scrape Schools" tab to start collecting data.
        """)
        
        # Add columns for a better layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("How to use")
            st.markdown("""
            1. Go to the **Scrape Schools** tab
            2. Select the schools you want to scrape
            3. Click "Start Scraping" to begin
            4. View detailed results in the **Results** tab
            """)
        
        with col2:
            st.subheader("Available Data")
            st.markdown("""
            For each school, we attempt to collect:
            - Tuition fees and payment schedules
            - Academic programs offered
            - Enrollment requirements and process
            - Upcoming events
            - Scholarships and discounts
            - Contact information
            """)
        
        # Note about results tab
        st.info("⚠️ Previously scraped data can be viewed in the **Results** tab if available.")
    
    # Scrape Schools Tab
    with main_tabs[1]:
        st.header("Select Schools to Scrape")
        
        # Get previously scraped school names from parsed data directory
        previously_scraped_schools = []
        if os.path.exists(PARSED_DATA_DIR):
            parsed_files = list(PARSED_DATA_DIR.glob("*_parsed.json"))
            for file_path in parsed_files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        school_data = json.load(f)
                    previously_scraped_schools.append(school_data["name"])
                except Exception as e:
                    logger.error(f"Error loading parsed data file {file_path}: {e}")
        
        # Get all school names for multiselect
        all_school_names = [school.get("name") for school in schools_data]
        
        # Create a dataframe with school names and their scraped status
        school_status_data = []
        for school_name in all_school_names:
            is_scraped = school_name in previously_scraped_schools
            school_status_data.append({
                "School": school_name,
                "Status": "✅ Already scraped" if is_scraped else "❌ Not scraped yet"
            })
        
        # Display the status table
        st.subheader("School Scraping Status")
        school_status_df = pd.DataFrame(school_status_data)
        st.dataframe(school_status_df, use_container_width=True, hide_index=True)
        
        # Use multiselect for school selection
        selected_school_names = st.multiselect(
            "Choose schools to scrape",
            options=all_school_names,
            default=all_school_names,
            help="Select one or more schools to scrape data from"
        )
        
        # Get the full school data for selected schools
        selected_schools = [school for school in schools_data if school.get("name") in selected_school_names]
        
        # Start scraping button
        col1, col2 = st.columns([3, 1])
        with col2:
            start_button = st.button("Start Scraping", 
                                    disabled=len(selected_schools) == 0,
                                    use_container_width=True,
                                    type="primary")
        
        # Instructions or empty space
        if not selected_school_names:
            st.info("Please select at least one school to begin.")
        
        # Main area for displaying scraping progress
        if start_button and selected_schools:
            # Create a progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            status_text.text("Initializing scraper...")
            
            # Process the selected schools
            try:
                status_text.text("Starting scraping process...")
                
                # Rerun the app to update the UI with the new results
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
                
                # Switch to Results tab when complete
                st.session_state.results = results
                st.rerun()  # Rerun to update the UI with the new results
            
            except Exception as e:
                st.error(f"An error occurred during the scraping process: {str(e)}")
                logger.error(f"Error in Streamlit app: {e}", exc_info=True)
            finally:
                # Close resources
                run_async(st.session_state.scraper.close())
    
    # Results Tab
    with main_tabs[2]:
        # Load results from session state (newly scraped schools)
        all_results = []
        
        # Add newly scraped schools from session state if available
        if 'results' in st.session_state and st.session_state.results:
            all_results.extend(st.session_state.results)
        
        # Load previously scraped schools from parsed_data directory
        if os.path.exists(PARSED_DATA_DIR):
            parsed_files = list(PARSED_DATA_DIR.glob("*_parsed.json"))
            
            # Get names of schools already in all_results to avoid duplicates
            existing_school_names = [school["name"] for school in all_results]
            
            # Load each parsed school file and add to results if not already present
            for file_path in parsed_files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        school_data = json.load(f)
                        
                    # Only add if not already in results (avoid duplicates)
                    if school_data["name"] not in existing_school_names:
                        all_results.append(school_data)
                        existing_school_names.append(school_data["name"])
                except Exception as e:
                    logger.error(f"Error loading parsed data file {file_path}: {e}")
        
        if all_results:
            st.header("School Information")
            
            # Show tabs for each school
            if len(all_results) > 0:
                # Create subtabs for individual school results and comparison
                result_tabs = st.tabs(["School Details", "Comparison View"])
                
                # School Details Tab
                with result_tabs[0]:
                    # Create a selector for schools
                    selected_school = st.selectbox(
                        "Select a school to view details",
                        options=[result["name"] for result in all_results]
                    )
                    
                    # Get the selected school data
                    result = next((r for r in all_results if r["name"] == selected_school), None)
                    
                    if result:
                        st.header(result["name"])
                        st.markdown(f"[Visit Website]({result.get('link', '#')})")
                        
                        # Create information category tabs
                        info_tabs = st.tabs([
                            "Tuition Fees", 
                            "Programs", 
                            "Enrollment", 
                            "Events & Scholarships", 
                            "Contact & Raw Data"
                        ])
                        
                        # Tuition Fees Tab
                        with info_tabs[0]:
                            if result.get("school_fee") and result["school_fee"] != "No information available":
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
                            else:
                                st.info("No tuition fee information available for this school")
                        
                        # Programs Tab
                        with info_tabs[1]:
                            if result.get("programs") and result["programs"] != "No information available":
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
                            else:
                                st.info("No program information available for this school")
                        
                        # Enrollment Tab
                        with info_tabs[2]:
                            if result.get("enrollment") and result["enrollment"] != "No information available":
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
                            else:
                                st.info("No enrollment information available for this school")
                        
                        # Events & Scholarships Tab
                        with info_tabs[3]:
                            col1, col2 = st.columns(2)
                            
                            # Events column
                            with col1:
                                st.subheader("Upcoming Events")
                                if result.get("events") and result["events"] != "No information available":
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
                                else:
                                    st.info("No upcoming events information available")
                            
                            # Scholarships column
                            with col2:
                                st.subheader("Scholarships & Discounts")
                                if result.get("scholarships") and result["scholarships"] != "No information available":
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
                                else:
                                    st.info("No scholarship information available")
                        
                        # Contact & Raw Data Tab
                        with info_tabs[4]:
                            col1, col2 = st.columns(2)
                            
                            # Contact info column
                            with col1:
                                st.subheader("Contact Information")
                                if result.get("contact") and result["contact"] != "No information available":
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
                                else:
                                    st.info("No contact information available")
                            
                            # Notes and raw data column
                            with col2:
                                # Notes
                                if result.get("notes") and result["notes"] != "No information available" and "Error" not in result.get("notes", ""):
                                    st.subheader("Notes")
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
                                    st.subheader("Raw Data")
                                    with open(raw_file_path, "r", encoding="utf-8") as f:
                                        raw_data = f.read()
                                    st.text_area("Raw Content (First 2000 chars)", raw_data[:2000], height=200)
                                    st.text(f"Full raw data saved at: {raw_file_path}")
                
                # Comparison View Tab
                with result_tabs[1]:
                    if len(all_results) > 1:
                        st.header("School Comparison")
                        
                        # Select fields to compare
                        comparison_fields = st.multiselect(
                            "Select fields to compare",
                            options=["Tuition Info", "Program Info", "Enrollment Info", "Events Info", "Scholarship Info", "Contact Info"],
                            default=["Tuition Info", "Program Info", "Enrollment Info"]
                        )
                        
                        if comparison_fields:
                            # Create a DataFrame for comparison
                            comparison_data = []
                            
                            field_mapping = {
                                "Tuition Info": "school_fee",
                                "Program Info": "program",
                                "Enrollment Info": "enrollment_process",
                                "Events Info": "events",
                                "Scholarship Info": "discounts_scholarships",
                                "Contact Info": "contact_info"
                            }
                            
                            for result in all_results:
                                row = {"School": result["name"]}
                                
                                for display_name, field_name in field_mapping.items():
                                    if display_name in comparison_fields:
                                        row[display_name] = result.get(field_name) != "No information available"
                                
                                comparison_data.append(row)
                            

                            comparison_df = pd.DataFrame(comparison_data)
                            st.dataframe(comparison_df, use_container_width=True)
                            
                        else:
                            st.info("Please select at least one field to compare")
                    else:
                        st.info("Need at least two schools to compare. Please scrape more schools.")
        else:
            st.info("No results available. Please go to the 'Scrape Schools' tab to collect data.")
    
    # Summary Tab (Newly Added)
    with main_tabs[3]:
        st.header("AI Generated Summaries")
        
        # Create subtabs for individual and comprehensive summaries
        summary_tabs = st.tabs(["Comprehensive Market Analysis", "Individual School Summaries"])
        
        # Comprehensive Summary Tab - This summarizes ALL schools together
        with summary_tabs[0]:
            st.subheader("Comprehensive School Market Analysis")
            st.markdown("""
            Generate a comprehensive market analysis that compares all scraped schools together.
            
            This analysis will provide:
            - Market overview of all schools
            - Comparative tuition analysis across different pricing tiers
            - Analysis of academic programs and curricula across schools
            - Summary of admission requirements and processes
            - Scholarship opportunities comparison
            - Distinctive features of each school
            - Recommendations for different types of students/families
            """)
            
            if not all_results or len(all_results) < 2:
                st.warning("You need at least two schools with scraped data to generate a comprehensive analysis. Please scrape more schools first.")
            else:
                # Add a button to explicitly trigger the summarization
                col1, col2 = st.columns([3, 1])
                with col2:
                    comprehensive_button = st.button(
                        "🔍 Generate Market Analysis", 
                        key="comprehensive_summary_button", 
                        type="primary",
                        use_container_width=True
                    )
                
                with col1:
                    st.info(f"Ready to analyze {len(all_results)} schools. Click the button to generate a comprehensive market analysis.")
                
                # Add a placeholder for the comprehensive summary
                comprehensive_placeholder = st.empty()
                
                # Generate comprehensive summary when button is clicked
                if comprehensive_button:
                    with st.spinner(f"Generating comprehensive analysis of {len(all_results)} schools..."):
                        comprehensive_summary = generate_combined_school_summary(all_results)
                        comprehensive_placeholder.markdown(comprehensive_summary)
        
        # Individual School Summaries Tab
        with summary_tabs[1]:
            st.subheader("Individual School Summaries")
            st.markdown("""
            Generate an AI summary for an individual school based on its scraped data.
            
            Each summary provides an overview of:
            - School philosophy and overview
            - Academic programs and curriculum
            - Tuition fees and financial information
            - Enrollment requirements and process
            - Unique features and offerings
            """)
            
            if not all_results:
                st.info("No schools have been scraped yet. Please scrape schools first to view summaries.")
            else:
                # Select a school to summarize
                selected_school = st.selectbox(
                    "Select a school to view AI-generated summary",
                    options=[result["name"] for result in all_results],
                    key="summary_school_selector"
                )
                
                # Get the selected school data
                school_data = next((r for r in all_results if r["name"] == selected_school), None)
                
                if school_data:
                    # Find the raw data file for this school
                    raw_file_path = RAW_DATA_DIR / f"{selected_school.replace(' ', '_')}_raw.txt"
                    
                    if raw_file_path.exists():
                        # Add a button to explicitly trigger the summarization
                        summary_col1, summary_col2 = st.columns([3, 1])
                        with summary_col2:
                            summarize_button = st.button("📝 Summarize Data", key="summarize_data_button", type="primary", use_container_width=True)
                        
                        # Add a placeholder for the summary
                        summary_placeholder = st.empty()
                        
                        # Show file info
                        with summary_col1:
                            st.info(f"Raw data file ready for {selected_school}. Click the 'Summarize Data' button to generate an AI summary.")
                        
                        # Generate summary when button is clicked
                        if summarize_button:
                            with st.spinner(f"Generating AI summary for {selected_school}..."):
                                # Read the raw data file
                                with open(raw_file_path, "r", encoding="utf-8") as f:
                                    raw_data = f.read()
                                
                                # Generate AI summary
                                summary = summarize_school_data_with_ai(raw_data, selected_school)
                                
                                # Display the summary
                                summary_placeholder.markdown(summary)
                        
                        # Add option to regenerate the summary
                        if st.button("🔄 Regenerate Summary", key="regenerate_summary"):
                            with st.spinner("Regenerating summary..."):
                                # Read the raw data file
                                with open(raw_file_path, "r", encoding="utf-8") as f:
                                    raw_data = f.read()
                                    
                                summary = summarize_school_data_with_ai(raw_data, selected_school)
                                summary_placeholder.markdown(summary)
                    else:
                        st.warning(f"Raw data file not found for {selected_school}. Please ensure the school has been scraped completely.")
    
    # Export Data Tab
    with main_tabs[4]:
        st.header("Export Scraped Data")
        st.markdown("""
        In this section, you can export the data that has been scraped and processed by the AI.
        
        Available export options:
        - **Excel Report:** A comprehensive Excel report containing all scraped school data.
        - **JSON Files:** Individual JSON files for each school containing the raw and parsed data.
        
        The exports automatically include ALL schools that have been scraped, not just selected ones.
        """)
        
        # Auto-generate Excel data on tab load
        with st.spinner("Preparing Excel export..."):
            excel_data = export_results_to_excel(all_results)
            if excel_data:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="📥 Download Excel Report (All Schools)",
                    data=excel_data,
                    file_name=f"all_schools_data_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_all_excel",
                    type="primary"
                )
            else:
                st.error("Failed to generate Excel file. Please check logs for details.")
        
        # JSON export section
        st.subheader("Download All School Data")
        
        # Create a combined JSON containing all school data
        if all_results:
            combined_json = json.dumps(all_results, indent=2)
            st.download_button(
                label="📥 Download All Schools as Combined JSON",
                data=combined_json,
                file_name=f"all_schools_combined_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_combined_json"
            )
            
            # Individual school downloads
            with st.expander("Individual School Data Downloads"):
                st.info("Expand to see download options for individual schools")
                for result in all_results:
                    school_name = result["name"]
                    json_data = json.dumps(result, indent=2)
                    
                    st.markdown(f"### {school_name}")
                    col1, col2 = st.columns(2)
                    
                    # Parsed data download
                    with col1:
                        st.download_button(
                            label=f"Download Parsed Data",
                            data=json_data,
                            file_name=f"{school_name.replace(' ', '_')}_data.json",
                            mime="application/json",
                            key=f"download_parsed_{school_name}"
                        )
                    
                    # Raw data download
                    raw_file_path = RAW_DATA_DIR / f"{school_name.replace(' ', '_')}_raw.txt"
                    if raw_file_path.exists():
                        with col2:
                            st.download_button(
                                label=f"Download Raw Data",
                                data=open(raw_file_path, "r", encoding="utf-8").read(),
                                file_name=f"{school_name.replace(' ', '_')}_raw_data.json",
                                mime="application/json",
                                key=f"download_raw_{school_name}"
                            )
        else:
            st.info("No data available to export. Please scrape schools first in the 'Scrape Schools' tab.")
    
    # About Tab
    with main_tabs[5]:
        st.header("About This App")
        st.markdown("""
        This is an AI-powered school web scraper that collects and analyzes data from various school websites.
        
        ### Features:
        - Scrape school websites for structured data
        - AI-driven data parsing and summarization
        - Comprehensive analytics on tuition fees and school programs
        - Downloadable reports and raw data access
        
        ### Technologies Used:
        - Streamlit for the web app framework
        - Langchain and Gemini AI for data processing and summarization
        - Plotly and Matplotlib for data visualization
        
        ### How to Use:
        1. Go to the **Scrape Schools** tab to select and scrape school data
        2. View and analyze the results in the **Results** and **Analytics** tabs
        3. Generate AI-powered summaries in the **Summary** tab
        4. Download data and reports as needed
        
        ### Notes:
        - Ensure you have the necessary permissions to scrape and use the data from school websites.
        - The AI summaries are generated based on the scraped data and may not reflect the most current information.
        """)
    

def extract_tuition_fees(school_data):
    """Extract tuition fee information from school data for analytics."""
    try:
        fee_data = school_data.get("school_fee", {})
        if isinstance(fee_data, str) or fee_data == "No information available":
            return {}
            
        school_name = school_data.get("name", "Unknown School")
        result = {"School": school_name, "Program/Grade Level": "General"}
        
        # Extract academic year
        if isinstance(fee_data, dict) and "academic_year" in fee_data:
            result["Academic Year"] = fee_data["academic_year"]
            
        # Extract tuition by level
        if isinstance(fee_data, dict) and "tuition_by_level" in fee_data and isinstance(fee_data["tuition_by_level"], dict):
            for level, details in fee_data["tuition_by_level"].items():
                if isinstance(details, dict):
                    # Create a new row for each grade level
                    level_row = {"School": school_name, "Program/Grade Level": level}
                    
                    # Copy Academic Year if available
                    if "Academic Year" in result:
                        level_row["Academic Year"] = result["Academic Year"]
                    
                    # Look for annual fee, semester fees, or description
                    if "annual" in details:
                        try:
                            # Try to convert to numeric
                            amount_str = details["annual"].replace(",", "").replace("$", "").replace("₱", "").replace("PHP", "").strip()
                            level_row["Annual Fee"] = float(amount_str)
                        except (ValueError, AttributeError):
                            level_row["Annual Fee"] = details["annual"]
                    
                    if "semester1" in details:
                        try:
                            # Try to convert to numeric
                            amount_str = details["semester1"].replace(",", "").replace("$", "").replace("₱", "").replace("PHP", "").strip()
                            level_row["Semester 1 Fee"] = float(amount_str)
                        except (ValueError, AttributeError):
                            level_row["Semester 1 Fee"] = details["semester1"]
                    
                    if "semester2" in details:
                        try:
                            # Try to convert to numeric
                            amount_str = details["semester2"].replace(",", "").replace("$", "").replace("₱", "").replace("PHP", "").strip()
                            level_row["Semester 2 Fee"] = float(amount_str)
                        except (ValueError, AttributeError):
                            level_row["Semester 2 Fee"] = details["semester2"]
                    
                    if "description" in details:
                        # Try to extract numeric values from description
                        desc = details["description"]
                        amount_match = re.search(r'(?:[$₱]|PHP)[,\s]*([0-9,]+(?:\.[0-9]+)?)', desc)
                        if amount_match:
                            # Clean up the amount and convert to numeric
                            amount_str = amount_match.group(1).replace(',', '')
                            try:
                                level_row["Extracted Fee"] = float(amount_str)
                            except ValueError:
                                pass
                        level_row["Description"] = desc
                    
                    return level_row  # Return one row per call for simplicity
                    
                elif isinstance(details, str):
                    # Try to extract numeric values from the string
                    amount_match = re.search(r'(?:[$₱]|PHP)[,\s]*([0-9,]+(?:\.[0-9]+)?)', details)
                    if amount_match:
                        # Clean up the amount and convert to numeric
                        amount_str = amount_match.group(1).replace(',', '')
                        try:
                            result[f"{level} Fee"] = float(amount_str)
                        except ValueError:
                            result[f"{level} Fee"] = details
                    else:
                        result[f"{level}"] = details
            
        return result
    except Exception as e:
        logger.error(f"Error extracting tuition data: {e}")
        return {"School": school_data.get("name", "Unknown School"), "Error": str(e)}

def summarize_school_data_with_ai(raw_data, school_name):
    """Generate an AI summary of the school data."""
    try:
        # Initialize the AI model
        model = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)
        
        # Create a prompt for summarizing the school data
        summary_prompt = ChatPromptTemplate.from_template(
            """You are an educational consultant tasked with summarizing information about {school_name}. 
            Please provide a concise, informative summary of the school based on the following raw data.
            
            Focus on these key aspects:
            1. School overview and educational philosophy
            2. Academic programs and curriculum
            3. Tuition fees and financial information
            4. Enrollment requirements and process
            5. What makes this school unique or distinctive
            
            Format your response with clear sections and bullet points where appropriate.
            Maintain a professional, informative tone throughout.
            
            Raw data:
            {raw_content}
            """
        )
        
        # Create the chain
        chain = summary_prompt | model
        
        # Generate the summary
        response = chain.invoke(
            {"school_name": school_name, "raw_content": raw_data[:15000]}  # Limit content length
        )
        
        # Extract the content
        return response.content if hasattr(response, 'content') else str(response)
        
    except Exception as e:
        logger.error(f"Error generating AI summary for {school_name}: {e}")
        return f"Unable to generate summary for {school_name}: {str(e)}"

def generate_combined_school_summary(all_results):
    """Generate a comprehensive summary of all scraped schools.
    
    This function:
    1. Collects raw data from all scraped schools
    2. Combines and chunks the data to stay within token limits
    3. Passes the data to Gemini AI for a comprehensive summary
    
    Args:
        all_results: List of school data dictionaries
        
    Returns:
        String containing the comprehensive AI-generated summary
    """
    try:
        # Initialize the AI model with a higher token capacity model
        model = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)
        
        # Import the comprehensive analysis template from parse.py
        from lib.parse import comprehensive_analysis_template
        
        # Collect raw data for all schools
        all_schools_data = []
        for result in all_results:
            school_name = result["name"]
            raw_file_path = RAW_DATA_DIR / f"{school_name.replace(' ', '_')}_raw.txt"
            
            if raw_file_path.exists():
                # Read just the essential information from each school's raw data
                try:
                    with open(raw_file_path, "r", encoding="utf-8") as f:
                        raw_content = f.read()
                    
                    # Extract key information with a limit of 3000 chars per school to avoid token limits
                    school_excerpt = f"\n\n===== SCHOOL: {school_name} =====\n"
                    
                    # Add a summary of structured data from the parsed result
                    school_excerpt += f"WEBSITE: {result.get('link', 'Not available')}\n\n"
                    
                    # Add tuition info
                    fee_data = result.get("school_fee", {})
                    if isinstance(fee_data, dict) and "academic_year" in fee_data:
                        school_excerpt += f"TUITION: Academic Year {fee_data.get('academic_year', '')}\n"
                        if "tuition_by_level" in fee_data and isinstance(fee_data["tuition_by_level"], dict):
                            school_excerpt += "TUITION LEVELS:\n"
                            for level, details in fee_data["tuition_by_level"].items():
                                if isinstance(details, dict):
                                    school_excerpt += f"- {level}: "
                                    if "annual" in details:
                                        school_excerpt += f"Annual: {details['annual']} "
                                    if "description" in details:
                                        desc = details["description"]
                                        if len(desc) > 100:
                                            desc = desc[:100] + "..."
                                        school_excerpt += f"{desc}\n"
                                    else:
                                        school_excerpt += "\n"
                                else:
                                    school_excerpt += f"- {level}: {details}\n"
                        
                    # Add program highlights
                    programs = result.get("programs", [])
                    if isinstance(programs, list) and len(programs) > 0:
                        school_excerpt += "PROGRAMS:\n"
                        for p in programs[:5]:
                            if isinstance(p, dict):
                                name = p.get("name", "")
                                grade = p.get("grade_level", "")
                                school_excerpt += f"- {name} ({grade})\n"
                    
                    # Add enrollment info
                    enrollment = result.get("enrollment", {})
                    if isinstance(enrollment, dict) and not isinstance(enrollment, str):
                        school_excerpt += "ENROLLMENT:\n"
                        if "requirements" in enrollment and enrollment["requirements"]:
                            school_excerpt += "Requirements: " + ", ".join(enrollment["requirements"][:3])
                            if len(enrollment["requirements"]) > 3:
                                school_excerpt += "..."
                            school_excerpt += "\n"
                    
                    # Add scholarship info
                    scholarships = result.get("scholarships", [])
                    if isinstance(scholarships, list) and len(scholarships) > 0 and not isinstance(scholarships, str):
                        school_excerpt += "SCHOLARSHIPS: Available\n"
                    
                    # Limit raw content to first ~1000 chars of meaningful data
                    content_start = raw_content.find("MAIN PAGE CONTENT:")
                    if content_start > 0:
                        relevant_content = raw_content[content_start:content_start+1000]
                        school_excerpt += f"EXCERPT: {relevant_content}...\n"
                    
                    all_schools_data.append(school_excerpt)
                    
                except Exception as e:
                    logger.error(f"Error processing raw data for {school_name}: {e}")
                    all_schools_data.append(f"===== SCHOOL: {school_name} =====\nError reading data: {str(e)}")
            else:
                all_schools_data.append(f"===== SCHOOL: {school_name} =====\nNo raw data file available.")
        
        # Combine all schools data
        combined_data = "\n\n".join(all_schools_data)
        
        # Split into chunks to respect token limits
        from lib.utils import split_dom_content
        chunks = split_dom_content(combined_data, max_length=12000)  # Chunk size suitable for gemini-1.5-flash-latest
        
        # Create comprehensive summary prompt
        comprehensive_prompt = ChatPromptTemplate.from_template(
            """You are an educational consultant tasked with creating a comprehensive market overview of international schools 
            based on the data provided. This data comes from multiple schools that have been scraped and analyzed.
            
            Create an informative, well-structured summary that covers:
            
            1. OVERVIEW: General trends and observations across all schools
            2. TUITION AND FEES: Compare tuition ranges and fee structures
            3. ACADEMIC PROGRAMS: Common programs and unique offerings
            4. ADMISSIONS: Typical enrollment requirements and processes
            5. COMPARATIVE ANALYSIS: What makes each school distinctive, their strengths, and target demographics
            6. RECOMMENDATIONS: Which schools might be appropriate for different student needs
            
            Format your response with clear section headers, bullet points, and tables where appropriate.
            Maintain a professional, objective tone throughout.
            
            Here is the combined data from all scraped schools:
            
            {data_chunk}
            """
        )
        
        # Process each chunk and combine results
        all_summaries = []
        for i, chunk in enumerate(chunks):
            try:
                logger.info(f"Processing chunk {i+1} of {len(chunks)} for combined school summary")
                
                # Create the chain
                chain = comprehensive_prompt | model
                
                # Generate the summary for this chunk
                response = chain.invoke({"data_chunk": chunk})
                
                # Extract the content
                chunk_summary = response.content if hasattr(response, 'content') else str(response)
                all_summaries.append(chunk_summary)
                
            except Exception as e:
                logger.error(f"Error generating summary for chunk {i+1}: {e}")
                all_summaries.append(f"Error processing data chunk {i+1}: {str(e)}")
        
        # Combine chunk summaries and add final integration if multiple chunks
        final_summary = "\n\n".join(all_summaries)
        
        # If we had multiple chunks, do a final integration pass
        if len(chunks) > 1:
            try:
                integration_prompt = ChatPromptTemplate.from_template(
                    """You are an educational consultant creating a final, integrated report on international schools.
                    You have processed multiple data chunks and now need to integrate the separate summaries into 
                    a single coherent report.
                    
                    The summaries may contain some redundant information. Your task is to:
                    1. Remove redundancies
                    2. Resolve any contradictions
                    3. Create a unified, well-structured report
                    4. Ensure all schools mentioned are included
                    5. Maintain the section structure: Market Overview, Tuition Analysis, Academic Programs, 
                       Admissions Landscape, Scholarship Opportunities, Comparative Strengths, and Recommendations
                    
                    Here are the separate summaries to integrate:
                    
                    {summaries}
                    """
                )
                
                # Create the integration chain
                integration_chain = integration_prompt | model
                
                # Generate the integrated summary
                integration_response = integration_chain.invoke({"summaries": final_summary})
                
                # Replace with integrated version
                final_summary = integration_response.content if hasattr(integration_response, 'content') else str(integration_response)
                
            except Exception as e:
                logger.error(f"Error integrating summaries: {e}")
                # If integration fails, we still have the combined summaries
        
        return final_summary
        
    except Exception as e:
        logger.error(f"Error generating combined school summary: {e}")
        return f"Unable to generate comprehensive summary: {str(e)}"


def export_results_to_excel(all_results):
    """Export the scraped school results to an Excel file.
    
    This function creates an Excel file with all schools in a single sheet,
    with each row representing one school and all their key data.
    
    Args:
        all_results: List of school data dictionaries
        
    Returns:
        BytesIO stream of the Excel file for download
    """
    try:
        # Create a Pandas Excel writer using openpyxl as the engine
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Create a single comprehensive sheet with all schools
            all_schools_data = []
            
            for result in all_results:
                # Extract basic school info
                school_data = {
                    "School Name": result.get("name", ""),
                    "Website": result.get("link", ""),
                }
                
                # Extract contact information
                if isinstance(result.get("contact"), dict):
                    contact = result.get("contact", {})
                    school_data["Email"] = contact.get("email", "")
                    school_data["Phone"] = ", ".join(str(p) for p in contact.get("phone_numbers", [])) if isinstance(contact.get("phone_numbers"), list) else ""
                    school_data["Address"] = contact.get("address", "")
                
                # Extract tuition fee information
                if isinstance(result.get("school_fee"), dict):
                    fee_data = result.get("school_fee", {})
                    school_data["Academic Year"] = fee_data.get("academic_year", "")
                    
                    # Combine tuition levels into a single field
                    if "tuition_by_level" in fee_data and isinstance(fee_data["tuition_by_level"], dict):
                        tuition_summary = []
                        for level, details in fee_data["tuition_by_level"].items():
                            if isinstance(details, dict):
                                fee_text = f"{level}: "
                                if "annual" in details:
                                    fee_text += f"Annual: {details['annual']} "
                                tuition_summary.append(fee_text)
                            elif isinstance(details, str):
                                tuition_summary.append(f"{level}: {details}")
                        
                        school_data["Tuition Summary"] = "; ".join(tuition_summary)
                
                # Extract programs
                if isinstance(result.get("programs"), list):
                    programs = result.get("programs", [])
                    program_summary = []
                    for program in programs:
                        if isinstance(program, dict):
                            program_text = program.get("name", "")
                            if "grade_level" in program:
                                program_text += f" ({program.get('grade_level', '')})"
                            program_summary.append(program_text)
                        elif isinstance(program, str):
                            program_summary.append(program)
                    
                    school_data["Programs"] = "; ".join(program_summary)
                
                # Extract enrollment information
                if isinstance(result.get("enrollment"), dict):
                    enrollment = result.get("enrollment", {})
                    
                    # Requirements
                    if "requirements" in enrollment and enrollment["requirements"]:
                        if isinstance(enrollment["requirements"], list):
                            school_data["Enrollment Requirements"] = "; ".join(enrollment["requirements"])
                        else:
                            school_data["Enrollment Requirements"] = str(enrollment["requirements"])
                
                # Extract events
                if isinstance(result.get("events"), list):
                    events = result.get("events", [])
                    event_summary = []
                    for event in events:
                        if isinstance(event, dict):
                            event_text = event.get("name", "")
                            if "date" in event:
                                event_text += f" ({event.get('date', '')})"
                            event_summary.append(event_text)
                        elif isinstance(event, str):
                            event_summary.append(event)
                    
                    school_data["Events"] = "; ".join(event_summary)
                
                # Extract scholarships
                if isinstance(result.get("scholarships"), list):
                    scholarships = result.get("scholarships", [])
                    scholarship_summary = []
                    for scholarship in scholarships:
                        if isinstance(scholarship, dict):
                            scholarship_text = scholarship.get("name", "")
                            if "amount" in scholarship:
                                scholarship_text += f" ({scholarship.get('amount', '')})"
                            scholarship_summary.append(scholarship_text)
                        elif isinstance(scholarship, str):
                            scholarship_summary.append(scholarship)
                    
                    school_data["Scholarships"] = "; ".join(scholarship_summary)
                
                # Add notes as the last column
                school_data["Notes"] = result.get("notes", "")
                
                all_schools_data.append(school_data)
            
            # Convert to DataFrame and write to Excel
            if all_schools_data:
                all_schools_df = pd.DataFrame(all_schools_data)
                all_schools_df.to_excel(writer, sheet_name="All Schools Data", index=False)
            
            # Create a second sheet with details about what was included
            metadata = {
                "Export Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Number of Schools": len(all_results),
                "School Names": ", ".join([result.get("name", "") for result in all_results]),
                "Export Format": "All schools in one sheet, one row per school"
            }
            
            metadata_df = pd.DataFrame([metadata])
            metadata_df.to_excel(writer, sheet_name="Export Info", index=False)
        
        # Seek to the beginning of the stream before reading
        output.seek(0)
        
        return output
    except Exception as e:
        logger.error(f"Error exporting results to Excel: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    main()