from bs4 import BeautifulSoup
import asyncio
import json
import logging
from services.session_manager import SessionManager

# Configure logging
logger = logging.getLogger(__name__)

# Chonkie is imported within the split_dom_content function to avoid import errors if not installed yet

def extract_body_content(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    body_content = soup.body
    if body_content:
        return str(body_content)
    return ""


def clean_body_content(body_content):
    soup = BeautifulSoup(body_content, "html.parser")

    # Remove unnecessary elements
    for element in soup(["script", "style", "iframe", "nav", "footer", "head", "meta", "link"]):
        element.extract()

    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, (type(soup.comment)))):
        comment.extract()

    # Get text with better formatting
    cleaned_content = soup.get_text(separator="\n")
    
    # Process lines for better readability
    lines = []
    for line in cleaned_content.splitlines():
        line = line.strip()
        if line:  # Skip empty lines
            lines.append(line)
    
    cleaned_content = "\n".join(lines)
    return cleaned_content


def split_dom_content(dom_content, max_length=8000):
    """
    Split content using Chonkie's SentenceChunker to maintain sentence context
    while controlling the maximum chunk size
    """
    from chonkie import SentenceChunker
    
    # Calculate approximate token count based on characters
    # A rough estimate is 4 characters per token for English text
    token_size = max_length // 4
    overlap_size = token_size // 4  # 25% overlap
    
    # Initialize the chunker with appropriate parameters
    chunker = SentenceChunker(
        tokenizer_or_token_counter="gpt2",  # Using gpt2 tokenizer (default)
        chunk_size=token_size,              # Maximum tokens per chunk 
        chunk_overlap=overlap_size,         # Overlap between chunks
        min_sentences_per_chunk=1           # Minimum sentences in each chunk
    )
    
    # Process the content into chunks
    sentence_chunks = chunker.chunk(dom_content)
    
    # Extract the text from each chunk
    chunks = [chunk.text for chunk in sentence_chunks]
    
    return chunks


async def extract_urls(url):
    """
    Extracts URLs from the given URL using the SessionManager.
    
    Args:
        url (str): The URL to extract links from.
        
    Returns:
        list: A list of extracted URLs.
    """
    session_manager = SessionManager()
    payload = json.dumps({"url": url})

    response = await session_manager.post("https://yourgpt.ai/api/extractUrls", data=payload)
    if response.status_code != 200:
        logger.error(f"Failed to extract URLs from {url}: {response.status_code}")
        return []

    logger.info(f"Received response from extractUrls API: {response.text[:100]}...")
    try:
        result = json.loads(response.text)
        # Extract the URLs array from the "urls" key in the response
        if isinstance(result, dict) and "urls" in result:
            return result["urls"]
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response: {e}")
        return []


async def extract_urls_from_website(url):
    """
    Wrapper function to maintain backward compatibility.
    This function calls extract_urls() and formats the result in the expected structure.
    
    Args:
        url (str): The base URL of the school website
        
    Returns:
        dict: A dictionary with categorized URLs
    """
    # Call the extract_urls function
    extracted_urls = await extract_urls(url)
    
    # Categorize URLs
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
    
    # Process each URL
    for url in extracted_urls:
        # Skip if URL is empty or None
        if not url:
            continue
            
        # Convert to lowercase for easier matching
        url_lower = url.lower()
        
        # Check each category
        for category, keywords_list in keywords.items():
            for keyword in keywords_list:
                if keyword in url_lower:
                    categories[category].append(url)
                    break
    
    return categories


def get_school_base_urls(schools_data):
    """
    Extract base URLs from school data.
    
    Args:
        schools_data (list): List of school data dictionaries
        
    Returns:
        dict: A dictionary mapping school names to base URLs
    """
    base_urls = {}
    
    for school in schools_data:
        school_name = school.get("name", "")
        
        # Try to get the link directly
        if "link" in school and school["link"]:
            base_urls[school_name] = school["link"]
            continue
            
        # Look for URLs in various fields
        for field in ["school_fee", "program", "Enrollment Process and Requirements", "Contact Information "]:
            value = school.get(field, "")
            if isinstance(value, str) and value and "http" in value:
                # Extract domain from URL
                parts = value.split("/")
                if len(parts) >= 3:
                    base_urls[school_name] = f"{parts[0]}//{parts[2]}"
                    break
            elif isinstance(value, list) and value:
                for item in value:
                    if isinstance(item, str) and item and "http" in item:
                        parts = item.split("/")
                        if len(parts) >= 3:
                            base_urls[school_name] = f"{parts[0]}//{parts[2]}"
                            break
    
    return base_urls