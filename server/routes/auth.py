from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from server.dependencies import get_db
from server.models import User, Organization
from server.schemas import (
    LoginRequest, 
    LoginResponse, 
    SignupCreateOrgRequest, 
    SignupCreateOrgResponse, 
    SignupJoinOrgRequest, 
    SignupJoinOrgResponse
)
from ..security import hash_password, verify_password, create_access_token
from uuid import UUID

router = APIRouter()

@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    access_token = create_access_token(data={"sub": str(user.id), "org_id": str(user.organization_id)})
    
    return LoginResponse(
        access_token=access_token,
        user_id=user.id,
        organization_id=user.organization_id
    )

@router.post("/signup/create-org", response_model=SignupCreateOrgResponse)
def signup_create_org(payload: SignupCreateOrgRequest, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Create Organization
    new_org = Organization(name=payload.organization_name)
    db.add(new_org)
    db.flush() # To get the org ID
    
    # Create User
    new_user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        organization_id=new_org.id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": str(new_user.id), "org_id": str(new_user.organization_id)})
    
    return SignupCreateOrgResponse(
        access_token=access_token,
        user_id=new_user.id,
        organization_id=new_user.organization_id
    )

@router.post("/signup/join-org", response_model=SignupJoinOrgResponse)
def signup_join_org(payload: SignupJoinOrgRequest, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Check if organization exists
    org = db.query(Organization).filter(Organization.id == payload.organization_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Create User
    new_user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        organization_id=org.id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": str(new_user.id), "org_id": str(new_user.organization_id)})
    
    return SignupJoinOrgResponse(
        access_token=access_token,
        user_id=new_user.id,
        organization_id=new_user.organization_id
    )
