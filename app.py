"""
app.py — VinUni AI Academic Advisor: Pure RAG chatbot with VinUni-styled UI.
Run with: streamlit run app.py
"""

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from rag import query

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FEEDBACK_LOG = Path(__file__).parent / "feedback_log.jsonl"
METADATA_FILE = Path(__file__).parent / "chroma_db" / "ingest_metadata.json"
LOGO_PATH = Path(__file__).parent / "Logo ĐH Vin University-Vinuni.png"

st.set_page_config(
    page_title="VinUni AI Academic Advisor",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# VinUni Theme CSS
# ---------------------------------------------------------------------------

VINUNI_CSS = """
<style>
    :root {
        --blue-dark: #0e3c78;
        --blue-mid: #144e8d;
        --red-main: #c72027;
        --red-dark: #a41117;
        --white: #ffffff;
        --gray-light: #f0f2f6;
    }

    .main-header {
        background: linear-gradient(135deg, var(--blue-dark), var(--blue-mid));
        color: var(--white);
        padding: 1.2rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    .main-header h1 {
        margin: 0; font-size: 1.6rem; font-weight: 700;
        color: var(--white) !important;
    }
    .main-header p {
        margin: 0.3rem 0 0 0; font-size: 0.9rem; opacity: 0.85;
        color: var(--white) !important;
    }

    section[data-testid="stSidebar"] {
        background-color: var(--blue-dark) !important;
    }
    section[data-testid="stSidebar"] * {
        color: var(--white) !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        background-color: var(--red-main) !important;
        color: var(--white) !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600;
        transition: background-color 0.2s;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background-color: var(--red-dark) !important;
    }

    .stChatMessage[data-testid="stChatMessage"] {
        border-radius: 12px !important;
        margin-bottom: 0.5rem;
    }

    .streamlit-expanderHeader {
        background-color: var(--blue-mid) !important;
        color: var(--white) !important;
        border-radius: 8px !important;
    }

    .footer-contact {
        font-size: 0.78rem; opacity: 0.7; text-align: center;
        padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.15);
    }

    .stChatInput > div > div > input:focus,
    .stChatInput > div > div > textarea:focus {
        border-color: var(--red-main) !important;
        box-shadow: 0 0 0 1px var(--red-main) !important;
    }

    header[data-testid="stHeader"] {
        background-color: var(--blue-dark) !important;
    }
</style>
"""

st.markdown(VINUNI_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_ingest_meta() -> dict:
    if METADATA_FILE.exists():
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_feedback(message_idx: int, feedback_type: str, question: str, answer: str):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": feedback_type,
        "message_idx": message_idx,
        "question": question,
        "answer": answer[:300],
    }
    with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def check_db_ready() -> bool:
    chroma_dir = Path(__file__).parent / "chroma_db"
    return chroma_dir.exists() and any(chroma_dir.iterdir())


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "feedback_given" not in st.session_state:
    st.session_state.feedback_given = set()

# ---------------------------------------------------------------------------
# Sidebar — Logo + Contact + Clear
# ---------------------------------------------------------------------------

with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
    else:
        st.markdown("## 🎓 VinUniversity")

    st.markdown("### AI Academic Advisor")
    st.caption("Tra cứu Quy chế Học vụ")

    st.divider()

    st.markdown("**Liên hệ Phòng Đào tạo**")
    st.markdown("📧 registrar@vinuni.edu.vn")
    st.markdown("📞 (024) 3975 6868")

    st.divider()

    if st.button("🗑️ Xóa lịch sử chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.feedback_given = set()
        st.rerun()

    st.divider()
    st.markdown(
        '<div class="footer-contact">'
        "Powered by GPT-4o-mini + RAG"
        "</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Main Chat Area
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="main-header">'
    "<h1>🎓 VinUni AI Academic Advisor</h1>"
    "<p>Hỏi bất kỳ điều gì về Quy chế Học vụ VinUniversity — Trả lời kèm trích dẫn điều khoản</p>"
    "</div>",
    unsafe_allow_html=True,
)

if not check_db_ready():
    st.error(
        "**Chưa có dữ liệu!** Vui lòng chạy `python ingest.py` trước để nạp tài liệu vào hệ thống.",
        icon="⚠️",
    )
    st.stop()

# Display chat history
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant":
            result = msg.get("result", {})

            # Sources expander
            if not result.get("guardrail_triggered") and result.get("sources"):
                with st.expander("📎 Nguồn tham khảo"):
                    for src in result["sources"]:
                        page = src["page"]
                        article = src.get("article", "")
                        snippet = src.get("text_snippet", "")
                        label = f"**Trang {page}**"
                        if article:
                            label += f" — {article}"
                        st.markdown(label)
                        st.caption(f"> {snippet}")
                        st.divider()

            # Stale data disclaimer
            ingest_date = result.get("ingest_date")
            if ingest_date and ingest_date != "unknown":
                st.caption(
                    f"ℹ️ Thông tin dựa trên tài liệu cập nhật lúc {ingest_date}. "
                    "Vui lòng kiểm tra trang chính thức của nhà trường để có thông tin mới nhất."
                )

            # Feedback buttons
            if i not in st.session_state.feedback_given:
                col1, col2, col3 = st.columns([1, 1, 4])
                question = st.session_state.messages[i - 1]["content"] if i > 0 else ""

                with col1:
                    if st.button("👍", key=f"up_{i}", help="Câu trả lời hữu ích"):
                        save_feedback(i, "thumbs_up", question, msg["content"])
                        st.session_state.feedback_given.add(i)
                        st.rerun()

                with col2:
                    if st.button("👎", key=f"down_{i}", help="Câu trả lời chưa đúng"):
                        save_feedback(i, "thumbs_down", question, msg["content"])
                        st.session_state.feedback_given.add(i)
                        st.rerun()

                with col3:
                    if st.button("🚩 Báo lỗi", key=f"report_{i}"):
                        save_feedback(i, "error_report", question, msg["content"])
                        st.session_state.feedback_given.add(i)
                        st.toast("Đã ghi nhận báo lỗi. Cảm ơn bạn!", icon="✅")
                        st.rerun()

# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------

if prompt := st.chat_input("Hỏi về quy chế học vụ... (VD: Điều kiện tốt nghiệp là gì?)"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Đang tìm kiếm trong quy chế..."):
            try:
                result = query(prompt)
            except Exception as e:
                result = {
                    "answer": f"Xin lỗi, đã có lỗi xảy ra: {str(e)}\n\nVui lòng thử lại hoặc liên hệ Phòng Đào tạo.",
                    "sources": [],
                    "guardrail_triggered": False,
                    "guardrail_type": None,
                    "ingest_date": "unknown",
                }

        answer = result["answer"]
        st.markdown(answer)

        if not result.get("guardrail_triggered") and result.get("sources"):
            with st.expander("📎 Nguồn tham khảo"):
                for src in result["sources"]:
                    page = src["page"]
                    article = src.get("article", "")
                    snippet = src.get("text_snippet", "")
                    label = f"**Trang {page}**"
                    if article:
                        label += f" — {article}"
                    st.markdown(label)
                    st.caption(f"> {snippet}")
                    st.divider()

        ingest_date = result.get("ingest_date")
        if ingest_date and ingest_date != "unknown":
            st.caption(
                f"ℹ️ Thông tin dựa trên tài liệu cập nhật lúc {ingest_date}. "
                "Vui lòng kiểm tra trang chính thức của nhà trường để có thông tin mới nhất."
            )

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "result": result,
    })
