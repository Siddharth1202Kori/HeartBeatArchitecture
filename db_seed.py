import sys
import uuid
import asyncio
from db import IS_SUPABASE, supabase_client, init_sqlite_db, hash_password

def seed_supabase():
    if not IS_SUPABASE:
        print("Supabase is not configured in .env. Skipping Supabase seeding.")
        return False
        
    print("Seeding Supabase with mock legal data...")
    
    # 1. Clear existing items (Optional/Be careful)
    # We will just insert and catch unique constraints
    try:
        # User IDs
        p1_id = str(uuid.uuid4())
        p2_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())
        
        users_seed = [
            {"id": p1_id, "username": "paralegal1", "password_hash": hash_password("password123"), "role": "paralegal", "name": "Jane Doe, CLA"},
            {"id": p2_id, "username": "paralegal2", "password_hash": hash_password("password123"), "role": "paralegal", "name": "John Smith, ACP"},
            {"id": admin_id, "username": "admin1", "password_hash": hash_password("admin123"), "role": "admin", "name": "Sarah Jenkins, Esq."}
        ]
        
        for u in users_seed:
            try:
                supabase_client.table("users").insert(u).execute()
                print(f"Inserted user: {u['username']}")
            except Exception as ex:
                print(f"User {u['username']} already exists or insertion failed: {ex}")
                
        # Case IDs
        c1_id = str(uuid.uuid4())
        c2_id = str(uuid.uuid4())
        c3_id = str(uuid.uuid4())
        
        cases_seed = [
            {"id": c1_id, "case_number": "C-2026-9812", "client_name": "Apex Global Corp.", "title": "Apex Acquisition & Merger Agreement"},
            {"id": c2_id, "case_number": "C-2026-4451", "client_name": "Maria Rodriguez", "title": "Rodriguez Personal Injury Claim"},
            {"id": c3_id, "case_number": "C-2026-1109", "client_name": "Quantum Tech Inc.", "title": "Quantum IP Patent Litigation"}
        ]
        
        for c in cases_seed:
            try:
                supabase_client.table("cases").insert(c).execute()
                print(f"Inserted case: {c['case_number']}")
            except Exception as ex:
                print(f"Case {c['case_number']} already exists or insertion failed: {ex}")
                
        # To tie tasks/docs, we fetch cases from Supabase to get active case IDs since inserts might fail if they exist
        res_cases = supabase_client.table("cases").select("id, case_number").execute().data
        case_map = {item["case_number"]: item["id"] for item in res_cases}
        
        c1_uuid = case_map.get("C-2026-9812", c1_id)
        c2_uuid = case_map.get("C-2026-4451", c2_id)
        c3_uuid = case_map.get("C-2026-1109", c3_id)
        
        # Tasks Seed
        tasks_seed = [
            {"id": str(uuid.uuid4()), "case_id": c1_uuid, "title": "Review NDA and Due Diligence Documents", "description": "Analyze contract terms and check for liability exclusions.", "status": "pending"},
            {"id": str(uuid.uuid4()), "case_id": c1_uuid, "title": "Draft Closing Memorandum", "description": "Prepare final summary of deal terms.", "status": "in_progress"},
            {"id": str(uuid.uuid4()), "case_id": c2_uuid, "title": "Organize Medical Records", "description": "Scan, tag, and chronologically index medical invoices.", "status": "pending"},
            {"id": str(uuid.uuid4()), "case_id": c2_uuid, "title": "Draft Complaint Initial Version", "description": "Initial drafting of claims and damages list.", "status": "pending"},
            {"id": str(uuid.uuid4()), "case_id": c3_uuid, "title": "Prior Art Patent Search", "description": "Research prior patents in active domain.", "status": "completed"}
        ]
        
        for t in tasks_seed:
            try:
                supabase_client.table("tasks").insert(t).execute()
                print(f"Inserted task: {t['title']}")
            except Exception as ex:
                print(f"Task {t['title']} failed to insert: {ex}")
                
        # Documents Seed
        docs_seed = [
            {"id": str(uuid.uuid4()), "case_id": c1_uuid, "name": "Apex_NDA_Signed.pdf", "file_path": "/files/cases/101/Apex_NDA_Signed.pdf"},
            {"id": str(uuid.uuid4()), "case_id": c1_uuid, "name": "Acquisition_Draft_v4.docx", "file_path": "/files/cases/101/Acquisition_Draft_v4.docx"},
            {"id": str(uuid.uuid4()), "case_id": c2_uuid, "name": "Medical_Report_Dr_Ames.pdf", "file_path": "/files/cases/102/Medical_Report_Dr_Ames.pdf"}
        ]
        
        for d in docs_seed:
            try:
                supabase_client.table("documents").insert(d).execute()
                print(f"Inserted document: {d['name']}")
            except Exception as ex:
                print(f"Document {d['name']} failed to insert: {ex}")
                
        print("Supabase database seeding completed successfully.")
        return True
    except Exception as e:
        print(f"Error seeding Supabase: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sqlite":
        print("Forcing SQLite initialization...")
        init_sqlite_db()
    else:
        if IS_SUPABASE:
            seed_supabase()
        else:
            print("SQLite is running. Auto-initialization on startup handles SQLite database.")
            init_sqlite_db()
