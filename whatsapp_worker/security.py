import json
import hmac
import hashlib
import logging
from typing import Mapping

import pytz
from datetime import datetime, timedelta
from passlib.context import CryptContext
from fastapi.security import HTTPBearer
import jwt
import requests

from whatsapp_worker.config import config

logger = logging.getLogger(__name__)
ist_tz = pytz.timezone('Asia/Kolkata')

ACCESS_TOKEN_EXPIRE_MINUTES = 5

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(ist_tz).replace(tzinfo=None) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    to_encode["sub"] = str(to_encode["sub"])
    return jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)


def validate_signature(raw_body: bytes, headers: Mapping[str, str]) -> bool:
    """
    Validate the webhook signature from Meta/WhatsApp.
    Uses HMAC-SHA256 with the app_secret fetched from internal API.
    """
    signature = headers.get("x-hub-signature-256", headers.get("X-Hub-Signature-256", ""))
    if not signature.startswith("sha256="):
        logger.warning("Missing or malformed X-Hub-Signature-256 header")
        return False

    # Dynamic fetch of app_secret based on phone_number_id from webhook payload
    app_secret = None
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
                f"{config.INTERNAL_API_BASE_URL}/internals/whatsapp/by-phone-number-id/{phone_number_id}",
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
