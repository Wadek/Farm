import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.user import User
from app.models.api_key import ApiKey
from app.schemas.user import UserCreate, UserResponse, Token
from app.services.auth_service import hash_password, verify_password, create_token
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=payload.email,
        hashed_password=hash_password(payload.password),
        name=payload.name,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/token", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_token(user.id, user.role))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


class ApiKeyCreate(BaseModel):
    label: str = "default"


@router.post("/api-keys", status_code=201)
def create_api_key(payload: ApiKeyCreate, current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Create a long-lived API key. The plaintext key is returned once — store it."""
    plaintext, key_hash = ApiKey.generate()
    record = ApiKey(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        label=payload.label,
        key_hash=key_hash,
        prefix=plaintext[:12],
    )
    db.add(record)
    db.commit()
    return {
        "id": record.id,
        "label": record.label,
        "key": plaintext,
        "prefix": record.prefix,
        "note": "Store this key now — it will not be shown again.",
    }


@router.get("/api-keys")
def list_api_keys(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    keys = db.query(ApiKey).filter(
        ApiKey.user_id == current_user.id,
        ApiKey.revoked == False,
    ).all()
    return [{"id": k.id, "label": k.label, "prefix": k.prefix, "created_at": k.created_at} for k in keys]


@router.delete("/api-keys/{key_id}", status_code=204)
def revoke_api_key(key_id: str, current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    record = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == current_user.id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Key not found")
    record.revoked = True
    db.commit()
