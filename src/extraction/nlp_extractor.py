import re
from typing import List, Optional, Set
from src.ingestion.models import ParsedDocument
from src.extraction.models import PartialMetadata


class NLPExtractor:
    def __init__(self):
        # Bug fixed: removed "c", "r", "go" — single-letter or common-English matches are too noisy.
        # Added "golang", "c++", "c#" with boundary-aware matching.
        self.skills_list = [
            # Languages
            "python", "java", "c++", "c#", "javascript", "typescript", "ruby", "php",
            "golang", "rust", "swift", "kotlin", "scala", "matlab",
            "sql", "html", "css", "bash", "shell",
            # Frameworks / Libraries
            "react", "angular", "vue", "node", "nodejs", "express", "django", "flask",
            "fastapi", "spring", "spring boot", "hibernate", "rails",
            "tensorflow", "pytorch", "keras", "pandas", "numpy", "scikit-learn",
            "opencv", "nltk", "spacy", "langchain",
            # Databases
            "mysql", "postgresql", "mongodb", "redis", "sqlite", "oracle",
            "cassandra", "dynamodb", "elasticsearch",
            # DevOps / Cloud
            "docker", "kubernetes", "aws", "azure", "gcp", "google cloud",
            "git", "github", "jenkins", "ansible", "terraform", "ci/cd", "linux",
            # Domains
            "machine learning", "deep learning", "artificial intelligence",
            "nlp", "computer vision", "data science", "data analytics",
            "web development", "mobile development", "android", "ios",
            "devops", "cloud computing", "cybersecurity",
            "data structures", "algorithms", "system design", "oop",
        ]

        # Canonical branch codes — expanded with IIT-specific programmes
        self.branch_mappings = {
            "computer science": "CSE",
            "cse": "CSE",
            "information technology": "IT",
            "electronics and communication": "ECE",
            "electronics": "ECE",
            "ece": "ECE",
            "electrical engineering": "EE",
            "electrical": "EE",
            "ee": "EE",
            "eee": "EE",
            "mechanical engineering": "ME",
            "mechanical": "ME",
            "me": "ME",
            "civil engineering": "CE",
            "civil": "CE",
            "ce": "CE",
            "chemical engineering": "CH",
            "chemical": "CH",
            "ch": "CH",
            "materials": "MT",
            "metallurgy": "MT",
            "mt": "MT",
            "mathematics and computing": "MnC",
            "maths and computing": "MnC",
            "mnc": "MnC",
            "mathematics": "MA",
            "physics": "PH",
            "engineering physics": "PH",
            "all branches": "ALL",
            "all departments": "ALL",
        }

        self.locations_list = [
            "bangalore", "bengaluru", "hyderabad", "pune", "mumbai", "chennai",
            "noida", "gurgaon", "gurugram", "delhi", "new delhi", "kolkata",
            "ahmedabad", "bhopal", "remote", "pan-india", "pan india",
        ]

        self.experience_patterns = [
            re.compile(r'\b([0-9]+\+?(?:\s*-\s*[0-9]+)?)\s*years?\s*(?:of\s+)?(?:relevant\s+)?experience\b', re.IGNORECASE),
            re.compile(r'\b([0-9]+\+?)\s*years?\b', re.IGNORECASE),
            re.compile(r'\b(?:freshers?)\b', re.IGNORECASE),
        ]

    def extract(self, doc: ParsedDocument, partial: PartialMetadata) -> PartialMetadata:
        text = doc.full_text
        text_lower = text.lower()

        extracted_skills = self._extract_skills(text_lower)
        if extracted_skills:
            merged = set(partial.required_skills) | set(extracted_skills)
            partial.required_skills = sorted(merged)
            partial.confidences['required_skills'] = 0.80

        extracted_branches = self._extract_branches(text_lower)
        if extracted_branches:
            merged = set(partial.eligible_branches) | set(extracted_branches)
            partial.eligible_branches = sorted(merged)
            partial.confidences['eligible_branches'] = 0.80

        extracted_locations = self._extract_locations(text_lower)
        if extracted_locations:
            merged = set(partial.location) | set(extracted_locations)
            partial.location = sorted(merged)
            partial.confidences['location'] = 0.80

        experience_str = self._extract_experience(text)
        if experience_str:
            partial.experience_required = experience_str
            partial.confidences['experience_required'] = 0.75

        return partial

    # ── Private helpers ────────────────────────────────────────────────────────

    def _extract_skills(self, text_lower: str) -> List[str]:
        found = []
        for skill in self.skills_list:
            escaped = re.escape(skill)
            # Special chars like c++ / c# need non-alphanum boundaries
            if skill in ("c++", "c#"):
                pat = rf'(?<![a-zA-Z0-9_]){escaped}(?![a-zA-Z0-9_])'
            else:
                pat = rf'\b{escaped}\b'
            if re.search(pat, text_lower):
                found.append(skill)
        return found

    def _extract_branches(self, text_lower: str) -> List[str]:
        found: Set[str] = set()
        for phrase, code in self.branch_mappings.items():
            if re.search(rf'\b{re.escape(phrase)}\b', text_lower):
                found.add(code)
        return list(found)

    def _extract_locations(self, text_lower: str) -> List[str]:
        found: Set[str] = set()
        canonical_map = {
            "bengaluru": "Bangalore",
            "gurugram":  "Gurgaon",
            "new delhi": "Delhi",
            "pan india": "Pan-India",
            "pan-india": "Pan-India",
            "remote":    "Remote",
        }
        for loc in self.locations_list:
            if re.search(rf'\b{re.escape(loc)}\b', text_lower):
                canon = canonical_map.get(loc, loc.title())
                found.add(canon)
        return list(found)

    def _extract_experience(self, text: str) -> Optional[str]:
        for pattern in self.experience_patterns:
            m = pattern.search(text)
            if m:
                raw = m.group(0).strip()
                if "fresher" in raw.lower():
                    return "Freshers eligible"
                return raw
        return None
