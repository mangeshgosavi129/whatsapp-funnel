import boto3
import json
import logging
from typing import Mapping, Optional, Tuple
from whatsapp_receive.config import config
from whatsapp_receive.security import validate_signature

# Initialize SQS client outside the function for better performance (warm starts)
sqs = boto3.client(
    'sqs',
    region_name=config.AWS_REGION,
    aws_access_key_id=config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
)

def push_to_queue(
    body: Mapping,
    headers: Mapping[str, str],
    raw_body: Optional[bytes] = None,
) -> Tuple[Mapping, int]:
    if not validate_signature(raw_body, headers):
        return {"status": "error", "message": "Invalid signature"}, 403
    
    # --- SQS Logic Starts Here ---
    try:
        message_body = json.dumps(body)
        sqs.send_message(
            QueueUrl=config.QUEUE_URL,
            MessageBody=message_body
        )    
    except Exception as e:
        logging.error(f"Failed to push to SQS: {str(e)}")
        return {"status": "error", "message": "Queue sync failed"}, 500
    return {"status": "ok"}, 200
