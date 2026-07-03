import re
from typing import Optional
from src.ingestion.models import ParsedDocument
from src.extraction.models import PartialMetadata


class RuleBasedExtractor:
    def __init__(self):
        # ── Company / Role (IIT Delhi JD form labels) ─────────────────────────
        # IIT Delhi PDFs have fixed labels — no need to fall through to LLM for these.
        self.company_patterns = [
            re.compile(r'name\s+of\s+company\s*:\s*\n*\s*([^\n\r]{2,80})', re.IGNORECASE),
            re.compile(r'company\s+name\s*:\s*([^\n\r]{2,80})', re.IGNORECASE),
            re.compile(r'organisation\s+name\s*:\s*([^\n\r]{2,80})', re.IGNORECASE),
        ]
        self.role_patterns = [
            re.compile(r'job\s+title\s*:\s*\n*\s*([^\n\r]{2,80})', re.IGNORECASE),
            re.compile(r'designation\s*:\s*\n*\s*([^\n\r]{2,80})', re.IGNORECASE),
            re.compile(r'role\s*:\s*\n*\s*([^\n\r]{2,80})', re.IGNORECASE),
        ]

        # ── CGPA ──────────────────────────────────────────────────────────────
        # Bug fixed: was [0-9] (single digit) — couldn't match 10.0
        self.cgpa_patterns = [
            re.compile(r'cgpa\s*(?:cutoff|criteria|min|minimum|of|required)?\s*(?:>=?|of|is|:|=>|=)?\s*([0-9]+(?:\.[0-9]+)?)\b', re.IGNORECASE),
            re.compile(r'gpa\s*(?:cutoff|min|minimum)?\s*(?:>=?|of|is|:|=>|=)?\s*([0-9]+(?:\.[0-9]+)?)\b', re.IGNORECASE),
            re.compile(r'cut[\s-]*off\s*(?:of|:)?\s*([0-9]+(?:\.[0-9]+)?)\s*cgpa\b', re.IGNORECASE),
            re.compile(r'minimum\s+(?:cgpa|gpa)\s*(?:of|:)?\s*([0-9]+(?:\.[0-9]+)?)', re.IGNORECASE),
        ]

        # ── CTC / Package ─────────────────────────────────────────────────────
        self.package_patterns = [
            re.compile(r'\b([0-9]+(?:\.[0-9]+)?)\s*(?:lpa|lakhs?|l\.p\.a\.?|per\s*annum)\b', re.IGNORECASE),
            re.compile(r'\bctc\s*(?:of|is|:)?\s*(?:rs\.?|inr|₹)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:lpa|lakhs?)\b', re.IGNORECASE),
            re.compile(r'\bpackage\s*(?:of|:)?\s*(?:rs\.?|inr|₹)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:lpa|lakhs?)\b', re.IGNORECASE),
        ]

        # ── Stipend ───────────────────────────────────────────────────────────
        # Bug fixed: patterns now handle comma-formatted numbers ("75,000")
        # and k-suffix ("50k"). k-suffix patterns are flagged via group 2 presence.
        self.stipend_patterns = [
            # "Stipend: ₹75,000 INR Per Month" / "stipend is 75000"
            re.compile(r'stipend\s*(?:\([^)]*\))?\s*(?:is|of|:)?\s*[=—\-]?\s*(?:rs\.?|inr|₹)?\s*[=—\-]?\s*([0-9][0-9,]{2,8})\b', re.IGNORECASE),
            # "75,000 Per Month" / "75000 per month"
            re.compile(r'\b([0-9][0-9,]{2,8})\s*(?:inr\s*)?(?:per\s*month|/\s*month|p\.?m\.?)\b', re.IGNORECASE),
            # "50k per month" / "stipend of 75k" — capture digit part then multiply ×1000
            re.compile(r'stipend\s*(?:of|:)?\s*(?:rs\.?|inr|₹)?\s*([0-9]{2,3})\s*k\b', re.IGNORECASE),
            re.compile(r'\b([0-9]{2,3})\s*k\s*(?:per\s*month|stipend|pm)\b', re.IGNORECASE),
        ]
        # Indices 2 and 3 above are k-suffix patterns (value must be ×1000)
        self._stipend_k_suffix_indices = {2, 3}

        # ── Duration ─────────────────────────────────────────────────────────
        # Bug fixed: was [1-9] — only 1-digit months; now handles 1-12
        self.duration_patterns = [
            re.compile(r'\b(1[0-2]|[1-9])\s*[-\s]?months?\b', re.IGNORECASE),
            re.compile(r'(?:internship|duration|period)\s*(?:of|for)?\s*(1[0-2]|[1-9])\s*months?\b', re.IGNORECASE),
        ]

        # ── Application deadline ──────────────────────────────────────────────
        self.deadline_patterns = [
            re.compile(r'(?:deadline|last\s+date)\s*(?:to\s*apply|for\s*application)?\s*(?:is|on|by|:)?\s*([0-9]{1,2}(?:st|nd|rd|th)?\s+[a-zA-Z]+\s+[0-9]{4})', re.IGNORECASE),
            re.compile(r'apply\s*before\s*([0-9]{1,2}(?:st|nd|rd|th)?\s+[a-zA-Z]+\s+[0-9]{4})', re.IGNORECASE),
            re.compile(r'(?:deadline|last\s+date)\s*:\s*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4})', re.IGNORECASE),
            re.compile(r'applications?\s*(?:close|due)\s*(?:on|by)?\s*([0-9]{1,2}(?:st|nd|rd|th)?\s+[a-zA-Z]+\s+[0-9]{4})', re.IGNORECASE),
        ]

    def extract(self, doc: ParsedDocument) -> PartialMetadata:
        partial = PartialMetadata()
        text = doc.full_text

        company = self._extract_company(text)
        if company:
            partial.company_name = company
            partial.confidences['company_name'] = 0.88

        role = self._extract_role(text)
        if role:
            partial.role_title = role
            partial.confidences['role_title'] = 0.88

        cgpa_val = self._extract_cgpa(text)
        if cgpa_val is not None:
            partial.cgpa_cutoff = cgpa_val
            partial.confidences['cgpa_cutoff'] = 0.90

        package_val = self._extract_package(text)
        if package_val is not None:
            partial.package_ctc = package_val
            partial.confidences['package_ctc'] = 0.90

        stipend_val = self._extract_stipend(text)
        if stipend_val is not None:
            partial.stipend_monthly = stipend_val
            partial.confidences['stipend_monthly'] = 0.88

        duration_val = self._extract_duration(text)
        if duration_val is not None:
            partial.duration_months = duration_val
            partial.confidences['duration_months'] = 0.88

        # Bug fixed: PPO checked BEFORE internship so a PPO JD isn't misclassified as internship
        job_type = self._extract_job_type(text)
        if job_type:
            partial.job_type = job_type
            partial.confidences['job_type'] = 0.90

        work_mode = self._extract_work_mode(text)
        if work_mode:
            partial.work_mode = work_mode
            partial.confidences['work_mode'] = 0.88

        deadline_str = self._extract_deadline(text)
        if deadline_str:
            partial.deadline = deadline_str
            partial.confidences['deadline'] = 0.85

        return partial

    # ── Private helpers ────────────────────────────────────────────────────────

    def _extract_cgpa(self, text: str) -> Optional[float]:
        for pattern in self.cgpa_patterns:
            for match in pattern.findall(text):
                try:
                    val = float(match)
                    if 4.0 <= val <= 10.0:
                        return val
                except ValueError:
                    continue
        return None

    def _extract_package(self, text: str) -> Optional[float]:
        for pattern in self.package_patterns:
            for match in pattern.findall(text):
                try:
                    val = float(match)
                    if 1.0 <= val <= 200.0:
                        return val
                except ValueError:
                    continue
        return None

    def _extract_stipend(self, text: str) -> Optional[float]:
        for i, pattern in enumerate(self.stipend_patterns):
            for match in pattern.findall(text):
                try:
                    # Remove commas from numbers like "75,000" or "1,50,000"
                    cleaned = str(match).replace(",", "").strip()
                    val = float(cleaned)
                    # k-suffix patterns capture digits only — multiply by 1000
                    if i in self._stipend_k_suffix_indices:
                        val *= 1000.0
                    if 1_000.0 <= val <= 300_000.0:
                        return val
                except (ValueError, TypeError):
                    continue
        return None

    def _extract_duration(self, text: str) -> Optional[int]:
        for pattern in self.duration_patterns:
            for match in pattern.findall(text):
                try:
                    val = int(match)
                    if 1 <= val <= 12:
                        return val
                except ValueError:
                    continue
        return None

    def _extract_job_type(self, text: str) -> Optional[str]:
        t = text.lower()
        # Bug fixed: substring "in" checks caused false matches:
        #   "ppo" in "opportunity"  → every JD with "opportunity" was PPO
        #   "fte" in "often"        → JDs with "often" were classified FTE
        # Now using word-boundary regex for all terms.
        if re.search(r'\bppo\b', t) or re.search(r'\bpre-placement offer\b', t) or re.search(r'\bpre placement offer\b', t):
            return "ppo"
        if re.search(r'\bfte\b', t) or re.search(r'\bfull[- ]time\b', t):
            return "fte"
        if re.search(r'\binternships?\b', t) or re.search(r'\binterns?\b', t):
            return "internship"
        if re.search(r'\bcontract\b', t):
            return "contract"
        return None

    def _extract_work_mode(self, text: str) -> Optional[str]:
        t = text.lower()
        if "remote" in t or "work from home" in t or "wfh" in t:
            return "remote"
        if "hybrid" in t:
            return "hybrid"
        if "on-site" in t or "onsite" in t or "in office" in t or "in-office" in t:
            return "onsite"
        return None

    def _extract_deadline(self, text: str) -> Optional[str]:
        for pattern in self.deadline_patterns:
            m = pattern.search(text)
            if m:
                return m.group(1).strip()
        return None

    def _extract_company(self, text: str) -> Optional[str]:
        for pattern in self.company_patterns:
            m = pattern.search(text)
            if m:
                # Strip roll-number watermarks (e.g. "2023EE10264") that OCR interleaves
                val = re.sub(r'\b20\d{2}[A-Z]{2}\d{5}\b', '', m.group(1)).strip()
                val = val.strip(":.,-")
                if len(val) >= 2:
                    return val
        return None

    def _extract_role(self, text: str) -> Optional[str]:
        for pattern in self.role_patterns:
            m = pattern.search(text)
            if m:
                val = re.sub(r'\b20\d{2}[A-Z]{2}\d{5}\b', '', m.group(1)).strip()
                val = val.strip(":.,-")
                if len(val) >= 2:
                    return val
        return None
