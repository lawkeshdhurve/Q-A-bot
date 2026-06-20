# Document Q&A Bot — RAG-based Assistant

A Retrieval-Augmented Generation (RAG) system that answers questions strictly from
a custom library of PDF/DOCX documents, with inline source citations (filename +
page number) and built-in hallucination guarding. Built as part of an AI Engineering
internship assignment.

---

## 🧠 What this project does

Large Language Models don't know about your private documents, and when asked
about content outside their training data they tend to hallucinate confident-sounding
but incorrect answers. This project solves that by:

1. **Ingesting** your own PDF/DOCX files into a local vector database.
2. **Retrieving** the most relevant chunks of those documents for any question asked.
3. **Generating** an answer using Google Gemini, but constraining it to use *only*
   the retrieved context — with the model explicitly instructed to say
   *"I cannot find the answer in the provided documents"* rather than guess.
4. **Citing** every fact with its source filename and page number.

---

## 🏗️ Architecture

```
 data/*.pdf, *.docx
        │
        ▼
 extractors.py  ──► page-level text + {source, page} metadata
        │
        ▼
 chunking.py    ──► recursive character splitting (1000 chars, 200 overlap)
        │
        ▼
 ingest.py      ──► embeds chunks (Gemini text-embedding-004) → ChromaDB (db/)
        │
        ▼
   [ persisted once — never re-run unless data/ changes ]
        │
        ▼
 query.py       ──► embed user question → top-k similarity search → ChromaDB
        │
        ▼
        ──► build grounded prompt with [Source, Page] tags
        │
        ▼
        ──► Gemini 2.5 Flash generates a cited, grounded answer
        │
        ▼
 main.py (Streamlit) / cli.py  ──► display answer + citations to user
```

**Why this is split into two phases (ingest vs. query):** Embedding API calls cost
time and tokens. By persisting the vector database to disk once (`db/`), the app
loads instantly on every subsequent run — no documents are ever re-embedded just
to answer a question.

---

## 📂 Project Structure

```
document-qa-bot/
├── .env                  # Your API key (not committed to git)
├── .env.example          # Template showing required variables
├── .gitignore
├── README.md
├── requirements.txt
├── generate_samples.py   # Generates the 3 sample documents in data/ (optional)
├── data/                 # Source documents
│   ├── business_doc.pdf  # Sample: fictional company annual report
│   ├── science_paper.pdf # Sample: fictional materials-science research paper
│   └── factsheet.docx    # Sample: fictional product factsheet
├── db/                   # Persistent ChromaDB storage (auto-created, gitignored)
└── src/
    ├── __init__.py
    ├── config.py         # Central config: model names, chunk size, prompts
    ├── extractors.py      # PDF/DOCX/TXT → page-level text + metadata
    ├── chunking.py        # Recursive character splitting logic
    ├── ingest.py          # Pipeline: extract → chunk → embed → persist
    ├── query.py           # Pipeline: embed query → retrieve → generate
    ├── main.py            # Streamlit web UI
    └── cli.py             # Lightweight terminal interface (alternative to Streamlit)
```

---

## ⚙️ Setup & Installation

### 1. Clone and enter the project
```bash
git clone <your-repo-url>
cd document-qa-bot
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Add your Gemini API key
Create a `.env` file in the project root (copy `.env.example`):
```
GEMINI_API_KEY=your_actual_key_here
```
Get a free key at [Google AI Studio](https://aistudio.google.com/app/apikey).

### 5. (Optional) Generate the sample documents
Three fictional sample documents (a business report, a research paper, and a
product factsheet) are provided to test the pipeline out of the box. To
regenerate them:
```bash
python generate_samples.py
```
To use your **own** documents instead, simply drop your PDF/DOCX/TXT files
into `data/` (replacing or alongside the samples).

### 6. Run ingestion (builds the vector database)
```bash
python src/ingest.py
```
You only need to re-run this when you add or change files in `data/`.

### 7. Launch the app

**Web UI (Streamlit):**
```bash
streamlit run src/main.py
```

**Or, terminal CLI:**
```bash
python src/cli.py
```

---

## 🔍 Design Decisions & Technical Notes

**Chunking strategy — recursive character splitting.**
Rather than cutting text at a fixed character offset, the chunker tries to split
on the "nicest" boundary first — paragraph breaks (`\n\n`), then line breaks (`\n`),
then sentence ends (`. `), then spaces, only falling back to a raw character cut
as a last resort. This keeps related sentences together inside a single chunk far
more often than naive fixed-width slicing. A 200-character overlap between
consecutive chunks ensures that a fact sitting right on a chunk boundary isn't
fully lost from either neighboring chunk's context.

**Metadata-first extraction.**
Every extracted unit of text is tagged with its source filename and page number
*before* chunking, and that metadata is propagated through to every chunk derived
from it. This is what allows query.py to generate accurate `(filename, Page N)`
citations rather than vague "found in your documents" answers.

**PDF vs. DOCX page tracking.**
PDFs have a real, fixed page concept, so each page is extracted and tagged
individually. DOCX files don't have a reliable page boundary at the XML level
(pagination depends on the rendering engine/fonts), so DOCX content is extracted
as a single logical unit (`page: 1`) — citations for DOCX sources reference the
filename only, which is an accepted tradeoff documented here rather than hidden.

**Strict grounding via system prompt.**
The system prompt explicitly forbids the model from using outside knowledge and
gives it an exact refusal string to use when the retrieved context doesn't
contain the answer. This is the primary anti-hallucination guardrail in this
system — retrieval quality matters, but the prompt-level constraint is what
actually stops the LLM from "filling in the gaps" with plausible-sounding guesses.

**Relevance score thresholding.**
Retrieved chunks are also filtered by a minimum cosine-similarity score
(`MIN_RELEVANCE_SCORE = 0.3` in `config.py`). If a user asks something completely
unrelated to the indexed documents, weak/irrelevant matches are dropped before
they ever reach the prompt — reducing the chance of the model being "tempted" to
answer from a barely-related chunk.

**Separation of ingest.py and query.py.**
Ingestion (expensive, run rarely) and querying (cheap, run constantly) are
deliberately separate scripts with no shared runtime state, matching the
assignment's required architecture. `config.py` centralizes every tunable
constant (chunk size, overlap, top-k, model names, prompt text) so behavior can
be adjusted without touching pipeline logic.

---

## ⚠️ A Note on Model Versions (Deviation from the Assignment Brief)

The original assignment reference document specifies `text-embedding-004` for
embeddings, `gemini-2.5-flash-preview-09-2025` for generation, and the
`google-generativeai` Python package.

**As of this build, all three have been officially retired by Google:**
- `text-embedding-004` was shut down January 14, 2026 (replaced by `gemini-embedding-001`).
- `gemini-2.5-flash-preview-09-2025` was shut down February 17, 2026 (replaced by the stable `gemini-2.5-flash`).
- The `google-generativeai` package itself is fully deprecated in favor of the actively maintained `google-genai` package.

Using the originally specified names would make the app fail immediately on
the very first API call, so this project uses the current stable equivalents:

| Assignment spec (now retired) | Used in this project |
|---|---|
| `text-embedding-004` | `gemini-embedding-001` |
| `gemini-2.5-flash-preview-09-2025` | `gemini-2.5-flash` |
| `google-generativeai` SDK | `google-genai` SDK |

All model/SDK names are centralized in `src/config.py` and `src/embeddings.py`,
so swapping them back (or to any future model) requires changing only those
two files.

---



```
You: What was Solara Dynamics' net revenue growth in FY2026?

Bot: Solara Dynamics Inc.'s net revenue grew by 14% year-over-year in FY2026,
reaching ₹842 crore compared to ₹738 crore in FY2025 (business_doc.pdf, Page 1).

Sources:
  - business_doc.pdf, Page 1
  - business_doc.pdf, Page 2
```

```
You: What is the capital of France?

Bot: I cannot find the answer in the provided documents.
```

---

## ⚠️ Known Limitations

- **DOCX page numbers** are not true page numbers (see Design Decisions above) —
  citations for `.docx` sources will always show `Page 1`.
- **No OCR support** — scanned/image-only PDFs with no embedded text layer will
  extract no content. A future improvement would add an OCR fallback (e.g.
  `pytesseract`) for such files.
- **Single embedding model dependency** — the same `text-embedding-004` model
  must be used for both ingestion and querying; switching embedding models
  requires re-running `ingest.py` from scratch.
- **No conversational memory across turns** — each question is answered
  independently; the bot doesn't currently use prior chat turns as additional
  context for retrieval.

---

## 🛣️ Possible Future Improvements

- Add OCR fallback for scanned documents.
- Support multi-turn conversational context in retrieval.
- Add a hybrid search (keyword + semantic) for queries with exact terms/numbers.
- Allow document upload directly from the Streamlit UI (auto-triggering ingestion).

---

## 📦 Tech Stack

| Component          | Technology                                   |
|---------------------|-----------------------------------------------|
| Language             | Python 3.11+                                  |
| Vector Database       | ChromaDB (persistent, local)                  |
| Embeddings            | Google `gemini-embedding-001`                 |
| LLM                    | Google `gemini-2.5-flash`                   |
| Document Parsing       | `pypdf`, `python-docx`                       |
| Web UI                  | Streamlit                                    |
| Env Management            | `python-dotenv`                            |
