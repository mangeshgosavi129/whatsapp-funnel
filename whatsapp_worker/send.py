import json
import logging
from typing import Any, Mapping, Tuple
import requests

logger = logging.getLogger(__name__)

def _api_url(version: str, phone_number_id: str) -> str:
    return f"https://graph.facebook.com/{version}/{phone_number_id}/messages"

def _get_text_payload(recipient: str, text: str) -> str:
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

def send_whatsapp_text(
    to: str, 
    message: str,
    access_token: str,
    phone_number_id: str,
    version: str = "v18.0",
) -> Tuple[Mapping, int]:
    """
    Sends a WhatsApp text message.
    
    Arguments:
        to: The recipient's phone number.
        message: The message body.
        access_token: WhatsApp Business API access token.
        phone_number_id: The phone number ID to send from.
        version: Graph API version.
    """
    # Validation
    if not (access_token and phone_number_id and to and message):
        logger.error("Missing WhatsApp configuration or recipient")
        return {"status": "error", "message": "Missing configuration"}, 500

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        # Timeout increased to 15s
        resp = requests.post(
            _api_url(version, phone_number_id), 
            data=_get_text_payload(to, message), 
            headers=headers, 
            timeout=15
        )
        resp.raise_for_status()
        return resp.json(), resp.status_code

    except requests.Timeout:
        logger.error("WhatsApp request timed out")
        return {"status": "error", "message": "Request timed out"}, 408

    except requests.RequestException as e:
        logger.error(f"WhatsApp send error: {e}")
        
        if 'resp' in locals():
             try:
                 return resp.json(), resp.status_code
             except Exception:
                 pass # Fall through to generic error
        return {"status": "error", "message": "Failed to send message"}, 500
