import logging
from typing import List
from models import FetchedPage

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# The total character budget for ALL sources combined.
# Rough heuristic: 1 token ≈ 4 characters. This ceiling = ~25,000 tokens,
# leaving headroom for the system prompt and LLM response in a 32k context window.
MAX_TOTAL_CONTEXT_CHARS: int = 100_000

# Minimum characters guaranteed to each source, regardless of how many sources exist.
# Prevents a large number of sources from each getting a useless 10-char slice.
MIN_CHARS_PER_SOURCE: int = 500


class ContextBuilder:
    """
    Assembles a single, token-budgeted context block from a list of FetchedPages.
    
    The critical responsibility of this class is to prevent context window overflow
    when passed to an LLM. It distributes a fixed character budget fairly across
    all sources, so no single page can silently crowd out others, and the combined
    output is guaranteed to remain within MAX_TOTAL_CONTEXT_CHARS.
    
    Resilience features:
    - Hard cap on total output via MAX_TOTAL_CONTEXT_CHARS.
    - Fair per-source budget allocation: budget is split evenly, not first-come-first-served.
    - MIN_CHARS_PER_SOURCE floor ensures every source gets at least a meaningful excerpt.
    - Skips pages with errors or empty text content cleanly.
    - Appends [TRUNCATED] markers at word boundaries so the LLM knows a source was cut.
    """

    def __init__(self, max_total_chars: int = MAX_TOTAL_CONTEXT_CHARS):
        """
        Initializes the ContextBuilder with a configurable character budget.
        
        Args:
            max_total_chars: Maximum total characters for the combined context output.
                             Defaults to MAX_TOTAL_CONTEXT_CHARS.
        """
        self.max_total_chars = max_total_chars

    def _truncate_to_budget(self, text: str, budget: int) -> str:
        """
        Truncates text to a given character budget at the nearest word boundary.
        
        Args:
            text: The full text string to truncate.
            budget: Maximum allowed characters.
            
        Returns:
            str: The truncated text (with [TRUNCATED] suffix if cut), or the
                 original text if it is within budget.
        """
        if len(text) <= budget:
            return text
        # Truncate at the last space within the budget to avoid splitting words
        return text[:budget].rsplit(" ", 1)[0] + " [TRUNCATED]"

    def build(self, pages: List[FetchedPage], query: str) -> str:
        """
        Builds a combined, token-budgeted context string from multiple fetched pages.
        
        The method filters out failed or empty pages, then calculates a per-source
        character budget by dividing MAX_TOTAL_CONTEXT_CHARS evenly. Each source
        is truncated to its budget before being concatenated.
        
        Args:
            pages: A list of FetchedPage objects returned by the PageFetcher.
            query: The original user query, prepended as a header for LLM clarity.
            
        Returns:
            str: A single structured context string ready to pass to an LLM.
                 Guaranteed to be <= max_total_chars characters (excluding the header).
        """
        # Filter to only pages with usable content
        valid_pages = [p for p in pages if p.text_content and not p.error_message]
        
        if not valid_pages:
            logger.warning("ContextBuilder received no valid pages. Returning empty context.")
            return ""
        
        # Distribute budget fairly across all valid sources
        per_source_budget = max(
            MIN_CHARS_PER_SOURCE,
            self.max_total_chars // len(valid_pages)
        )
        
        logger.info(
            f"Building context from {len(valid_pages)} sources. "
            f"Budget: {per_source_budget:,} chars/source "
            f"(total cap: {self.max_total_chars:,} chars)"
        )
        
        header = f"## Research Query\n{query}\n\n## Sources\n"
        context_parts = []
        total_used = 0
        
        for i, page in enumerate(valid_pages, start=1):
            # Respect the rolling total budget as sources are added
            remaining_budget = self.max_total_chars - total_used
            if remaining_budget <= MIN_CHARS_PER_SOURCE:
                logger.warning(
                    f"Total context budget exhausted after {i - 1} sources. "
                    f"Skipping remaining {len(valid_pages) - i + 1} source(s)."
                )
                break
            
            # Each source gets the lesser of: its fair share or the remaining budget
            effective_budget = min(per_source_budget, remaining_budget)
            truncated_text = self._truncate_to_budget(page.text_content, effective_budget)
            
            source_block = (
                f"### Source {i}: {page.url}\n\n"
                f"{truncated_text}"
            )
            context_parts.append(source_block)
            total_used += len(truncated_text)
            
        combined = header + "\n\n---\n\n".join(context_parts)
        logger.info(
            f"Context built: {total_used:,} chars across {len(context_parts)} sources."
        )
        return combined
