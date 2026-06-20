"""
query.py
Query pipeline: embeds the user's question, retrieves the most relevant
chunks from the persisted ChromaDB collection, builds a strictly-grounded
prompt, and calls Gemini to generate a cited answer.

This module loads the EXISTING database from disk - it never re-embeds
the source documents. Run ingest.py first to build the database.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chromadb
from google import genai

import config
from embeddings import GeminiEmbeddingFunction

_genai_client = genai.Client(api_key=config.GEMINI_API_KEY)

# Module-level caches so Streamlit reruns (or repeated CLI queries) don't
# reconnect to ChromaDB / reload the embedding function on every call.
_collection = None
_query_embedding_fn = None


def _get_collection():
    """Lazily loads (and caches) the persisted ChromaDB collection.

    Note: we deliberately load this WITHOUT an embedding_function bound to
    it. Embedding generation for queries is handled manually in
    retrieve_chunks() using the RETRIEVAL_QUERY task type (as opposed to
    RETRIEVAL_DOCUMENT, used at ingestion time) - using the matching task
    type on each side of the search measurably improves retrieval quality.
    """
    global _collection
    if _collection is not None:
        return _collection

    if not os.path.exists(config.DB_DIR) or not os.listdir(config.DB_DIR):
        raise FileNotFoundError(
            f"No vector database found at '{config.DB_DIR}'. "
            f"Run 'python src/ingest.py' first to index your documents."
        )

    client = chromadb.PersistentClient(path=config.DB_DIR)

    try:
        _collection = client.get_collection(name=config.COLLECTION_NAME)
    except Exception as e:
        raise RuntimeError(
            f"Could not load collection '{config.COLLECTION_NAME}'. "
            f"Did ingestion complete successfully? Original error: {e}"
        )

    return _collection


def _get_query_embedding_fn():
    """Lazily loads (and caches) the query-side embedding function."""
    global _query_embedding_fn
    if _query_embedding_fn is None:
        _query_embedding_fn = GeminiEmbeddingFunction(
            api_key=config.GEMINI_API_KEY,
            model_name=config.EMBEDDING_MODEL,
            task_type="RETRIEVAL_QUERY"
        )
    return _query_embedding_fn


def retrieve_chunks(user_query: str, k: int = None) -> list[dict]:
    """
    Embeds the user's query and retrieves the top-k most similar chunks
    from the vector database, filtering out weak matches below
    MIN_RELEVANCE_SCORE.

    Returns a list of dicts: {"text": ..., "metadata": ..., "score": ...}
    where score is a 0-1 cosine similarity (higher = more relevant).
    """
    k = k or config.TOP_K
    collection = _get_collection()
    embedding_fn = _get_query_embedding_fn()

    # Embed the query ourselves (RETRIEVAL_QUERY task type) rather than
    # letting ChromaDB embed it with the collection's default function,
    # which was configured for RETRIEVAL_DOCUMENT at ingest time.
    query_embedding = embedding_fn([user_query])[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"]
    )

    docs = results["documents"][0] if results["documents"] else []
    metas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []

    retrieved = []
    for doc, meta, dist in zip(docs, metas, distances):
        # ChromaDB's cosine *distance* is 0 (identical) to 2 (opposite).
        # Convert to a similarity score in [0, 1] that's more intuitive
        # to threshold against: 1.0 = perfect match, 0.0 = unrelated.
        similarity = 1 - (dist / 2)
        if similarity >= config.MIN_RELEVANCE_SCORE:
            retrieved.append({"text": doc, "metadata": meta, "score": round(similarity, 3)})

    return retrieved


def build_grounded_prompt(user_query: str, retrieved_chunks: list[dict]) -> str:
    """
    Formats retrieved chunks into a labeled context block and assembles
    the full grounding prompt sent to the LLM. Each chunk is explicitly
    tagged with its source filename and page number so the model can
    (and is instructed to) cite them inline.
    """
    context_blocks = []
    for chunk in retrieved_chunks:
        source = chunk["metadata"]["source"]
        page = chunk["metadata"]["page"]
        context_blocks.append(f"[Source: {source}, Page: {page}]\n{chunk['text']}")

    context_payload = "\n\n---\n\n".join(context_blocks) if context_blocks else "(No relevant context found.)"

    prompt = (
        f"{config.SYSTEM_PROMPT}\n\n"
        f"CONTEXT INFORMATION:\n{context_payload}\n\n"
        f"USER QUESTION: {user_query}\n\n"
        f"GROUNDED ANSWER:"
    )
    return prompt


def query_rag_pipeline(user_query: str, k: int = None) -> dict:
    """
    Full RAG query pipeline:
      1. Retrieve top-k relevant chunks from the vector DB.
      2. Build a strictly-grounded prompt with inline source citations.
      3. Call Gemini to generate the final answer.

    Returns a dict with the answer text, the list of unique citations,
    and the raw retrieved chunks (useful for debugging / displaying
    "sources used" in the UI).
    """
    retrieved_chunks = retrieve_chunks(user_query, k=k)

    if not retrieved_chunks:
        return {
            "answer": "I cannot find the answer in the provided documents.",
            "citations": [],
            "chunks": []
        }

    prompt = build_grounded_prompt(user_query, retrieved_chunks)

    response = _genai_client.models.generate_content(
        model=config.GENERATION_MODEL,
        contents=prompt
    )

    # De-duplicate citations while preserving order (a single source/page
    # can appear in multiple retrieved chunks).
    seen = set()
    citations = []
    for chunk in retrieved_chunks:
        source = chunk["metadata"]["source"]
        page = chunk["metadata"]["page"]
        label = f"{source}, Page {page}"
        if label not in seen:
            seen.add(label)
            citations.append(label)

    return {
        "answer": response.text.strip(),
        "citations": citations,
        "chunks": retrieved_chunks
    }
