"""
main.py
Streamlit-based interactive UI for the Document Q&A Bot.

Run with:
    streamlit run src/main.py

This loads the ChromaDB collection persisted by ingest.py (it does NOT
re-embed documents) and lets the user chat with their document library
through a simple, clean interface with inline source citations.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import config
from query import query_rag_pipeline

st.set_page_config(
    page_title="Document Q&A Bot",
    page_icon="📚",
    layout="centered"
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("📚 Document Q&A Bot")
    st.caption("Retrieval-Augmented Generation over your document library.")

    st.markdown("---")
    st.subheader("⚙️ Settings")
    top_k = st.slider("Chunks to retrieve (k)", min_value=2, max_value=8, value=config.TOP_K)
    show_sources = st.checkbox("Show retrieved source chunks", value=True)

    st.markdown("---")
    st.subheader("📁 Indexed Documents")
    if os.path.exists(config.DATA_DIR):
        files = sorted(os.listdir(config.DATA_DIR))
        files = [f for f in files if not f.startswith(".")]
        if files:
            for f in files:
                st.markdown(f"- `{f}`")
        else:
            st.info("No documents found in data/")
    else:
        st.info("data/ directory not found")

    st.markdown("---")
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.caption(
        "Built with ChromaDB + Google Gemini "
        f"({config.GENERATION_MODEL}). Answers are strictly grounded in the "
        "indexed documents — the bot will not use outside knowledge."
    )

# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------
st.header("Ask a question about your documents")

# Check that the vector DB exists before allowing queries.
db_ready = os.path.exists(config.DB_DIR) and len(os.listdir(config.DB_DIR)) > 0
if not db_ready:
    st.error(
        "No vector database found. Run the ingestion pipeline first:\n\n"
        "```\npython src/ingest.py\n```\n\n"
        "Then restart this app."
    )
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

# Render chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("citations"):
            with st.expander("📎 Sources cited"):
                for c in msg["citations"]:
                    st.markdown(f"- {c}")
        if msg["role"] == "assistant" and msg.get("chunks") and show_sources:
            with st.expander("🔍 Retrieved chunks (debug view)"):
                for chunk in msg["chunks"]:
                    meta = chunk["metadata"]
                    st.markdown(
                        f"**{meta['source']} — Page {meta['page']}** "
                        f"(relevance score: {chunk['score']})"
                    )
                    st.text(chunk["text"][:400] + ("..." if len(chunk["text"]) > 400 else ""))
                    st.markdown("---")

# Chat input
user_question = st.chat_input("Ask something about your documents...")

if user_question:
    st.session_state.messages.append({"role": "user", "content": user_question})
    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        with st.spinner("Searching documents and generating answer..."):
            try:
                result = query_rag_pipeline(user_question, k=top_k)
            except Exception as e:
                result = {
                    "answer": f"⚠️ An error occurred while processing your question: {e}",
                    "citations": [],
                    "chunks": []
                }

        st.markdown(result["answer"])

        if result.get("citations"):
            with st.expander("📎 Sources cited"):
                for c in result["citations"]:
                    st.markdown(f"- {c}")

        if result.get("chunks") and show_sources:
            with st.expander("🔍 Retrieved chunks (debug view)"):
                for chunk in result["chunks"]:
                    meta = chunk["metadata"]
                    st.markdown(
                        f"**{meta['source']} — Page {meta['page']}** "
                        f"(relevance score: {chunk['score']})"
                    )
                    st.text(chunk["text"][:400] + ("..." if len(chunk["text"]) > 400 else ""))
                    st.markdown("---")

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "citations": result.get("citations", []),
        "chunks": result.get("chunks", [])
    })
