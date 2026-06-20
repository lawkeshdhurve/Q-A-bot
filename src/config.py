"""
config.py
Centralized configuration and constants for the Document Q&A Bot.
Keeping these values in one place makes the pipeline easy to tune
without hunting through ingest.py / query.py for magic numbers.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- API Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise EnvironmentError(
        "GEMINI_API_KEY not found. Create a .env file in the project root "
        "with the line: GEMINI_API_KEY=your_key_here"
    )

# --- Model Configuration ---
# NOTE: The assignment reference doc specifies gemini-2.5-flash-preview-09-2025
# and text-embedding-004. As of this build, BOTH have been officially retired
# by Google (text-embedding-004 shut down Jan 14 2026; the dated preview flash
# model shut down Feb 17 2026). Using either would make the app fail on first
# run, so this project uses their current, stable replacements instead.
GENERATION_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL = "gemini-embedding-001"

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_DIR = os.path.join(BASE_DIR, "db")

# --- Chunking Parameters ---
CHUNK_SIZE = 1000          # characters per chunk
CHUNK_OVERLAP = 200        # overlap between consecutive chunks

# --- Retrieval Parameters ---
TOP_K = 4                  # number of chunks retrieved per query
MIN_RELEVANCE_SCORE = 0.3  # filters out weakly related chunks (cosine similarity)

# --- ChromaDB Collection ---
COLLECTION_NAME = "document_knowledge_base"

# --- System Prompt (Strict Grounding) ---
SYSTEM_PROMPT = (
    "You are a precise, professional document Q&A assistant. "
    "Answer the user's question using ONLY the information provided in the "
    "CONTEXT section below. Cite the source filename and page number inline "
    "next to every fact you state, in the format (filename, Page X). "
    "If the answer cannot be found in the provided context, respond exactly: "
    "'I cannot find the answer in the provided documents.' "
    "Do not use any outside knowledge, do not guess, and do not fabricate "
    "information that is not explicitly present in the context."
)
