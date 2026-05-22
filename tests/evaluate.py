import json
import csv
from time import time
import sys
import os
import requests
import uuid

# Add the parent directory to sys.path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.main import run_research_agent # Your main agent entry point
from dotenv import load_dotenv
load_dotenv(override=True)

# Extended dataset fulfilling all criteria
TEST_DATASET = [
    {
        "id": 1,
        "type": "factual",
        "query": "Who is the ceo of apple?"
    },
    {
        "id": 2,
        "type": "multi-hop",
        "query": "Who is the CEO of the company that acquired GitHub, and where did they go to college?"
    },
    {
        "id": 3,
        "type": "insufficient-evidence",
        "query": "what did the prime minister of India had for dinner on 15th may 2026"
    },
    {
        "id": 4,
        "type": "comparison",
        "query": "What are the key differences between rabi and kharif crops?"
    },
    {
        "id": 5,
        "type": "conflicting-sources",
        "query": "Is drinking coffee good for your heart? Explain the different perspectives."
    }
]

MULTI_TURN_TESTS = [
    "Which is the 20th element on the periodic table?",
    "What is its atomic mass, and which element is isobar to this element?"
]

def evaluate_with_llm(query, response, citations, chat_history=None):
    """Uses LLM-as-a-judge to evaluate the quality of the response."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Missing API key for evaluation.")
        return {"grounding_score": 0, "correctness_score": 0, "uncertainty_score": 0, "reasoning": "No API key"}
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
    
    prompt = f"""
    Evaluate the following response to a user query.
    User Query: {query}
    Previous Chat History (if any): {json.dumps(chat_history) if chat_history else "None"}
    Response: {response}
    Number of Citations provided: {len(citations)}

    Score the response on a scale of 1 to 5 for each of the following criteria:
    1. grounding_score: How well is the answer grounded in citations?
    2. correctness_score: How correct and useful is the answer?
    3. uncertainty_score: How well does it handle uncertainty or conflicting information?

    Respond ONLY with a valid JSON object in this format:
    {{
        "grounding_score": 5,
        "correctness_score": 4,
        "uncertainty_score": 5,
        "reasoning": "A brief explanation of the scores."
    }}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
    }
    
    max_retries = 6
    backoff = 10.0
    
    for attempt in range(max_retries):
        try:
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30.0)
            if res.status_code == 429:
                if attempt < max_retries - 1:
                    print(f"Evaluator rate limit hit. Retrying in {backoff}s...")
                    import time as time_module
                    time_module.sleep(backoff)
                    backoff *= 2
                    continue
                else:
                    print("Evaluator rate limit hit. No retries remaining.")
                    res.raise_for_status()
            res.raise_for_status()
            data = res.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except Exception as e:
            if attempt < max_retries - 1:
                safe_error = str(e).replace(api_key, "[REDACTED_API_KEY]") if api_key else str(e)
                print(f"Evaluator error: {safe_error}. Retrying in {backoff}s...")
                import time as time_module
                time_module.sleep(backoff)
                backoff *= 2
                continue
            error_msg = str(e).replace(api_key, "[REDACTED_API_KEY]")
            return {"grounding_score": 0, "correctness_score": 0, "uncertainty_score": 0, "reasoning": error_msg}

def run_evaluation():
    print("Starting Lite Search Evaluation...")
    results = []

    # Single-turn evaluation
    for item in TEST_DATASET:
        print(f"Testing Query [{item['type']}]: {item['query']}")
        start_time = time()
        
        session_id = str(uuid.uuid4())
        response, citations = run_research_agent(item['query'], session_id=session_id)
        
        duration = time() - start_time
        
        # Add a sleep to prevent hitting Gemini's API rate limits between generation and evaluation
        import time as time_module
        time_module.sleep(30)
        
        eval_scores = evaluate_with_llm(item['query'], response, citations)
        
        results.append({
            "id": f"single_{item['id']}",
            "query": item["query"],
            "type": item["type"],
            "response": response,
            "citations_count": len(citations),
            "duration_seconds": round(duration, 2),
            "grounding_score": eval_scores.get("grounding_score", 0),
            "correctness_score": eval_scores.get("correctness_score", 0),
            "uncertainty_score": eval_scores.get("uncertainty_score", 0),
            "robustness_score": "N/A",  # Not applicable for single turn
            "eval_reasoning": eval_scores.get("reasoning", "")
        })
        
        # Additional sleep between iterations
        time_module.sleep(30)

    # Multi-turn evaluation for robustness
    print("\nStarting Multi-turn Robustness Evaluation...")
    session_id = str(uuid.uuid4())
    chat_history = []
    
    robustness_scores = []
    for i, query in enumerate(MULTI_TURN_TESTS):
        print(f"Testing Multi-turn Query {i+1}: {query}")
        start_time = time()
        
        response, citations = run_research_agent(query, session_id=session_id, chat_history=chat_history)
        
        duration = time() - start_time
        
        import time as time_module
        time_module.sleep(30)
        
        eval_scores = evaluate_with_llm(query, response, citations, chat_history)
        
        # Robustness is partly correctness and partly retaining context
        # We can approximate robustness by averaging its performance over the turns
        robustness_scores.append(eval_scores.get("correctness_score", 0))
        
        results.append({
            "id": f"multi_{i+1}",
            "query": query,
            "type": "multi-turn",
            "response": response,
            "citations_count": len(citations),
            "duration_seconds": round(duration, 2),
            "grounding_score": eval_scores.get("grounding_score", 0),
            "correctness_score": eval_scores.get("correctness_score", 0),
            "uncertainty_score": eval_scores.get("uncertainty_score", 0),
            "robustness_score": eval_scores.get("correctness_score", 0),
            "eval_reasoning": eval_scores.get("reasoning", "")
        })
        
        chat_history.append({"query": query, "response": response})
        time_module.sleep(30)

    # Output to CSV for your final report
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(root_dir, "evaluation_report.csv")
    
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
        
    print("\n--- SUMMARY OF RESULTS ---")
    avg_grounding = sum(r["grounding_score"] for r in results) / len(results)
    avg_correctness = sum(r["correctness_score"] for r in results) / len(results)
    avg_uncertainty = sum(r["uncertainty_score"] for r in results) / len(results)
    
    multi_turn_results = [r for r in results if r["type"] == "multi-turn"]
    avg_robustness = sum(r["robustness_score"] for r in multi_turn_results) / len(multi_turn_results) if multi_turn_results else 0
    
    print(f"Average Grounding & Citation Score: {avg_grounding:.2f}/5")
    print(f"Average Correctness & Usefulness Score: {avg_correctness:.2f}/5")
    print(f"Average Uncertainty & Conflicts Handling Score: {avg_uncertainty:.2f}/5")
    print(f"Average Robustness Score (Multi-turn): {avg_robustness:.2f}/5")
    
    print(f"\nEvaluation complete. Check {csv_path} for detailed records including intermediate artifacts.")

if __name__ == "__main__":
    run_evaluation()