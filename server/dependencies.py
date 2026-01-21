import jwt
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from server.database import SessionLocal
from server.schemas import AuthContext
from server.models import User
from server.config import config
from server.security import security
from uuid import UUID

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_auth_context(
    token: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> AuthContext:
    try:
        payload = jwt.decode(
            token.credentials, 
            config.SECRET_KEY, 
            algorithms=[config.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        
        user = db.query(User).filter(User.id == UUID(user_id)).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        
        return AuthContext(
            user_id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            is_active=user.is_active
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

async def get_ws_auth_context(
    token: str,
    db: Session = Depends(get_db)
) -> Optional[AuthContext]:
    try:
        payload = jwt.decode(
            token, 
            config.SECRET_KEY, 
            algorithms=[config.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        
        user = db.query(User).filter(User.id == UUID(user_id)).first()
        if user is None:
            return None
        
        return AuthContext(
            user_id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            is_active=user.is_active
        )
    except jwt.PyJWTError:
        return None
