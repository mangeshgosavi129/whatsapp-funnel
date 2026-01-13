import os

#for AWS Lambda, env varibles are set in the dashboard
class WhatsAppReceiveConfig:
    def __init__(self) -> None:
        self.VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
        self.APP_SECRET = os.getenv("APP_SECRET")
        self.ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
        self.VERSION = os.getenv("VERSION")
        self.PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
        self.QUEUE_URL = os.getenv("QUEUE_URL")
        self.AWS_REGION = os.getenv("AWS_REGION_SQS")
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID_SQS")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY_SQS")

config = WhatsAppReceiveConfig()