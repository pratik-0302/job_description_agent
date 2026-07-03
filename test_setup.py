"""
Run this script ONCE after installing requirements to verify every
dependency is working correctly before building the project.

Usage:
    python test_setup.py
"""

import sys

PASS = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"
HEAD = "\033[1m"
END  = "\033[0m"

results = []

def check(name, fn):
    try:
        detail = fn()
        print(f"{PASS} — {name}" + (f"  [{detail}]" if detail else ""))
        results.append(True)
    except Exception as e:
        print(f"{FAIL} — {name}  [{e}]")
        results.append(False)


print(f"\n{HEAD}=== AI Placement Intelligence Agent — Setup Check ==={END}\n")

# ── 1. Python version ─────────────────────────────────────────────────────────
check("Python 3.10+",
      lambda: f"Python {sys.version.split()[0]}" if sys.version_info >= (3, 10)
              else (_ for _ in ()).throw(RuntimeError("Need Python 3.10+")))

# ── 2. Core libraries ─────────────────────────────────────────────────────────
check("PyMuPDF (PDF parser)",
      lambda: __import__("fitz") and "OK")

check("python-docx (DOCX parser)",
      lambda: __import__("docx") and "OK")

check("ChromaDB (vector store)",
      lambda: __import__("chromadb") and "OK")

check("sentence-transformers (embeddings)",
      lambda: __import__("sentence_transformers") and "OK")

check("LangGraph (agent orchestration)",
      lambda: __import__("langgraph") and "OK")

check("langchain-ollama (LLM client)",
      lambda: __import__("langchain_ollama") and "OK")

check("FastAPI (backend)",
      lambda: __import__("fastapi") and "OK")

check("Streamlit (frontend)",
      lambda: __import__("streamlit") and "OK")

check("PyYAML (config files)",
      lambda: __import__("yaml") and "OK")

check("SQLAlchemy (database ORM)",
      lambda: __import__("sqlalchemy") and "OK")

check("Watchdog (file monitoring)",
      lambda: __import__("watchdog") and "OK")

# ── 3. Embedding model (downloads ~130 MB on first run) ───────────────────────
def test_embedding():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    vec = model.encode("software engineer python")
    assert len(vec) == 384
    return f"vector dim={len(vec)}"

check("Embedding model BAAI/bge-small-en-v1.5", test_embedding)

# ── 4. ChromaDB in-memory smoke test ─────────────────────────────────────────
def test_chromadb():
    import chromadb
    client = chromadb.Client()
    col = client.create_collection("test")
    col.add(documents=["test doc"], ids=["1"])
    res = col.query(query_texts=["test"], n_results=1)
    assert res["ids"][0][0] == "1"
    return "insert + query OK"

check("ChromaDB in-memory test", test_chromadb)

# ── 5. Config loader ──────────────────────────────────────────────────────────
def test_config():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
    from config import load_config
    cfg = load_config("config.yaml")
    assert cfg.llm.model == "qwen3:8b"
    return f"LLM={cfg.llm.model}"

check("Config loader (config.yaml)", test_config)

# ── 6. Ollama connectivity (optional — needs Ollama running) ──────────────────
def test_ollama():
    import urllib.request
    req = urllib.request.urlopen("http://localhost:11434", timeout=3)
    return "Ollama server reachable"

try:
    check("Ollama server (localhost:11434)", test_ollama)
except Exception:
    print(f"\033[93m SKIP\033[0m — Ollama (install from ollama.com and run: ollama pull qwen3:8b)")
    results.append(True)  # not a hard failure for setup

# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(results)
total  = len(results)
print(f"\n{HEAD}{'─'*50}{END}")
if passed == total:
    print(f"\033[92m{HEAD}All {total} checks passed. You are ready to build!{END}\033[0m")
else:
    failed = total - passed
    print(f"\033[91m{HEAD}{failed} check(s) failed. Fix them before proceeding.{END}\033[0m")
print()
