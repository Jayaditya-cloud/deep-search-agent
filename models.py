from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

@dataclass
class SearchQuery:
    """
    Represents a search query to be executed by the agent.
    
    Attributes:
        query: The actual text string to search for.
        max_results: The maximum number of results requested.
    """
    query: str
    max_results: int = 10


@dataclass
class SearchResult:
    """
    Represents a single search result returned from a search engine.
    
    Attributes:
        url: The URL of the search result.
        title: The title of the search result page.
        snippet: A brief snippet or description from the search result.
    """
    url: str
    title: str
    snippet: str


@dataclass
class FetchedPage:
    """
    Represents the parsed content of a fetched web page.
    
    Attributes:
        url: The URL that was fetched.
        html_content: The raw HTML content of the page.
        text_content: The extracted clean text content (parsed using BeautifulSoup).
        status_code: The HTTP status code returned by the fetch request.
        error_message: Any error message encountered during fetching (if applicable).
    """
    url: str
    html_content: str
    text_content: str
    status_code: int
    error_message: Optional[str] = None


@dataclass
class AgentTurn:
    """
    Represents a single turn (thought/action/observation cycle) of the agent.
    
    Attributes:
        session_id: A unique identifier for the current research session.
        thought: The internal reasoning or plan of the agent for this turn.
        action: The type of action taken (e.g., 'search', 'fetch', 'finish').
        action_input: The input for the action (e.g., search query, or URL to fetch).
        observation: The result of the action (e.g., search results summary, or fetched text).
        turn_id: An optional unique identifier for the turn.
        timestamp: When the turn occurred. Defaults to the current UTC time.
    """
    session_id: str
    thought: str
    action: str
    action_input: str
    observation: str
    turn_id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
