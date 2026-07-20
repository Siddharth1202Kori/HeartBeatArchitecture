import os
import asyncio
from fastapi import FastAPI, Depends, Request, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import db
import session_manager
import timer_manager
from redis_client import init_redis

load_dotenv()

app = FastAPI(
    title="Paralegal Session & Time Tracker API",
    description="Backend API for tracking paralegal workspace sessions and time entries using Redis & Supabase.",
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup and Shutdown Lifespans
background_tasks = set()

@app.on_event("startup")
async def startup_event():
    # Initialize Redis client connection
    await init_redis()
    # Start background heartbeat monitor to clean stale active timers
    loop = asyncio.get_event_loop()
    task = loop.create_task(timer_manager.cleanup_stale_timers_job())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    print("🚀 FastAPI application started successfully.")

# Pydantic schemas for request bodies
class LoginRequest(BaseModel):
    username: str
    password: str

class TimerStatusRequest(BaseModel):
    case_id: str = None
    task_id: str = None
    document_id: str = None

# --- AUTHENTICATION ROUTES ---

@app.post("/api/auth/login")
async def login(login_data: LoginRequest):
    username = login_data.username.strip()
    password = login_data.password
    
    user = db.get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password."
        )
        
    # Verify hashed password
    if not session_manager.verify_password(password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password."
        )
        
    # Create session token and sign it
    jwt_token = await session_manager.create_session(
        user_id=user["id"],
        username=user["username"],
        name=user["name"],
        role=user["role"]
    )
    
    response = JSONResponse(content={
        "status": "success",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "role": user["role"]
        }
    })
    
    # Set secure, HTTP-only cookie
    response.set_cookie(
        key=session_manager.COOKIE_NAME,
        value=jwt_token,
        httponly=True,
        max_age=session_manager.SESSION_EXPIRE_SECONDS,
        samesite="lax",
        secure=False  # Set to True in production with HTTPS
    )
    return response

@app.post("/api/auth/logout")
async def logout(request: Request):
    response = JSONResponse(content={"status": "success", "message": "Logged out successfully."})
    await session_manager.destroy_session(request, response)
    return response

@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(session_manager.get_current_user)):
    return {"status": "success", "user": current_user}

# --- WORKSPACE DATA ROUTES ---

@app.get("/api/workspace/data")
async def get_workspace_info(current_user: dict = Depends(session_manager.get_current_user)):
    """Returns cases, tasks, and documents to populate context lists."""
    return db.get_workspace_data()

# --- TIMER ROUTES ---

@app.get("/api/timer/status")
async def get_timer_status(
    case_id: str = None, 
    task_id: str = None, 
    document_id: str = None, 
    current_user: dict = Depends(session_manager.get_current_user)
):
    """
    Returns active timer state or auto-starts one on access.
    Accepts optional workspace context overrides.
    """
    # Reject admins from creating timers, they only view logs
    if current_user["role"] == "admin":
        return {"status": "inactive", "message": "Admins do not run timers."}
        
    timer = await timer_manager.get_or_create_timer(
        paralegal_id=current_user["user_id"],
        case_id=case_id,
        task_id=task_id,
        document_id=document_id
    )
    return {"status": "active", "timer": timer}

@app.post("/api/timer/heartbeat")
async def timer_heartbeat(current_user: dict = Depends(session_manager.get_current_user)):
    """Heartbeat sent by UI client to verify active browser tab session."""
    if current_user["role"] == "admin":
        return {"status": "ignored"}
        
    timer = await timer_manager.register_heartbeat(current_user["user_id"])
    return {"status": "ok", "timer": timer}

@app.post("/api/timer/pause")
async def pause_active_timer(current_user: dict = Depends(session_manager.get_current_user)):
    if current_user["role"] == "admin":
        raise HTTPException(status_code=403, detail="Admins cannot pause timers.")
        
    timer = await timer_manager.pause_timer(current_user["user_id"])
    return {"status": "paused", "timer": timer}

@app.post("/api/timer/resume")
async def resume_active_timer(current_user: dict = Depends(session_manager.get_current_user)):
    if current_user["role"] == "admin":
        raise HTTPException(status_code=403, detail="Admins cannot resume timers.")
        
    timer = await timer_manager.resume_timer(current_user["user_id"])
    return {"status": "resumed", "timer": timer}

@app.post("/api/timer/stop")
async def stop_and_save_active_timer(
    req: TimerStatusRequest = None,
    current_user: dict = Depends(session_manager.get_current_user)
):
    """
    Stops the active timer, computes duration, and commits time entry to Database.
    Optionally auto-starts a new timer on another task context immediately.
    """
    if current_user["role"] == "admin":
        raise HTTPException(status_code=403, detail="Admins cannot save time entries.")
        
    try:
        entry = await timer_manager.stop_and_save_timer(current_user["user_id"])
        
        # If new context was passed in stop request, start the next context timer right away
        next_timer = None
        if req and req.case_id and req.task_id:
            next_timer = await timer_manager.get_or_create_timer(
                paralegal_id=current_user["user_id"],
                case_id=req.case_id,
                task_id=req.task_id,
                document_id=req.document_id
            )
            
        return {
            "status": "stopped",
            "saved_entry": entry,
            "next_timer": next_timer
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/timer/summary")
async def get_time_summary(
    date: str = None, 
    paralegal_id: str = None,
    current_user: dict = Depends(session_manager.get_current_user)
):
    """
    Gets daily summary of billable time entries.
    Admins can query any paralegal's logs. Paralegals can only query their own.
    """
    query_paralegal_id = paralegal_id
    if current_user["role"] != "admin":
        # Force paralegals to only query their own history
        query_paralegal_id = current_user["user_id"]
        
    entries = db.get_daily_time_entries(paralegal_id=query_paralegal_id, date_str=date)
    return {"status": "success", "entries": entries}

# --- STATIC FILE SERVING ---

# Serve the static UI files under /static
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def redirect_to_index():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    # Auto-initialize SQLite db if needed, then run server
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
