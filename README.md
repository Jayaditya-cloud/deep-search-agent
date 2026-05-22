# Lite Search

A robust, web-based research assistant powered by a Large Language Model (Gemini) and Web Search (Tavily). The agent accepts user queries, searches the web, analyzes content, and provides citation-grounded answers with full visibility into its intermediate reasoning steps.

## Deliverables Met
- **Working app**: A responsive web UI built with Flask, providing real-time streaming updates.
- **Web research ingestion**: Utilizes the Tavily Search API to gather accurate and relevant web pages.
- **Persistent sessions**: SQLite database (`agent_memory.db`) tracks conversation history and persists context across turns.
- **Citation-grounded answers**: Responses include inline citations and references (URL/title/domain).
- **Streaming intermediate step updates**: Server-Sent Events (SSE) stream the agent's live actions (searching, reading, analyzing) directly to the UI.
- **Evaluation harness**: Includes an evaluation system that records queries, responses, citation counts, and durations in `evaluation_report.csv`.

---

## Video Demo
*(Insert your video demo link here)*

---

## Setup and Run Instructions

### Prerequisites
- Python 3.8+
- [Tavily API Key](https://tavily.com/)
- [Gemini API Key](https://aistudio.google.com/)

### Installation
1. Clone the repository or download the source code.
2. Install the required dependencies:
   ```bash
   pip install -r requirements_web.txt
   ```
   *(Note: Ensure you have your project's main requirements installed as well if they are in a separate file, e.g., `requests`, `google-generativeai`, etc.)*

### Environment Variables
Copy the `.env.example` file to a new file named `.env`:
```bash
cp .env.example .env
```
Fill in the `.env` file with your actual API keys and credentials:
```env
GEMINI_API_KEY=your_gemini_key_here
TAVILY_API_KEY=your_tavily_key_here

APP_USERNAME=admin
APP_PASSWORD=research123
FLASK_SECRET_KEY=change-me-to-a-long-random-string
PORT=5000
```

### Running the Web App
Execute the main application file:
```bash
python app.py
```
Open your browser and navigate to `http://localhost:5000` (or whatever port you configured).
Login with the credentials specified in your `.env` file (default: `admin` / `research123`).

### Running the CLI (Optional)
If you prefer a terminal interface, you can run:
```bash
python chat.py
```

---

## Hosting and Deployment

Since this application runs on a Python (Flask) backend and utilizes an SQLite database (`agent_memory.db`) to persist search context and conversation logs, **it cannot be hosted on static hosting services like GitHub Pages** (which only supports static HTML/CSS/JS assets). 

Instead, it must be deployed to a cloud platform that supports dynamic Python runtimes and persistent storage. Here are the step-by-step instructions for popular hosting services:

### Option 1: Render (Recommended)
1. **Prepare your repository**:
   - Ensure `requirements_web.txt` contains all dependencies (including `gunicorn`).
2. **Create a Render Web Service**:
   - Log in to [Render](https://render.com/) and click **New > Web Service**.
   - Connect your GitHub repository.
3. **Configure Settings**:
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements_web.txt`
   - **Start Command**: `gunicorn app:app`
4. **Configure Environment Variables**:
   - Under the **Environment** tab, click **Add Environment Variable** and add:
     - `GEMINI_API_KEY`: *(your Gemini key)*
     - `TAVILY_API_KEY`: *(your Tavily key)*
     - `FLASK_SECRET_KEY`: *(a secure random string)*
     - `APP_USERNAME`: `admin` (or your chosen username)
     - `APP_PASSWORD`: `your_secure_password`
5. **Persistent Disk (Optional)**:
   - To make sure the SQLite database `agent_memory.db` persists across service restarts, add a persistent disk in Render under **Disks**:
     - **Mount Path**: `/data`
     - Update the database path in your environment variables to `/data/agent_memory.db`.

### Option 2: Railway
1. **Install Railway CLI** or connect your GitHub account at [Railway.app](https://railway.app/).
2. **Create a New Project**:
   - Choose **Deploy from GitHub repo** and select your repository.
3. **Add Variables**:
   - Add the necessary environment variables (`GEMINI_API_KEY`, `TAVILY_API_KEY`, `FLASK_SECRET_KEY`, `APP_USERNAME`, `APP_PASSWORD`).
4. **Deployment Configuration**:
   - Railway will automatically detect the Python environment and run `gunicorn app:app` or `python app.py` based on your project structure.
   - For database persistence, you can mount a persistent volume and point the database file there.

### Option 3: PythonAnywhere
1. Sign up for a [PythonAnywhere](https://www.pythonanywhere.com/) account.
2. Go to **Consoles > Bash** and clone your repository.
3. Set up a virtualenv and install dependencies:
   ```bash
   mkvirtualenv --python=/usr/bin/python3.10 my-env
   pip install -r requirements_web.txt
   ```
4. Configure the Web App tab:
   - Create a new Flask web app.
   - Set the path to your virtualenv and source code directory.
   - Edit the WSGI configuration file to import your Flask instance:
     ```python
     import sys
     path = '/home/yourusername/yourprojectdir'
     if path not in sys.path:
         sys.path.insert(0, path)
     from app import app as application
     ```
5. Set environment variables using a `.env` file in your project directory or within the WSGI configuration file.

---

## Design Note (Part 1)

### Architecture Overview
The system is divided into three main layers:
1. **Frontend (UI)**: Built with plain HTML, CSS, and vanilla JavaScript. It uses Server-Sent Events (SSE) to display typing effects and real-time step updates (e.g., "Searching the web", "Reading web pages").
2. **Backend (Flask)**: Handles routing, session management, user authentication, and orchestrates the SSE stream. It uses threading to run the agent asynchronously without blocking the web server.
3. **Agent Core (`agent/main.py`)**: The brain of the application. It takes the query, uses `search_client.py` (Tavily) to find sources, fetches page content, and relies on the Gemini LLM to synthesize a final answer based strictly on the retrieved context.

### Persistence
SQLite (`database.py`) is used to store `turn_metrics` and chat history. A `last_session_id.txt` file helps quickly resume the most recent session upon restarting the app.

---

## Example Conversations

**User**: What is the current interest rate set by the US Federal Reserve?
**Agent Response**:
Based on the provided research context, the interest rates set by the US Federal Reserve are as follows:
* **Target Federal Funds Rate:** The Federal Open Market Committee (FOMC) maintains the target federal funds interest rate at a range of 3.50% to 3.75% [1]. This rate was held steady at this range during the April 29, 2026 meeting [2].
* **Benchmark Interest Rate:** The benchmark interest rate in the United States was last recorded at 3.75% [3].
*(Agent lists exact source URLs below)*

**User**: Who is the CEO of the company that acquired GitHub, and where did they go to college?
**Agent Response**:
Based on the provided sources, the company that acquired GitHub is Microsoft, and its CEO is Satya Nadella [1]. However, the provided context does not contain any information regarding where Satya Nadella went to college.

---

## Evaluation Methodology and Findings

The application features an evaluation page and logs metrics into `evaluation_report.csv`. 

### Methodology
We evaluate queries based on several dimensions:
- **Query Type**: Categorized by complexity (factual, multi-hop, insufficient-evidence).
- **Citation Count**: Measuring the number of unique sources grounded in the final response to ensure hallucination reduction.
- **Duration**: Measuring the end-to-end time (in seconds) it takes the agent to search, parse, and synthesize an answer.

### Findings
- **Factual Queries**: Perform exceptionally well, with high citation accuracy and an average duration of ~10 seconds.
- **Multi-hop Queries**: The agent correctly identifies components of complex queries but rightfully refuses to answer parts where context is missing, demonstrating strong hallucination resistance.
- **Insufficient Evidence**: When probed with obscure or undocumented queries, the agent successfully identifies the lack of data and avoids making up facts.

---

## Limitations and Future Improvements

### Limitations
1. **Context Window Size**: Extremely large websites might cause token limit issues with the LLM during context synthesis.
2. **Search API Rate Limits**: Searching is constrained by Tavily's limits and potential HTTP 429 errors.
3. **Single-Agent Pipeline**: Currently follows a linear search-then-synthesize path, without iterative "deep diving" if the first search yields poor results.

### Future Improvements
1. **Deployment**: Since the website is likely to be deployed via GitHub, setting up CI/CD pipelines (e.g., GitHub Actions) to automatically build, test, and deploy the Flask app to a platform like Render or Heroku.
2. **Agentic Loops**: Implementing a "Re-Act" style loop where the agent can choose to search again with a refined query if the initial context was insufficient.
3. **Parallel Processing**: Fetching and parsing web pages concurrently rather than sequentially to drastically reduce response duration.
4. **Vector Database integration**: For long-term memory across drastically different sessions and semantic similarity searches within documents.
