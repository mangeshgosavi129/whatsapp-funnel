import logging
import boto3
from typing import Mapping, Optional, Tuple
import json
import base64
from whatsapp_receive.config import config

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
    """
    Push raw webhook payload to SQS for worker to process.
    Signature verification is handled by the worker.
    """
    try:
        # Encode raw_body as base64 for transport
        raw_body_b64 = base64.b64encode(raw_body).decode('utf-8') if raw_body else None
        
        message_payload = {
            "body": body,
            "headers": dict(headers),  # Convert to plain dict
            "raw_body_b64": raw_body_b64,
        }
        
        sqs.send_message(
            QueueUrl=config.QUEUE_URL,
            MessageBody=json.dumps(message_payload)
        )
    except Exception as e:
        logging.error(f"Failed to push to SQS: {str(e)}")
        return {"status": "error", "message": "Queue sync failed"}, 500
    return {"status": "ok"}, 200
