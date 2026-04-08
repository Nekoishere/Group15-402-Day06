"""
ingest.py — One-time script to process the Academic Regulations PDF into ChromaDB.
Run this once before starting the app: python ingest.py
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import pypdf
import chromadb

load_dotenv()

PDF_PATH = Path(__file__).parent / "Academic-Regulations-For-Full-Time-Undergraduate-Programs.pdf"
CHROMA_DIR = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "vinuni_regs"
METADATA_FILE = CHROMA_DIR / "ingest_metadata.json"

MAX_CHUNK_SIZE = 600  # characters


def extract_pages(pdf_path: Path) -> list[dict]:
    """Extract text from each page, returning list of {page, text}."""
    reader = pypdf.PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append({"page": i, "text": text})
    print(f"  Extracted {len(pages)} pages with text.")
    return pages


def detect_article(text: str) -> str:
    """Try to extract the nearest Article/Clause heading from a chunk."""
    # Match Vietnamese "Điều X" or English "Article X"
    match = re.search(r"(Điều\s+\d+[^\n]*|Article\s+\d+[^\n]*)", text, re.IGNORECASE)
    if match:
        return match.group(0).strip()[:80]
    return ""


def chunk_page(page_num: int, text: str) -> list[dict]:
    """
    Split a page's text into chunks.
    Strategy: split on Article/Clause boundaries first, then by paragraph,
    then enforce a max size.
    """
    chunks = []

    # Split on Article / Điều boundaries to keep clauses together
    article_pattern = re.compile(r"(?=Điều\s+\d+|Article\s+\d+)", re.IGNORECASE)
    sections = article_pattern.split(text)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # If section is within size, keep as one chunk
        if len(section) <= MAX_CHUNK_SIZE:
            article = detect_article(section)
            chunks.append({
                "page": page_num,
                "article": article,
                "text": section,
            })
        else:
            # Split further by paragraph
            paragraphs = [p.strip() for p in section.split("\n\n") if p.strip()]
            current = ""
            current_article = detect_article(section)

            for para in paragraphs:
                if len(current) + len(para) + 2 <= MAX_CHUNK_SIZE:
                    current = (current + "\n\n" + para).strip()
                else:
                    if current:
                        chunks.append({
                            "page": page_num,
                            "article": current_article,
                            "text": current,
                        })
                    # If single paragraph still too large, hard-split by sentence
                    if len(para) > MAX_CHUNK_SIZE:
                        sentences = re.split(r"(?<=[.!?])\s+", para)
                        current = ""
                        for sentence in sentences:
                            if len(current) + len(sentence) + 1 <= MAX_CHUNK_SIZE:
                                current = (current + " " + sentence).strip()
                            else:
                                if current:
                                    chunks.append({
                                        "page": page_num,
                                        "article": current_article,
                                        "text": current,
                                    })
                                current = sentence
                        if current:
                            chunks.append({
                                "page": page_num,
                                "article": current_article,
                                "text": current,
                            })
                        current = ""
                    else:
                        current = para

            if current:
                chunks.append({
                    "page": page_num,
                    "article": current_article,
                    "text": current,
                })

    return chunks


def embed_texts(texts: list[str], client) -> list[list[float]]:
    """Embed a batch of texts using OpenAI text-embedding-3-small."""
    # OpenAI allows up to 2048 inputs per call; batch in groups of 100 to be safe
    BATCH_SIZE = 100
    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch,
        )
        all_embeddings.extend([item.embedding for item in response.data])
        print(f"  Embedded {min(i + BATCH_SIZE, len(texts))}/{len(texts)} chunks...")
    return all_embeddings


def main():
    print("=== VinUni RAG Ingestor ===\n")

    # --- Check PDF exists ---
    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}")
        return

    # --- Connect to ChromaDB ---
    CHROMA_DIR.mkdir(exist_ok=True)
    db = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # --- Check if already ingested ---
    existing = db.list_collections()
    existing_names = [c.name for c in existing]
    if COLLECTION_NAME in existing_names:
        col = db.get_collection(COLLECTION_NAME)
        if col.count() > 0:
            print(f"Collection '{COLLECTION_NAME}' already has {col.count()} chunks. Skipping ingestion.")
            print("Delete ./chroma_db/ to re-ingest.")
            return

    # --- Extract PDF ---
    print(f"Loading PDF: {PDF_PATH.name}")
    pages = extract_pages(PDF_PATH)

    # --- Chunk ---
    print("\nChunking pages...")
    all_chunks = []
    for p in pages:
        chunks = chunk_page(p["page"], p["text"])
        all_chunks.extend(chunks)
    print(f"  Total chunks: {len(all_chunks)}")

    # --- Embed ---
    from openai import OpenAI
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    print("\nEmbedding chunks with text-embedding-3-small...")
    texts = [c["text"] for c in all_chunks]
    embeddings = embed_texts(texts, openai_client)

    # --- Store in ChromaDB ---
    print("\nStoring in ChromaDB...")
    collection = db.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    ids = [f"chunk_{i}" for i in range(len(all_chunks))]
    metadatas = [
        {
            "page": c["page"],
            "article": c["article"],
            "source": PDF_PATH.name,
        }
        for c in all_chunks
    ]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    print(f"  Stored {len(all_chunks)} chunks.")

    # --- Save ingest metadata ---
    ingest_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "ingest_date": ingest_date,
                "source_file": PDF_PATH.name,
                "total_chunks": len(all_chunks),
                "total_pages": len(pages),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\nDone! Ingestion metadata saved to {METADATA_FILE}")
    print(f"Ingest date recorded: {ingest_date}")
    print("\nYou can now run: streamlit run app.py")


if __name__ == "__main__":
    main()
