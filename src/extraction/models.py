import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class PartialMetadata:
    company_name: Optional[str] = None
    role_title: Optional[str] = None
    job_type: Optional[str] = None  # "internship", "fte", "ppo", "contract"
    package_ctc: Optional[float] = None
    stipend_monthly: Optional[float] = None
    cgpa_cutoff: Optional[float] = None
    eligible_branches: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    experience_required: Optional[str] = None
    deadline: Optional[str] = None  # ISO-8601 string
    location: List[str] = field(default_factory=list)
    work_mode: Optional[str] = None  # "remote", "hybrid", "on-site"
    duration_months: Optional[int] = None
    selection_process: List[str] = field(default_factory=list)
    bond_clause: Optional[bool] = None
    perks: List[str] = field(default_factory=list)
    
    # Confidence tracker (mapping field_name -> float score)
    confidences: Dict[str, float] = field(default_factory=dict)

@dataclass
class ExtractionReport:
    doc_id: str
    field_confidences: Dict[str, float] = field(default_factory=dict)
    fields_from_rules: List[str] = field(default_factory=list)
    fields_from_nlp: List[str] = field(default_factory=list)
    fields_from_llm: List[str] = field(default_factory=list)
    fields_missing: List[str] = field(default_factory=list)
    llm_called: bool = False
    total_duration_ms: int = 0
