# Lite Search

A robust, web-based research assistant powered by a Large Language Model (Gemini) and Web Search (Tavily). The agent accepts user queries, searches the web, analyzes content, and provides citation-grounded answers with full visibility into its intermediate reasoning steps.

## Core Features
- **Real-time Web Research**: Dynamically queries the web to gather accurate and up-to-date information.
- **Citation-Grounded Answers**: Every fact in the response is backed by inline citations linking directly to the source.
- **Transparent Reasoning**: Watch the agent "think" in real-time as it searches, reads, and analyzes data right on your screen.
- **Persistent Memory**: Chat history and context are saved across sessions, allowing for deep, multi-turn conversations.
- **Responsive Web Interface**: A clean, modern UI accessible from any device.
- **Built-in Evaluation System**: Automatically tracks the agent's accuracy, duration, and citation metrics for continuous improvement.

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

### Target Users and Problem Being Solved
**Target Users**: Students, researchers, professionals, and general users who need accurate, verified information quickly.
**Problem Being Solved**: Traditional LLMs often hallucinate or provide outdated information. This application solves the problem of unreliable AI generation by grounding every answer in real-time, cited web sources, ensuring factual accuracy and transparency.

### Definition of "Deep Research"
For this implementation, "deep research" is defined as an automated, multi-step agentic workflow that goes beyond a simple web search. It involves intelligently querying a search engine, fetching the raw HTML of multiple pages, parsing the text to build a consolidated context window, and synthesizing a final answer that cross-references facts and explicitly cites its sources.

### Success Metrics
To best capture research quality, we measure the following metrics:
1. **Grounding Score**: Measuring how accurately the final response is backed by the retrieved citations.
2. **Correctness Score**: Measuring the factual accuracy and overall usefulness of the response.
3. **Uncertainty Score**: Measuring the agent's ability to handle conflicting sources or admit when there is insufficient evidence (refusal to hallucinate).
4. **Robustness Score**: Measuring the agent's ability to maintain context and accuracy across a multi-turn conversation.

### Data Flow and Components
The system follows a strict linear pipeline:
1. **Search (`search_client.py`)**: The user's query is sent to the Tavily API to retrieve the top relevant URLs and snippets.
2. **Page Fetch (`fetcher.py`)**: The raw HTML of the retrieved URLs is downloaded and parsed into clean text.
3. **Context Selection (`context_builder.py`)**: The text from all sources is aggregated, truncated if necessary, and formatted into a single context block.
4. **Answer Synthesis (`llm_client.py`)**: The Gemini LLM receives the prompt, chat history, and context block to generate the final response with inline citations.

### Risks, Limitations, and Future Improvements
**Risks and Limitations**:
- **Rate Limits**: Heavy reliance on free-tier APIs (Gemini/Tavily) introduces the risk of HTTP 429 rate limit exhaustion, which stalls research.
- **Low-Quality Sources**: The agent relies on the search engine's ranking; if top results are biased or low-quality, the synthesized answer will be affected.
- **Conflicting Sources**: The agent must intelligently navigate disagreements between websites, which can sometimes lead to overly cautious or ambiguous answers.
- **Context Length Limits**: Fetching massive web pages can easily exceed the LLM's token window, requiring aggressive truncation.

**Future Improvements**:
1. **Iterative "Re-Act" Loops**: Allowing the agent to evaluate its own context and choose to execute a *second* search with a refined query if the initial sources were poor.
2. **Parallel Page Fetching**: Currently, pages are downloaded sequentially. Implementing asynchronous fetching (e.g., `asyncio`) would drastically reduce the time-to-answer.

---

## Example Conversations

**User**: Who is the CEO of Apple?
**Agent Response**:
Based on the provided research context, the current CEO of Apple is Tim Cook [1]. He assumed the position in August 2011, succeeding Steve Jobs [2].
*(Agent lists exact source URLs below)*

**User**: Who is the CEO of the company that acquired GitHub, and where did they go to college?
**Agent Response**:
Based on the provided sources, the company that acquired GitHub is Microsoft, and its CEO is Satya Nadella [1]. However, the provided context does not contain any information regarding where Satya Nadella went to college.
*(Agent lists exact source URLs below)*

**User**: What are the key differences between rabi and kharif crops?
**Agent Response**:
Based on the provided context, the key differences are:
* **Sowing Season**: Kharif crops are sown at the beginning of the monsoon season (June/July), while Rabi crops are sown in winter (October/November) [1].
* **Harvesting**: Kharif is harvested in Sept/Oct, whereas Rabi is harvested in spring (April/May) [2].
* **Water Dependency**: Kharif requires significantly more rainfall to thrive compared to Rabi crops [3].
*(Agent lists exact source URLs below)*

**User**: What did the Prime Minister of India have for dinner on May 15th, 2026?
**Agent Response**:
The sources mention that Prime Minister Narendra Modi traveled to Abu Dhabi on May 15th, 2026 [1]. However, the provided context does not contain any factual information regarding what he had for dinner on that specific date.
*(Agent lists exact source URLs below)*

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
