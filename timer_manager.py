import json
import asyncio
from datetime import datetime, timezone
from redis_client import get_redis
import db

async def get_or_create_timer(paralegal_id: str, case_id: str = None, task_id: str = None, document_id: str = None) -> dict:
    """Gets the active timer for a paralegal, or auto-starts one with the specified or fallback context."""
    redis = await get_redis()
    timer_key = f"active_timer:{paralegal_id}"
    
    timer_json = await redis.get(timer_key)
    if timer_json:
        return json.loads(timer_json)
        
    # Auto-start timer: If context is not supplied, fetch defaults from database
    if not case_id or not task_id:
        data = db.get_workspace_data()
        if data["cases"]:
            case_id = case_id or data["cases"][0]["id"]
            # Find a task corresponding to the case
            case_tasks = [t for t in data["tasks"] if t["case_id"] == case_id]
            if case_tasks:
                task_id = task_id or case_tasks[0]["id"]
            elif data["tasks"]:
                task_id = task_id or data["tasks"][0]["id"]
                
    if not case_id or not task_id:
        # Fallbacks in case seed data is missing
        case_id = "00000000-0000-0000-0000-000000000000"
        task_id = "00000000-0000-0000-0000-000000000000"

    now_iso = datetime.now(timezone.utc).isoformat()
    
    new_timer = {
        "case_id": case_id,
        "task_id": task_id,
        "document_id": document_id,
        "start_time": now_iso,
        "last_heartbeat": now_iso,
        "accumulated_seconds": 0,
        "is_paused": False,
        "last_paused_or_resumed_at": now_iso
    }
    
    await redis.set(timer_key, json.dumps(new_timer))
    print(f"⏱️ [AUTO-START] Started new timer for paralegal {paralegal_id} on case {case_id}, task {task_id}")
    return new_timer

async def pause_timer(paralegal_id: str) -> dict:
    """Pauses the active timer and accumulates the elapsed duration."""
    redis = await get_redis()
    timer_key = f"active_timer:{paralegal_id}"
    
    timer_json = await redis.get(timer_key)
    if not timer_json:
        # Auto-start a new timer if none exists, then pause it
        timer = await get_or_create_timer(paralegal_id)
        timer_json = json.dumps(timer)
        
    timer = json.loads(timer_json)
    
    if timer["is_paused"]:
        return timer
        
    now = datetime.now(timezone.utc)
    last_resumed = datetime.fromisoformat(timer["last_paused_or_resumed_at"])
    elapsed = int((now - last_resumed).total_seconds())
    
    timer["accumulated_seconds"] += max(0, elapsed)
    timer["is_paused"] = True
    timer["last_paused_or_resumed_at"] = now.isoformat()
    timer["last_heartbeat"] = now.isoformat()
    
    await redis.set(timer_key, json.dumps(timer))
    print(f"⏸️ [PAUSE] Paused timer for paralegal {paralegal_id}. Accumulated: {timer['accumulated_seconds']}s")
    return timer

async def resume_timer(paralegal_id: str) -> dict:
    """Resumes a paused timer."""
    redis = await get_redis()
    timer_key = f"active_timer:{paralegal_id}"
    
    timer_json = await redis.get(timer_key)
    if not timer_json:
        return await get_or_create_timer(paralegal_id)
        
    timer = json.loads(timer_json)
    
    if not timer["is_paused"]:
        return timer
        
    now_iso = datetime.now(timezone.utc).isoformat()
    timer["is_paused"] = False
    timer["last_paused_or_resumed_at"] = now_iso
    timer["last_heartbeat"] = now_iso
    
    await redis.set(timer_key, json.dumps(timer))
    print(f"▶️ [RESUME] Resumed timer for paralegal {paralegal_id}.")
    return timer

async def register_heartbeat(paralegal_id: str) -> dict:
    """Updates the heartbeat timestamp of the active timer to keep it alive."""
    redis = await get_redis()
    timer_key = f"active_timer:{paralegal_id}"
    
    timer_json = await redis.get(timer_key)
    if not timer_json:
        # If timer key expired/was cleared but browser is still sending heartbeats, auto-restart it
        return await get_or_create_timer(paralegal_id)
        
    timer = json.loads(timer_json)
    now_iso = datetime.now(timezone.utc).isoformat()
    timer["last_heartbeat"] = now_iso
    
    # Optional: If not paused, check if we need to sync/adjust time drift
    await redis.set(timer_key, json.dumps(timer))
    return timer

async def stop_and_save_timer(paralegal_id: str) -> dict:
    """Stops the active timer, calculates final duration, and persists it to the database."""
    redis = await get_redis()
    timer_key = f"active_timer:{paralegal_id}"
    
    timer_json = await redis.get(timer_key)
    if not timer_json:
        raise ValueError("No active timer found to save.")
        
    timer = json.loads(timer_json)
    
    # Calculate final duration
    total_seconds = timer["accumulated_seconds"]
    now = datetime.now(timezone.utc)
    
    if not timer["is_paused"]:
        last_resumed = datetime.fromisoformat(timer["last_paused_or_resumed_at"])
        elapsed = int((now - last_resumed).total_seconds())
        total_seconds += max(0, elapsed)
        
    # Write to database (Supabase or SQLite)
    entry = db.create_time_entry(
        paralegal_id=paralegal_id,
        case_id=timer["case_id"],
        task_id=timer["task_id"],
        document_id=timer["document_id"],
        start_time=timer["start_time"],
        end_time=now.isoformat(),
        duration_seconds=total_seconds
    )
    
    # Clear active state in Redis
    await redis.delete(timer_key)
    print(f"💾 [STOP & SAVE] Persisted time entry of {total_seconds}s for paralegal {paralegal_id} to DB.")
    return entry

async def cleanup_stale_timers_job():
    """Background task to detect missed heartbeats (>30 seconds) and auto-flush logs to Supabase."""
    print("🔄 Starting background heartbeat cleanup job loop...")
    while True:
        try:
            await asyncio.sleep(15)  # Scan every 15 seconds
            redis = await get_redis()
            keys = await redis.keys("active_timer:*")
            
            if not keys:
                continue
                
            now = datetime.now(timezone.utc)
            
            for key in keys:
                paralegal_id = key.split(":")[-1]
                timer_json = await redis.get(key)
                if not timer_json:
                    continue
                    
                timer = json.loads(timer_json)
                last_hb = datetime.fromisoformat(timer["last_heartbeat"])
                seconds_since_hb = (now - last_hb).total_seconds()
                
                # If missed heartbeats for more than 30 seconds
                if seconds_since_hb > 30:
                    print(f"🚨 [HEARTBEAT CRASH] Paralegal {paralegal_id} offline for {int(seconds_since_hb)}s. Auto-saving time entry...")
                    
                    # Calculate duration up to last registered heartbeat
                    total_seconds = timer["accumulated_seconds"]
                    if not timer["is_paused"]:
                        last_resumed = datetime.fromisoformat(timer["last_paused_or_resumed_at"])
                        # If heartbeat is before last resumed (shouldn't happen), use 0
                        elapsed = int((last_hb - last_resumed).total_seconds())
                        total_seconds += max(0, elapsed)
                        
                    # Only save if there was actual time accrued
                    if total_seconds > 0:
                        try:
                            db.create_time_entry(
                                paralegal_id=paralegal_id,
                                case_id=timer["case_id"],
                                task_id=timer["task_id"],
                                document_id=timer["document_id"],
                                start_time=timer["start_time"],
                                end_time=timer["last_heartbeat"],
                                duration_seconds=total_seconds
                            )
                            print(f"💾 [AUTO-SAVE SUCCESS] Flushed {total_seconds}s entry for paralegal {paralegal_id}.")
                        except Exception as db_err:
                            print(f"❌ Failed to auto-save stale timer to DB: {db_err}")
                            
                    # Remove active timer from cache
                    await redis.delete(key)
        except Exception as e:
            print(f"❌ Error in stale timer cleanup background loop: {e}")
            await asyncio.sleep(5)
