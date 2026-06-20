"""
ingest.py
Pipeline script: scans the data/ directory, extracts text, chunks it,
generates embeddings, and persists everything into a local ChromaDB
collection on disk.

Run this once whenever you add/change documents in data/:
    python src/ingest.py

After running, query.py / main.py can load the persisted database
instantly without re-embedding anything.
"""

import os
import sys
import glob

# Allow running this file directly (python src/ingest.py) as well as
# as a module (python -m src.ingest) by making sure src/ is importable.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chromadb
from tqdm import tqdm

import config
from extractors import extract_document
from chunking import chunk_extracted_pages
from embeddings import GeminiEmbeddingFunction

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt")


def discover_documents(data_dir: str) -> list[str]:
    """Finds all supported document files inside the data/ directory."""
    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(glob.glob(os.path.join(data_dir, f"*{ext}")))
    return sorted(files)


def run_ingestion():
    print("=" * 60)
    print("DOCUMENT Q&A BOT — INGESTION PIPELINE")
    print("=" * 60)

    # --- Step 1: Discover documents ---
    files = discover_documents(config.DATA_DIR)
    if not files:
        print(f"\nNo supported documents found in {config.DATA_DIR}")
        print(f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")
        return

    print(f"\nFound {len(files)} document(s) in {config.DATA_DIR}:")
    for f in files:
        print(f"  - {os.path.basename(f)}")

    # --- Step 2: Extract text from each document ---
    print("\n[1/3] Extracting text from documents...")
    all_pages = []
    for file_path in tqdm(files, desc="Extracting"):
        pages = extract_document(file_path)
        all_pages.extend(pages)

    if not all_pages:
        print("\nNo text could be extracted from any document. Aborting.")
        return
    print(f"  -> Extracted {len(all_pages)} page/section unit(s) total.")

    # --- Step 3: Chunk the extracted text ---
    print("\n[2/3] Chunking text (recursive character splitting)...")
    chunks = chunk_extracted_pages(
        all_pages,
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP
    )
    print(f"  -> Produced {len(chunks)} chunk(s) "
          f"(chunk_size={config.CHUNK_SIZE}, overlap={config.CHUNK_OVERLAP}).")

    # --- Step 4: Embed and persist to ChromaDB ---
    print("\n[3/3] Generating embeddings and saving to ChromaDB...")
    save_to_vector_db(chunks, db_path=config.DB_DIR)

    print("\n" + "=" * 60)
    print("INGESTION COMPLETE")
    print(f"Vector database persisted at: {config.DB_DIR}")
    print("You can now run the Q&A bot: streamlit run src/main.py")
    print("=" * 60)


def save_to_vector_db(chunks: list[dict], db_path: str):
    """
    Embeds text chunks (via Gemini's embedding model, see config.EMBEDDING_MODEL)
    and saves them into a persistent, disk-based ChromaDB collection.

    Using a PersistentClient means the embeddings only need to be computed
    once. On every subsequent run, query.py loads this same collection from
    disk and reuses the stored vectors without any new embedding API calls
    for the source documents.
    """
    client = chromadb.PersistentClient(path=db_path)

    embedding_fn = GeminiEmbeddingFunction(
        api_key=config.GEMINI_API_KEY,
        model_name=config.EMBEDDING_MODEL,
        task_type="RETRIEVAL_DOCUMENT"
    )

    # Wipe and recreate the collection on every ingest run so re-running
    # ingest.py after editing data/ doesn't leave stale/duplicate chunks
    # from a previous version of the documents.
    try:
        client.delete_collection(name=config.COLLECTION_NAME)
    except Exception:
        pass  # Collection didn't exist yet - nothing to delete.

    collection = client.create_collection(
        name=config.COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"}
    )

    # Batch upload. ChromaDB calls the embedding function internally for
    # each batch, so we don't need to call the Gemini embedding API by hand.
    batch_size = 50
    total = len(chunks)

    for start in tqdm(range(0, total, batch_size), desc="Embedding & indexing"):
        end = min(start + batch_size, total)
        batch = chunks[start:end]

        ids = [f"id_{start + i}" for i in range(len(batch))]
        documents = [c["text"] for c in batch]
        metadatas = [c["metadata"] for c in batch]

        collection.add(ids=ids, documents=documents, metadatas=metadatas)

    print(f"  -> Successfully indexed {total} chunks in collection "
          f"'{config.COLLECTION_NAME}'.")


if __name__ == "__main__":
    run_ingestion()
