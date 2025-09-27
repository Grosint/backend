import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.schemas.auth import Token

# Initialize router
router = APIRouter()

# Get logger
logger = logging.getLogger(__name__)


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    # In a real app, authenticate against database
    # This is a simplified example using hardcoded values for demo
    if form_data.username != settings.TEST_USER or not verify_password(
        form_data.password, get_password_hash(settings.TEST_PASSWORD)
    ):
        logger.warning(f"Failed login attempt for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_access_token(data={"sub": form_data.username})

    logger.info(f"Successful login for user: {form_data.username}")

    return {"access_token": access_token, "token_type": "bearer"}


# Note: Using proper password hashing from security.py
