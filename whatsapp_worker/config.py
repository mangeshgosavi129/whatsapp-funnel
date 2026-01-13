import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve paths
current_file_path = Path(__file__).resolve()
root_dir = current_file_path.parent.parent
env_path = root_dir / ".env.dev"

# Load env variables
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    print(f"Warning: .env.dev file not found at {env_path}")

class WhatsAppSendConfig:
    def __init__(self):
        self.SECRET_KEY = os.getenv("SECRET_KEY")
        self.ALGORITHM = os.getenv("ALGORITHM")

config = WhatsAppSendConfig()
