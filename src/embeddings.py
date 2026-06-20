"""
embeddings.py
A small wrapper around Google's modern `google-genai` SDK that implements
ChromaDB's EmbeddingFunction interface.

Why this exists instead of using chromadb.utils.embedding_functions.
GoogleGenerativeAiEmbeddingFunction directly: that built-in helper is hard-
wired to the OLD, now fully deprecated `google.generativeai` package and
defaults to a different embedding model. Google has since released the
`google-genai` SDK as the actively maintained replacement, so this wrapper
calls that SDK directly while still exposing the exact interface ChromaDB
expects (a callable that takes a list of strings and returns a list of
embedding vectors).
"""

from google import genai
from google.genai import types
from chromadb import EmbeddingFunction, Documents, Embeddings

import config


class GeminiEmbeddingFunction(EmbeddingFunction):
    """
    ChromaDB-compatible embedding function backed by Gemini's
    `gemini-embedding-001` model via the google-genai SDK.

    task_type matters here: documents being indexed should use
    RETRIEVAL_DOCUMENT, while user queries at search time should use
    RETRIEVAL_QUERY. Using the right task type for each side measurably
    improves retrieval quality - it's not just a label.
    """

    def __init__(self, api_key: str, model_name: str = None, task_type: str = "RETRIEVAL_DOCUMENT"):
        self._client = genai.Client(api_key=api_key)
        self._model_name = model_name or config.EMBEDDING_MODEL
        self._task_type = task_type

    def __call__(self, input: Documents) -> Embeddings:
        # The API accepts a batch of strings in one call.
        response = self._client.models.embed_content(
            model=self._model_name,
            contents=list(input),
            config=types.EmbedContentConfig(task_type=self._task_type)
        )
        return [embedding.values for embedding in response.embeddings]

    def name(self) -> str:
        # ChromaDB persists this name alongside the collection to detect
        # embedding-function mismatches between ingestion and query time.
        return f"gemini-embedding-function-{self._task_type.lower()}"
