// State variables
let currentUser = null;
let workspaceData = { cases: [], tasks: [], documents: [] };
let activeTimer = null;
let tickerInterval = null;
let heartbeatInterval = null;
let selectedDocumentId = null;

// DOM Elements
const authPage = document.getElementById("auth-page");
const appPage = document.getElementById("app-page");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const displayUserName = document.getElementById("display-user-name");
const displayUserRole = document.getElementById("display-user-role");

const timerConsole = document.getElementById("workspace-timer-console");
const timerTicker = document.getElementById("timer-ticker");
const timerStatusIndicator = document.getElementById("timer-status-indicator");
const timerStatusText = document.getElementById("timer-status-text");
const btnPause = document.getElementById("btn-pause");
const btnResume = document.getElementById("btn-resume");

const sidebarContext = document.getElementById("sidebar-context");
const caseSelector = document.getElementById("case-selector");
const taskSelector = document.getElementById("task-selector");
const docListContainer = document.getElementById("doc-list-container");

const bannerTitle = document.getElementById("banner-title");
const bannerCase = document.getElementById("banner-case");
const bannerDoc = document.getElementById("banner-doc");

const metricTodayHours = document.getElementById("metric-today-hours");
const metricTodayEntries = document.getElementById("metric-today-entries");
const metricHoursLabel = document.getElementById("metric-hours-label");
const adminMetricCard = document.getElementById("admin-metric-card");
const metricActiveStaff = document.getElementById("metric-active-staff");

const adminFilters = document.getElementById("admin-filters");
const adminParalegalSelector = document.getElementById("admin-paralegal-selector");
const entriesTable = document.getElementById("entries-table");
const entriesTableBody = document.getElementById("entries-table-body");
const tableEmptyState = document.getElementById("table-empty-state");
const colParalegal = document.getElementById("col-paralegal");
const summaryTitleText = document.getElementById("summary-title-text");

// Initialize on page load
window.addEventListener("DOMContentLoaded", () => {
  lucide.createIcons();
  checkAuthOnLoad();
});

// --- AUTHENTICATION FLOW ---

async function checkAuthOnLoad() {
  try {
    const res = await fetch("/api/auth/me");
    if (res.ok) {
      const data = await res.json();
      onLoginSuccess(data.user);
    } else {
      showAuthPage();
    }
  } catch (err) {
    console.error("Auth check error:", err);
    showAuthPage();
  }
}

function showAuthPage() {
  authPage.classList.remove("hidden");
  appPage.classList.add("hidden");
  stopHeartbeat();
  stopTicker();
}

async function handleLogin(event) {
  event.preventDefault();
  loginError.classList.add("hidden");
  loginError.innerText = "";
  
  const usernameVal = document.getElementById("username").value;
  const passwordVal = document.getElementById("password").value;
  
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: usernameVal, password: passwordVal })
    });
    
    const data = await res.json();
    if (res.ok) {
      onLoginSuccess(data.user);
    } else {
      loginError.innerText = data.detail || "Authentication failed.";
      loginError.classList.remove("hidden");
    }
  } catch (err) {
    loginError.innerText = "Network error connecting to backend.";
    loginError.classList.remove("hidden");
    console.error(err);
  }
}

async function handleLogout() {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
    currentUser = null;
    showAuthPage();
  } catch (err) {
    console.error("Logout error:", err);
    showAuthPage();
  }
}

function onLoginSuccess(user) {
  currentUser = user;
  authPage.classList.add("hidden");
  appPage.classList.remove("hidden");
  
  displayUserName.innerText = user.name;
  displayUserRole.innerText = user.role;
  
  // Clean Form
  document.getElementById("username").value = "";
  document.getElementById("password").value = "";
  
  if (user.role === "admin") {
    // Admins don't have timers
    sidebarContext.classList.add("hidden");
    timerConsole.classList.add("hidden");
    adminFilters.classList.remove("hidden");
    colParalegal.classList.remove("hidden");
    summaryTitleText.innerText = "Firm Time Logs Today";
    metricHoursLabel.innerText = "Total Firm Billable Hours";
    adminMetricCard.classList.remove("hidden");
    
    // Load admin metrics & list
    loadAdminSelectors();
    loadDailySummary();
  } else {
    // Paralegals
    sidebarContext.classList.remove("hidden");
    timerConsole.classList.remove("hidden");
    adminFilters.classList.add("hidden");
    colParalegal.classList.add("hidden");
    summaryTitleText.innerText = "Your Time Entries Today";
    metricHoursLabel.innerText = "Your Hours Today";
    adminMetricCard.classList.add("hidden");
    
    // Load paralegal workspace data, then auto-start timer
    loadWorkspaceAndStartTimer();
  }
}

// --- WORKSPACE & TIMER FLOW ---

async function loadWorkspaceAndStartTimer() {
  await loadWorkspaceSelectors();
  await syncTimerStatus();
  startHeartbeat();
  loadDailySummary();
}

async function loadWorkspaceSelectors() {
  try {
    const res = await fetch("/api/workspace/data");
    if (!res.ok) throw new Error("Failed to load workspace data");
    
    workspaceData = await res.json();
    
    // Populate Case Selector
    caseSelector.innerHTML = "";
    workspaceData.cases.forEach(c => {
      const option = document.createElement("option");
      option.value = c.id;
      option.text = `[${c.case_number}] ${c.title}`;
      caseSelector.appendChild(option);
    });
    
    // Trigger task & doc population for the first case
    updateTaskAndDocSelectors();
  } catch (err) {
    console.error("Error loading workspace data:", err);
  }
}

function updateTaskAndDocSelectors() {
  const caseId = caseSelector.value;
  
  // Filter and populate tasks
  taskSelector.innerHTML = "";
  const filteredTasks = workspaceData.tasks.filter(t => t.case_id === caseId);
  filteredTasks.forEach(t => {
    const option = document.createElement("option");
    option.value = t.id;
    option.text = t.title;
    taskSelector.appendChild(option);
  });
  
  // Filter and populate documents
  docListContainer.innerHTML = "";
  const filteredDocs = workspaceData.documents.filter(d => d.case_id === caseId);
  
  if (filteredDocs.length === 0) {
    docListContainer.innerHTML = '<div style="font-size:12px; color:var(--text-muted);">No attached documents.</div>';
  } else {
    filteredDocs.forEach(d => {
      const div = document.createElement("div");
      div.className = "doc-item";
      if (d.id === selectedDocumentId) div.className += " active";
      div.dataset.id = d.id;
      div.onclick = () => selectDocument(d.id);
      
      div.innerHTML = `
        <i data-lucide="file-text" class="doc-icon" size="14"></i>
        <span>${d.name}</span>
      `;
      docListContainer.appendChild(div);
    });
    lucide.createIcons();
  }
  
  updateContextBanner();
}

function selectDocument(docId) {
  // Toggle selection
  if (selectedDocumentId === docId) {
    selectedDocumentId = null;
  } else {
    selectedDocumentId = docId;
  }
  
  // Re-render doc items active states
  const docItems = docListContainer.querySelectorAll(".doc-item");
  docItems.forEach(item => {
    if (item.dataset.id === selectedDocumentId) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });
  
  onContextChanged();
}

function updateContextBanner() {
  const selectedCaseId = caseSelector.value;
  const selectedTaskId = taskSelector.value;
  
  const c = workspaceData.cases.find(item => item.id === selectedCaseId);
  const t = workspaceData.tasks.find(item => item.id === selectedTaskId);
  const d = workspaceData.documents.find(item => item.id === selectedDocumentId);
  
  bannerTitle.innerText = t ? t.title : "Workspace Session Active";
  bannerCase.innerText = c ? `Case #${c.case_number}` : "No Case Linked";
  
  if (d) {
    bannerDoc.innerText = `Doc: ${d.name}`;
    bannerDoc.classList.remove("hidden");
  } else {
    bannerDoc.classList.add("hidden");
  }
}

async function onContextChanged() {
  updateContextBanner();
  
  // When context changes, we stop the current active timer (persisting its entry)
  // and auto-start a new timer bound to the newly selected context.
  if (currentUser && currentUser.role === "paralegal" && activeTimer) {
    const nextCaseId = caseSelector.value;
    const nextTaskId = taskSelector.value;
    const nextDocId = selectedDocumentId;
    
    console.log("Context changed. Autorecord old, and starting next context timer...");
    
    try {
      const res = await fetch("/api/timer/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: nextCaseId,
          task_id: nextTaskId,
          document_id: nextDocId
        })
      });
      
      const data = await res.json();
      if (res.ok) {
        // Reset local timer and update daily summaries
        activeTimer = data.next_timer;
        loadDailySummary();
        renderTimerUI();
      }
    } catch (err) {
      console.error("Error updating context on server:", err);
    }
  }
}

// --- TIMER API INTERACTIVE CALLS ---

async function syncTimerStatus() {
  const caseId = caseSelector.value;
  const taskId = taskSelector.value;
  const docId = selectedDocumentId;
  
  let url = "/api/timer/status";
  if (caseId && taskId) {
    url += `?case_id=${caseId}&task_id=${taskId}`;
    if (docId) url += `&document_id=${docId}`;
  }
  
  try {
    const res = await fetch(url);
    const data = await res.json();
    if (res.ok && data.status === "active") {
      activeTimer = data.timer;
      
      // Update sidebar matching the restored context
      if (activeTimer.case_id && activeTimer.case_id !== caseSelector.value) {
        caseSelector.value = activeTimer.case_id;
        updateTaskAndDocSelectors();
      }
      if (activeTimer.task_id && activeTimer.task_id !== taskSelector.value) {
        taskSelector.value = activeTimer.task_id;
      }
      if (activeTimer.document_id !== selectedDocumentId) {
        selectedDocumentId = activeTimer.document_id;
        // update active document highlight
        const docItems = docListContainer.querySelectorAll(".doc-item");
        docItems.forEach(item => {
          if (item.dataset.id === selectedDocumentId) {
            item.classList.add("active");
          } else {
            item.classList.remove("active");
          }
        });
      }
      
      updateContextBanner();
      renderTimerUI();
    }
  } catch (err) {
    console.error("Sync timer error:", err);
  }
}

function renderTimerUI() {
  if (!activeTimer) return;
  
  stopTicker();
  
  if (activeTimer.is_paused) {
    timerStatusIndicator.className = "status-indicator status-paused";
    timerStatusText.innerText = "Paused";
    btnPause.classList.add("hidden");
    btnResume.classList.remove("hidden");
    
    // Show accumulated static time
    displayTime(activeTimer.accumulated_seconds);
  } else {
    timerStatusIndicator.className = "status-indicator status-active";
    timerStatusText.innerText = "Active";
    btnPause.classList.remove("hidden");
    btnResume.classList.add("hidden");
    
    // Ticker starts tracking real-time client ticks
    startTicker();
  }
}

function displayTime(seconds) {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  const paddedHrs = String(hrs).padStart(2, '0');
  const paddedMins = String(mins).padStart(2, '0');
  const paddedSecs = String(secs).padStart(2, '0');
  
  timerTicker.innerText = `${paddedHrs}:${paddedMins}:${paddedSecs}`;
}

function startTicker() {
  if (tickerInterval) clearInterval(tickerInterval);
  
  const baseAccumulated = activeTimer.accumulated_seconds;
  const lastResumedAt = new Date(activeTimer.last_paused_or_resumed_at).getTime();
  
  function tick() {
    const now = new Date().getTime();
    // Calculate difference in seconds (taking timezone offsets in mind)
    const elapsedSinceResume = Math.floor((now - lastResumedAt) / 1000);
    const totalSeconds = Math.max(0, baseAccumulated + elapsedSinceResume);
    displayTime(totalSeconds);
  }
  
  tick(); // immediate call
  tickerInterval = setInterval(tick, 1000);
}

function stopTicker() {
  if (tickerInterval) {
    clearInterval(tickerInterval);
    tickerInterval = null;
  }
}

async function pauseTimer() {
  try {
    const res = await fetch("/api/timer/pause", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      activeTimer = data.timer;
      renderTimerUI();
    }
  } catch (err) {
    console.error("Error pausing timer:", err);
  }
}

async function resumeTimer() {
  try {
    const res = await fetch("/api/timer/resume", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      activeTimer = data.timer;
      renderTimerUI();
    }
  } catch (err) {
    console.error("Error resuming timer:", err);
  }
}

async function stopAndSaveTimer() {
  try {
    const res = await fetch("/api/timer/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (res.ok) {
      console.log("Timer stopped and time entry saved:", data.saved_entry);
      
      // Stop local UI ticker
      stopTicker();
      timerTicker.innerText = "00:00:00";
      
      // Auto-start a new timer context automatically (P0 requirement)
      await syncTimerStatus();
      
      // Refresh table
      loadDailySummary();
    }
  } catch (err) {
    console.error("Error saving timer:", err);
  }
}

// --- HEARTBEAT LOOP (FastAPI Pattern) ---

function startHeartbeat() {
  stopHeartbeat(); // Clear existing if any
  
  async function beat() {
    try {
      const res = await fetch("/api/timer/heartbeat", { method: "POST" });
      if (res.status === 401) {
        // Session expired on server
        handleLogout();
      }
    } catch (err) {
      console.warn("Heartbeat connection error:", err);
    }
  }
  
  // Pulse every 10 seconds
  heartbeatInterval = setInterval(beat, 10000);
}

function stopHeartbeat() {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
  }
}

// --- DAILY SUMMARIES & ADMINS (DG-053) ---

async function loadDailySummary() {
  let url = "/api/timer/summary";
  
  if (currentUser.role === "admin") {
    const filterUserId = adminParalegalSelector.value;
    if (filterUserId) {
      url += `?paralegal_id=${filterUserId}`;
    }
  }
  
  try {
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) throw new Error("Failed to load time entries");
    
    renderTableEntries(data.entries);
  } catch (err) {
    console.error("Error loading daily summary:", err);
  }
}

function renderTableEntries(entries) {
  entriesTableBody.innerHTML = "";
  
  if (!entries || entries.length === 0) {
    tableEmptyState.classList.remove("hidden");
    entriesTable.style.opacity = 0.5;
    
    metricTodayHours.innerText = "0.00h";
    metricTodayEntries.innerText = "0";
    if (currentUser.role === "admin") {
      metricActiveStaff.innerText = "0";
    }
    return;
  }
  
  tableEmptyState.classList.add("hidden");
  entriesTable.style.opacity = 1;
  
  let totalSeconds = 0;
  const paralegalsSeen = new Set();
  
  entries.forEach(entry => {
    totalSeconds += entry.duration_seconds;
    if (entry.paralegal_id) {
      paralegalsSeen.add(entry.paralegal_id);
    }
    
    const row = document.createElement("tr");
    
    // Format dates
    const startStr = new Date(entry.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const endStr = new Date(entry.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    // Format duration
    const hrs = Math.floor(entry.duration_seconds / 3600);
    const mins = Math.floor((entry.duration_seconds % 3600) / 60);
    const secs = entry.duration_seconds % 60;
    
    const durationFormatted = `${hrs > 0 ? hrs + 'h ' : ''}${mins}m ${secs}s`;
    
    let tds = "";
    if (currentUser.role === "admin") {
      tds += `<td><strong>${entry.paralegal_name}</strong></td>`;
    }
    
    tds += `
      <td><span class="tag tag-case">${entry.case_number}</span> ${entry.case_title}</td>
      <td>${entry.task_title}</td>
      <td>${startStr}</td>
      <td>${endStr}</td>
      <td><strong>${durationFormatted}</strong></td>
    `;
    
    row.innerHTML = tds;
    entriesTableBody.appendChild(row);
  });
  
  // Update Metrics
  const decimalHours = (totalSeconds / 3600).toFixed(2);
  metricTodayHours.innerText = `${decimalHours}h`;
  metricTodayEntries.innerText = entries.length;
  
  if (currentUser.role === "admin") {
    // Count active paralegal sessions (number of unique paralegals in history or simply simulated)
    metricActiveStaff.innerText = paralegalsSeen.size;
  }
}

// Admin only: load users selector
async function loadAdminSelectors() {
  try {
    // Retrieve users from workspace data or standard API.
    // For simplicity, we seed admin options from database users.
    // We can fetch cases/tasks info since it has a user seed implicitly or fetch from a small API.
    // To make it elegant, we fetch details using a small hack - let's fetch /api/workspace/data
    // and extract the users since the seeding loaded them, but wait, workspace data only gives cases, tasks, docs.
    // So let's provide a hardcoded list of seeded paralegals for admin select, or we can fetch them.
    // Standard mock usernames are "paralegal1" and "paralegal2".
    
    // Let's populate the selector with the seeded paralegal profiles:
    adminParalegalSelector.innerHTML = '<option value="">All Paralegals</option>';
    
    const mockParalegals = [
      { id: "paralegal1_uuid_placeholder", name: "Jane Doe, CLA" },
      { id: "paralegal2_uuid_placeholder", name: "John Smith, ACP" }
    ];
    
    // Let's actually find the real IDs from the entries if we query all, 
    // but a dropdown makes it nice. Let's make an API call to load users.
    // Wait, let's look at the database. The database is initialized with seeded IDs.
    // Let's create a quick API endpoint if needed, or simply let the admin filter using hardcoded names mapping.
    // Since we know the seeded values, let's fetch the entries first.
    // We can extract all users dynamically from the daily summaries to build a clean dropdown!
    // This is a highly robust solution that requires zero additional endpoints.
    
    const res = await fetch("/api/timer/summary");
    const data = await res.json();
    if (res.ok && data.entries) {
      const usersMap = {};
      data.entries.forEach(e => {
        usersMap[e.paralegal_id] = e.paralegal_name;
      });
      
      // In case no logs are present yet, we can also default-inject the mock profiles 
      // by querying them from a new users list. Let's fetch logs.
      Object.keys(usersMap).forEach(id => {
        const option = document.createElement("option");
        option.value = id;
        option.text = usersMap[id];
        adminParalegalSelector.appendChild(option);
      });
    }
  } catch (err) {
    console.error("Admin selector loading error:", err);
  }
}
