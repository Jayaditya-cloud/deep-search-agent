import os
import sys
import uuid
import json
import csv
import sqlite3
import logging
import threading
from queue import Queue, Empty
from functools import wraps
from flask import (
    Flask, render_template, request, session,
    redirect, url_for, Response, jsonify, stream_with_context
)
from dotenv import load_dotenv

# Load .env file if present
load_dotenv(override=True)

# Ensure project root is importable
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import init_db, get_chat_history, delete_session
from agent.main import run_research_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "deep-research-secret-key-change-me")

# ── Credentials ──────────────────────────────────────────────
APP_USERNAME = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "research123")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(BASE_DIR, "last_session_id.txt")
DB_PATH = os.path.join(BASE_DIR, "agent_memory.db")
EVAL_CSV = os.path.join(BASE_DIR, "evaluation_report.csv")

# Step type → human label + icon mapping (used in SSE events)
STEP_LABELS = {
    "search":      ("Searching the web",         "search"),
    "search_done": ("Sources found",              "check"),
    "fetch":       ("Reading web pages",          "fetch"),
    "fetch_page":  ("Fetching page",              "fetch"),
    "context":     ("Analysing content",          "context"),
    "synthesize":  ("Writing answer",             "synthesize"),
    "error":       ("Error",                      "error"),
}

# ── Init DB on startup ────────────────────────────────────────
init_db(DB_PATH)


# ── Auth decorator ────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_or_create_session_id():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            sid = f.read().strip()
        if sid:
            return sid
    sid = str(uuid.uuid4())
    _write_session_id(sid)
    return sid


def _write_session_id(sid: str):
    with open(SESSION_FILE, "w") as f:
        f.write(sid)


# ── Auth routes ────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username == APP_USERNAME and password == APP_PASSWORD:
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("index"))
        error = "Invalid username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Main UI ────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    session_id = get_or_create_session_id()
    history = get_chat_history(session_id, DB_PATH)
    return render_template("index.html", session_id=session_id, history=history,
                           username=session.get("username", "User"))


# ── Evaluation page ────────────────────────────────────────────
@app.route("/evaluation")
@login_required
def evaluation():
    rows = []
    if os.path.exists(EVAL_CSV):
        with open(EVAL_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    return render_template("evaluation.html", rows=rows,
                           username=session.get("username", "User"))


# ── API: Chat (SSE streaming with step events) ─────────────────
@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data = request.get_json(force=True)
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "Empty query"}), 400

    session_id = get_or_create_session_id()

    # Shared queue: agent thread pushes events, SSE generator consumes them
    event_queue = Queue()

    def progress_cb(step_type, message, extra=None):
        """Called by the agent for each intermediate step."""
        event_queue.put({
            "type": "step",
            "step": step_type,
            "text": message
        })

    def run_agent():
        try:
            response, citations = run_research_agent(
                query,
                chat_history=get_chat_history(session_id, DB_PATH),
                session_id=session_id,
                progress_cb=progress_cb
            )
            event_queue.put({
                "type": "response",
                "text": response,
                "citations": citations  # list of {url, title, domain, snippet}
            })
        except Exception as e:
            logger.exception("Agent error")
            event_queue.put({"type": "error", "text": str(e)})

    thread = threading.Thread(target=run_agent, daemon=True)
    thread.start()

    def generate():
        # Initial thinking signal
        yield f"data: {json.dumps({'type': 'thinking'})}\n\n"

        while True:
            try:
                event = event_queue.get(timeout=120)
            except Empty:
                yield f"data: {json.dumps({'type': 'error', 'text': 'Request timed out.'})}\n\n"
                return

            if event["type"] == "step":
                yield f"data: {json.dumps(event)}\n\n"

            elif event["type"] == "response":
                text = event["text"]
                citations = event["citations"]

                # Stream the text word-by-word for a typing effect
                words = text.split(" ")
                chunk_size = 3
                for i in range(0, len(words), chunk_size):
                    chunk = " ".join(words[i:i + chunk_size])
                    if i + chunk_size < len(words):
                        chunk += " "
                    yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

                # Final event with rich citations
                yield f"data: {json.dumps({'type': 'done', 'citations': citations})}\n\n"
                return

            elif event["type"] == "error":
                yield f"data: {json.dumps(event)}\n\n"
                return

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


# ── API: History ───────────────────────────────────────────────
@app.route("/api/history")
@login_required
def api_history():
    session_id = get_or_create_session_id()
    history = get_chat_history(session_id, DB_PATH)
    return jsonify({"session_id": session_id, "history": history})


# ── API: Reset session ─────────────────────────────────────────
@app.route("/api/reset", methods=["POST"])
@login_required
def api_reset():
    new_sid = str(uuid.uuid4())
    _write_session_id(new_sid)
    return jsonify({"session_id": new_sid, "message": "New session started."})


# ── API: All sessions ──────────────────────────────────────────
@app.route("/api/sessions")
@login_required
def api_sessions():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tm.session_id, tm.user_query, tm.timestamp
                FROM turn_metrics tm
                INNER JOIN (
                    SELECT session_id, MIN(id) as first_id
                    FROM turn_metrics
                    GROUP BY session_id
                ) first ON tm.session_id = first.session_id AND tm.id = first.first_id
                ORDER BY tm.timestamp DESC
                LIMIT 20
            """)
            rows = cursor.fetchall()
            sessions = [
                {"session_id": r[0], "first_query": r[1], "timestamp": r[2]}
                for r in rows
            ]
    except Exception as e:
        logger.error(f"Failed to fetch sessions: {e}")
        sessions = []
    return jsonify({"sessions": sessions})


# ── API: Load a specific session ───────────────────────────────
@app.route("/api/sessions/<session_id>/load", methods=["POST"])
@login_required
def api_load_session(session_id):
    _write_session_id(session_id)
    history = get_chat_history(session_id, DB_PATH)
    return jsonify({"session_id": session_id, "history": history})

# ── API: Delete a specific session ───────────────────────────────
@app.route("/api/sessions/<session_id>", methods=["DELETE"])
@login_required
def api_delete_session(session_id):
    success = delete_session(session_id, DB_PATH)
    if success:
        # If we deleted the active session, start a new one
        current = get_or_create_session_id()
        if current == session_id:
            new_sid = str(uuid.uuid4())
            _write_session_id(new_sid)
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Could not delete session"}), 500


# ── API: Evaluation data ───────────────────────────────────────
@app.route("/api/evaluation")
@login_required
def api_evaluation():
    rows = []
    if os.path.exists(EVAL_CSV):
        with open(EVAL_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    return jsonify({"rows": rows})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n*** Lite Search Web UI ***")
    print(f"   Open http://localhost:{port} in your browser")
    print(f"   Login: {APP_USERNAME} / {APP_PASSWORD}\n")
    app.run(debug=True, port=port, threaded=True)
