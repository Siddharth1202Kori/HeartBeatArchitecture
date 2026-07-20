import os
import uuid
import sqlite3
import bcrypt
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

IS_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY and "placeholder" not in SUPABASE_URL.lower())

supabase_client = None

if IS_SUPABASE:
    try:
        from supabase import create_client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Connected to Supabase database successfully.")
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}. Falling back to local SQLite.")
        IS_SUPABASE = False

DB_FILE = "workspace.db"

def get_sqlite_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Helper to hash passwords using bcrypt
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

# Local SQLite Initialization & Seeding
def init_sqlite_db():
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL CHECK (role IN ('paralegal', 'admin')),
      name TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cases (
      id TEXT PRIMARY KEY,
      case_number TEXT UNIQUE NOT NULL,
      client_name TEXT NOT NULL,
      title TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
      id TEXT PRIMARY KEY,
      case_id TEXT NOT NULL,
      title TEXT NOT NULL,
      description TEXT,
      status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
      id TEXT PRIMARY KEY,
      case_id TEXT NOT NULL,
      name TEXT NOT NULL,
      file_path TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS time_entries (
      id TEXT PRIMARY KEY,
      paralegal_id TEXT NOT NULL,
      case_id TEXT NOT NULL,
      task_id TEXT NOT NULL,
      document_id TEXT,
      start_time TEXT NOT NULL,
      end_time TEXT NOT NULL,
      duration_seconds INTEGER NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (paralegal_id) REFERENCES users(id),
      FOREIGN KEY (case_id) REFERENCES cases(id),
      FOREIGN KEY (task_id) REFERENCES tasks(id),
      FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL
    )""")
    
    conn.commit()

    # Check if empty to run seeding
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        print("Seeding local SQLite database with mock legal data...")
        
        # User IDs
        p1_id = str(uuid.uuid4())
        p2_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())
        
        users_seed = [
            (p1_id, "paralegal1", hash_password("password123"), "paralegal", "Jane Doe, CLA"),
            (p2_id, "paralegal2", hash_password("password123"), "paralegal", "John Smith, ACP"),
            (admin_id, "admin1", hash_password("admin123"), "admin", "Sarah Jenkins, Esq.")
        ]
        cursor.executemany("INSERT INTO users (id, username, password_hash, role, name) VALUES (?, ?, ?, ?, ?)", users_seed)
        
        # Case IDs
        c1_id = str(uuid.uuid4())
        c2_id = str(uuid.uuid4())
        c3_id = str(uuid.uuid4())
        
        cases_seed = [
            (c1_id, "C-2026-9812", "Apex Global Corp.", "Apex Acquisition & Merger Agreement"),
            (c2_id, "C-2026-4451", "Maria Rodriguez", "Rodriguez Personal Injury Claim"),
            (c3_id, "C-2026-1109", "Quantum Tech Inc.", "Quantum IP Patent Litigation")
        ]
        cursor.executemany("INSERT INTO cases (id, case_number, client_name, title) VALUES (?, ?, ?, ?)", cases_seed)
        
        # Tasks Seed
        tasks_seed = [
            (str(uuid.uuid4()), c1_id, "Review NDA and Due Diligence Documents", "Analyze contract terms and check for liability exclusions.", "pending"),
            (str(uuid.uuid4()), c1_id, "Draft Closing Memorandum", "Prepare final summary of deal terms.", "in_progress"),
            (str(uuid.uuid4()), c2_id, "Organize Medical Records", "Scan, tag, and chronologically index medical invoices.", "pending"),
            (str(uuid.uuid4()), c2_id, "Draft Complaint Initial Version", "Initial drafting of claims and damages list.", "pending"),
            (str(uuid.uuid4()), c3_id, "Prior Art Patent Search", "Research prior patents in active domain.", "completed")
        ]
        cursor.executemany("INSERT INTO tasks (id, case_id, title, description, status) VALUES (?, ?, ?, ?, ?)", tasks_seed)
        
        # Documents Seed
        docs_seed = [
            (str(uuid.uuid4()), c1_id, "Apex_NDA_Signed.pdf", "/files/cases/101/Apex_NDA_Signed.pdf"),
            (str(uuid.uuid4()), c1_id, "Acquisition_Draft_v4.docx", "/files/cases/101/Acquisition_Draft_v4.docx"),
            (str(uuid.uuid4()), c2_id, "Medical_Report_Dr_Ames.pdf", "/files/cases/102/Medical_Report_Dr_Ames.pdf")
        ]
        cursor.executemany("INSERT INTO documents (id, case_id, name, file_path) VALUES (?, ?, ?, ?)", docs_seed)
        
        conn.commit()
        print("Local SQLite database seeded successfully.")

    conn.close()

if not IS_SUPABASE:
    init_sqlite_db()

# DB Query Functions
def get_user_by_username(username: str):
    if IS_SUPABASE:
        try:
            res = supabase_client.table("users").select("*").eq("username", username).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"Supabase error get_user_by_username: {e}")
            return None
    else:
        conn = get_sqlite_conn()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        return dict(user) if user else None

def get_user_by_id(user_id: str):
    if IS_SUPABASE:
        try:
            res = supabase_client.table("users").select("*").eq("id", user_id).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"Supabase error get_user_by_id: {e}")
            return None
    else:
        conn = get_sqlite_conn()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        return dict(user) if user else None

def get_workspace_data():
    """Returns all cases, tasks, and documents to populate the workspace selections"""
    if IS_SUPABASE:
        try:
            cases = supabase_client.table("cases").select("*").execute().data
            tasks = supabase_client.table("tasks").select("*").execute().data
            docs = supabase_client.table("documents").select("*").execute().data
            return {"cases": cases, "tasks": tasks, "documents": docs}
        except Exception as e:
            print(f"Supabase error get_workspace_data: {e}")
            return {"cases": [], "tasks": [], "documents": []}
    else:
        conn = get_sqlite_conn()
        cases = [dict(row) for row in conn.execute("SELECT * FROM cases").fetchall()]
        tasks = [dict(row) for row in conn.execute("SELECT * FROM tasks").fetchall()]
        docs = [dict(row) for row in conn.execute("SELECT * FROM documents").fetchall()]
        conn.close()
        return {"cases": cases, "tasks": tasks, "documents": docs}

def create_time_entry(paralegal_id: str, case_id: str, task_id: str, document_id: str, start_time: str, end_time: str, duration_seconds: int):
    entry_id = str(uuid.uuid4())
    if IS_SUPABASE:
        try:
            payload = {
                "id": entry_id,
                "paralegal_id": paralegal_id,
                "case_id": case_id,
                "task_id": task_id,
                "document_id": document_id if document_id else None,
                "start_time": start_time,
                "end_time": end_time,
                "duration_seconds": int(duration_seconds)
            }
            res = supabase_client.table("time_entries").insert(payload).execute()
            return res.data[0] if res.data else payload
        except Exception as e:
            print(f"Supabase error create_time_entry: {e}")
            raise e
    else:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO time_entries (id, paralegal_id, case_id, task_id, document_id, start_time, end_time, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (entry_id, paralegal_id, case_id, task_id, document_id, start_time, end_time, duration_seconds))
        conn.commit()
        conn.close()
        return {
            "id": entry_id,
            "paralegal_id": paralegal_id,
            "case_id": case_id,
            "task_id": task_id,
            "document_id": document_id,
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration_seconds
        }

def get_daily_time_entries(paralegal_id: str = None, date_str: str = None):
    """
    Get all time entries. Optionally filtered by paralegal and date.
    date_str should be like 'YYYY-MM-DD'. If not provided, defaults to today.
    """
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
    if IS_SUPABASE:
        try:
            # Query filters
            query = supabase_client.table("time_entries").select("*, users(name), cases(case_number, title), tasks(title)")
            if paralegal_id:
                query = query.eq("paralegal_id", paralegal_id)
            
            # Since Supabase start_time is timestamptz, we do date check using gte/lte
            start_of_day = f"{date_str}T00:00:00.000Z"
            end_of_day = f"{date_str}T23:59:59.999Z"
            query = query.gte("start_time", start_of_day).lte("start_time", end_of_day)
            
            res = query.order("start_time", desc=True).execute()
            
            # Flatten relations for front-end consumption
            formatted = []
            for item in res.data:
                formatted.append({
                    "id": item["id"],
                    "paralegal_id": item["paralegal_id"],
                    "paralegal_name": item.get("users", {}).get("name", "Unknown"),
                    "case_id": item["case_id"],
                    "case_number": item.get("cases", {}).get("case_number", ""),
                    "case_title": item.get("cases", {}).get("title", ""),
                    "task_id": item["task_id"],
                    "task_title": item.get("tasks", {}).get("title", ""),
                    "document_id": item["document_id"],
                    "start_time": item["start_time"],
                    "end_time": item["end_time"],
                    "duration_seconds": item["duration_seconds"]
                })
            return formatted
        except Exception as e:
            print(f"Supabase error get_daily_time_entries: {e}")
            return []
    else:
        conn = get_sqlite_conn()
        query = """
            SELECT te.*, u.name as paralegal_name, c.case_number, c.title as case_title, t.title as task_title
            FROM time_entries te
            JOIN users u ON te.paralegal_id = u.id
            JOIN cases c ON te.case_id = c.id
            JOIN tasks t ON te.task_id = t.id
            WHERE substr(te.start_time, 1, 10) = ?
        """
        params = [date_str]
        if paralegal_id:
            query += " AND te.paralegal_id = ?"
            params.append(paralegal_id)
            
        query += " ORDER BY te.start_time DESC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]
