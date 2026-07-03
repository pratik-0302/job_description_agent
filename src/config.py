import yaml
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class PathsConfig:
    jd_files:  str = "jd_files"
    chroma_db: str = "data/chroma"
    sqlite_db: str = "data/metadata.db"


@dataclass
class EmbeddingConfig:
    model:       str = "BAAI/bge-small-en-v1.5"
    batch_size:  int = 32
    instruction: str = "Represent this job description for retrieval: "


@dataclass
class ChunkingConfig:
    chunk_size:    int = 400
    chunk_overlap: int = 60


@dataclass
class LLMConfig:
    model:           str   = "llama3.2:latest"
    base_url:        str   = "http://localhost:11434"
    temperature:     float = 0.1
    timeout_seconds: int   = 120


@dataclass
class RetrievalConfig:
    top_k: int = 5


@dataclass
class APIConfig:
    host: str = "0.0.0.0"
    port: int = 8000


@dataclass
class AppConfig:
    paths:     PathsConfig     = field(default_factory=PathsConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chunking:  ChunkingConfig  = field(default_factory=ChunkingConfig)
    llm:       LLMConfig       = field(default_factory=LLMConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    api:       APIConfig       = field(default_factory=APIConfig)


def load_config(config_path: str = "config.yaml") -> AppConfig:
    path = Path(config_path)
    if not path.exists():
        return AppConfig()

    with open(path) as f:
        raw = yaml.safe_load(f)

    cfg = AppConfig()
    if "paths"     in raw: cfg.paths     = PathsConfig(**raw["paths"])
    if "embedding" in raw: cfg.embedding = EmbeddingConfig(**raw["embedding"])
    if "chunking"  in raw: cfg.chunking  = ChunkingConfig(**raw["chunking"])
    if "llm"       in raw: cfg.llm       = LLMConfig(**raw["llm"])
    if "retrieval" in raw: cfg.retrieval = RetrievalConfig(**raw["retrieval"])
    if "api"       in raw: cfg.api       = APIConfig(**raw["api"])
    return cfg
