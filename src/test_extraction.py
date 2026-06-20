import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extractors import extract_document
import config

def test_extract():
    files = sorted(os.listdir(config.DATA_DIR))
    print(f"Files in data: {files}")
    for f in files:
        if f.startswith("."):
            continue
        path = os.path.join(config.DATA_DIR, f)
        pages = extract_document(path)
        print(f"\n--- {f} ---")
        print(f"Extracted {len(pages)} pages")
        for i, page in enumerate(pages):
            print(f"Page {page['metadata']['page']}: {page['text'][:200]}...")

if __name__ == "__main__":
    test_extract()
