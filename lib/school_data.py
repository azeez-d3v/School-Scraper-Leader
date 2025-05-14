from typing import Dict, List


class SchoolData:
    """Utility class to manage school information"""

    @staticmethod
    def get_school_links():
        """
        Returns a list of Philippine school website URLs to be scraped.
        
        Returns:
            list: A list of URLs as strings
        """
        return [
            "https://www.ismanila.org",
            "https://www.britishschoolmanila.org",
            "https://reedleyschool.edu.ph", 
            "https://www.southville.edu.ph",
            "https://singaporeschools.ph",
            "https://faith.edu.ph",
            "https://www.jca.edu.ph"
        ]