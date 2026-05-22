import pytest
from unittest.mock import patch

@pytest.fixture
def mock_tavily_response():
    """Simulates a successful JSON response from the search API."""
    return {
        "results": [
            {
                "title": "Test Source 1",
                "url": "https://example.com/1",
                "content": "This is a relevant snippet about the topic.",
                "score": 0.98
            },
            {
                "title": "SEO Spam Site",
                "url": "https://badsite.com",
                "content": "Buy cheap shoes here. Not relevant.",
                "score": 0.21
            }
        ]
    }

@pytest.fixture
def mock_html_content():
    """Simulates a raw HTML page fetched from the web."""
    return """
    <html>
        <body>
            <nav>Don't scrape this</nav>
            <article>
                <p>This is the core text we actually want to extract.</p>
            </article>
            <script>console.log('Ignore me');</script>
        </body>
    </html>
    """
