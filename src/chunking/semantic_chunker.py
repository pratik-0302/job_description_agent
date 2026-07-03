import re
import uuid
from typing import List, Optional
from src.ingestion.models import ParsedDocument
from src.config import AppConfig


class TextChunk:
    def __init__(
        self,
        chunk_id: str,
        doc_id: str,
        chunk_index: int,
        chunk_type: str,   # "text" | "table"
        content: str,
        token_count: int,
        section_heading: Optional[str] = None,
        page_number: Optional[int] = None,
        company_name: Optional[str] = None,
        role_title: Optional[str] = None,
        job_type: Optional[str] = None,
    ):
        self.chunk_id       = chunk_id
        self.doc_id         = doc_id
        self.chunk_index    = chunk_index
        self.chunk_type     = chunk_type
        self.content        = content
        self.token_count    = token_count
        self.section_heading = section_heading
        self.page_number    = page_number
        self.company_name   = company_name
        self.role_title     = role_title
        self.job_type       = job_type

    def to_dict(self) -> dict:
        return {
            "chunk_id":       self.chunk_id,
            "doc_id":         self.doc_id,
            "chunk_index":    self.chunk_index,
            "chunk_type":     self.chunk_type,
            "content":        self.content,
            "token_count":    self.token_count,
            "section_heading": self.section_heading,
            "page_number":    self.page_number,
            "company_name":   self.company_name,
            "role_title":     self.role_title,
            "job_type":       self.job_type,
        }


class TokenEstimator:
    @staticmethod
    def estimate(text: str) -> int:
        if not text:
            return 0
        return int(len(text.split()) * 1.3)


class SemanticChunkerModule:
    def __init__(self, cfg: AppConfig):
        self.chunk_size    = cfg.chunking.chunk_size    # e.g. 400 tokens
        self.chunk_overlap = cfg.chunking.chunk_overlap  # e.g. 60 tokens

    # ── Public API ─────────────────────────────────────────────────────────────

    def chunk_document(self, doc: ParsedDocument, metadata: Optional[dict] = None) -> List[TextChunk]:
        chunks: List[TextChunk] = []
        chunk_index = 0

        company = (metadata or {}).get("company_name")
        role    = (metadata or {}).get("role_title")
        j_type  = (metadata or {}).get("job_type")

        # ── 1. Section-based chunking ──────────────────────────────────────────
        for section in doc.sections:
            content = section.content
            if not content.strip():
                continue

            heading       = section.heading_text
            heading_prefix = f"Section: {heading}\n\n" if heading else ""
            heading_tokens = TokenEstimator.estimate(heading_prefix)

            paragraphs = [p.strip() for p in re.split(r'\n\n|\n', content) if p.strip()]

            current_parts: List[str] = []
            current_tokens = heading_tokens
            overlap_buf: List[str] = []

            def _emit(parts: List[str]) -> TextChunk:
                nonlocal chunk_index
                text = heading_prefix + "\n\n".join(parts)
                c = TextChunk(
                    chunk_id=str(uuid.uuid4()),
                    doc_id=doc.doc_id,
                    chunk_index=chunk_index,
                    chunk_type="text",
                    content=text,
                    token_count=TokenEstimator.estimate(text),
                    section_heading=heading,
                    page_number=section.start_page,
                    company_name=company,
                    role_title=role,
                    job_type=j_type,
                )
                chunk_index += 1
                return c

            for para in paragraphs:
                para_tokens = TokenEstimator.estimate(para)

                if para_tokens > self.chunk_size:
                    # Paragraph too large — split by sentence
                    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', para) if s.strip()]
                    for sent in sentences:
                        sent_tokens = TokenEstimator.estimate(sent)
                        if current_tokens + sent_tokens > self.chunk_size:
                            if current_parts:
                                chunks.append(_emit(current_parts))
                                overlap_buf = current_parts[-2:] if len(current_parts) >= 2 else current_parts[:]
                            current_parts = list(overlap_buf) + [sent]
                            current_tokens = heading_tokens + TokenEstimator.estimate(" ".join(current_parts))
                        else:
                            current_parts.append(sent)
                            current_tokens += sent_tokens
                else:
                    if current_tokens + para_tokens > self.chunk_size:
                        if current_parts:
                            chunks.append(_emit(current_parts))
                            overlap_buf = current_parts[-1:] if current_parts else []
                        current_parts = list(overlap_buf) + [para]
                        current_tokens = heading_tokens + TokenEstimator.estimate("\n\n".join(current_parts))
                    else:
                        current_parts.append(para)
                        current_tokens += para_tokens

            if current_parts:
                chunks.append(_emit(current_parts))

        # ── 2. Table chunks ────────────────────────────────────────────────────
        for table in doc.tables:
            raw = table.raw_text
            if not raw.strip():
                continue

            table_tokens = TokenEstimator.estimate(raw)
            max_table = self.chunk_size * 2
            if table_tokens > max_table:
                rows = raw.split('\n')
                kept, acc = [], 0
                for row in rows:
                    rt = TokenEstimator.estimate(row)
                    if acc + rt > max_table:
                        break
                    kept.append(row)
                    acc += rt
                raw = "\n".join(kept) + "\n[table truncated]"
                table_tokens = TokenEstimator.estimate(raw)

            chunks.append(TextChunk(
                chunk_id=str(uuid.uuid4()),
                doc_id=doc.doc_id,
                chunk_index=chunk_index,
                chunk_type="table",
                content=raw,
                token_count=table_tokens,
                section_heading="Table",
                page_number=table.source_page,
                company_name=company,
                role_title=role,
                job_type=j_type,
            ))
            chunk_index += 1

        # ── 3. Fallback: chunk full_text when no sections were extracted ────────
        # Happens with heavily OCR'd docs that produce no section boundaries.
        if not chunks and doc.full_text.strip():
            chunks = self._chunk_plain_text(
                doc.full_text, doc.doc_id, company, role, j_type, start_index=0
            )

        return chunks

    # ── Private ────────────────────────────────────────────────────────────────

    def _chunk_plain_text(
        self,
        text: str,
        doc_id: str,
        company: Optional[str],
        role: Optional[str],
        j_type: Optional[str],
        start_index: int = 0,
    ) -> List[TextChunk]:
        chunks: List[TextChunk] = []
        idx = start_index
        paragraphs = [p.strip() for p in re.split(r'\n\n+', text) if p.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]

        current_parts: List[str] = []
        current_tokens = 0
        overlap_buf: List[str] = []

        def _emit_plain(parts: List[str]) -> TextChunk:
            nonlocal idx
            content = "\n\n".join(parts)
            c = TextChunk(
                chunk_id=str(uuid.uuid4()),
                doc_id=doc_id,
                chunk_index=idx,
                chunk_type="text",
                content=content,
                token_count=TokenEstimator.estimate(content),
                section_heading=None,
                page_number=None,
                company_name=company,
                role_title=role,
                job_type=j_type,
            )
            idx += 1
            return c

        for para in paragraphs:
            pt = TokenEstimator.estimate(para)
            if current_tokens + pt > self.chunk_size:
                if current_parts:
                    chunks.append(_emit_plain(current_parts))
                    overlap_buf = current_parts[-1:]
                current_parts = list(overlap_buf) + [para]
                current_tokens = TokenEstimator.estimate("\n\n".join(current_parts))
            else:
                current_parts.append(para)
                current_tokens += pt

        if current_parts:
            chunks.append(_emit_plain(current_parts))

        return chunks
