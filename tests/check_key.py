import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Load .env.dev explicitly
current_file_path = Path(__file__).resolve()
env_path = current_file_path.parent / ".env.dev"

print(f"📂 Loading config from: {env_path}")
load_dotenv(dotenv_path=env_path, override=True)

api_key = os.getenv("GROQ_API_KEY")
model = os.getenv("LLM_MODEL")
base_url = os.getenv("LLM_BASE_URL")

print(f"🔑 Key: {api_key[:10]}...{api_key[-4:] if api_key else 'None'}")
print(f"🧠 Model: {model}")
print(f"🌐 Base URL: {base_url}")

if not api_key or "your_" in api_key:
    print("❌ ERROR: Invalid or placeholder API Key detected.")
    sys.exit(1)

client = OpenAI(
    api_key=api_key,
    base_url=base_url
)

print("\n🔄 Attempting connection to Groq...")

try:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": "Test connection. Reply with 'OK'."}
        ],
        max_tokens=10
    )
    print(f"✅ Success! Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ Connection Failed: {e}")
