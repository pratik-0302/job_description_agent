import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

@dataclass
class DocumentRecord:
    doc_id: str
    file_path: str
    file_name: str
    file_extension: str
    file_size_bytes: int
    content_hash: str
    discovered_at: datetime.datetime
    last_modified_at: datetime.datetime
    status: str = "pending"
    indexed_at: Optional[datetime.datetime] = None
    failure_reason: Optional[str] = None

@dataclass
class PipelineEvent:
    event_id: str
    event_type: str  # "new", "modified", "deleted"
    doc_id: str
    file_path: str
    file_extension: str
    timestamp: datetime.datetime
    priority: int = 0

@dataclass
class TextBlock:
    text: str
    font_size: float
    is_bold: bool
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    block_type: str = "text"  # "text", "heading", "bullet"

@dataclass
class ParsedPage:
    page_number: int
    text: str
    text_blocks: List[TextBlock] = field(default_factory=list)
    has_tables: bool = False

@dataclass
class ParsedSection:
    section_id: str
    heading_text: Optional[str]
    heading_level: int  # 1-6, or 0 if no heading
    content: str
    start_page: Optional[int] = None

@dataclass
class ParsedTable:
    table_id: str
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    source_page: Optional[int] = None
    raw_text: str = ""

@dataclass
class ParsedDocument:
    doc_id: str
    file_path: str
    file_type: str  # "pdf" or "docx"
    full_text: str
    pages: List[ParsedPage] = field(default_factory=list)
    sections: List[ParsedSection] = field(default_factory=list)
    tables: List[ParsedTable] = field(default_factory=list)
    document_title: Optional[str] = None
    page_count: int = 0
    char_count: int = 0
    parsed_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    parser_version: str = "1.0"
