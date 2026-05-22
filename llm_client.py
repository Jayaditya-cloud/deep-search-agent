import os
import logging
import requests
import time
from typing import Optional

logger = logging.getLogger(__name__)

class LLMClient:
    """
    A generic client for interacting with the Google Gemini API.
    Uses pure `requests` to remain lightweight and avoid heavy frameworks.
    """
    
    def __init__(self, api_key: str = None, model: str = "gemini-3.5-flash"):
        """
        Initializes the LLMClient.
        
        Args:
            api_key: The API key for Gemini. If not provided, it attempts
                     to read from the GEMINI_API_KEY environment variable.
            model: The name of the model to use.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("No GEMINI_API_KEY provided. LLM generation will fail.")
            
        self.model = model
        # Using Gemini's standard REST endpoint
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    def generate_response(self, query: str, context: str, chat_history: list = None) -> Optional[str]:
        """
        Generates a final synthesized response based on the search context and past chat history.
        
        Args:
            query: The original user query.
            context: The text context assembled by the ContextBuilder.
            chat_history: A list of dicts with {"query": ..., "response": ...}
            
        Returns:
            str: The generated response from the LLM, or None if the request fails.
        """
        if not self.api_key:
            logger.error("Cannot generate response: API key is missing.")
            return None
            
        system_prompt = (
            "You are an expert research assistant. Your task is to answer the user's query "
            "based strictly on the provided research context. If the context does not contain "
            "sufficient information to answer the query, clearly state that you do not have "
            "enough evidence. Do not hallucinate or use outside knowledge."
        )
        
        user_prompt = f"## Context from Web Search\n{context}\n\n## Current User Query\n{query}\n\nProvide a comprehensive answer with citations if possible."
        
        contents = []
        
        # Inject previous conversation history so the LLM remembers past turns
        if chat_history:
            for turn in chat_history:
                contents.append({"role": "user", "parts": [{"text": turn["query"]}]})
                contents.append({"role": "model", "parts": [{"text": turn["response"]}]})
                
        # Add the current query
        contents.append({
            "role": "user",
            "parts": [{"text": user_prompt}]
        })
        
        payload = {
            "contents": contents,
            "systemInstruction": {
                "role": "user",
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": 0.3, # Low temperature for more factual responses
                "maxOutputTokens": 1000
            }
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Gemini takes the API key either as a query param or an x-goog-api-key header
        params = {"key": self.api_key}
        
        max_retries = 6
        backoff = 10.0
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Sending context to Gemini LLM for synthesis (Attempt {attempt+1}/{max_retries})...")
                # 30 second timeout as LLM generation can take a while
                response = requests.post(self.base_url, json=payload, headers=headers, params=params, timeout=30.0)
                
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        logger.warning(f"Rate limit exceeded (HTTP 429) for Gemini API. Retrying in {backoff}s...")
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                    else:
                        logger.warning("Rate limit exceeded (HTTP 429) for Gemini API. No retries remaining.")
                        return "Error: LLM rate limit exceeded."
                    
                response.raise_for_status()
                
                data = response.json()
                # Extract text from Gemini's response structure
                return data["candidates"][0]["content"]["parts"][0]["text"]
                
            except requests.exceptions.Timeout:
                logger.error("LLM request timed out.")
                return "Error: Synthesis request timed out."
            except requests.exceptions.RequestException as e:
                logger.error(f"LLM request encountered an error: {e}")
                if attempt < max_retries - 1:
                    logger.warning(f"Retrying request after error in {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                return f"Error: Failed to generate response ({str(e)})."
            except (KeyError, IndexError) as e:
                logger.error(f"Failed to parse LLM response: {e}")
                return "Error: Unexpected API response format."
        return "Error: Synthesis failed."
