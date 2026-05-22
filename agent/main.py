import os
import sys
import uuid
import logging

# Ensure the root directory is in the path so we can import our root modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_client import WebSearcher
from fetcher import PageFetcher
from context_builder import ContextBuilder
from database import init_db, create_session, record_turn, record_turn_metrics
from llm_client import LLMClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def run_research_agent(query: str, max_search_results: int = 3, chat_history: list = None, session_id: str = None, progress_cb=None):
    """
    Main entry point for the Deep Research Agent.
    Executes a simple linear research loop: Search -> Fetch -> Context -> Summarize.
    
    Args:
        query: The user's research question.
        max_search_results: How many URLs to fetch and analyze.
        chat_history: Optional history of previous queries and responses in the current session.
        session_id: Optional session identifier for persistent memory.
        progress_cb: Optional callable(step_type, message, data=None) for streaming step updates.
        
    Returns:
        tuple: (response_text, citations_list)
               citations_list is a list of dicts: {url, title, domain, snippet}
    """
    def _step(step_type, message, data=None):
        """Helper to emit a progress step."""
        if progress_cb:
            progress_cb(step_type, message, data)
        logger.info(f"[{step_type}] {message}")

    if not session_id:
        session_id = str(uuid.uuid4())
        
    logger.info(f"Research session {session_id} for query: '{query}'")
    
    # 1. Initialize DB and start session
    init_db()
    create_session(session_id, query)
    
    # 2. Search phase
    _step("search", f"Searching the web for: \"{query}\"")
    searcher = WebSearcher()
    record_turn(session_id, "I need to search the web for relevant information.", "search", query, "")
    
    search_results = searcher.search(query, max_results=max_search_results)
    
    if not search_results:
        msg = "No search results found or rate limit exceeded."
        logger.warning(msg)
        _step("error", msg)
        record_turn(session_id, "No results from search engine.", "error", "", msg)
        return "I could not find any information on this topic.", []
        
    _step("search_done", f"Found {len(search_results)} relevant sources")
    record_turn(session_id, f"Found {len(search_results)} search results.", "observation", "", f"Top URL: {search_results[0].url}")
    
    # 3. Fetch phase
    fetcher = PageFetcher()
    fetched_pages = []
    citation_objects = []   # rich dicts: {url, title, domain, snippet}
    
    urls_to_fetch = [res.url for res in search_results]
    _step("fetch", f"Reading {len(urls_to_fetch)} web pages...")
    record_turn(session_id, f"Fetching {len(urls_to_fetch)} pages.", "fetch", str(urls_to_fetch), "")
    
    for i, res in enumerate(search_results, 1):
        _step("fetch_page", f"Reading page {i}/{len(search_results)}: {res.url}")
        page = fetcher.fetch(res.url)
        fetched_pages.append(page)
        if page.text_content:  # Only cite if we actually got text
            # Extract domain for display
            try:
                from urllib.parse import urlparse
                domain = urlparse(res.url).netloc.replace("www.", "")
            except Exception:
                domain = res.url
            citation_objects.append({
                "url": res.url,
                "title": res.title or domain,
                "domain": domain,
                "snippet": res.snippet[:200] if res.snippet else ""
            })
            
    record_turn(session_id, "Finished fetching pages.", "observation", "", f"Successfully fetched {len(citation_objects)} pages.")
    
    # 4. Build Context phase
    _step("context", f"Analysing content from {len(citation_objects)} sources...")
    builder = ContextBuilder()
    context = builder.build(fetched_pages, query)
    record_turn(session_id, "Building combined context for the LLM.", "build_context", "", f"Context size: {len(context)} chars")
    
    # 5. Synthesis phase
    _step("synthesize", "Synthesising a comprehensive answer...")
    if not citation_objects:
        response = "I could not retrieve enough reliable information to answer your query."
    else:
        llm = LLMClient()
        response = llm.generate_response(query, context, chat_history, progress_cb=_step)
        
        if not response:
            response = "Error: LLM generation failed due to missing API key or network error."
        
    record_turn(session_id, "Presenting final answer to the user.", "finish", "", response)
    
    urls_opened_str = ",".join(c["url"] for c in citation_objects) if citation_objects else ""
    record_turn_metrics(
        session_id=session_id,
        user_query=query,
        search_queries=query,
        urls_opened=urls_opened_str,
        context_snippets=context,
        final_answer=response
    )
    
    return response, citation_objects

if __name__ == "__main__":
    import sys
    test_query = sys.argv[1] if len(sys.argv) > 1 else "What is the capital of France?"
    res, cites = run_research_agent(test_query)
    print("\n--- Final Response ---")
    print(res)
    print("\n--- Citations ---")
    for c in cites:
        print(f"- [{c['domain']}] {c['title']} -- {c['url']}")
