import os
import uuid
import datetime
import json
from typing import List, Optional
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine, Column, String, Integer, Float, ForeignKey, Text, event, func
# pyrefly: ignore [missing-import]
from sqlalchemy.engine import Engine
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

Base = declarative_base()

class Document(Base):
    __tablename__ = 'documents'

    doc_id = Column(String(36), primary_key=True)
    file_path = Column(Text, unique=True, nullable=False)
    file_name = Column(String(255), nullable=False)
    file_extension = Column(String(10), nullable=False)
    file_size_bytes = Column(Integer)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    discovered_at = Column(String(50), nullable=False) # ISO-8601 string
    indexed_at = Column(String(50), nullable=True) # ISO-8601 string
    status = Column(String(20), nullable=False, default='pending', index=True)
    failure_reason = Column(Text, nullable=True)

    metadata_rel = relationship("JDMetadata", back_populates="document", uselist=False, cascade="all, delete-orphan")
    skills = relationship("JDSkill", back_populates="document", cascade="all, delete-orphan")
    locations = relationship("JDLocation", back_populates="document", cascade="all, delete-orphan")
    branches = relationship("JDBranch", back_populates="document", cascade="all, delete-orphan")
    selection_rounds = relationship("JDSelectionRound", back_populates="document", cascade="all, delete-orphan")

class JDMetadata(Base):
    __tablename__ = 'jd_metadata'

    metadata_id = Column(String(36), primary_key=True)
    doc_id = Column(String(36), ForeignKey('documents.doc_id', ondelete='CASCADE'), unique=True, nullable=False)
    company_name = Column(String(255), index=True)
    role_title = Column(String(255))
    job_type = Column(String(20)) # e.g. internship, fte, ppo, contract
    package_ctc = Column(Float, index=True)
    stipend_monthly = Column(Float)
    cgpa_cutoff = Column(Float, index=True)
    experience_required = Column(String(100))
    deadline = Column(String(50), index=True) # ISO-8601 string
    work_mode = Column(String(50))
    duration_months = Column(Integer)
    bond_clause = Column(Integer) # 0 or 1
    extraction_confidence = Column(Float)
    extracted_at = Column(String(50)) # ISO-8601 string

    document = relationship("Document", back_populates="metadata_rel")

class JDSkill(Base):
    __tablename__ = 'jd_skills'

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String(36), ForeignKey('documents.doc_id', ondelete='CASCADE'), nullable=False)
    skill = Column(String(100), nullable=False)
    skill_normalized = Column(String(100), nullable=False, index=True)

    document = relationship("Document", back_populates="skills")

class JDLocation(Base):
    __tablename__ = 'jd_locations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String(36), ForeignKey('documents.doc_id', ondelete='CASCADE'), nullable=False)
    location = Column(String(100), nullable=False)

    document = relationship("Document", back_populates="locations")

class JDBranch(Base):
    __tablename__ = 'jd_branches'

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String(36), ForeignKey('documents.doc_id', ondelete='CASCADE'), nullable=False)
    branch_code = Column(String(20), nullable=False, index=True) # e.g. CSE, ECE

    document = relationship("Document", back_populates="branches")

class JDSelectionRound(Base):
    __tablename__ = 'jd_selection_rounds'

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String(36), ForeignKey('documents.doc_id', ondelete='CASCADE'), nullable=False)
    round_order = Column(Integer, nullable=False)
    round_name = Column(String(100), nullable=False)

    document = relationship("Document", back_populates="selection_rounds")


class EmbeddingCache(Base):
    __tablename__ = 'embedding_cache'

    content_hash = Column(String(64), primary_key=True)
    model_name = Column(String(100), primary_key=True)
    embedding = Column(Text, nullable=False)  # JSON-encoded float list is safer and standard for cross-platform DB viewing
    cached_at = Column(String(50), nullable=False)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


class SQLiteManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        # Ensure directory exists
        db_dir = os.path.dirname(os.path.abspath(db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        self.engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def get_session(self):
        return self.SessionLocal()


class DocumentRepository:
    def __init__(self, session):
        self.session = session

    def insert_document(self, record_dict: dict) -> Document:
        doc = Document(
            doc_id=record_dict.get('doc_id') or str(uuid.uuid4()),
            file_path=record_dict['file_path'],
            file_name=record_dict['file_name'],
            file_extension=record_dict['file_extension'],
            file_size_bytes=record_dict.get('file_size_bytes'),
            content_hash=record_dict['content_hash'],
            discovered_at=record_dict.get('discovered_at') or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            status=record_dict.get('status', 'pending'),
            failure_reason=record_dict.get('failure_reason')
        )
        try:
            self.session.add(doc)
            self.session.commit()
            return doc
        except Exception:
            self.session.rollback()
            raise

    def update_document_status(self, doc_id: str, status: str, failure_reason: Optional[str] = None, indexed_at: Optional[str] = None):
        doc = self.session.query(Document).filter(Document.doc_id == doc_id).first()
        if doc:
            doc.status = status
            doc.failure_reason = failure_reason
            if indexed_at:
                doc.indexed_at = indexed_at
            elif status == 'indexed':
                doc.indexed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            try:
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
        return doc

    def get_document_by_path(self, file_path: str) -> Optional[Document]:
        return self.session.query(Document).filter(Document.file_path == file_path).first()

    def get_document_by_hash(self, content_hash: str) -> Optional[Document]:
        return self.session.query(Document).filter(Document.content_hash == content_hash).first()

    def list_documents(self, status_filter: Optional[str] = None) -> List[Document]:
        query = self.session.query(Document)
        if status_filter:
            query = query.filter(Document.status == status_filter)
        return query.all()

    def delete_document(self, doc_id: str):
        doc = self.session.query(Document).filter(Document.doc_id == doc_id).first()
        if doc:
            try:
                self.session.delete(doc)
                self.session.commit()
                return True
            except Exception:
                self.session.rollback()
                raise
        return False


class MetadataRepository:
    def __init__(self, session):
        self.session = session

    def insert_metadata(self, doc_id: str, data: dict) -> JDMetadata:
        # For idempotency, clear existing metadata and linked tables first
        self.delete_metadata(doc_id)

        meta = JDMetadata(
            metadata_id=str(uuid.uuid4()),
            doc_id=doc_id,
            company_name=data.get('company_name'),
            role_title=data.get('role_title'),
            job_type=data.get('job_type'),
            package_ctc=data.get('package_ctc'),
            stipend_monthly=data.get('stipend_monthly'),
            cgpa_cutoff=data.get('cgpa_cutoff'),
            experience_required=data.get('experience_required'),
            deadline=data.get('deadline'),
            work_mode=data.get('work_mode'),
            duration_months=data.get('duration_months'),
            bond_clause=(1 if data['bond_clause'] else 0) if data.get('bond_clause') is not None else None,
            extraction_confidence=data.get('extraction_confidence', 0.0),
            extracted_at=data.get('extracted_at') or datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        
        try:
            self.session.add(meta)
            
            # Insert skills
            for skill in data.get('required_skills', []):
                s_normalized = skill.strip().lower()
                if s_normalized:
                    s_row = JDSkill(doc_id=doc_id, skill=skill.strip(), skill_normalized=s_normalized)
                    self.session.add(s_row)
                    
            # Insert locations
            for loc in data.get('location', []):
                if loc.strip():
                    l_row = JDLocation(doc_id=doc_id, location=loc.strip())
                    self.session.add(l_row)
                    
            # Insert branches
            for br in data.get('eligible_branches', []):
                if br.strip():
                    b_row = JDBranch(doc_id=doc_id, branch_code=br.strip().upper())
                    self.session.add(b_row)
                    
            # Insert selection rounds
            for idx, rnd in enumerate(data.get('selection_process', []), start=1):
                if rnd.strip():
                    r_row = JDSelectionRound(doc_id=doc_id, round_order=idx, round_name=rnd.strip())
                    self.session.add(r_row)
                    
            self.session.commit()
            return meta
        except Exception:
            self.session.rollback()
            raise

    def get_metadata(self, doc_id: str) -> Optional[JDMetadata]:
        return self.session.query(JDMetadata).filter(JDMetadata.doc_id == doc_id).first()

    def delete_metadata(self, doc_id: str) -> bool:
        meta = self.get_metadata(doc_id)
        # Clear child tables directly as well to ensure clean deletes
        try:
            self.session.query(JDSkill).filter(JDSkill.doc_id == doc_id).delete()
            self.session.query(JDLocation).filter(JDLocation.doc_id == doc_id).delete()
            self.session.query(JDBranch).filter(JDBranch.doc_id == doc_id).delete()
            self.session.query(JDSelectionRound).filter(JDSelectionRound.doc_id == doc_id).delete()
            if meta:
                self.session.delete(meta)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise


class EmbeddingCacheRepository:
    def __init__(self, session):
        self.session = session

    def get_cached_embedding(self, content_hash: str, model_name: str) -> Optional[List[float]]:
        entry = self.session.query(EmbeddingCache).filter(
            EmbeddingCache.content_hash == content_hash,
            EmbeddingCache.model_name == model_name
        ).first()
        if entry:
            try:
                return json.loads(entry.embedding)
            except Exception:
                return None
        return None

    def cache_embedding(self, content_hash: str, model_name: str, embedding: List[float]):
        entry = EmbeddingCache(
            content_hash=content_hash,
            model_name=model_name,
            embedding=json.dumps(embedding),
            cached_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        try:
            self.session.merge(entry)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise


class QueryRepository:
    def __init__(self, session):
        self.session = session

    def filter_jobs(self, filters: dict) -> List[JDMetadata]:
        query = self.session.query(JDMetadata)
        
        if filters.get("skills"):
            query = query.join(JDSkill, JDMetadata.doc_id == JDSkill.doc_id)
            skills = [s.lower().strip() for s in filters["skills"]]
            query = query.filter(func.lower(JDSkill.skill_normalized).in_(skills))
            
        if filters.get("locations"):
            query = query.join(JDLocation, JDMetadata.doc_id == JDLocation.doc_id)
            locs = [l.lower().strip() for l in filters["locations"]]
            query = query.filter(func.lower(JDLocation.location).in_(locs))
            
        if filters.get("branches"):
            query = query.join(JDBranch, JDMetadata.doc_id == JDBranch.doc_id)
            branches = [b.lower().strip() for b in filters["branches"]]
            query = query.filter(func.lower(JDBranch.branch_code).in_(branches))
            
        if filters.get("company_name"):
            comp = filters["company_name"].lower().strip()
            query = query.filter(func.lower(JDMetadata.company_name) == comp)
            
        if filters.get("job_type"):
            j_type = filters["job_type"].lower().strip()
            query = query.filter(func.lower(JDMetadata.job_type) == j_type)
            
        if filters.get("min_package") is not None:
            query = query.filter(JDMetadata.package_ctc >= filters["min_package"])
            
        if filters.get("max_cgpa_cutoff") is not None:
            query = query.filter(JDMetadata.cgpa_cutoff <= filters["max_cgpa_cutoff"])
            
        if filters.get("work_mode"):
            mode = filters["work_mode"].lower().strip()
            query = query.filter(func.lower(JDMetadata.work_mode) == mode)
            
        results = query.all()
        seen = set()
        deduped = []
        for r in results:
            if r.doc_id not in seen:
                seen.add(r.doc_id)
                deduped.append(r)
        return deduped



