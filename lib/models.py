from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

@dataclass
class SchoolFee:
    """Data class for structured tuition and fee information"""
    academic_year: str = ""
    tuition_by_level: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    other_fees: List[Dict[str, Any]] = field(default_factory=list)
    due_dates: List[Dict[str, str]] = field(default_factory=list)
    
    def is_empty(self) -> bool:
        """Check if the fee structure is empty"""
        return not (self.academic_year or self.tuition_by_level or self.other_fees)

@dataclass
class EnrollmentInfo:
    """Data class for structured enrollment information"""
    requirements: List[str] = field(default_factory=list)
    documents: List[str] = field(default_factory=list)
    process_steps: List[Dict[str, str]] = field(default_factory=list)
    
    def is_empty(self) -> bool:
        """Check if enrollment information is empty"""
        return not (self.requirements or self.documents or self.process_steps)

@dataclass
class ContactInfo:
    """Data class for structured contact information"""
    address: str = ""
    phone_numbers: List[str] = field(default_factory=list)
    email: str = ""
    website: str = ""
    social_media: Dict[str, str] = field(default_factory=dict)
    
    def is_empty(self) -> bool:
        """Check if contact information is empty"""
        return not (self.address or self.phone_numbers or self.email or self.website)

@dataclass
class SchoolInfo:
    """Data class for standardized school information"""
    name: str
    link: str
    school_fee: SchoolFee = field(default_factory=SchoolFee)
    programs: List[Dict[str, Any]] = field(default_factory=list)
    enrollment: EnrollmentInfo = field(default_factory=EnrollmentInfo)
    events: List[Dict[str, str]] = field(default_factory=list)
    scholarships: List[Dict[str, Any]] = field(default_factory=list)
    contact: ContactInfo = field(default_factory=ContactInfo)
    notes: str = field(default_factory=lambda: f"Scraped at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    def to_dict(self):
        """Convert to dictionary for easier serialization"""
        return {
            "name": self.name,
            "link": self.link,
            "school_fee": self._format_school_fee(),
            "programs": self.programs if self.programs else "No information available",
            "enrollment": self._format_enrollment(),
            "events": self.events if self.events else "No information available",
            "scholarships": self.scholarships if self.scholarships else "No information available",
            "contact": self._format_contact(),
            "notes": self.notes
        }
    
    def _format_school_fee(self):
        """Format school fee information"""
        if self.school_fee.is_empty():
            return "No information available"
        
        fee_data = {
            "academic_year": self.school_fee.academic_year,
            "tuition_by_level": self.school_fee.tuition_by_level,
            "other_fees": self.school_fee.other_fees,
            "due_dates": self.school_fee.due_dates
        }
        
        # Remove empty fields
        return {k: v for k, v in fee_data.items() if v}
    
    def _format_enrollment(self):
        """Format enrollment information"""
        if self.enrollment.is_empty():
            return "No information available"
        
        enrollment_data = {
            "requirements": self.enrollment.requirements,
            "documents": self.enrollment.documents,
            "process_steps": self.enrollment.process_steps
        }
        
        # Remove empty fields
        return {k: v for k, v in enrollment_data.items() if v}
    
    def _format_contact(self):
        """Format contact information"""
        if self.contact.is_empty():
            return "No information available"
        
        contact_data = {
            "address": self.contact.address,
            "phone_numbers": self.contact.phone_numbers,
            "email": self.contact.email,
            "website": self.contact.website,
            "social_media": self.contact.social_media
        }
        
        # Remove empty fields
        return {k: v for k, v in contact_data.items() if v}