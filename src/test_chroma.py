import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chromadb
import config
from query import retrieve_chunks

def test():
    client = chromadb.PersistentClient(path=config.DB_DIR)
    print("Collections:", client.list_collections())
    try:
        col = client.get_collection(config.COLLECTION_NAME)
        print("Collection count:", col.count())
        # Print a few documents from the collection
        peek = col.peek(limit=5)
        print("Peek documents:")
        for doc, meta in zip(peek['documents'], peek['metadatas']):
            print(f"- Source: {meta['source']}, Page: {meta['page']}")
            print(f"  Content: {doc[:100]}...")
    except Exception as e:
        print("Error getting collection:", e)
        return

    # Let's test a simple query
    queries = [
        "What is the science paper about?",
        "What is this business document about?",
        "What is in the factsheet?",
        "test query"
    ]
    for q in queries:
        print(f"\nQuery: {q}")
        try:
            chunks = retrieve_chunks(q, k=4)
            print(f"Retrieved {len(chunks)} chunks:")
            for c in chunks:
                print(f"  - [{c['score']}] Source: {c['metadata']['source']}, Page: {c['metadata']['page']}")
                print(f"    Text: {c['text'][:150]}...")
        except Exception as e:
            print("Query error:", e)

if __name__ == "__main__":
    test()
