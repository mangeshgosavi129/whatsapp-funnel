"""
LLM Configuration for HTL Pipeline.
Uses Groq for fast, cost-effective inference.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
current_file_path = Path(__file__).resolve()
root_dir = current_file_path.parent.parent
env_path = root_dir / ".env.dev"

if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

class LLMConfig:
    def __init__(self)-> None:  
        self.api_key=os.getenv("GROQ_API_KEY")
        self.model=os.getenv("LLM_MODEL")
        self.base_url=os.getenv("LLM_BASE_URL")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
# Exported configuration object
llm_config = LLMConfig()
