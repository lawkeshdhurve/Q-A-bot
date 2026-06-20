"""
cli.py
Lightweight command-line interface for the Document Q&A Bot.
Useful for quick testing without launching the full Streamlit app
(e.g. while recording a terminal demo, or debugging the pipeline).

Run with:
    python src/cli.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from query import query_rag_pipeline


def main():
    print("=" * 60)
    print("DOCUMENT Q&A BOT — CLI MODE")
    print("=" * 60)

    if not os.path.exists(config.DB_DIR) or not os.listdir(config.DB_DIR):
        print(f"\nNo vector database found at '{config.DB_DIR}'.")
        print("Run 'python src/ingest.py' first to index your documents.\n")
        return

    print("\nAsk a question about your documents. Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            user_query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_query:
            continue
        if user_query.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        try:
            result = query_rag_pipeline(user_query)
        except Exception as e:
            print(f"\n[Error] {e}\n")
            continue

        print(f"\nBot: {result['answer']}\n")
        if result["citations"]:
            print("Sources:")
            for c in result["citations"]:
                print(f"  - {c}")
        print()


if __name__ == "__main__":
    main()
