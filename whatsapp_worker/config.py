import os
from pathlib import Path
from dotenv import load_dotenv

current_file_path = Path(__file__).resolve()
root_dir = current_file_path.parent.parent
env_path = root_dir / ".env.prod"

if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    print(f"Warning: .env.prod file not found at {env_path}")

class WhatsAppSendConfig:
    def __init__(self) -> None:
        # self.ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
        # self.VERSION = os.getenv("VERSION")
        # self.PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

        self.QUEUE_URL = os.getenv("QUEUE_URL")
        self.AWS_REGION = os.getenv("AWS_REGION")
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
        
        self.SECRET_KEY = os.getenv("SECRET_KEY")
        self.ALGORITHM = os.getenv("ALGORITHM")

        self.INTERNAL_API_BASE_URL = os.getenv("INTERNAL_API_BASE_URL")
        self.INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET") or self.SECRET_KEY

config = WhatsAppSendConfig()