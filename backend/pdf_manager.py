import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber

from config import CHUNK_OVERLAP_CHARS, CHUNK_SIZE_CHARS, PDFS_DIR
from backend.vector_store import VectorStore
from config import CHROMA_DIR


class PDFManager:
    """Manages PDF upload, text extraction, chunking, and ChromaDB indexing."""

    _INDEX_FILE = PDFS_DIR / "index.json"

    def __init__(self):
        self._vector_store = VectorStore(str(CHROMA_DIR))
        self._lock = threading.Lock()
        self._index: dict = self._load_index()

    # ── Public API ────────────────────────────────────────────────

    def upload_pdf(self, file_storage) -> dict:
        """Save uploaded file and start background indexing."""
        pdf_id = str(uuid.uuid4())
        original_name = file_storage.filename
        stored_name = f"{pdf_id}.pdf"
        file_path = PDFS_DIR / stored_name

        file_storage.save(str(file_path))
        size_bytes = file_path.stat().st_size

        meta = {
            "id": pdf_id,
            "filename": original_name,
            "stored_name": stored_name,
            "size_bytes": size_bytes,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "status": "indexing",
            "chunk_count": 0,
            "page_count": 0,
            "error": None,
        }
        with self._lock:
            self._index[pdf_id] = meta
            self._save_index()

        # Start background indexing
        t = threading.Thread(
            target=self._index_pdf_background,
            args=(pdf_id, str(file_path)),
            daemon=True,
        )
        t.start()

        return meta

    def delete_pdf(self, pdf_id: str) -> bool:
        """Delete PDF file, index entry, and ChromaDB chunks."""
        with self._lock:
            if pdf_id not in self._index:
                return False
            meta = self._index.pop(pdf_id)
            self._save_index()

        # Delete file
        file_path = PDFS_DIR / meta["stored_name"]
        if file_path.exists():
            file_path.unlink()

        # Remove from ChromaDB
        self._vector_store.delete_by_pdf_id(pdf_id)
        return True

    def list_pdfs(self) -> list[dict]:
        """Return sorted list of PDF metadata (newest first)."""
        with self._lock:
            items = list(self._index.values())
        items.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
        return items

    def get_status(self, pdf_id: str) -> str | None:
        with self._lock:
            meta = self._index.get(pdf_id)
        return meta["status"] if meta else None

    # ── Background indexing ───────────────────────────────────────

    def _index_pdf_background(self, pdf_id: str, file_path: str) -> None:
        """Extract, chunk, embed and store PDF content. Runs in background thread."""
        try:
            meta = self._index.get(pdf_id, {})
            filename = meta.get("filename", "unknown.pdf")

            chunks, page_count = self._extract_and_chunk(file_path, pdf_id, filename)

            if not chunks:
                self._update_status(pdf_id, "error", chunk_count=0, page_count=page_count,
                                    error="No text could be extracted. The PDF may be image-based.")
                return

            self._vector_store.add_chunks(chunks)
            self._update_status(pdf_id, "ready", chunk_count=len(chunks), page_count=page_count)

        except Exception as e:
            self._update_status(pdf_id, "error", error=str(e))

    def _extract_and_chunk(
        self, file_path: str, pdf_id: str, filename: str
    ) -> tuple[list[dict], int]:
        """
        Open PDF with pdfplumber, extract text per page, split into chunks.
        Returns (chunks_list, page_count).
        """
        chunks = []
        page_count = 0

        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if not text.strip():
                    continue  # Skip empty / image pages

                page_chunks = self._split_text(text)
                for chunk_idx, chunk_text in enumerate(page_chunks):
                    if not chunk_text.strip():
                        continue
                    chunk_id = f"{pdf_id}_p{page_num}_c{chunk_idx}"
                    # Detect section header (e.g., "1.2 Điều kiện...")
                    section = self._detect_section(chunk_text)
                    chunks.append({
                        "text": chunk_text.strip(),
                        "id": chunk_id,
                        "metadata": {
                            "source_pdf": filename,
                            "pdf_id": pdf_id,
                            "page": page_num,
                            "section": section,
                        },
                    })

        return chunks, page_count

    def _split_text(self, text: str) -> list[str]:
        """
        Split text into overlapping chunks.
        Strategy: split on paragraph breaks first, then by character limit.
        """
        # Split on paragraph boundaries
        paragraphs = re.split(r"\n\s*\n", text)
        chunks: list[str] = []
        current = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If single paragraph is too long, split further
            if len(para) > CHUNK_SIZE_CHARS:
                # First flush what we have
                if current:
                    chunks.append(current)
                    current = ""
                # Split large paragraph on newlines
                lines = para.split("\n")
                for line in lines:
                    if len(current) + len(line) + 1 <= CHUNK_SIZE_CHARS:
                        current += ("\n" if current else "") + line
                    else:
                        if current:
                            chunks.append(current)
                        current = line
            else:
                if len(current) + len(para) + 2 <= CHUNK_SIZE_CHARS:
                    current += ("\n\n" if current else "") + para
                else:
                    if current:
                        chunks.append(current)
                    current = para

        if current:
            chunks.append(current)

        # Add overlap: prepend tail of previous chunk to current chunk
        if len(chunks) > 1:
            overlapped = [chunks[0]]
            for i in range(1, len(chunks)):
                tail = chunks[i - 1][-CHUNK_OVERLAP_CHARS:]
                overlapped.append(tail + "\n" + chunks[i])
            return overlapped

        return chunks

    def _detect_section(self, text: str) -> str:
        """Try to extract a section header from the start of the chunk."""
        first_line = text.strip().split("\n")[0]
        # Match patterns like "1.", "1.2", "1.2.3", "Điều 5.", "Article 3"
        if re.match(r"^(\d+\.)+\d*\s+\S", first_line) or \
           re.match(r"^(Điều|Article|Section|Chương|Chapter)\s+\d+", first_line, re.IGNORECASE):
            return first_line[:80]
        return ""

    # ── Index file management ─────────────────────────────────────

    def _update_status(
        self, pdf_id: str, status: str,
        chunk_count: int = 0, page_count: int = 0, error: str | None = None
    ) -> None:
        with self._lock:
            if pdf_id in self._index:
                self._index[pdf_id]["status"] = status
                if chunk_count:
                    self._index[pdf_id]["chunk_count"] = chunk_count
                if page_count:
                    self._index[pdf_id]["page_count"] = page_count
                if error:
                    self._index[pdf_id]["error"] = error
                self._save_index()

    def _load_index(self) -> dict:
        if self._INDEX_FILE.exists():
            try:
                with open(self._INDEX_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_index(self) -> None:
        """Must be called while holding self._lock."""
        tmp = self._INDEX_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._INDEX_FILE)
