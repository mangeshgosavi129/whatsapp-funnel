import pytz
from datetime import datetime, timedelta
from passlib.context import CryptContext
from fastapi.security import HTTPBearer
import jwt
from server.config import config

ist_tz = pytz.timezone('Asia/Kolkata')

ACCESS_TOKEN_EXPIRE_MINUTES = 1440*30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(ist_tz).replace(tzinfo=None) + expires_delta
    else:
        expire = datetime.now(ist_tz).replace(tzinfo=None) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    to_encode["sub"] = str(to_encode["sub"])
    return jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
