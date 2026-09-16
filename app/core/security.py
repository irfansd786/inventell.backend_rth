from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _encode(payload: dict, expires: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    to_encode = {**payload, 'type': token_type, 'iat': now, 'exp': now + expires}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, role: str) -> str:
    return _encode(
        {'sub': subject, 'role': role},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        'access',
    )


def create_refresh_token(subject: str) -> str:
    return _encode(
        {'sub': subject},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        'refresh',
    )


def decode_token(token: str, expected_type: str = 'access') -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError('Token has expired')
    except jwt.PyJWTError:
        raise ValueError('Invalid token')
    if payload.get('type') != expected_type:
        raise ValueError('Invalid token type')
    return payload
