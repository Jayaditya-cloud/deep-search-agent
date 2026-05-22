import sys
import os
import requests
import pytest
from unittest.mock import patch

# Add the parent directory to sys.path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetcher import PageFetcher

def test_html_extraction(mock_html_content):
    """Test that BeautifulSoup properly extracts core text and ignores scripts/nav."""
    fetcher = PageFetcher()
    clean_text = fetcher._parse_html(mock_html_content)
    
    # Assertions to ensure our parser works correctly
    assert "This is the core text we actually want to extract." in clean_text
    assert "Ignore me" not in clean_text
    assert "Don't scrape this" not in clean_text

@patch('fetcher.requests.get')
def test_fetch_timeout_handling(mock_get):
    """Test that the app doesn't crash if a website takes too long to load."""
    
    # Force the mock to simulate a timeout
    mock_get.side_effect = requests.exceptions.Timeout("Timeout")
    
    fetcher = PageFetcher(timeout=1.0)
    result = fetcher.fetch("https://example.com")
    
    # Our function should catch this and return a FetchedPage with an error message
    assert result.url == "https://example.com"
    assert result.error_message is not None
    assert "timed out" in result.error_message
    assert result.status_code == 0
    assert result.text_content == ""