import os
import uuid
import json
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from redis_client import get_redis
import db

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-workspace-key-change-in-production-12345")
SESSION_EXPIRE_SECONDS = int(os.getenv("SESSION_EXPIRE_SECONDS", 7200))
COOKIE_NAME = "session_token"

async def create_session(user_id: str, username: str, name: str, role: str) -> str:
    """Creates a session in Redis and returns a signed JWT session token."""
    session_token = str(uuid.uuid4())
    redis = await get_redis()
    
    # Session metadata to store in Redis
    session_data = {
        "user_id": user_id,
        "username": username,
        "name": name,
        "role": role
    }
    
    # Store session in Redis with expiration
    await redis.set(
        f"session:{session_token}", 
        json.dumps(session_data), 
        ex=SESSION_EXPIRE_SECONDS
    )
    
    # Generate signed JWT containing only the session_token
    payload = {
        "session_token": session_token,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=SESSION_EXPIRE_SECONDS)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return token

async def get_current_user(request: Request) -> dict:
    """FastAPI dependency to authenticate requests and get the current user profile from Redis."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        # Check Authorization Header if Cookie is missing (fallback for dev/testing APIs)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided."
        )
        
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        session_token = payload.get("session_token")
        if not session_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token structure."
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token."
        )
        
    # Query session from Redis
    redis = await get_redis()
    session_json = await redis.get(f"session:{session_token}")
    if not session_json:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Active session not found or expired."
        )
        
    session_data = json.loads(session_json)
    
    # Slide session expiration (Extend session life on interaction)
    await redis.set(
        f"session:{session_token}", 
        session_json, 
        ex=SESSION_EXPIRE_SECONDS
    )
    
    return session_data

async def destroy_session(request: Request, response: JSONResponse = None) -> bool:
    """Destroys the session in Redis and clears cookies."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
        
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        session_token = payload.get("session_token")
        if session_token:
            redis = await get_redis()
            await redis.delete(f"session:{session_token}")
    except Exception:
        # Ignore decoding errors on logout
        pass
        
    if response:
        response.delete_cookie(COOKIE_NAME)
    return True

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a hashed bcrypt password."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
