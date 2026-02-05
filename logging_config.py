import logging
import sys

def setup_logging(level=logging.INFO):
    """
    Centralized logging configuration for all services.
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Minimize noisy logs from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("amqp").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info("Logging configured successfully.")
