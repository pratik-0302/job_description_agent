import re


class IntentDetector:
    # Bug fixed: removed overly broad followup terms ("it", "their", "that", "them") that matched
    # normal English in first-turn questions, causing every other query to be misclassified as followup.
    _FOLLOWUP_PATTERNS = [
        re.compile(r'\bthis company\b', re.IGNORECASE),
        re.compile(r'\bthat company\b', re.IGNORECASE),
        re.compile(r'\bthat role\b',    re.IGNORECASE),
        re.compile(r'\bprevious(?:ly)?\b', re.IGNORECASE),
        re.compile(r'\bmentioned (?:above|earlier|company|role)\b', re.IGNORECASE),
        re.compile(r'\bsame company\b', re.IGNORECASE),
    ]

    _COMPARE_KW   = ["compare", " vs ", "versus", "difference between", "which is better", "contrast"]
    _ANALYTICS_KW = [
        "how many", "average", "percentage", "distribution", "trend",
        "highest", "lowest", "statistics", "stats", "count", "total",
        "salary of", "median",
    ]
    _RECOMMEND_KW = [
        "recommend", "suggest", "best for me", "suitable", "eligible",
        "eligibility", "which job", "where should i apply", "matching my profile",
        "what should i apply",
    ]
    _SUMMARY_KW   = ["summarize", "summary", "overview", "tell me about", "brief", "details of"]

    @staticmethod
    def detect_intent(query_text: str) -> str:
        if not query_text:
            return "search"

        q = query_text.lower().strip()

        # Followup — only explicit back-references, not loose pronouns
        for pat in IntentDetector._FOLLOWUP_PATTERNS:
            if pat.search(q):
                return "followup"

        for kw in IntentDetector._COMPARE_KW:
            if kw in q:
                return "compare"

        for kw in IntentDetector._ANALYTICS_KW:
            if kw in q:
                return "analytics"

        for kw in IntentDetector._RECOMMEND_KW:
            if kw in q:
                return "recommend"

        for kw in IntentDetector._SUMMARY_KW:
            if kw in q:
                return "summary"

        return "search"
