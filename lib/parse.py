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
    "Tuition Fees: [Extract all details about tuition costs, payment schedules, and fees]\n\n"    "Programs Offered: [Extract all academic programs, curriculum details, and grade levels]\n\n"
    "Enrollment Requirements: [Extract all admission requirements and eligibility criteria]\n\n"
    "Enrollment Process: [Extract the step-by-step application procedures]\n\n"
    "Upcoming Events: [Extract information about school events and dates]\n\n"
    "Scholarships/Discounts: [Extract details about scholarships and financial aid]\n\n"
    "Facilities: [Extract information about school facilities including labs, libraries, sports facilities, arts centers, etc.]\n\n"
    "Faculty and Staff: [Extract details about faculty qualifications, departments, notable members, and staff information]\n\n"
    "Achievements and Accreditations: [Extract information about awards, recognitions, accreditations, and notable achievements]\n\n"
    "Marketing and Branding: [Extract taglines, value propositions, and key messaging themes used by the school]\n\n"
    "Technical Infrastructure: [Extract information about technology used, digital platforms, learning management systems]\n\n"
    "Student Life: [Extract details about clubs, organizations, testimonials, campus activities, and partnerships]\n\n"
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
    
    # Check if content contains PDF data and log it
    pdf_content_count = dom_content.count("[PDF CONTENT FROM:")
    if pdf_content_count > 0:
        logger.info(f"Found {pdf_content_count} PDF content sections in data for {school_name}")
    
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
            "    ]\n"            "  }},\n"
            "  \"facilities\": [\n"
            "    {{\n"
            "      \"name\": \"[FACILITY NAME]\",\n"
            "      \"type\": \"[TYPE: lab, library, sports, arts, etc.]\",\n"
            "      \"description\": \"[DESCRIPTION]\",\n"
            "      \"features\": [\n"
            "        \"[FEATURE 1]\",\n"
            "        \"[FEATURE 2]\"\n"
            "      ]\n"
            "    }}\n"
            "    // Additional facilities as needed\n"
            "  ],\n"
            "  \"faculty\": [\n"
            "    {{\n"
            "      \"department\": \"[DEPARTMENT NAME]\",\n"
            "      \"staff_count\": \"[NUMBER OF STAFF]\",\n"
            "      \"qualifications\": \"[GENERAL QUALIFICATIONS]\",\n"
            "      \"notable_members\": [\n"
            "        {{\n"
            "          \"name\": \"[NAME]\",\n"
            "          \"position\": \"[POSITION]\",\n"
            "          \"bio\": \"[BRIEF BIO]\"\n"
            "        }}\n"
            "      ]\n"
            "    }}\n"
            "    // Additional faculty departments as needed\n"
            "  ],\n"
            "  \"achievements\": [\n"
            "    {{\n"
            "      \"type\": \"[TYPE: Award, Accreditation, Recognition, etc.]\",\n"
            "      \"name\": \"[NAME OF ACHIEVEMENT]\",\n"
            "      \"year\": \"[YEAR RECEIVED]\",\n"
            "      \"description\": \"[DESCRIPTION]\",\n"
            "      \"issuing_body\": \"[ORGANIZATION THAT ISSUED IT]\"\n"
            "    }}\n"
            "    // Additional achievements as needed\n"
            "  ],\n"
            "  \"marketing_content\": {{\n"
            "    \"taglines\": [\n"
            "      \"[TAGLINE OR SLOGAN]\"\n"
            "    ],\n"
            "    \"value_propositions\": [\n"
            "      \"[VALUE PROPOSITION]\"\n"
            "    ],\n"
            "    \"key_messaging\": [\n"
            "      \"[KEY MESSAGE]\"\n"
            "    ],\n"
            "    \"content_strategy\": \"[OVERALL CONTENT APPROACH]\"\n"
            "  }},\n"
            "  \"technical_data\": {{\n"
            "    \"technology_infrastructure\": \"[DESCRIPTION OF TECH INFRASTRUCTURE]\",\n"
            "    \"digital_platforms\": [\n"
            "      \"[PLATFORM NAME AND PURPOSE]\"\n"
            "    ],\n"
            "    \"learning_management_system\": \"[LMS NAME IF ANY]\",\n"
            "    \"tech_initiatives\": [\n"
            "      \"[TECH INITIATIVE DESCRIPTION]\"\n"
            "    ]\n"
            "  }},\n"
            "  \"student_life\": {{\n"
            "    \"clubs_organizations\": [\n"
            "      {{\n"
            "        \"name\": \"[CLUB/ORGANIZATION NAME]\",\n"
            "        \"description\": \"[DESCRIPTION]\"\n"
            "      }}\n"
            "    ],\n"
            "    \"testimonials\": [\n"
            "      {{\n"
            "        \"quote\": \"[TESTIMONIAL QUOTE]\",\n"
            "        \"source\": \"[SOURCE: Student, Parent, Alumni, etc.]\"\n"
            "      }}\n"
            "    ],\n"
            "    \"partnerships\": [\n"
            "      {{\n"
            "        \"partner\": \"[PARTNER NAME]\",\n"
            "        \"nature\": \"[NATURE OF PARTNERSHIP]\"\n"
            "      }}\n"
            "    ],\n"
            "    \"activities\": [\n"
            "      \"[ACTIVITY DESCRIPTION]\"\n"
            "    ],\n"
            "    \"campus_life\": \"[DESCRIPTION OF CAMPUS LIFE]\"\n"
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
            "5. For enrollment, separate requirements from required documents and provide step-by-step process\n"            "6. Remove any JSON comments (lines with // ) in your final output\n"
            "7. Pay special attention to PDF content sections marked with [PDF CONTENT FROM: url] as these may contain important structured information\n"
            "8. For facilities, be as detailed as possible about each type of facility and its features\n"
            "9. For faculty, extract information about qualifications, departments, and any notable staff members\n"
            "10. For achievements, capture all awards, accreditations, and recognitions with dates when available\n" 
            "11. For marketing content, focus on the key messaging, taglines, and value propositions used by the school\n"
            "12. For technical data, include information about the school's technology infrastructure and digital platforms\n"
            "13. For student life, include clubs, organizations, testimonials, partnerships, and campus activities\n\n"
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
        
        # Log successful parsing of PDF content
        if pdf_content_count > 0:
            logger.info(f"Successfully processed {pdf_content_count} PDF content sections for {school_name}")
            
            # Check if the extracted data contains information likely from PDFs
            if "tuition" in json_data or "enrollment" in json_data:
                logger.info(f"Extracted structured data from PDFs for {school_name}")
        
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
            logger.error(f"Failed to parse JSON from code block: {e}")
            logger.info("Attempting to fix JSON structure...")
            try:
                # Try to fix common JSON issues
                fixed_json = json_str.replace("'", "\"")  # Replace single quotes with double quotes
                fixed_json = re.sub(r',\s*}', '}', fixed_json)  # Remove trailing commas in objects
                fixed_json = re.sub(r',\s*\]', ']', fixed_json)  # Remove trailing commas in arrays
                return json.loads(fixed_json)
            except json.JSONDecodeError:
                logger.error("Failed to fix JSON from code block")
                return None
    
    # If no code block, try parsing the whole text as JSON
    try:
        # Try to find JSON-like structure with curly braces
        json_candidates = re.findall(r'({[^{]*})', response_text, re.DOTALL)
        
        # Try each candidate, starting with the largest one
        json_candidates.sort(key=len, reverse=True)
        
        for json_candidate in json_candidates:
            try:
                # Clean up the candidate
                cleaned = json_candidate.replace("'", "\"")  # Replace single quotes with double quotes
                cleaned = re.sub(r',\s*}', '}', cleaned)  # Remove trailing commas in objects
                cleaned = re.sub(r',\s*\]', ']', cleaned)  # Remove trailing commas in arrays
                parsed = json.loads(cleaned)
                logger.info("Found valid JSON structure outside of code block")
                return parsed
            except json.JSONDecodeError:
                continue
        
        # If we get here, we weren't able to find a valid JSON structure
        logger.error("No valid JSON structure found in the response")
        return None
    except Exception as e:
        logger.error(f"Error while trying to extract JSON: {e}")
        return None

def create_school_info_from_json(json_data, school_name):
    """Create a SchoolInfo object from parsed JSON data"""
    from lib.models import (
        SchoolInfo, SchoolFee, EnrollmentInfo, ContactInfo, 
        Facility, FacultyInfo, FacultyMember, Achievement,
        MarketingContent, TechnicalData, ClubOrganization,
        Testimonial, Partnership, StudentLife
    )
    
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
    
    # Extract facilities
    if "facilities" in json_data and json_data["facilities"]:
        facilities = []
        for facility_data in json_data["facilities"]:
            facility = Facility()
            facility.name = facility_data.get("name", "")
            facility.type = facility_data.get("type", "")
            facility.description = facility_data.get("description", "")
            facility.features = facility_data.get("features", [])
            
            facilities.append(facility)
        
        school_info.facilities = facilities
    
    # Extract faculty information
    if "faculty" in json_data and json_data["faculty"]:
        faculty_list = []
        for dept_data in json_data["faculty"]:
            faculty = FacultyInfo()
            faculty.department = dept_data.get("department", "")
            faculty.staff_count = dept_data.get("staff_count", "")
            faculty.qualifications = dept_data.get("qualifications", "")
            
            # Process notable members
            if "notable_members" in dept_data and dept_data["notable_members"]:
                members = []
                for member_data in dept_data["notable_members"]:
                    member = FacultyMember()
                    member.name = member_data.get("name", "")
                    member.position = member_data.get("position", "")
                    member.bio = member_data.get("bio", "")
                    members.append(member)
                
                faculty.notable_members = members
            
            faculty_list.append(faculty)
        
        school_info.faculty = faculty_list
    
    # Extract achievements
    if "achievements" in json_data and json_data["achievements"]:
        achievements = []
        for achievement_data in json_data["achievements"]:
            achievement = Achievement()
            achievement.type = achievement_data.get("type", "")
            achievement.name = achievement_data.get("name", "")
            achievement.year = achievement_data.get("year", "")
            achievement.description = achievement_data.get("description", "")
            achievement.issuing_body = achievement_data.get("issuing_body", "")
            
            achievements.append(achievement)
        
        school_info.achievements = achievements
    
    # Extract marketing content
    if "marketing_content" in json_data and json_data["marketing_content"]:
        marketing = MarketingContent()
        marketing_data = json_data["marketing_content"]
        
        marketing.taglines = marketing_data.get("taglines", [])
        marketing.value_propositions = marketing_data.get("value_propositions", [])
        marketing.key_messaging = marketing_data.get("key_messaging", [])
        marketing.content_strategy = marketing_data.get("content_strategy", "")
        
        school_info.marketing_content = marketing
    
    # Extract technical data
    if "technical_data" in json_data and json_data["technical_data"]:
        tech_data = TechnicalData()
        tech_info = json_data["technical_data"]
        
        tech_data.technology_infrastructure = tech_info.get("technology_infrastructure", "")
        tech_data.digital_platforms = tech_info.get("digital_platforms", [])
        tech_data.learning_management_system = tech_info.get("learning_management_system", "")
        tech_data.tech_initiatives = tech_info.get("tech_initiatives", [])
        
        school_info.technical_data = tech_data
    
    # Extract student life information
    if "student_life" in json_data and json_data["student_life"]:
        student_life = StudentLife()
        student_life_data = json_data["student_life"]
        
        # Process clubs and organizations
        if "clubs_organizations" in student_life_data and student_life_data["clubs_organizations"]:
            clubs = []
            for club_data in student_life_data["clubs_organizations"]:
                club = ClubOrganization()
                club.name = club_data.get("name", "")
                club.description = club_data.get("description", "")
                clubs.append(club)
            
            student_life.clubs_organizations = clubs
        
        # Process testimonials
        if "testimonials" in student_life_data and student_life_data["testimonials"]:
            testimonials = []
            for testimonial_data in student_life_data["testimonials"]:
                testimonial = Testimonial()
                testimonial.quote = testimonial_data.get("quote", "")
                testimonial.source = testimonial_data.get("source", "")
                testimonials.append(testimonial)
            
            student_life.testimonials = testimonials
        
        # Process partnerships
        if "partnerships" in student_life_data and student_life_data["partnerships"]:
            partnerships = []
            for partnership_data in student_life_data["partnerships"]:
                partnership = Partnership()
                partnership.partner = partnership_data.get("partner", "")
                partnership.nature = partnership_data.get("nature", "")
                partnerships.append(partnership)
            
            student_life.partnerships = partnerships
        
        student_life.activities = student_life_data.get("activities", [])
        student_life.campus_life = student_life_data.get("campus_life", "")
        
        school_info.student_life = student_life
    
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
    from lib.models import (
        SchoolInfo, SchoolFee, EnrollmentInfo, ContactInfo, 
        Facility, FacultyInfo, FacultyMember, Achievement,
        MarketingContent, TechnicalData, ClubOrganization,
        Testimonial, Partnership, StudentLife
    )
    
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
        "Facilities:": "facilities",
        "Faculty and Staff:": "faculty",
        "Faculty Information:": "faculty", 
        "Achievements and Accreditations:": "achievements",
        "Marketing and Branding:": "marketing_content",
        "Technical Infrastructure:": "technical_data",
        "Student Life:": "student_life",
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
        
    # Process Facilities information
    if extracted_data.get("facilities"):
        facilities = []
        
        # Try to split by paragraphs or lines
        items = extracted_data["facilities"].split('\n\n')
        if len(items) <= 1:
            items = extracted_data["facilities"].split('\n')
            
        for item in items:
            if not item.strip():
                continue
                
            # Try to extract facility name and type
            facility = Facility()
            lines = item.split('\n')
            
            if len(lines) > 0:
                # First line is usually the name
                facility.name = lines[0].strip()
                facility.description = " ".join(line.strip() for line in lines[1:])
                
                # Try to infer facility type from the name
                if any(keyword in facility.name.lower() for keyword in ["lab", "laboratory", "science"]):
                    facility.type = "Laboratory"
                elif any(keyword in facility.name.lower() for keyword in ["library", "books", "reading"]):
                    facility.type = "Library"
                elif any(keyword in facility.name.lower() for keyword in ["gym", "sport", "field", "court", "swimming", "pool"]):
                    facility.type = "Sports"
                elif any(keyword in facility.name.lower() for keyword in ["art", "music", "theater", "drama", "auditorium"]):
                    facility.type = "Arts"
                elif any(keyword in facility.name.lower() for keyword in ["cafeteria", "canteen", "dining"]):
                    facility.type = "Dining"
                else:
                    facility.type = "Other"
                
                facilities.append(facility)
        
        school_info.facilities = facilities
        
    # Process Faculty information
    if extracted_data.get("faculty"):
        faculty_info = FacultyInfo()
        
        # Try to extract department and staff count information
        dept_pattern = r'Department[s]?:\s*(.*)'
        dept_match = re.search(dept_pattern, extracted_data["faculty"], re.IGNORECASE)
        if dept_match:
            faculty_info.department = dept_match.group(1).strip()
            
        staff_count_pattern = r'(?:Staff count|Number of staff|Faculty size):\s*(\d+)'
        staff_match = re.search(staff_count_pattern, extracted_data["faculty"], re.IGNORECASE)
        if staff_match:
            faculty_info.staff_count = staff_match.group(1).strip()
            
        qualifications_pattern = r'Qualifications?:\s*(.*)'
        qualifications_match = re.search(qualifications_pattern, extracted_data["faculty"], re.IGNORECASE)
        if qualifications_match:
            faculty_info.qualifications = qualifications_match.group(1).strip()
            
        # Extract notable members if they exist
        notable_members = []
        member_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\s*[-:]\s*)([^:]+?)(?:\s*(?:Bio)?\s*[:]\s*(.+?))?(?=\n[A-Z]|\Z)'
        member_matches = re.findall(member_pattern, extracted_data["faculty"], re.DOTALL)
        
        for match in member_matches:
            member = FacultyMember()
            member.name = match[0].strip()
            member.position = match[1].strip() if len(match) > 1 else ""
            member.bio = match[2].strip() if len(match) > 2 else ""
            notable_members.append(member)
            
        faculty_info.notable_members = notable_members
        
        # Add to the school info if we have any faculty data
        if not faculty_info.is_empty():
            school_info.faculty = [faculty_info]  # List of departments
    
    # Process Achievements information
    if extracted_data.get("achievements"):
        achievements = []
        
        # Try to extract individual achievements
        achievement_pattern = r'([^:]+?)(?:\s*\((\d{4})\))?\s*(?::\s*(.+?))?(?=\n[A-Z]|\Z)'
        achievement_matches = re.findall(achievement_pattern, extracted_data["achievements"], re.DOTALL)
        
        for match in achievement_matches:
            achievement = Achievement()
            achievement.name = match[0].strip()
            achievement.year = match[1].strip() if len(match) > 1 and match[1] else ""
            achievement.description = match[2].strip() if len(match) > 2 and match[2] else ""
            
            # Try to infer type from the name
            if any(keyword in achievement.name.lower() for keyword in ["accreditation", "accredited"]):
                achievement.type = "Accreditation"
            elif any(keyword in achievement.name.lower() for keyword in ["award", "prize", "medal"]):
                achievement.type = "Award"
            elif any(keyword in achievement.name.lower() for keyword in ["recognition", "recognized"]):
                achievement.type = "Recognition"
            else:
                achievement.type = "Achievement"
                
            achievements.append(achievement)
            
        # If we couldn't parse specific achievements, just use lines
        if not achievements:
            for line in extracted_data["achievements"].split('\n'):
                if line.strip():
                    achievement = Achievement()
                    achievement.name = line.strip()
                    achievement.type = "Achievement"
                    achievements.append(achievement)
        
        school_info.achievements = achievements
        
    # Process Marketing Content
    if extracted_data.get("marketing_content"):
        marketing = MarketingContent()
        
        # Try to extract taglines
        tagline_pattern = r'(?:Tagline|Slogan)[s]?:\s*(.*)'
        tagline_match = re.search(tagline_pattern, extracted_data["marketing_content"], re.IGNORECASE)
        if tagline_match:
            taglines = [t.strip() for t in tagline_match.group(1).split(',')]
            marketing.taglines = taglines
            
        # Try to extract value propositions
        value_pattern = r'Value Proposition[s]?:\s*(.*)'
        value_match = re.search(value_pattern, extracted_data["marketing_content"], re.IGNORECASE)
        if value_match:
            values = [v.strip() for v in value_match.group(1).split(',')]
            marketing.value_propositions = values
            
        # Try to extract key messaging
        messaging_pattern = r'Key Message[s]?:\s*(.*)'
        messaging_match = re.search(messaging_pattern, extracted_data["marketing_content"], re.IGNORECASE)
        if messaging_match:
            messages = [m.strip() for m in messaging_match.group(1).split(',')]
            marketing.key_messaging = messages
            
        # Try to extract content strategy
        strategy_pattern = r'(?:Content Strategy|Marketing Approach):\s*(.*)'
        strategy_match = re.search(strategy_pattern, extracted_data["marketing_content"], re.IGNORECASE)
        if strategy_match:
            marketing.content_strategy = strategy_match.group(1).strip()
            
        # If we didn't find structured content, add lines as taglines or key messages
        if marketing.is_empty():
            for line in extracted_data["marketing_content"].split('\n'):
                if line.strip():
                    if not marketing.taglines:
                        marketing.taglines = [line.strip()]
                    else:
                        if not marketing.key_messaging:
                            marketing.key_messaging = [line.strip()]
                        
        # Add to school info if we have any marketing data
        if not marketing.is_empty():
            school_info.marketing_content = marketing
            
    # Process Technical Data
    if extracted_data.get("technical_data"):
        tech_data = TechnicalData()
        
        # Try to extract technology infrastructure
        infra_pattern = r'(?:Technology Infrastructure|IT Infrastructure):\s*(.*)'
        infra_match = re.search(infra_pattern, extracted_data["technical_data"], re.IGNORECASE)
        if infra_match:
            tech_data.technology_infrastructure = infra_match.group(1).strip()
            
        # Try to extract digital platforms
        platforms_pattern = r'Digital Platform[s]?:\s*(.*)'
        platforms_match = re.search(platforms_pattern, extracted_data["technical_data"], re.IGNORECASE)
        if platforms_match:
            platforms = [p.strip() for p in platforms_match.group(1).split(',')]
            tech_data.digital_platforms = platforms
            
        # Try to extract LMS
        lms_pattern = r'(?:Learning Management System|LMS):\s*(.*)'
        lms_match = re.search(lms_pattern, extracted_data["technical_data"], re.IGNORECASE)
        if lms_match:
            tech_data.learning_management_system = lms_match.group(1).strip()
            
        # Try to extract tech initiatives
        initiatives_pattern = r'(?:Technology Initiatives|Tech Initiatives):\s*(.*)'
        initiatives_match = re.search(initiatives_pattern, extracted_data["technical_data"], re.IGNORECASE)
        if initiatives_match:
            initiatives = [i.strip() for i in initiatives_match.group(1).split(',')]
            tech_data.tech_initiatives = initiatives
            
        # Add to school info if we have any tech data
        if not tech_data.is_empty():
            school_info.technical_data = tech_data
            
    # Process Student Life information
    if extracted_data.get("student_life"):
        student_life = StudentLife()
        
        # Try to extract clubs and organizations
        clubs_pattern = r'Clubs(?:\s+and\s+Organizations)?:\s*(.*?)(?=\n[A-Z]|\Z)'
        clubs_match = re.search(clubs_pattern, extracted_data["student_life"], re.IGNORECASE | re.DOTALL)
        if clubs_match:
            clubs_text = clubs_match.group(1).strip()
            club_list = clubs_text.split('\n')
            for club_text in club_list:
                if club_text.strip():
                    club = ClubOrganization()
                    club.name = club_text.strip()
                    student_life.clubs_organizations.append(club)
                    
        # Try to extract testimonials
        testimonial_pattern = r'"([^"]+)"\s*[-—]\s*([^,]+)'
        testimonial_matches = re.findall(testimonial_pattern, extracted_data["student_life"])
        for match in testimonial_matches:
            testimonial = Testimonial()
            testimonial.quote = match[0].strip()
            testimonial.source = match[1].strip()
            student_life.testimonials.append(testimonial)
            
        # Try to extract partnerships
        partnership_pattern = r'Partnership(?:s)?:\s*(.*?)(?=\n[A-Z]|\Z)'
        partnership_match = re.search(partnership_pattern, extracted_data["student_life"], re.IGNORECASE | re.DOTALL)
        if partnership_match:
            partnership_text = partnership_match.group(1).strip()
            partnership_list = partnership_text.split('\n')
            for p_text in partnership_list:
                if p_text.strip():
                    partnership = Partnership()
                    partnership.partner = p_text.strip()
                    student_life.partnerships.append(partnership)
                    
        # Try to extract campus life description
        campus_pattern = r'Campus Life:\s*(.*?)(?=\n[A-Z]|\Z)'
        campus_match = re.search(campus_pattern, extracted_data["student_life"], re.IGNORECASE | re.DOTALL)
        if campus_match:
            student_life.campus_life = campus_match.group(1).strip()
            
        # Add to school info if we have any student life data
        if not student_life.is_empty():
            school_info.student_life = student_life
    
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
    headers = [
        'Tuition Fees:', 'Programs Offered:', 'Enrollment Requirements:', 
        'Enrollment Process:', 'Upcoming Events:', 'Scholarships/Discounts:', 
        'Facilities:', 'Faculty Information:', 'Faculty and Staff:', 'Achievements:', 
        'Achievements and Accreditations:', 'Marketing Content:', 'Marketing and Branding:',
        'Technical Data:', 'Technical Infrastructure:', 'Student Life:',
        'Contact Information:', 'Notes:'
    ]
    
    pattern = rf"{re.escape(section_header)}(.*?)(?=(?:{'|'.join([re.escape(h) for h in headers])})|$)"
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        section_text = match.group(1).strip()
        return clean_section_text(section_text) if section_text else "No information available"
    
    # If exact match fails, try case-insensitive
    pattern = rf"{re.escape(section_header)}(.*?)(?=(?:{'|'.join([re.escape(h) for h in headers])})|$)"
    match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
    if match:
        section_text = match.group(1).strip()
        return clean_section_text(section_text) if section_text else "No information available"
    
    # Try partial match by removing the colon
    section_name = section_header.rstrip(':').lower()
    pattern = rf"{re.escape(section_name)}[:\s]+(.*?)(?=(?:{'|'.join([re.escape(h) for h in headers])})|$)"
    match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
    if match:
        section_text = match.group(1).strip()
        return clean_section_text(section_text) if section_text else "No information available"
        
    return "No information available"
