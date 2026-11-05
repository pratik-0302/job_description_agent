# Job Description Agent

An AI-powered placement intelligence system that helps students explore, search, compare, and understand job descriptions using structured metadata, semantic retrieval, and a locally hosted language model.

## Overview

Job descriptions often contain important information scattered across long documents: eligibility criteria, required skills, role responsibilities, locations, compensation, and experience requirements. This project organizes those documents into a searchable knowledge base and provides a natural-language interface for asking questions about them.

The application combines:

- **Document ingestion** to discover and parse PDF/DOCX job descriptions.
- **Metadata extraction** to identify structured fields such as company, role, location, skills, branch eligibility, CGPA, salary, and experience.
- **Semantic chunking and embeddings** to represent relevant sections of each document as vectors.
- **SQLite** for structured metadata and **ChromaDB** for vector storage.
- **Hybrid retrieval** to combine exact structured filtering with semantic similarity search.
- **Reciprocal Rank Fusion (RRF)** to merge rankings from different retrieval methods.
- **LangGraph** to coordinate multi-step query workflows.
- **Ollama** to run the language model locally.
- **FastAPI** to expose backend functionality to a frontend.

## Key Features

- Ingest job descriptions from PDF and DOCX files.
- Extract useful metadata using a layered extraction approach (rules, NLP, and LLM-based extraction).
- Split long documents into smaller, overlapping chunks for better retrieval.
- Generate embeddings using `BAAI/bge-small-en-v1.5`.
- Store document metadata in SQLite and embeddings/chunks in ChromaDB.
- Retrieve information using both structured and semantic search.
- Fuse retrieval rankings using Reciprocal Rank Fusion.
- Support natural-language workflows such as searching, comparing, recommending, and analytics, depending on the configured workflow.
- Generate responses with a locally served Llama model through Ollama.
- Serve the application through a FastAPI backend.

## Architecture

```text
                  JOB DESCRIPTION FILES
                       PDF / DOCX
                           |
                           v
                   Document Discovery
                           |
                           v
                    Document Parser
                           |
              +------------+-------------+
              |                          |
              v                          v
       Metadata Extraction         Raw Document Text
       Rules -> NLP -> LLM                |
              |                          v
              v                    Semantic Chunking
        SQLite Storage                    |
                                         v
                                  BGE Embeddings
                                         |
                                         v
                                     ChromaDB


 User Query
     |
     v
 FastAPI
     |
     v
 Intent / Entity Processing
     |
     v
 Hybrid Retrieval
   /          \
  v            v
SQLite      ChromaDB
  \            /
   v          v
    Reciprocal Rank Fusion
             |
             v
       LangGraph Workflow
             |
             v
       Prompt Construction
             |
             v
       Ollama (Local LLM)
             |
             v
        Final Response
```

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Language | Python | Backend and AI pipeline |
| API | FastAPI | HTTP interface |
| Workflow orchestration | LangGraph | Stateful, multi-step query workflow |
| LLM runtime | Ollama | Local language-model inference |
| LLM | Llama 3.2 | Natural-language response generation |
| Embeddings | BAAI/bge-small-en-v1.5 | Semantic vector representations |
| Vector database | ChromaDB | Storage and similarity search for document chunks |
| Structured database | SQLite | Job-description metadata |
| Configuration | YAML | Application configuration |

## Project Structure

The following is a guide to the main modules:

```text
src/
├── agents/
│   └── agent_graph.py          # LangGraph workflow orchestration
├── api/
│   └── app.py                  # FastAPI application
├── chunking/
│   └── semantic_chunker.py     # Document chunking
├── embedding/
│   └── embedding_pipeline.py   # Embedding generation
├── extraction/
│   ├── llm_extractor.py        # LLM-based metadata extraction
│   ├── metadata_extractor.py   # Extraction orchestration
│   ├── models.py               # Metadata data models
│   ├── nlp_extractor.py        # NLP-based extraction
│   └── rule_extractor.py       # Rule/regex-based extraction
├── ingestion/
│   ├── automatic_indexer.py    # End-to-end indexing pipeline
│   ├── discovery.py            # Input document discovery
│   ├── models.py               # Ingestion data models
│   └── parser.py               # PDF/DOCX text extraction
├── llm/
│   ├── ollama_client.py        # Ollama communication
│   └── prompt_builder.py       # Prompt construction
├── retrieval/
│   ├── hybrid_retriever.py     # Structured + semantic retrieval
│   ├── intent_detector.py      # Query intent detection
│   ├── query_cache.py          # Query-result caching
│   └── result_fusion.py        # Retrieval rank fusion
├── storage/
│   └── sqlite_manager.py       # SQLite operations
└── vector_db/
    └── chroma_manager.py       # ChromaDB operations
```

## How It Works

### 1. Document ingestion

The ingestion pipeline discovers supported job-description files and extracts their text. A content hash can be used to identify duplicate files independently of their filenames.

### 2. Metadata extraction

The extracted text is analyzed to populate structured fields. The extraction design uses a cascade:

1. **Rule-based extraction** for predictable patterns such as CGPA, salary, and experience.
2. **NLP-based extraction** for entities and linguistic patterns.
3. **LLM-based extraction** for information that is difficult to capture with fixed rules.

Extracted values should be validated before being stored.

### 3. Chunking and embeddings

Long documents are divided into smaller chunks so retrieval can focus on relevant sections rather than entire files. The configured embedding model converts each chunk into a dense vector.

### 4. Storage

- **SQLite** stores structured job-description metadata.
- **ChromaDB** stores document chunks, embeddings, and associated metadata.

### 5. Hybrid retrieval

Structured retrieval is useful for exact constraints (for example, branch or CGPA eligibility). Semantic retrieval is useful for meaning-based questions (for example, finding roles that involve backend development). The two result lists can be combined using Reciprocal Rank Fusion:

```text
RRF(d) = sum over rankings r of 1 / (k + rank_r(d))
```

### 6. Agent workflow and response generation

The LangGraph workflow coordinates the query-processing steps. The application detects the user's intent, retrieves relevant information, prepares context, and calls the local LLM through Ollama to generate a response grounded in the retrieved documents.

## Configuration

The application uses a YAML configuration file. The configuration discussed during development includes settings similar to:

```yaml
paths:
  jd_files: "jd_files"
  chroma_db: "data/chroma"
  sqlite_db: "data/metadata.db"

embedding:
  model: "BAAI/bge-small-en-v1.5"
  batch_size: 32
  instruction: "Represent this job description for retrieval: "

chunking:
  chunk_size: 400
  chunk_overlap: 60

llm:
  model: "llama3.2:latest"
  base_url: "http://localhost:11434"
  temperature: 0.1
  timeout_seconds: 120

retrieval:
  top_k: 5

api:
  host: "0.0.0.0"
  port: 8000

logging:
  level: "INFO"
```

Adjust paths and settings to match your local environment and the configuration file in the repository. Do not commit secrets or machine-specific credentials.

## Getting Started

### Prerequisites

- Python environment compatible with the project's dependencies.
- Ollama installed if you want to run the local LLM workflow.
- The required Python packages installed from the dependency file provided by the repository.
- Job-description documents in the configured input directory.

### 1. Clone the repository

```bash
git clone https://github.com/pratik-0302/job_description_agent.git
cd job_description_agent
```

### 2. Create and activate a virtual environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

If the repository contains a `requirements.txt` file:

```bash
pip install -r requirements.txt
```

If dependencies are managed through another file or package manager, follow that project's dependency configuration instead.

### 4. Set up Ollama

Install Ollama, then pull the configured model:

```bash
ollama pull llama3.2
```

Start the Ollama service:

```bash
ollama serve
```

Ollama normally serves its local API at `http://localhost:11434`. Ensure that this matches the configured `llm.base_url`.

### 5. Configure the application

Review the YAML configuration and update document, database, and vector-store paths for your environment. Add your job-description PDF/DOCX files to the configured input directory.

### 6. Start the API

If the repository provides `main.py` as the application entry point, start it using:

```bash
python main.py
```

Otherwise, use the entry point and command defined by the repository. If the FastAPI application is exposed as `src.api.app:app`, a typical development command is:

```bash
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

## Design Decisions

- **Structured + semantic search:** exact eligibility constraints and natural-language relevance are different retrieval problems, so the system uses both.
- **Rank fusion:** RRF combines ranked results without requiring SQL and vector similarity scores to share the same scale.
- **Local LLM inference:** Ollama allows the configured language model to run locally instead of requiring a hosted inference API.
- **Modular architecture:** ingestion, extraction, storage, retrieval, orchestration, and API responsibilities are separated into dedicated modules.
- **Layered extraction:** deterministic rules are applied before more flexible NLP/LLM methods where appropriate.

## Limitations and Future Improvements

Potential areas for further development include:

- Improve parsing of tables, multi-column PDFs, and scanned documents using OCR.
- Add stronger validation and confidence scores for extracted eligibility fields.
- Evaluate retrieval quality with a labeled set of placement queries.
- Add automated tests for ingestion, extraction, retrieval, and agent workflows.
- Add observability for retrieval results, LLM latency, and failure cases.
- Add authentication and deployment configuration if the application is exposed beyond a local development environment.

## Contributing

Contributions and suggestions are welcome. For changes, consider opening an issue describing the proposed improvement before submitting a pull request.

## License

No license is specified here. Add a license file if you intend to define permissions for reuse and distribution.
