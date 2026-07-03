"""
AI Placement Intelligence Agent — Entry Point

Usage:
    python main.py              # start the FastAPI backend
    streamlit run frontend.py   # start the Streamlit UI (separate terminal)
"""

import uvicorn
from src.config import load_config

if __name__ == "__main__":
    cfg = load_config("config.yaml")
    print(f"Starting API on http://{cfg.api.host}:{cfg.api.port}")
    uvicorn.run("src.api.app:app", host=cfg.api.host, port=cfg.api.port, reload=True)
