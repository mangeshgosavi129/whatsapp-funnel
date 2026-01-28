import json
import hmac
import hashlib
import logging
from typing import Mapping, Optional, Tuple
import requests
from whatsapp_receive.config import config

logger = logging.getLogger(__name__)

def verify_webhook(params: Mapping[str, str]) -> Tuple[str | Mapping, int]:
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    logger.info("Verification began")
    # Check if token matches (dynamic fetch)
    if mode and token and mode == "subscribe" and challenge:
        if not config.INTERNAL_API_BASE_URL or not config.INTERNAL_API_SECRET:
            return {"status": "error", "message": "Internal API not configured"}, 500
        try:
            resp = requests.get(
                f"http://{config.INTERNAL_API_BASE_URL}/internals/whatsapp/by-verify-token",
                params={"verify_token": token},
                headers={"X-Internal-Secret": config.INTERNAL_API_SECRET},
                timeout=10,
            )
            if resp.status_code == 200:
                return str(challenge), 200
        except Exception as e:
            logger.error(f"Internal verify-token lookup failed: {e}")
            return {"status": "error", "message": "Internal verify-token lookup failed"}, 500
    if not (mode and token):
        return {"status": "error", "message": "Missing parameters"}, 400
    return {"status": "error", "message": "Verification failed"}, 403


def validate_signature(raw_body: bytes, headers: Mapping[str, str]) -> bool:
    signature = headers.get("X-Hub-Signature-256", "")
    if not signature.startswith("sha256="):
        logger.warning("Missing or malformed X-Hub-Signature-256 header")
        return False

    # Dynamic fetch of app_secret based on phone_number_id from webhook payload
    # We MUST have an app_secret to verify. If we can't find it locally or via API, we must fail.
    try:
        body = raw_body.decode("utf-8")
        payload = json.loads(body)
        # Safe traversal to get phone_number_id
        phone_number_id = (
            payload.get("entry", [{}])[0]
            .get("changes", [{}])[0]
            .get("value", {})
            .get("metadata", {})
            .get("phone_number_id")
        )
        
        if phone_number_id:
            resp = requests.get(
                f"http://{config.INTERNAL_API_BASE_URL}/internals/whatsapp/by-phone-number-id/{phone_number_id}",
                headers={"X-Internal-Secret": config.INTERNAL_API_SECRET},
                timeout=10,
            )
            if resp.status_code == 200:
                app_secret = resp.json().get("app_secret")
            else:
                logger.error(f"Internal API returned {resp.status_code} for app_secret fetch")
        else:
            logger.warning("Could not extract phone_number_id from payload for dynamic secret fetch")

    except Exception as e:
        logger.error(f"Error fetching dynamic app_secret: {e}")
        return False

    if not app_secret:
        logger.error("No app_secret found for signature verification. Denying request.")
        return False

    provided = signature[7:]
    expected = hmac.new(bytes(app_secret, "latin-1"), msg=raw_body, digestmod=hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, provided):
        logger.warning("Signature mismatch")
        return False
    
    return True
