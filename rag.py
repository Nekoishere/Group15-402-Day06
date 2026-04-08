import os
import re
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
import chromadb

load_dotenv()

CHROMA_DIR = Path(__file__).parent / "chroma_db"
METADATA_FILE = CHROMA_DIR / "ingest_metadata.json"
COLLECTION_NAME = "vinuni_regs"
TOP_K = 5

# ---------------------------------------------------------------------------
# Guardrail keyword lists
# ---------------------------------------------------------------------------

FINANCIAL_KEYWORDS = [
    "học phí", "học bổng", "tiền", "phí", "chi phí", "giá",
    "fee", "tuition", "scholarship", "cost", "price", "payment",
    "nộp tiền", "hoàn trả", "refund",
]

DISTRESS_KEYWORDS = [
    "căng thẳng", "trầm cảm", "áp lực", "lo lắng", "tuyệt vọng",
    "muốn bỏ học", "bỏ học", "không muốn tiếp tục", "mệt mỏi quá",
    "overwhelmed", "depressed", "anxious", "want to quit", "give up",
    "stressed", "burnout", "mental health",
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are VinUni AI Academic Advisor. Answer ONLY based on the provided context from VinUniversity's Academic Regulations.

Rules:
- If the answer is not in the context, say: "Tôi không tìm thấy thông tin này trong quy chế. Vui lòng liên hệ Phòng Đào tạo."
- Always cite the specific Article and Clause number (e.g. "Theo Điều 5, Khoản 2..." or "According to Article 5, Clause 2...").
- For questions about tuition/scholarships/money, DO NOT generate an answer. Instead say: "Vấn đề tài chính vui lòng liên hệ trực tiếp Phòng Đào tạo" and provide the official link.
- Respond in the same language the student uses (Vietnamese or English).
- Be concise and precise. Do not add information beyond what is in the context."""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_ingest_date() -> str:
    if METADATA_FILE.exists():
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return meta.get("ingest_date", "unknown")
    return "unknown"


def _check_keywords(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def _make_result(answer: str, sources: list[dict], guardrail: str | None) -> dict:
    return {
        "answer": answer,
        "sources": sources,
        "guardrail_triggered": guardrail is not None,
        "guardrail_type": guardrail,
        "ingest_date": _load_ingest_date(),
    }


# ---------------------------------------------------------------------------
# Main query function
# ---------------------------------------------------------------------------

def query(question: str) -> dict:
    """
    Run a RAG query against the VinUni Academic Regulations.

    Returns:
        {
            answer: str,
            sources: [{page, article, text_snippet}],
            guardrail_triggered: bool,
            guardrail_type: str | None,   # "financial" | "distress" | None
            ingest_date: str,
        }
    """

    # --- Guardrail: emotional distress (check first — safety is highest priority) ---
    if _check_keywords(question, DISTRESS_KEYWORDS):
        answer = (
            "Mình nhận thấy bạn đang trải qua giai đoạn khó khăn. "
            "Đây không phải là câu hỏi học vụ mà mình có thể giúp tốt nhất.\n\n"
            "**Vui lòng liên hệ ngay bộ phận Tư vấn Tâm lý Sinh viên của VinUni** "
            "để được hỗ trợ kịp thời.\n\n"
            "Bạn không cần phải đối mặt với điều này một mình. 💙"
        )
        return _make_result(answer, [], "distress")

    # --- Guardrail: financial questions ---
    if _check_keywords(question, FINANCIAL_KEYWORDS):
        answer = (
            "Vấn đề tài chính (học phí, học bổng, v.v.) vui lòng liên hệ trực tiếp "
            "**Phòng Đào tạo (Registrar's Office)** để được tư vấn chính xác nhất.\n\n"
            "Thông tin tài chính thay đổi theo từng năm học và mình không cung cấp "
            "con số cụ thể để tránh gây nhầm lẫn."
        )
        return _make_result(answer, [], "financial")

    # --- RAG pipeline ---
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # 1. Embed question
    embed_response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=[question],
    )
    query_embedding = embed_response.data[0].embedding

    # 2. Retrieve from ChromaDB
    db = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = db.get_collection(COLLECTION_NAME)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"],
    )

    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    # 3. Build context string
    context_parts = []
    sources = []
    for doc, meta, dist in zip(docs, metas, distances):
        label = f"[Page {meta['page']}"
        if meta.get("article"):
            label += f", {meta['article']}"
        label += "]"
        context_parts.append(f"{label}\n{doc}")
        sources.append({
            "page": meta["page"],
            "article": meta.get("article", ""),
            "text_snippet": doc[:200] + ("..." if len(doc) > 200 else ""),
            "distance": round(dist, 4),
        })

    context = "\n\n---\n\n".join(context_parts)
    user_message = f"[CONTEXT]\n{context}\n\n[QUESTION]\n{question}"

    # 4. Generate answer
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.0,  # zero temperature for maximum precision
        max_tokens=800,
    )

    answer = response.choices[0].message.content.strip()

    return _make_result(answer, sources, None)
