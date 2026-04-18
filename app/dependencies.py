from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.user import User, UserRole
from app.services.auth_service import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    # Try API key first (X-API-Key header)
    api_key_raw = request.headers.get("X-API-Key")
    if api_key_raw:
        from app.models.api_key import ApiKey
        from sqlalchemy import func as sqlfunc
        key_hash = ApiKey.hash(api_key_raw)
        record = db.query(ApiKey).filter(
            ApiKey.key_hash == key_hash,
            ApiKey.revoked == False,
        ).first()
        if not record:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        record.last_used_at = sqlfunc.now()
        db.commit()
        user = db.query(User).filter(User.id == record.user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user

    # Fall back to JWT Bearer
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        token_data = decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_farmer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.farmer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Farmers only")
    return current_user


def require_buyer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.buyer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Buyers only")
    return current_user
