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
class Facility:
    """Data class for facility information"""
    name: str = ""
    type: str = ""
    description: str = ""
    features: List[str] = field(default_factory=list)
    
    def is_empty(self) -> bool:
        """Check if facility information is empty"""
        return not (self.name or self.description or self.features)

@dataclass
class FacultyMember:
    """Data class for notable faculty members"""
    name: str = ""
    position: str = ""
    bio: str = ""

@dataclass
class FacultyInfo:
    """Data class for faculty information"""
    department: str = ""
    staff_count: str = ""
    qualifications: str = ""
    notable_members: List[FacultyMember] = field(default_factory=list)
    
    def is_empty(self) -> bool:
        """Check if faculty information is empty"""
        return not (self.department or self.staff_count or self.qualifications or self.notable_members)

@dataclass
class Achievement:
    """Data class for school achievements"""
    type: str = ""
    name: str = ""
    year: str = ""
    description: str = ""
    issuing_body: str = ""
    
    def is_empty(self) -> bool:
        """Check if achievement is empty"""
        return not (self.name or self.description)

@dataclass
class MarketingContent:
    """Data class for marketing content"""
    taglines: List[str] = field(default_factory=list)
    value_propositions: List[str] = field(default_factory=list)
    key_messaging: List[str] = field(default_factory=list)
    content_strategy: str = ""
    
    def is_empty(self) -> bool:
        """Check if marketing content is empty"""
        return not (self.taglines or self.value_propositions or self.key_messaging or self.content_strategy)

@dataclass
class TechnicalData:
    """Data class for technical information"""
    technology_infrastructure: str = ""
    digital_platforms: List[str] = field(default_factory=list)
    learning_management_system: str = ""
    tech_initiatives: List[str] = field(default_factory=list)
    
    def is_empty(self) -> bool:
        """Check if technical data is empty"""
        return not (self.technology_infrastructure or self.digital_platforms or self.learning_management_system or self.tech_initiatives)

@dataclass
class ClubOrganization:
    """Data class for clubs and organizations"""
    name: str = ""
    description: str = ""

@dataclass
class Testimonial:
    """Data class for testimonials"""
    quote: str = ""
    source: str = ""

@dataclass
class Partnership:
    """Data class for partnerships"""
    partner: str = ""
    nature: str = ""

@dataclass
class StudentLife:
    """Data class for student life information"""
    clubs_organizations: List[ClubOrganization] = field(default_factory=list)
    testimonials: List[Testimonial] = field(default_factory=list)
    partnerships: List[Partnership] = field(default_factory=list)
    activities: List[str] = field(default_factory=list)
    campus_life: str = ""
    
    def is_empty(self) -> bool:
        """Check if student life information is empty"""
        return not (self.clubs_organizations or self.testimonials or self.partnerships or self.activities or self.campus_life)

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
    facilities: List[Facility] = field(default_factory=list)
    faculty: List[FacultyInfo] = field(default_factory=list)
    achievements: List[Achievement] = field(default_factory=list)
    marketing_content: MarketingContent = field(default_factory=MarketingContent)
    technical_data: TechnicalData = field(default_factory=TechnicalData)
    student_life: StudentLife = field(default_factory=StudentLife)
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
            "facilities": self._format_facilities(),
            "faculty": self._format_faculty(),
            "achievements": self._format_achievements(),
            "marketing_content": self._format_marketing_content(),
            "technical_data": self._format_technical_data(),
            "student_life": self._format_student_life(),
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
    
    def _format_facilities(self):
        """Format facilities information"""
        if not self.facilities:
            return "No information available"
        
        return [
            {
                "name": facility.name,
                "type": facility.type,
                "description": facility.description,
                "features": facility.features
            }
            for facility in self.facilities
        ]
    
    def _format_faculty(self):
        """Format faculty information"""
        if not self.faculty:
            return "No information available"
        
        return [
            {
                "department": f.department,
                "staff_count": f.staff_count,
                "qualifications": f.qualifications,
                "notable_members": [
                    {
                        "name": member.name,
                        "position": member.position,
                        "bio": member.bio
                    }
                    for member in f.notable_members
                ]
            }
            for f in self.faculty
        ]
    
    def _format_achievements(self):
        """Format achievements information"""
        if not self.achievements:
            return "No information available"
        
        return [
            {
                "type": a.type,
                "name": a.name,
                "year": a.year,
                "description": a.description,
                "issuing_body": a.issuing_body
            }
            for a in self.achievements
        ]
    
    def _format_marketing_content(self):
        """Format marketing content"""
        if self.marketing_content.is_empty():
            return "No information available"
        
        marketing_data = {
            "taglines": self.marketing_content.taglines,
            "value_propositions": self.marketing_content.value_propositions,
            "key_messaging": self.marketing_content.key_messaging,
            "content_strategy": self.marketing_content.content_strategy
        }
        
        # Remove empty fields
        return {k: v for k, v in marketing_data.items() if v}
    
    def _format_technical_data(self):
        """Format technical data"""
        if self.technical_data.is_empty():
            return "No information available"
        
        tech_data = {
            "technology_infrastructure": self.technical_data.technology_infrastructure,
            "digital_platforms": self.technical_data.digital_platforms,
            "learning_management_system": self.technical_data.learning_management_system,
            "tech_initiatives": self.technical_data.tech_initiatives
        }
        
        # Remove empty fields
        return {k: v for k, v in tech_data.items() if v}
    
    def _format_student_life(self):
        """Format student life information"""
        if self.student_life.is_empty():
            return "No information available"
        
        student_life_data = {
            "clubs_organizations": [
                {"name": club.name, "description": club.description}
                for club in self.student_life.clubs_organizations
            ],
            "testimonials": [
                {"quote": t.quote, "source": t.source}
                for t in self.student_life.testimonials
            ],
            "partnerships": [
                {"partner": p.partner, "nature": p.nature}
                for p in self.student_life.partnerships
            ],
            "activities": self.student_life.activities,
            "campus_life": self.student_life.campus_life
        }
        
        # Remove empty fields
        return {k: v for k, v in student_life_data.items() if v}
    
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