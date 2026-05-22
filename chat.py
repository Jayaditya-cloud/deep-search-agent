import os
import sys
import uuid

# Ensure the root directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.main import run_research_agent
from database import get_chat_history, init_db
from dotenv import load_dotenv

load_dotenv(override=True)

def main():
    print("========================================")
    print("🔍 Welcome to Lite Search! 🔍")
    print("========================================")
    
    tavily_key = os.getenv("TAVILY_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not tavily_key or not gemini_key:
        print("\n⚠️ WARNING: Missing API Keys ⚠️")
        print("Your agent will not work correctly without real API keys.")
        if not tavily_key:
            print("- Missing TAVILY_API_KEY (Get one at https://tavily.com/)")
        if not gemini_key:
            print("- Missing GEMINI_API_KEY (Get one at https://aistudio.google.com/)")
        print("\nPlease set them in your terminal before running tests, for example:")
        print("set TAVILY_API_KEY=tvly-your_real_key_here")
        print("set GEMINI_API_KEY=AIzaSy...your_real_key_here\n")
        
    session_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_session_id.txt")
    
    # Ensure database is initialized (creates new tables if they don't exist)
    init_db()
    
    # Auto-resume logic
    if os.path.exists(session_file):
        with open(session_file, "r") as f:
            session_id = f.read().strip()
        print(f"\n[Resuming previous session: {session_id}]")
        chat_history = get_chat_history(session_id)
        if chat_history:
            print(f"Loaded {len(chat_history)} past turns from memory.")
    else:
        session_id = str(uuid.uuid4())
        with open(session_file, "w") as f:
            f.write(session_id)
        print(f"\n[Started new session: {session_id}]")
        chat_history = []
        
    while True:
        try:
            query = input("\nWhat would you like me to research? (type 'quit' to exit)\n> ")
            if query.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
                
            if query.lower() in ['reset', 'new']:
                if os.path.exists(session_file):
                    os.remove(session_file)
                session_id = str(uuid.uuid4())
                with open(session_file, "w") as f:
                    f.write(session_id)
                chat_history = []
                print(f"\n[🧹 Started a brand new session: {session_id}]")
                continue
                
            if not query.strip():
                continue
                
            print("\n🔍 Researching...")
            response, citations = run_research_agent(query, chat_history=chat_history, session_id=session_id)
            
            # Save the turn to history for memory
            if response and not response.startswith("Error:"):
                chat_history.append({"query": query, "response": response})
            
            print("\n" + "="*50)
            print("📝 AGENT RESPONSE:")
            print("="*50)
            print(response)
            
            if citations:
                print("\n🔗 SOURCES USED:")
                for i, cite in enumerate(citations, 1):
                    print(f"[{i}] {cite}")
            print("="*50)
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break

if __name__ == "__main__":
    main()
