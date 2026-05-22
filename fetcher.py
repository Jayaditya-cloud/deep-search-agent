import logging
import requests
from bs4 import BeautifulSoup
from models import FetchedPage

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Hard ceiling on raw HTML bytes to prevent memory exhaustion on massive pages.
# Pages beyond this limit are truncated before being handed to BeautifulSoup.
MAX_HTML_BYTES: int = 2_000_000  # 2 MB

# Hard ceiling on extracted plain text characters per page.
# Prevents a single page from dominating the LLM context window.
MAX_TEXT_CHARS: int = 15_000

# Tags that are guaranteed to produce noise (CSS, JS) and never useful text.
NOISE_TAGS: list = ["script", "style", "noscript", "header", "footer", "nav", "aside"]


class PageFetcher:
    """
    Fetches web pages via HTTP and extracts clean plain text using BeautifulSoup.
    
    This class is strictly scoped to fetching and parsing. It does NOT perform
    search API calls (see search_client.py) or context assembly (see context_builder.py).
    
    Resilience features:
    - Streams response bytes and enforces a MAX_HTML_BYTES cap to prevent
      memory exhaustion from large or malicious pages.
    - Strips all <script>, <style>, and other noise tags before parsing,
      preventing massive inline CSS/JS from inflating the DOM tree.
    - Truncates final extracted text to MAX_TEXT_CHARS characters.
    """

    def __init__(self, timeout: float = 10.0):
        """
        Initializes the PageFetcher.
        
        Args:
            timeout: Seconds to wait for the server to respond before giving up.
        """
        self.timeout = timeout
        self.headers = {
            "User-Agent": "DeepResearchAgent/1.0 (Academic Research Bot)"
        }

    def _stream_with_cap(self, response: requests.Response) -> str:
        """
        Reads response content in chunks, stopping at MAX_HTML_BYTES.
        
        This is the critical guard against memory exhaustion. Instead of calling
        response.text (which loads the full body), we stream and bail early.
        
        Args:
            response: An active requests.Response object with streaming enabled.
            
        Returns:
            str: The raw HTML content, capped at MAX_HTML_BYTES.
        """
        chunks = []
        total_bytes = 0
        
        for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
            if chunk:
                # decode_unicode=True asks requests to decode, but some servers
                # send no Content-Encoding header so the chunk stays as bytes.
                # Handle both types safely.
                if isinstance(chunk, bytes):
                    total_bytes += len(chunk)
                    chunks.append(chunk.decode("utf-8", errors="replace"))
                else:
                    total_bytes += len(chunk.encode("utf-8", errors="replace"))
                    chunks.append(chunk)
                
                if total_bytes >= MAX_HTML_BYTES:
                    logger.warning(
                        f"Page exceeds {MAX_HTML_BYTES:,} byte limit. "
                        f"Truncating HTML before parsing."
                    )
                    break
                    
        return "".join(chunks)


    def _parse_html(self, html: str) -> str:
        """
        Parses HTML into clean plain text using BeautifulSoup.
        
        Strips all noise tags (script, style, nav, etc.) before parsing so that
        BeautifulSoup never processes inline CSS or JavaScript. The resulting
        text is then capped at MAX_TEXT_CHARS to enforce a per-page budget.
        
        Args:
            html: Raw HTML content (potentially already byte-capped).
            
        Returns:
            str: Clean, extracted text content, truncated to MAX_TEXT_CHARS.
        """
        soup = BeautifulSoup(html, "html.parser")
        
        # Decompose (remove) all noise tags from the parse tree BEFORE
        # calling get_text(). This prevents CSS/JS from polluting the output
        # and significantly reduces the memory footprint of the DOM tree.
        for tag in soup.find_all(NOISE_TAGS):
            tag.decompose()
            
        text = soup.get_text(separator=" ", strip=True)
        
        # Normalize whitespace collapsed by get_text into single spaces
        text = " ".join(text.split())
        
        if len(text) > MAX_TEXT_CHARS:
            logger.warning(
                f"Extracted text ({len(text):,} chars) exceeds {MAX_TEXT_CHARS:,} char limit. "
                f"Truncating."
            )
            # Truncate cleanly at the last word boundary within the limit
            text = text[:MAX_TEXT_CHARS].rsplit(" ", 1)[0] + " [TRUNCATED]"
            
        return text

    def fetch(self, url: str) -> FetchedPage:
        """
        Fetches a URL and returns a FetchedPage with extracted text content.
        
        This method is resilient to:
        - Large pages (streaming + byte cap)
        - Malformed HTML with massive inline CSS (noise tag decomposition)
        - Network timeouts and HTTP errors (returns FetchedPage with error_message)
        
        Args:
            url: The URL to fetch.
            
        Returns:
            FetchedPage: A dataclass containing the URL, raw HTML (capped),
                         extracted text, HTTP status code, and any error message.
        """
        try:
            logger.info(f"Fetching: {url}")
            
            # stream=True is critical — prevents requests from loading the entire
            # response body into memory before we get a chance to cap it.
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                stream=True
            )
            response.raise_for_status()
            
            html_content = self._stream_with_cap(response)
            text_content = self._parse_html(html_content)
            
            logger.info(
                f"Successfully fetched '{url}' "
                f"({len(html_content):,} HTML chars -> {len(text_content):,} text chars)"
            )
            
            return FetchedPage(
                url=url,
                html_content=html_content,
                text_content=text_content,
                status_code=response.status_code
            )
            
        except requests.exceptions.Timeout:
            msg = f"Request timed out after {self.timeout}s"
            logger.error(f"{msg} for URL: {url}")
            return FetchedPage(url=url, html_content="", text_content="", status_code=0, error_message=msg)
            
        except requests.exceptions.HTTPError as e:
            msg = f"HTTP error: {e.response.status_code}"
            logger.error(f"{msg} for URL: {url}")
            return FetchedPage(url=url, html_content="", text_content="", status_code=e.response.status_code, error_message=msg)
            
        except requests.exceptions.RequestException as e:
            msg = f"Network error: {e}"
            logger.error(f"{msg} for URL: {url}")
            return FetchedPage(url=url, html_content="", text_content="", status_code=0, error_message=str(e))
