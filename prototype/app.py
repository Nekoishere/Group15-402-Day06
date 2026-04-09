import os
import uuid
from flask import (
    Flask, render_template, request, session,
    redirect, url_for, jsonify, flash
)
from dotenv import load_dotenv

load_dotenv()

from config import SUGGESTED_QUESTIONS
from backend.auth import check_credentials, login_required
from backend.memory import ConversationMemory
from backend.pdf_manager import PDFManager
from backend.chatbot import VinLexChatbot

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

# Singletons — initialized once at startup
memory = ConversationMemory()
pdf_manager = PDFManager()
chatbot = VinLexChatbot()


@app.before_request
def ensure_session_id():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())


# ─────────────────────────────────────────────
# Page routes
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template(
        "index.html",
        active_tab="chat",
        suggested_questions=SUGGESTED_QUESTIONS,
    )


@app.route("/contact")
def contact():
    return render_template("contact.html", active_tab="contact")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if check_credentials(username, password):
            session["user"] = username
            return redirect(url_for("index"))
        flash("Tên đăng nhập hoặc mật khẩu không đúng.", "error")
    return render_template("login.html", active_tab="login")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


@app.route("/management")
@login_required
def management():
    pdfs = pdf_manager.list_pdfs()
    return render_template("management.html", active_tab="management", pdfs=pdfs)


# ─────────────────────────────────────────────
# Conversation API
# ─────────────────────────────────────────────

@app.route("/api/conversations", methods=["GET"])
def api_list_conversations():
    sid = session["session_id"]
    convs = memory.get_conversations(sid)
    return jsonify(convs)


@app.route("/api/conversations", methods=["POST"])
def api_create_conversation():
    sid = session["session_id"]
    conv = memory.create_conversation(sid)
    return jsonify(conv), 201


@app.route("/api/conversations/<conv_id>", methods=["DELETE"])
def api_delete_conversation(conv_id):
    sid = session["session_id"]
    deleted = memory.delete_conversation(sid, conv_id)
    if deleted:
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/conversations/<conv_id>/messages", methods=["GET"])
def api_get_messages(conv_id):
    sid = session["session_id"]
    conv = memory.get_conversation(sid, conv_id)
    if conv is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(conv.get("messages", []))


# ─────────────────────────────────────────────
# Chat API
# ─────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    conv_id = data.get("conversation_id")
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"error": "Empty message"}), 400

    sid = session["session_id"]

    # Ensure conversation exists
    if not conv_id:
        conv = memory.create_conversation(sid)
        conv_id = conv["id"]
    else:
        conv = memory.get_conversation(sid, conv_id)
        if conv is None:
            conv = memory.create_conversation(sid)
            conv_id = conv["id"]

    # Save user message
    memory.add_message(sid, conv_id, role="user", content=message)

    # Get recent history for context
    recent = memory.get_recent_messages(sid, conv_id, n=10)
    # Exclude the message we just added (it's the last one)
    history = recent[:-1] if recent else []

    # Process through chatbot
    result = chatbot.process(message, history)

    # Save assistant response
    memory.add_message(
        sid, conv_id,
        role="assistant",
        content=result["answer"],
        sources=result.get("sources", []),
        query_type=result.get("query_type", ""),
    )

    return jsonify({
        "conversation_id": conv_id,
        "answer": result["answer"],
        "sources": result.get("sources", []),
        "query_type": result.get("query_type", ""),
        "redirect_to_contact": result.get("redirect_to_contact", False),
        "suggest_counseling": result.get("suggest_counseling", False),
    })


# ─────────────────────────────────────────────
# PDF Management API
# ─────────────────────────────────────────────

@app.route("/api/pdfs", methods=["GET"])
@login_required
def api_list_pdfs():
    return jsonify(pdf_manager.list_pdfs())


@app.route("/api/pdfs/upload", methods=["POST"])
@login_required
def api_upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename or not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are allowed"}), 400
    pdf_meta = pdf_manager.upload_pdf(f)
    return jsonify(pdf_meta), 201


@app.route("/api/pdfs/<pdf_id>", methods=["DELETE"])
@login_required
def api_delete_pdf(pdf_id):
    deleted = pdf_manager.delete_pdf(pdf_id)
    if deleted:
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/pdfs/<pdf_id>/status", methods=["GET"])
@login_required
def api_pdf_status(pdf_id):
    status = pdf_manager.get_status(pdf_id)
    if status is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"pdf_id": pdf_id, "status": status})


# ─────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, threaded=True, use_reloader=False, port=5000)
