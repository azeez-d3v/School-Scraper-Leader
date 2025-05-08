from curl_cffi import requests
import json
import time
from datetime import datetime
import logging
import re
import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Initialize the Google Generative AI model
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    logger.warning("GOOGLE_API_KEY not found in environment variables. Please set it in your .env file or system environment.")

model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", temperature=0)

# Comprehensive analysis prompt for summarizing all schools together
comprehensive_analysis_template = (
    "You are an educational consultant tasked with creating a comprehensive market analysis of multiple schools. "
    "You have been provided with data about several different schools that has been scraped and processed. "
    "Your task is to analyze this data holistically and create a comparative summary that highlights similarities, "
    "differences, and key insights across all schools.\n\n"
    
    "FORMAT YOUR RESPONSE WITH THE FOLLOWING SECTIONS:\n\n"
    
    "## MARKET OVERVIEW\n"
    "- Provide a high-level summary of the school landscape represented in the data\n"
    "- Identify common themes, educational philosophies, or positioning across schools\n\n"
    
    "## TUITION ANALYSIS\n"
    "- Compare tuition ranges across all schools\n"
    "- Identify pricing tiers and what differentiates schools in different price brackets\n"
    "- Note any unusual or distinctive fee structures\n\n"
    
    "## ACADEMIC PROGRAMS\n"
    "- Identify common academic programs and curricula\n"
    "- Highlight unique or specialized programs offered by specific schools\n"
    "- Compare grade level offerings and educational approaches\n\n"
    
    "## ADMISSIONS LANDSCAPE\n"
    "- Summarize typical admission requirements and processes\n"
    "- Note differences in selectivity or admission criteria\n"
    "- Highlight any unique enrollment approaches\n\n"
    
    "## SCHOLARSHIP OPPORTUNITIES\n"
    "- Compare financial aid and scholarship availability\n"
    "- Identify which schools offer the most generous or accessible scholarships\n\n"
    
    "## COMPARATIVE STRENGTHS\n"
    "- For each school, identify its distinctive features or competitive advantages\n"
    "- Suggest which types of students might be best suited for each school\n\n"
    
    "## RECOMMENDATIONS\n"
    "- Provide specific recommendations for different types of families/students\n"
    "- Example: \"Families seeking [X] should consider [School Y] because...\"\n\n"
    
    "IMPORTANT GUIDELINES:\n"
    "1. Focus on factual analysis based on the provided data\n"
    "2. Make direct comparisons between schools where appropriate\n"
    "3. Use clear, professional language\n"
    "4. If information for certain schools is limited, acknowledge this rather than making assumptions\n"
    "5. Format with clear section headings, bullet points, and tables where appropriate\n\n"
    
    "SCHOOLS DATA TO ANALYZE:\n{combined_schools_data}"
)

# Enhanced prompt template with clear instruction to structure output in key-value format
template = (
    "You are a data extraction expert. Your task is to extract structured information from school website content.\n\n"
    "School Name: {school_name}\n\n"
    "FORMAT YOUR RESPONSE EXACTLY AS BELOW WITH CLEAR SECTION HEADERS:\n\n"
    "Tuition Fees: [Extract all details about tuition costs, payment schedules, and fees]\n\n"
    "Programs Offered: [Extract all academic programs, curriculum details, and grade levels]\n\n"
    "Enrollment Requirements: [Extract all admission requirements and eligibility criteria]\n\n"
    "Enrollment Process: [Extract the step-by-step application procedures]\n\n"
    "Upcoming Events: [Extract information about school events and dates]\n\n"
    "Scholarships/Discounts: [Extract details about scholarships and financial aid]\n\n"
    "Contact Information: [Extract all contact details including address, phone, email]\n\n"
    "Notes: [Any additional relevant information]\n\n"
    "IMPORTANT INSTRUCTIONS:\n"
    "1. Always include the section headers exactly as shown above\n"
    "2. If information for a section is truly not available, write only 'No information available'\n"
    "3. Format content in plain text without markdown formatting\n"
    "4. Keep your response focused on extracting facts\n"
    "5. Include specific details, dates, amounts, and requirements when available\n\n"
    "Here's the content to analyze:\n\n{dom_content}"
)

def clean_section_text(text):
    """Clean up the extracted section text to remove formatting artifacts"""
    # Remove markdown-style formatting
    text = re.sub(r'\*\*|\*|-\*', '', text)
    # Remove bullet points but keep the text
    text = re.sub(r'^\s*[-•*]\s*', '', text, flags=re.MULTILINE)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove any lines that only contain formatting characters
    text = re.sub(r'^[=\-_*]+$', '', text, flags=re.MULTILINE)
    return text.strip()

def fix_response_format(response, school_name):
    """Fix the format of a response that doesn't match our expected structure"""
    fixed_response = f"Information about {school_name}:\n\n"
    
    # Define our expected sections
    sections = [
        "Tuition Fees:", "Programs Offered:", "Enrollment Requirements:",
        "Enrollment Process:", "Upcoming Events:", "Scholarships/Discounts:",
        "Contact Information:", "Notes:"
    ]
    
    # Try to find content for each section
    for section in sections:
        fixed_response += f"{section}\n"
        
        # Remove the colon for the search pattern
        search_term = section.rstrip(':').lower()
        
        # Look for content related to this section
        patterns = [
            # Exact section header
            rf"{re.escape(section)}(.*?)(?=(?:{create_section_pattern(sections)})|$)",
            # Section name without colon
            rf"{re.escape(search_term)}[:\s]+(.*?)(?=(?:{create_section_pattern(sections)})|$)",
            # Section concept mention
            rf"(?:about|regarding) (?:the )?{re.escape(search_term)}[:\s]+(.*?)(?=(?:{create_section_pattern(sections)})|$)"
        ]
        
        section_content = ""
        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
            if match:
                section_content = match.group(1).strip()
                break
        
        if section_content:
            section_content = clean_section_text(section_content)
            fixed_response += section_content + "\n\n"
        else:
            fixed_response += "No information available\n\n"
    
    return fixed_response

def create_section_pattern(sections):
    """Create regex pattern for finding any of the section headers"""
    escaped_sections = [re.escape(section) for section in sections]
    return '|'.join(escaped_sections)

def parse_with_langchain(dom_content, parse_description, school_name=""):
    """Parse content using Google Generative AI model through LangChain"""
    
    if not dom_content:
        logger.warning("No content provided for parsing")
        return "No data available - empty content provided"
    
    # Extract the school name from the parse description if not provided
    if not school_name:
        name_match = re.search(r"Extract information about (.*?) including", parse_description)
        if name_match:
            school_name = name_match.group(1)
        else:
            school_name = "the school"
    
    logger.info(f"Processing content for {school_name}")
    
    try:
        # Format the prompt template with instructions for structured output
        structured_template = (
            "You are a data extraction expert. Extract structured information from school website content.\n\n"
            "School Name: {school_name}\n\n"
            "FORMAT YOUR RESPONSE EXACTLY IN JSON FORMAT:\n\n"
            "```json\n"
            "{{\n"
            "  \"tuition\": {{\n"
            "    \"academic_year\": \"[ACADEMIC YEAR]\",\n"
            "    \"tuition_by_level\": {{\n"
            "      \"[GRADE/LEVEL NAME]\": {{\n"
            "        \"annual\": \"[ANNUAL FEE]\",\n"
            "        \"semester1\": \"[SEMESTER 1 FEE]\",\n"
            "        \"semester2\": \"[SEMESTER 2 FEE]\"\n"
            "      }},\n"
            "      // Additional grade levels as needed\n"
            "    }},\n"
            "    \"other_fees\": [\n"
            "      {{\n"
            "        \"name\": \"[FEE NAME]\",\n"
            "        \"amount\": \"[AMOUNT]\",\n"
            "        \"description\": \"[DESCRIPTION]\"\n"
            "      }}\n"
            "      // Additional fees as needed\n"
            "    ],\n"
            "    \"due_dates\": [\n"
            "      {{\n"
            "        \"period\": \"[PERIOD NAME]\",\n"
            "        \"date\": \"[DUE DATE]\"\n"
            "      }}\n"
            "      // Additional due dates as needed\n"
            "    ]\n"
            "  }},\n"
            "  \"programs\": [\n"
            "    {{\n"
            "      \"name\": \"[PROGRAM NAME]\",\n"
            "      \"grade_level\": \"[GRADE LEVEL]\",\n"
            "      \"description\": \"[DESCRIPTION]\"\n"
            "    }}\n"
            "    // Additional programs as needed\n"
            "  ],\n"
            "  \"enrollment\": {{\n"
            "    \"requirements\": [\n"
            "      \"[REQUIREMENT 1]\",\n"
            "      \"[REQUIREMENT 2]\"\n"
            "      // Additional requirements as needed\n"
            "    ],\n"
            "    \"documents\": [\n"
            "      \"[DOCUMENT 1]\",\n"
            "      \"[DOCUMENT 2]\"\n"
            "      // Additional documents as needed\n"
            "    ],\n"
            "    \"process_steps\": [\n"
            "      {{\n"
            "        \"step\": \"[STEP NUMBER]\",\n"
            "        \"description\": \"[STEP DESCRIPTION]\"\n"
            "      }}\n"
            "      // Additional steps as needed\n"
            "    ]\n"
            "  }},\n"
            "  \"events\": [\n"
            "    {{\n"
            "      \"name\": \"[EVENT NAME]\",\n"
            "      \"date\": \"[EVENT DATE]\",\n"
            "      \"description\": \"[EVENT DESCRIPTION]\"\n"
            "    }}\n"
            "    // Additional events as needed\n"
            "  ],\n"
            "  \"scholarships\": [\n"
            "    {{\n"
            "      \"name\": \"[SCHOLARSHIP NAME]\",\n"
            "      \"eligibility\": \"[ELIGIBILITY CRITERIA]\",\n"
            "      \"amount\": \"[AMOUNT OR PERCENTAGE]\",\n"
            "      \"description\": \"[DESCRIPTION]\"\n"
            "    }}\n"
            "    // Additional scholarships as needed\n"
            "  ],\n"
            "  \"contact\": {{\n"
            "    \"address\": \"[FULL ADDRESS]\",\n"
            "    \"phone_numbers\": [\n"
            "      \"[PHONE NUMBER 1]\",\n"
            "      \"[PHONE NUMBER 2]\"\n"
            "      // Additional phone numbers as needed\n"
            "    ],\n"
            "    \"email\": \"[EMAIL ADDRESS]\",\n"
            "    \"website\": \"[WEBSITE URL]\",\n"
            "    \"social_media\": {{\n"
            "      \"facebook\": \"[FACEBOOK URL]\",\n"
            "      \"twitter\": \"[TWITTER URL]\",\n"
            "      \"instagram\": \"[INSTAGRAM URL]\"\n"
            "      // Additional social media as needed\n"
            "    }}\n"
            "  }},\n"
            "  \"notes\": \"[ANY ADDITIONAL RELEVANT INFORMATION]\"\n"
            "}}\n"
            "```\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "1. Return ONLY valid JSON - no explanations or text outside the JSON structure\n"
            "2. If information for a section is truly not available, provide empty arrays or empty strings as appropriate\n"
            "3. Include specific details, dates, amounts, and requirements when available\n"
            "4. For tuition, separate by grade levels and include pricing details for different payment periods\n"
            "5. For enrollment, separate requirements from required documents and provide step-by-step process\n"
            "6. Remove any JSON comments (lines with // ) in your final output\n\n"
            "Here's the content to analyze:\n\n{dom_content}"
        )
        
        prompt = ChatPromptTemplate.from_template(structured_template)
        chain = prompt | model
        
        # Invoke the LangChain chain
        logger.info(f"Sending request to Google Generative AI for {school_name}")
        response = chain.invoke(
            {"dom_content": dom_content, "school_name": school_name}
        )
        
        # Extract the result from the response
        result = response.content if hasattr(response, 'content') else str(response)
        
        logger.info(f"Received response from Google Generative AI, length: {len(result)}")
        
        # Extract JSON from the response
        json_data = extract_json_from_response(result)
        
        if not json_data:
            logger.warning(f"No valid JSON found in response for {school_name}, falling back to legacy format")
            return handle_legacy_format(result, school_name)
        
        # Convert the JSON data to a SchoolInfo object
        school_info = create_school_info_from_json(json_data, school_name)
        
        # Convert back to dictionary for output
        return school_info.to_dict()
        
    except Exception as e:
        logger.error(f"Error parsing content: {e}")

def extract_json_from_response(response_text):
    """Extract JSON from the response text"""
    # Remove markdown formatting for code blocks
    json_pattern = r'```(?:json)?\s*({.*?})\s*```'
    json_match = re.search(json_pattern, response_text, re.DOTALL)
    
    if json_match:
        json_str = json_match.group(1)
        # Remove any remaining comment lines
        json_str = re.sub(r'^\s*//.*$', '', json_str, flags=re.MULTILINE)
        # Parse the JSON
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return None
    
    # If no code block, try parsing the whole text as JSON
    try:
        # Remove any markdown or text outside of JSON
        text = re.sub(r'^.*?({.*}).*$', r'\1', response_text, flags=re.DOTALL)
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse response as JSON")
        return None

def create_school_info_from_json(json_data, school_name):
    """Create a SchoolInfo object from parsed JSON data"""
    from lib.models import SchoolInfo, SchoolFee, EnrollmentInfo, ContactInfo
    
    # Create the main SchoolInfo object
    school_info = SchoolInfo(
        name=school_name,
        link=""  # We'll set this later from the schools_data
    )
    
    # Extract tuition information
    if "tuition" in json_data and json_data["tuition"]:
        school_fee = SchoolFee()
        tuition_data = json_data["tuition"]
        
        # Academic year
        school_fee.academic_year = tuition_data.get("academic_year", "")
        
        # Tuition by level
        if "tuition_by_level" in tuition_data:
            school_fee.tuition_by_level = tuition_data["tuition_by_level"]
        
        # Other fees
        if "other_fees" in tuition_data:
            school_fee.other_fees = tuition_data["other_fees"]
        
        # Due dates
        if "due_dates" in tuition_data:
            school_fee.due_dates = tuition_data["due_dates"]
        
        school_info.school_fee = school_fee
    
    # Extract programs
    if "programs" in json_data and json_data["programs"]:
        school_info.programs = json_data["programs"]
    
    # Extract enrollment information
    if "enrollment" in json_data and json_data["enrollment"]:
        enrollment = EnrollmentInfo()
        enrollment_data = json_data["enrollment"]
        
        # Requirements
        if "requirements" in enrollment_data:
            enrollment.requirements = enrollment_data["requirements"]
        
        # Documents
        if "documents" in enrollment_data:
            enrollment.documents = enrollment_data["documents"]
        
        # Process steps
        if "process_steps" in enrollment_data:
            enrollment.process_steps = enrollment_data["process_steps"]
        
        school_info.enrollment = enrollment
    
    # Extract events
    if "events" in json_data and json_data["events"]:
        school_info.events = json_data["events"]
    
    # Extract scholarships
    if "scholarships" in json_data and json_data["scholarships"]:
        school_info.scholarships = json_data["scholarships"]
    
    # Extract contact information
    if "contact" in json_data and json_data["contact"]:
        contact = ContactInfo()
        contact_data = json_data["contact"]
        
        # Address
        contact.address = contact_data.get("address", "")
        
        # Phone numbers
        if "phone_numbers" in contact_data:
            contact.phone_numbers = contact_data["phone_numbers"]
        
        # Email
        contact.email = contact_data.get("email", "")
        
        # Website
        contact.website = contact_data.get("website", "")
        
        # Social media
        if "social_media" in contact_data:
            contact.social_media = contact_data["social_media"]
        
        school_info.contact = contact
    
    # Extract notes
    if "notes" in json_data and json_data["notes"]:
        school_info.notes = json_data["notes"]
    
    return school_info

def handle_legacy_format(response_text, school_name):
    """Handle legacy text format responses"""
    from lib.models import SchoolInfo, SchoolFee, EnrollmentInfo, ContactInfo
    
    # Create a basic SchoolInfo object
    school_info = SchoolInfo(
        name=school_name,
        link=""
    )
    
    # Try to extract sections using the legacy approach
    sections = {
        "Tuition Fees:": "school_fee",
        "Programs Offered:": "program",
        "Enrollment Requirements:": "enrollment_requirements",
        "Enrollment Process:": "enrollment_process",
        "Upcoming Events:": "events",
        "Scholarships/Discounts:": "scholarships",
        "Contact Information:": "contact",
        "Notes:": "notes"
    }
    
    # Extract data from each section
    extracted_data = {}
    for section_header, field_name in sections.items():
        section_text = _extract_section(response_text, section_header)
        extracted_data[field_name] = section_text if section_text != "No information available" else ""
    
    # Process School Fee information
    if extracted_data["school_fee"]:
        school_fee = SchoolFee()
        school_fee.academic_year = extract_academic_year(extracted_data["school_fee"])
        
        # Parse tuition by level
        levels = {}
        lines = extracted_data["school_fee"].split('\n')
        current_level = "General"
        level_info = {"description": ""}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if this line appears to define a new level
            if ':' in line and not line.startswith('Due') and not line.startswith('Payment'):
                # Save previous level if any
                if level_info["description"]:
                    levels[current_level] = level_info
                
                # Start new level
                parts = line.split(':', 1)
                current_level = parts[0].strip()
                level_info = {"description": parts[1].strip()}
            else:
                # Continue with current level
                level_info["description"] += " " + line
        
        # Add the last level
        if level_info["description"]:
            levels[current_level] = level_info
            
        # If we couldn't parse levels specifically, use the whole text as general description
        if not levels:
            levels["General"] = {"description": extracted_data["school_fee"]}
            
        school_fee.tuition_by_level = levels
        
        # Try to extract payment dates
        due_dates = []
        date_pattern = r'(\w+\s+\w+)\s+[Dd]ue:?\s+(\d{1,2}\s+\w+\s+\d{4})'
        for match in re.finditer(date_pattern, extracted_data["school_fee"]):
            due_dates.append({
                "period": match.group(1),
                "date": match.group(2)
            })
        
        # If we found due dates, add them
        if due_dates:
            school_fee.due_dates = due_dates
            
        # Try to extract other fees
        other_fees = []
        fee_pattern = r'([A-Za-z\s]+Fee):\s+([^$]*[$][0-9,.]+)'
        for match in re.finditer(fee_pattern, extracted_data["school_fee"]):
            other_fees.append({
                "name": match.group(1).strip(),
                "amount": match.group(2).strip(),
                "description": ""
            })
        
        # If we found other fees, add them
        if other_fees:
            school_fee.other_fees = other_fees
            
        school_info.school_fee = school_fee
    
    # Process Programs information
    if extracted_data["program"]:
        programs = []
        for paragraph in extracted_data["program"].split('\n\n'):
            if not paragraph.strip():
                continue
                
            # Try to extract program name and description
            lines = paragraph.split('\n')
            if len(lines) > 0:
                program_name = lines[0].strip()
                description = " ".join(line.strip() for line in lines[1:])
                
                programs.append({
                    "name": program_name,
                    "grade_level": extract_grade_level(program_name),
                    "description": description
                })
            
        # If we couldn't parse specific programs, split by lines
        if not programs:
            programs = []
            for line in extracted_data["program"].split('\n'):
                if line.strip():
                    programs.append({
                        "name": line.strip(),
                        "grade_level": extract_grade_level(line),
                        "description": ""
                    })
                    
        school_info.programs = programs
    
    # Process Enrollment information
    enrollment = EnrollmentInfo()
    
    # Handle requirements
    if extracted_data["enrollment_requirements"]:
        requirements = []
        for line in extracted_data["enrollment_requirements"].split('\n'):
            if line.strip():
                requirements.append(line.strip())
        enrollment.requirements = requirements
    
    # Handle process steps
    if extracted_data["enrollment_process"]:
        process_steps = []
        step_num = 1
        
        # Check if there are numbered steps
        step_pattern = r'(?:Step|)\s*(\d+)[.:]?\s*(.*)'
        numbered_steps = re.findall(step_pattern, extracted_data["enrollment_process"])
        
        if numbered_steps:
            for step_match in numbered_steps:
                process_steps.append({
                    "step": step_match[0],
                    "description": step_match[1].strip()
                })
        else:
            # Just list as bullet points
            for line in extracted_data["enrollment_process"].split('\n'):
                if line.strip():
                    process_steps.append({
                        "step": str(step_num),
                        "description": line.strip()
                    })
                    step_num += 1
                    
        enrollment.process_steps = process_steps
    
    # If we have either requirements or process steps, add the enrollment info
    if not enrollment.is_empty():
        school_info.enrollment = enrollment
    
    # Process Events information
    if extracted_data["events"]:
        events = []
        # Try to match event name and date pattern
        event_pattern = r'([^:]+):\s*([^(]+(?:\([^)]+\))?)\.?'
        event_matches = re.findall(event_pattern, extracted_data["events"])
        
        if event_matches:
            for event_match in event_matches:
                name = event_match[0].strip()
                details = event_match[1].strip()
                
                # Try to extract date from details
                date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', details)
                date = date_match.group(1) if date_match else ""
                
                events.append({
                    "name": name,
                    "date": date,
                    "description": details
                })
        else:
            # Just split by lines
            for line in extracted_data["events"].split('\n'):
                if line.strip():
                    events.append({
                        "name": line.strip(),
                        "date": "",
                        "description": ""
                    })
                    
        school_info.events = events
    
    # Process Scholarships information
    if extracted_data["scholarships"]:
        scholarships = []
        # Split by paragraphs or lines
        items = extracted_data["scholarships"].split('\n\n')
        if len(items) <= 1:
            items = extracted_data["scholarships"].split('\n')
            
        for item in items:
            if not item.strip():
                continue
                
            scholarships.append({
                "name": item.strip(),
                "eligibility": "",
                "amount": "",
                "description": ""
            })
            
        school_info.scholarships = scholarships
    
    # Process Contact information
    if extracted_data["contact"]:
        contact = ContactInfo()
        
        # Try to extract email
        email_match = re.search(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', extracted_data["contact"], re.IGNORECASE)
        if email_match:
            contact.email = email_match.group(0)
        
        # Try to extract phone numbers
        phone_pattern = r'(?:Phone|Tel|Telephone|Contact)(?:[:\s]*)([0-9+\-()\s./]+)'
        phone_matches = re.findall(phone_pattern, extracted_data["contact"])
        if phone_matches:
            contact.phone_numbers = [phone.strip() for phone in phone_matches]
        else:
            # Try generic phone number pattern
            phone_pattern = r'(?:\+\d{1,3}[-\s]*)?\(?\d{3}\)?[-\s]*\d{3}[-\s]*\d{4}'
            phone_matches = re.findall(phone_pattern, extracted_data["contact"])
            if phone_matches:
                contact.phone_numbers = [phone.strip() for phone in phone_matches]
        
        # Try to extract website
        website_match = re.search(r'https?://\S+', extracted_data["contact"])
        if website_match:
            contact.website = website_match.group(0)
        
        # Try to extract address - look for "Address:" or long text with commas
        address_pattern = r'(?:Address|Location)(?:[:\s]*)([^$]+)'
        address_match = re.search(address_pattern, extracted_data["contact"])
        if address_match:
            contact.address = address_match.group(1).strip()
        else:
            # Look for a line with multiple commas that might be an address
            for line in extracted_data["contact"].split('\n'):
                if line.count(',') >= 2 and len(line) > 20:
                    contact.address = line.strip()
                    break
        
        # If we have any contact information, add it
        if not contact.is_empty():
            school_info.contact = contact
    
    # Process Notes
    if extracted_data["notes"]:
        school_info.notes = extracted_data["notes"]
    
    return school_info.to_dict()

def extract_grade_level(text):
    """Extract grade level information from text"""
    grade_patterns = [
        r'Grade[s]?\s+(\d+)(?:\s*-\s*(\d+))?',
        r'(\d+)(?:th|st|nd|rd)?\s*-\s*(\d+)(?:th|st|nd|rd)?\s+Grade',
        r'(?<!\w)(\d{1,2})(?!\w)'
    ]
    
    for pattern in grade_patterns:
        match = re.search(pattern, text)
        if match:
            # If it's a range (e.g., 9-12), return the lower and upper bounds
            if match.group(2):
                return f"Grade {match.group(1)} to Grade {match.group(2)}"
            else:
                return f"Grade {match.group(1)}"
    
    return "Grade information not found"

def extract_academic_year(text):
    """Extract academic year information from text"""
    year_pattern = r'(\d{4})\s*[-–]\s*(\d{4})'
    match = re.search(year_pattern, text)
    if match:
        return f"AY {match.group(1)}-{match.group(2)}"
    return "Academic year not found"

def _extract_section(response_text, section_header):
    """Extract a section from the response text using the section header"""
    pattern = rf"{re.escape(section_header)}(.*?)(?=(?:{'|'.join([re.escape(h) for h in ['Tuition Fees:', 'Programs Offered:', 'Enrollment Requirements:', 'Enrollment Process:', 'Upcoming Events:', 'Scholarships/Discounts:', 'Contact Information:', 'Notes:']])})|$)"
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        section_text = match.group(1).strip()
        return clean_section_text(section_text) if section_text else "No information available"
    return "No information available"
