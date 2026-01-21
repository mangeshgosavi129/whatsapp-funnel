from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from server.dependencies import get_db, get_auth_context
from server.models import User
from server.schemas import UserOut, UserUpdate, AuthContext
from uuid import UUID

router = APIRouter()

@router.get("/", response_model=List[UserOut])
def get_users(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Get all users for the current organization.
    """
    return db.query(User).filter(User.organization_id == auth.organization_id).all()

@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Get details for a specific user.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.organization_id == auth.organization_id
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user

@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Update user details.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.organization_id == auth.organization_id
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Delete a user.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.organization_id == auth.organization_id
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Optional: Prevent deleting the current user? 
    # For now, let's keep it simple as requested.
    
    db.delete(user)
    db.commit()
    return None
