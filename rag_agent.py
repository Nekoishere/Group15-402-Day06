"""
rag_agent.py — Agentic RAG: guardrails → retrieve → confidence check → answer/clarify.

Two LLM calls per query:
  Call 1: Confidence assessor — is the retrieved context enough? Detect language.
  Call 2: Answer generator — produce cited answer in the right language + enthusiastic tone.
"""

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
# Prompts
# ---------------------------------------------------------------------------

CONFIDENCE_ASSESSOR_PROMPT = """You are evaluating whether provided context from VinUniversity's Academic Regulations is sufficient to answer a student's question.

1. Detect the language of the question: "vi" for Vietnamese, "en" for English.
2. Determine if the retrieved context contains enough information to give a complete, accurate answer.
3. If NOT sufficient (question is ambiguous, too vague, spans unrelated topics, or context has no relevant info), set confident=false and write ONE short clarifying follow-up question in the SAME language as the student's question.

Return ONLY valid JSON, no markdown fences:
{"confident": true/false, "clarifying_question": null or "string", "detected_language": "vi" or "en"}"""

ANSWER_GENERATOR_PROMPT_VI = """Bạn là VinUni AI Academic Advisor — một trợ lý tư vấn học vụ thân thiện, nhiệt tình và am hiểu quy chế của VinUniversity.

Quy tắc:
- CHỈ trả lời dựa trên ngữ cảnh được cung cấp. KHÔNG bịa thông tin.
- Luôn trích dẫn cụ thể Điều và Khoản, ví dụ: (Điều 5, Khoản 2).
- Nếu thông tin không có trong ngữ cảnh: "Tôi không tìm thấy thông tin này trong quy chế. Vui lòng liên hệ Phòng Đào tạo."
- Về vấn đề tài chính (học phí, học bổng): "Vấn đề tài chính vui lòng liên hệ trực tiếp Phòng Đào tạo."
- Trả lời bằng tiếng Việt.
- Giọng văn: ấm áp, nhiệt tình, dễ hiểu.
- Kết thúc mỗi câu trả lời bằng: "Bạn có muốn hỏi thêm điều gì khác không? Mình luôn sẵn sàng hỗ trợ! 😊" """

ANSWER_GENERATOR_PROMPT_EN = """You are VinUni AI Academic Advisor — a friendly, enthusiastic, and knowledgeable assistant for VinUniversity's academic regulations.

Rules:
- Answer ONLY based on the provided context. NEVER fabricate information.
- Always cite specific Article and Clause numbers, e.g.: (Article 5, Clause 2).
- If the answer is not in the context: "I couldn't find this information in the regulations. Please contact the Registrar's Office."
- For financial topics (tuition, scholarships): "For financial matters, please contact the Registrar's Office directly."
- Respond in English.
- Tone: warm, enthusiastic, clear.
- End every answer with: "Feel free to ask anything else! I'm always here to help! 😊" """

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


def _make_result(
    answer: str,
    sources: list[dict],
    guardrail: str | None,
    needs_clarification: bool = False,
    detected_language: str = "vi",
) -> dict:
    return {
        "answer": answer,
        "sources": sources,
        "guardrail_triggered": guardrail is not None,
        "guardrail_type": guardrail,
        "needs_clarification": needs_clarification,
        "detected_language": detected_language,
        "ingest_date": _load_ingest_date(),
    }


# ---------------------------------------------------------------------------
# Main query function
# ---------------------------------------------------------------------------

def query(question: str, conversation_history: list[dict] | None = None) -> dict:
    """
    Agentic RAG query against VinUni Academic Regulations.

    Args:
        question: the student's question
        conversation_history: optional list of recent messages [{role, content}]

    Returns dict with: answer, sources, guardrail_triggered, guardrail_type,
                       needs_clarification, detected_language, ingest_date
    """

    # --- Guardrail: emotional distress (highest priority) ---
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

    # --- RAG Pipeline ---
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Step 1: Embed question
    embed_response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=[question],
    )
    query_embedding = embed_response.data[0].embedding

    # Step 2: Retrieve from ChromaDB
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

    # Build context + sources
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

    # Step 3: CALL 1 — Confidence Assessor
    assessor_message = (
        f"[RETRIEVED CONTEXT]\n{context}\n\n"
        f"[STUDENT QUESTION]\n{question}"
    )

    assessor_response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": CONFIDENCE_ASSESSOR_PROMPT},
            {"role": "user", "content": assessor_message},
        ],
        temperature=0.0,
        max_tokens=200,
    )

    assessor_text = assessor_response.choices[0].message.content.strip()

    # Parse assessor JSON
    try:
        # Strip markdown fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", assessor_text).strip().rstrip("`")
        assessment = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: assume confident, Vietnamese
        assessment = {"confident": True, "clarifying_question": None, "detected_language": "vi"}

    detected_lang = assessment.get("detected_language", "vi")
    confident = assessment.get("confident", True)

    # If not confident → return clarifying question
    if not confident and assessment.get("clarifying_question"):
        clarification = assessment["clarifying_question"]
        # Add enthusiastic framing
        if detected_lang == "vi":
            clarification += "\n\nMình muốn chắc chắn trả lời đúng ý bạn nhé! 😊"
        else:
            clarification += "\n\nJust want to make sure I give you the right answer! 😊"
        return _make_result(
            clarification, sources, None,
            needs_clarification=True,
            detected_language=detected_lang,
        )

    # Step 4: CALL 2 — Answer Generator
    system_prompt = ANSWER_GENERATOR_PROMPT_VI if detected_lang == "vi" else ANSWER_GENERATOR_PROMPT_EN

    # Build messages with conversation history for context
    messages = [{"role": "system", "content": system_prompt}]

    if conversation_history:
        for msg in conversation_history[-4:]:  # Last 4 messages (2 turns)
            messages.append({"role": msg["role"], "content": msg["content"]})

    user_message = f"[CONTEXT]\n{context}\n\n[QUESTION]\n{question}"
    messages.append({"role": "user", "content": user_message})

    answer_response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.1,
        max_tokens=1000,
    )

    answer = answer_response.choices[0].message.content.strip()

    return _make_result(
        answer, sources, None,
        needs_clarification=False,
        detected_language=detected_lang,
    )
