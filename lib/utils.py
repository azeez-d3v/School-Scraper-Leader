from bs4 import BeautifulSoup

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
    Split content more intelligently - by paragraphs when possible
    to maintain context, with a maximum chunk size
    """
    # First try to split by double newlines (paragraphs)
    paragraphs = dom_content.split("\n\n")
    
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed max length, save current chunk and start a new one
        if len(current_chunk) + len(paragraph) + 2 > max_length:
            if current_chunk:
                chunks.append(current_chunk)
            
            # If paragraph itself is too long, split it
            if len(paragraph) > max_length:
                # Split long paragraph by sentences or just by characters if needed
                for i in range(0, len(paragraph), max_length):
                    chunks.append(paragraph[i:i+max_length])
            else:
                current_chunk = paragraph
        else:
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks
