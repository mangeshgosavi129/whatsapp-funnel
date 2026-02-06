import logging
import time
from logging_config import setup_logging, Logger

def verify_logging():
    print("Setting up logging...")
    setup_logging()
    
    print("Logging test messages...")
    server_logger = Logger.get_logger("server")
    server_logger.info("TEST: This is a server info log")
    server_logger.error("TEST: This is a server error log")
    
    llm_logger = logging.getLogger("llm")
    llm_logger.info("TEST: This is an LLM log")
    
    worker_logger = logging.getLogger("whatsapp_worker")
    worker_logger.info("TEST: This is a worker log")
    
    celery_logger = logging.getLogger("celery")
    celery_logger.info("TEST: This is a celery log")
    
    print("Check logs/ directory now.")

if __name__ == "__main__":
    verify_logging()
