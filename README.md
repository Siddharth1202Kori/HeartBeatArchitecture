# Paralegal Workspace Session & Time Tracker

A premium, high-fidelity real-time workspace tracking system. Built with a **FastAPI** backend, **Supabase** or **SQLite** database, **Redis** session storage (with automatic in-memory fallback), and a glassmorphic **Single Page Application** frontend.

## Features
- **Auto-Start Tracking (P0)**: Timers start automatically when a paralegal accesses their workspace console.
- **Manual Control (P0 / DG-051)**: Pause, resume, and stop controls elegantly situated in the header console.
- **Traceability (P0 / DG-052)**: Saved time entries are strictly linked to `paralegal_id`, `case_id`, `task_id`, and `document_id` for invoicing accuracy.
- **Heartbeat & Crash Recovery**: Client sends heartbeats every 10 seconds. If a browser/tab is closed unexpectedly, a background task automatically stops the active timer and saves the accrued duration up to the last registered heartbeat, avoiding runaway timer entries.
- **Daily Summaries (DG-053)**: Metric summaries and table listing for the day's time entries.
- **Admin Dashboard**: Switch filters to inspect total firm hours or isolate logs to individual paralegals.

---

## Technical Stack & Configuration

### Requirements
- Python 3.9+
- Redis (Optional: if not installed, the app transparently swaps in an In-Memory Redis emulator)
- Supabase Account (Optional: if credentials are omitted in `.env`, the app automatically spawns a local `workspace.db` SQLite database)

### Setup & Installation
1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. (Optional) Configure environment variables in `.env` if utilizing remote Supabase or remote Redis. If you leave `.env` as is, the project runs out-of-the-box using local SQLite and an in-memory Redis fallback.

3. Start the FastAPI server:
   ```bash
   python main.py
   ```
   The server will run on `http://127.0.0.1:8000`.

---

## Test Accounts (Seeded automatically)

| Username | Password | Role | Name |
| :--- | :--- | :--- | :--- |
| **`paralegal1`** | `password123` | Paralegal | Jane Doe, CLA |
| **`paralegal2`** | `password123` | Paralegal | John Smith, ACP |
| **`admin1`** | `admin123` | Admin | Sarah Jenkins, Esq. |

---

## Verification & Testing Scenarios

### Scenario 1: Auto-Start & Manual Controls
1. Open `http://127.0.0.1:8000` in your browser.
2. Sign in as `paralegal1` with `password123`.
3. Notice that the timer **starts ticking immediately** on login (matching current active case/task context).
4. Click **Pause** in the header. The timer pauses and changes status.
5. Click **Resume** to resume tracking.
6. Click **Stop (Square)** to commit the log to the database. The entry appears in the summary table. A new timer auto-starts.

### Scenario 2: Context Linking (Traceability)
1. In the left panel, change the **Linked Case** or **Linked Task**.
2. Notice the top banner updates context immediately.
3. Behind the scenes, the server automatically flushes the time logged on the *previous* task and seamlessly starts a new timer for the *newly selected* task context.

### Scenario 3: Heartbeat Crash Recovery (Fail-safe)
1. Sign in as `paralegal1` and let the timer run for about 15-20 seconds.
2. Close the browser tab.
3. Open a different browser or private window, and sign in as `admin1` with `admin123`.
4. Check the firm logs table. Within 30 seconds of closing the tab, you will see `paralegal1`'s time entry automatically saved with the precise elapsed duration up to the last registered heartbeat!
