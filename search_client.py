import os
import logging
import requests
from typing import List

from models import SearchResult

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class WebSearcher:
    """
    Client for performing web searches via the Tavily Search API.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initializes the WebSearcher.
        
        Args:
            api_key: The API key for Tavily. If not provided, it attempts to read
                     from the TAVILY_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            logger.warning("No Tavily API key provided. Search might fail if key is required.")
            
        self.base_url = "https://api.tavily.com/search"

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Executes a search query and returns a list of SearchResult objects.
        Handles timeouts and 429 rate limit errors gracefully.
        
        Args:
            query: The search string to look up.
            max_results: Maximum number of search results to return.
            
        Returns:
            List[SearchResult]: A list of parsed search results. Returns an empty 
                                list if the search fails or is rate-limited.
        """
        if not self.api_key:
            logger.error("Cannot perform search: API key is missing.")
            return []

        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False
        }
        
        try:
            logger.info(f"Executing search for query: '{query}'")
            # 10 second timeout to prevent the agent from hanging indefinitely
            response = requests.post(self.base_url, json=payload, timeout=10.0)
            
            # Handle rate limiting specifically
            if response.status_code == 429:
                logger.warning("Rate limit exceeded (HTTP 429) for Tavily API.")
                return []
                
            # Raise an exception for other HTTP errors (4xx, 5xx)
            response.raise_for_status()
            
            data = response.json()
            results_data = data.get("results", [])
            
            parsed_results = []
            for item in results_data:
                # Map Tavily's response keys to our SearchResult dataclass
                parsed_results.append(SearchResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("content", "")
                ))
                
            return parsed_results

        except requests.exceptions.Timeout:
            logger.error(f"Search request timed out for query: '{query}'")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Search request encountered an error: {e}")
            return []
