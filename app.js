/**
 * app.js — 3SBC Staffing Intelligence Platform
 * Full SPA logic: Firebase Auth, Job Finder, Bench ATS,
 * Submission CRM, Vendor CRM, Analytics, AI Match, Email Generator
 */

// ═══════════════════════════════════════════════════════════
// FIREBASE CONFIGURATION
// ═══════════════════════════════════════════════════════════
const FIREBASE_CONFIG = {
  apiKey:            "AIzaSyC8u6pbURwdJ9B1Q88yxKOMICHQcHlCt2E",
  authDomain:        "sbc-219bf.firebaseapp.com",
  databaseURL:       "https://sbc-219bf-default-rtdb.firebaseio.com",
  projectId:         "sbc-219bf",
  storageBucket:     "sbc-219bf.firebasestorage.app",
  messagingSenderId: "309369056231",
  appId:             "1:309369056231:web:1d5a3ba894c58bd046ab42",
  measurementId:     "G-QX6H17CWY4"
};

// ═══════════════════════════════════════════════════════════
// APP STATE
// ═══════════════════════════════════════════════════════════
const STATE = {
  user:           null,
  userRole:       'recruiter', // 'admin' | 'recruiter'
  allCandidates:  [],
  submissions:    [],
  vendors:        [],
  savedJobs:      [],
  lastJobSearch:  null,
  activeTab:      'jobFinder',
  jobResults:     {},
  pendingJob:     null,   // job selected for submission
  pendingCandidate: null, // consultant selected for submission
};

// ═══════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════
function toast(msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function formatDate(ts) {
  if (!ts) return '—';
  try {
    const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return String(ts); }
}

function initials(name) {
  return (name || 'XX').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function scoreClass(score) {
  const s = parseInt(score) || 0;
  if (s >= 80) return 'score-high';
  if (s >= 60) return 'score-medium';
  return 'score-low';
}

function statusBadge(status) {
  const s = (status || 'New').toLowerCase().replace(/\s+/g, '');
  return `<span class="status-badge status-${s}">${status || 'New'}</span>`;
}

function escHtml(str) {
  return String(str || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

// ═══════════════════════════════════════════════════════════
// FIREBASE INIT & AUTH
// ═══════════════════════════════════════════════════════════
let _auth = null, _db = null, _firebase = null;

function initFirebase() {
  if (typeof firebase === 'undefined') {
    console.warn('[3SBC] Firebase SDK not loaded — running in offline mode');
    showApp(null);
    return;
  }
  if (!firebase.apps.length) {
    firebase.initializeApp(FIREBASE_CONFIG);
  }
  _auth = firebase.auth();
  _db   = firebase.firestore();

  _auth.onAuthStateChanged(user => {
    if (user) {
      STATE.user = user;
      showApp(user);
      loadUserRole(user.uid);
    } else {
      STATE.user = null;
      showLogin();
    }
  });
}

async function loadUserRole(uid) {
  try {
    const doc = await _db.collection('users').doc(uid).get();
    if (doc.exists) {
      STATE.userRole = doc.data().role || 'recruiter';
    } else {
      // First-time user — create record
      await _db.collection('users').doc(uid).set({
        role:       'recruiter',
        email:      STATE.user.email,
        created_at: Date.now() / 1000,
      });
    }
  } catch(e) {
    console.warn('[3SBC] loadUserRole:', e);
  }
}

function showLogin() {
  document.getElementById('loginPage').classList.remove('hidden');
  document.getElementById('mainApp').classList.add('hidden');
}

function showApp(user) {
  document.getElementById('loginPage').classList.add('hidden');
  document.getElementById('mainApp').classList.remove('hidden');
  if (user) {
    document.getElementById('navUserEmail').textContent = user.email;
  }
  switchTab('jobFinder');
  loadBenchData();
}

// ── Login form ───────────────────────────────────────────────
function setupAuth() {
  const form  = document.getElementById('loginForm');
  const error = document.getElementById('loginError');
  const btn   = document.getElementById('loginBtn');

  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('loginEmail').value.trim();
    const pwd   = document.getElementById('loginPassword').value;
    if (!email || !pwd) return;

    btn.disabled    = true;
    btn.textContent = 'Signing in…';
    error.textContent = '';

    try {
      if (!_auth) {
        // Demo mode — skip auth
        showApp({ email: email, uid: 'demo' });
        return;
      }
      await _auth.signInWithEmailAndPassword(email, pwd);
    } catch(err) {
      let msg = 'Login failed. Check your email and password.';
      if (err.code === 'auth/user-not-found')  msg = 'No account found for this email.';
      if (err.code === 'auth/wrong-password')  msg = 'Incorrect password.';
      if (err.code === 'auth/invalid-email')   msg = 'Invalid email address.';
      if (err.code === 'auth/too-many-requests') msg = 'Too many attempts. Try again later.';
      error.textContent = msg;
    } finally {
      btn.disabled    = false;
      btn.textContent = 'Sign In';
    }
  });

  document.getElementById('logoutBtn')?.addEventListener('click', async () => {
    if (_auth) await _auth.signOut();
    else showLogin();
  });
}

// ═══════════════════════════════════════════════════════════
// TAB NAVIGATION
// ═══════════════════════════════════════════════════════════
function setupTabs() {
  document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
}

function switchTab(tabId) {
  STATE.activeTab = tabId;
  document.querySelectorAll('.nav-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
  document.querySelectorAll('.tab-content').forEach(p => {
    p.classList.toggle('active', p.id === tabId + 'Tab');
    p.style.display = p.id === tabId + 'Tab' ? 'flex' : 'none';
  });
  if (tabId === 'submissions') loadSubmissions();
  if (tabId === 'vendors')     loadVendors();
  if (tabId === 'analytics')   renderAnalytics();
  if (tabId === 'bench')       renderBench();
}

// ═══════════════════════════════════════════════════════════
// ─────────────────────────────────────────────────────────
// JOB FINDER TAB
// ─────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════
function setupJobFinder() {
  const form = document.getElementById('jobSearchForm');
  if (form) {
    form.addEventListener('submit', (e) => { e.preventDefault(); runJobSearch(); });
  }
}

async function runJobSearch() {
  const skill    = document.getElementById('jfSkill')?.value.trim();
  const location = document.getElementById('jfLocation')?.value.trim();
  const jobType  = document.getElementById('jfType')?.value || 'contract';
  const days     = document.getElementById('jfDays')?.value || '3';
  const btn      = document.getElementById('jfSearchBtn');

  if (!skill || !location) { toast('Enter a skill and location to search', 'warn'); return; }

  // Show loading state
  btn.disabled = true;
  btn.textContent = '⏳ Searching…';
  document.getElementById('kanbanBoard').innerHTML = renderKanbanLoading();
  document.getElementById('rateBanner').classList.add('hidden');

  try {
    const url = `/api/jobs/search?skill=${encodeURIComponent(skill)}&location=${encodeURIComponent(location)}&job_type=${jobType}&days=${days}`;
    const res  = await fetch(url);
    const data = await res.json();

    STATE.jobResults   = data.boards || {};
    STATE.lastJobSearch = { skill, location, jobType, days };

    renderKanbanBoard(data);

    if (data.rate_intelligence && data.rate_intelligence.display) {
      renderRateBanner(data.rate_intelligence);
    }

    const total = data.total || 0;
    toast(`Found ${total} jobs across ${Object.keys(STATE.jobResults).length} boards${data.cached ? ' (cached)' : ''}`, 'success');

  } catch(err) {
    console.error('[3SBC] Job search error:', err);
    toast('Job search failed. Check connection.', 'error');
    document.getElementById('kanbanBoard').innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="e-icon">⚠️</div>
        <div class="e-title">Search failed</div>
        <div class="e-sub">The backend could not reach the job boards. Try again.</div>
      </div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '🔍 Search Jobs';
  }
}

function renderKanbanLoading() {
  const boards = ['Dice','Indeed','LinkedIn','ZipRecruiter','Monster'];
  return boards.map(b => `
    <div class="kanban-column">
      <div class="kanban-header">
        <div class="board-label"><div class="board-dot"></div>${b}</div>
      </div>
      <div class="kanban-loading"><div class="spinner"></div>Searching…</div>
    </div>`).join('');
}

function renderKanbanBoard(data) {
  const boards = data.boards || {};
  const boardConfig = {
    dice:         { label: 'Dice',         color: 'dice' },
    indeed:       { label: 'Indeed',       color: 'indeed' },
    linkedin:     { label: 'LinkedIn',     color: 'linkedin' },
    ziprecruiter: { label: 'ZipRecruiter', color: 'ziprecruiter' },
    monster:      { label: 'Monster',      color: 'monster' },
  };

  const html = Object.entries(boardConfig).map(([key, cfg]) => {
    const jobs = boards[key] || [];
    return `
      <div class="kanban-column">
        <div class="kanban-header">
          <div class="board-label">
            <div class="board-dot ${cfg.color}"></div>
            <span>${cfg.label}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="board-count">${jobs.length}</span>
            ${data.cached ? '<span class="board-cached">cached</span>' : ''}
          </div>
        </div>
        <div class="kanban-cards">
          ${jobs.length === 0
            ? `<div class="kanban-empty"><div class="empty-icon">🔍</div><div class="empty-text">No jobs found</div></div>`
            : jobs.map(j => renderJobCard(j)).join('')
          }
        </div>
      </div>`;
  }).join('');

  document.getElementById('kanbanBoard').innerHTML = html;
}

function renderJobCard(job) {
  const salary = job.salary ? `<span class="job-salary">💰 ${escHtml(job.salary)}</span>` : '';
  const easyApply = job.easy_apply ? '<span class="easy-apply-badge">Easy Apply</span>' : '';
  const alsoOn  = job.also_on ? `<span class="also-on-badge">+${escHtml(job.also_on)}</span>` : '';

  return `
    <div class="job-card" data-job-id="${escHtml(job.id)}">
      <div class="job-card-top">
        <div class="job-title">${escHtml(job.title)}</div>
        <div class="flex items-center gap-2">${easyApply}${alsoOn}</div>
      </div>
      <div class="job-company">${escHtml(job.company)}</div>
      <div class="job-meta">
        <span class="job-meta-item">📍 ${escHtml(job.location)}</span>
        <span class="job-meta-item">🕐 ${escHtml(job.posted)}</span>
        <span class="job-meta-item">📄 ${escHtml(job.job_type)}</span>
        ${salary}
      </div>
      <div class="job-card-actions">
        <button class="btn-card btn-card-primary" onclick="openMatchModal(${JSON.stringify(escHtml(JSON.stringify(job)))})">🤖 Match</button>
        <button class="btn-card btn-card-green"   onclick="openSubmitModal(${JSON.stringify(escHtml(JSON.stringify(job)))})">✅ Submit</button>
        <button class="btn-card btn-card-outline"  onclick="saveJob(${JSON.stringify(escHtml(JSON.stringify(job)))})">⭐ Save</button>
        <a class="btn-card btn-card-outline" href="${escHtml(job.url)}" target="_blank" rel="noopener">🔗 Open</a>
      </div>
    </div>`;
}

function renderRateBanner(ri) {
  const banner = document.getElementById('rateBanner');
  if (!banner || !ri) return;
  banner.classList.remove('hidden');
  banner.innerHTML = `
    <span class="rate-icon">💰</span>
    <div>
      <div class="rate-label">Market Rate Intelligence</div>
      <div class="rate-value">${escHtml(ri.display)}</div>
    </div>
    <div class="flex gap-3" style="margin-left:auto">
      <div class="rate-stat"><div class="stat-val">$${ri.low}/hr</div><div class="stat-lbl">Low</div></div>
      <div class="rate-stat"><div class="stat-val">$${ri.median}/hr</div><div class="stat-lbl">Median</div></div>
      <div class="rate-stat"><div class="stat-val">$${ri.high}/hr</div><div class="stat-lbl">High</div></div>
    </div>`;
}

// ── AI Match Modal ───────────────────────────────────────────
async function openMatchModal(jobJsonEsc) {
  const job = JSON.parse(jobJsonEsc.replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"'));
  STATE.pendingJob = job;

  const modal = document.getElementById('matchModal');
  document.getElementById('matchModalTitle').textContent = `AI Match — ${job.title}`;
  document.getElementById('matchModalCompany').textContent = `${job.company} · ${job.location}`;
  document.getElementById('matchResultsList').innerHTML = '<div class="loading-state"><div class="spinner"></div>Ranking consultants…</div>';
  modal.classList.remove('hidden');

  try {
    const res  = await fetch('/api/jobs/match', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ job, candidates: STATE.allCandidates }),
    });
    const data = await res.json();
    renderMatchResults(data.matches || []);
  } catch(e) {
    document.getElementById('matchResultsList').innerHTML = '<div class="text-muted" style="padding:16px">Failed to rank matches.</div>';
  }
}

function renderMatchResults(matches) {
  if (!matches.length) {
    document.getElementById('matchResultsList').innerHTML = '<div class="empty-state"><div class="e-icon">🤷</div><div class="e-title">No matches found</div></div>';
    return;
  }
  document.getElementById('matchResultsList').innerHTML = `
    <div class="match-list">
      ${matches.map((m, i) => {
        const sc = parseInt(m.fit_score);
        const col = sc >= 80 ? 'var(--green)' : sc >= 60 ? 'var(--yellow)' : 'var(--red)';
        const jobJson = escHtml(JSON.stringify(STATE.pendingJob));
        const candName = escHtml(m.name);
        const candSkill = escHtml(m.skill);
        const candLoc   = escHtml(m.location);
        return `
          <div class="match-item">
            <div class="match-rank">#${i+1}</div>
            <div style="width:44px;height:44px;border-radius:50%;border:2px solid ${col};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;color:${col};flex-shrink:0">${sc}%</div>
            <div class="match-info">
              <div class="match-name">${candName}</div>
              <div class="match-skill-loc">${candSkill} · ${candLoc}</div>
              <div style="font-size:10px;color:var(--text-muted);margin-top:2px">${escHtml(m.reason)}</div>
            </div>
            <button class="match-btn" onclick="selectMatchAndSubmit(${JSON.stringify(candName)},${JSON.stringify(candSkill)},${JSON.stringify(candLoc)})">Submit →</button>
          </div>`;
      }).join('')}
    </div>`;
}

function selectMatchAndSubmit(name, skill, location) {
  closeModal('matchModal');
  if (!STATE.pendingJob) return;
  STATE.pendingCandidate = { name, skill, location };
  openSubmitModalWithCandidate(STATE.pendingJob, name, skill, location);
}

// ── Submit Modal ─────────────────────────────────────────────
function openSubmitModal(jobJsonEsc) {
  const job = JSON.parse(jobJsonEsc.replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"'));
  STATE.pendingJob = job;
  _openSubmitModalCore(job, '', '', '');
}

function openSubmitModalWithCandidate(job, name, skill, location) {
  _openSubmitModalCore(job, name, skill, location);
}

function _openSubmitModalCore(job, cName, cSkill, cLoc) {
  const modal = document.getElementById('submitModal');
  document.getElementById('submitJobTitle').textContent   = job.title;
  document.getElementById('submitJobCompany').textContent = `${job.company} · ${job.location}`;
  document.getElementById('submitConsultant').value  = cName  || '';
  document.getElementById('submitSkill').value       = cSkill || '';
  document.getElementById('submitLocation').value    = cLoc   || '';
  document.getElementById('submitRate').value        = '';
  document.getElementById('submitVendorEmail').value = '';
  document.getElementById('submitVendorName').value  = '';
  document.getElementById('submitNotes').value       = '';
  document.getElementById('dupWarning').classList.add('hidden');
  document.getElementById('emailBox').classList.add('hidden');
  modal.classList.remove('hidden');

  // Pre-fill vendor from CRM
  prefillVendor(job.company);

  // Auto-select consultant from bench
  if (cName) {
    document.getElementById('submitConsultant').value = cName;
  }
}

function prefillVendor(company) {
  const match = STATE.vendors.find(v => v.company?.toLowerCase().includes(company?.toLowerCase()));
  if (match) {
    document.getElementById('submitVendorEmail').value = match.email || '';
    document.getElementById('submitVendorName').value  = match.name  || '';
  }
}

async function checkDuplicate() {
  const consultant = document.getElementById('submitConsultant').value.trim();
  const job        = STATE.pendingJob;
  if (!consultant || !job) return;

  try {
    const res  = await fetch('/api/submissions/check-duplicate', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        consultant_name: consultant,
        company:         job.company,
        job_id:          job.id,
        days_window:     90,
      }),
    });
    const data = await res.json();
    const box  = document.getElementById('dupWarning');
    if (data.duplicate) {
      box.textContent = data.message;
      box.classList.remove('hidden');
    } else {
      box.classList.add('hidden');
    }
  } catch(e) {
    // Fail silently
  }
}

async function generateEmail() {
  const job     = STATE.pendingJob;
  const cName   = document.getElementById('submitConsultant').value.trim();
  const cSkill  = document.getElementById('submitSkill').value.trim();
  const cLoc    = document.getElementById('submitLocation').value.trim();
  const cRate   = document.getElementById('submitRate').value.trim();
  const vName   = document.getElementById('submitVendorName').value.trim();
  const vEmail  = document.getElementById('submitVendorEmail').value.trim();
  const recruiter = STATE.user?.email?.split('@')[0] || 'Recruiter';

  try {
    const res = await fetch('/api/submissions/email', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        consultant:     { name: cName, skill: cSkill, location: cLoc, rate: cRate },
        job:            job,
        vendor:         { name: vName, email: vEmail },
        recruiter_name: recruiter,
      }),
    });
    const data = await res.json();
    const box  = document.getElementById('emailBox');
    document.getElementById('emailContent').textContent = data.body || '';
    box.classList.remove('hidden');
  } catch(e) {
    toast('Could not generate email', 'error');
  }
}

function copyEmail() {
  const text = document.getElementById('emailContent').textContent;
  navigator.clipboard.writeText(text).then(() => toast('Email copied to clipboard!', 'success'));
}

async function confirmSubmit() {
  const job       = STATE.pendingJob;
  const consultant = document.getElementById('submitConsultant').value.trim();
  const skill      = document.getElementById('submitSkill').value.trim();
  const location   = document.getElementById('submitLocation').value.trim();
  const rate       = document.getElementById('submitRate').value.trim();
  const vEmail     = document.getElementById('submitVendorEmail').value.trim();
  const vName      = document.getElementById('submitVendorName').value.trim();
  const notes      = document.getElementById('submitNotes').value.trim();

  if (!consultant || !job) { toast('Enter consultant name', 'warn'); return; }

  try {
    const record = {
      consultant_name:  consultant,
      consultant_skill: skill,
      job_id:           job.id,
      job_title:        job.title,
      company:          job.company,
      location:         job.location,
      board:            job.board,
      job_url:          job.url,
      salary:           job.salary,
      rate_offered:     rate,
      vendor_email:     vEmail,
      vendor_name:      vName,
      notes:            notes,
      status:           'Submitted',
      follow_up:        false,
      submitted_by:     STATE.user?.email || 'Recruiter',
      user_id:          STATE.user?.uid   || 'demo',
      created_at:       Date.now() / 1000,
      updated_at:       Date.now() / 1000,
    };

    if (_db) {
      await _db.collection('submissions').add(record);
    } else {
      STATE.submissions.unshift({ ...record, id: 'local_' + Date.now() });
    }

    // Update vendor last_contacted
    if (vEmail && _db) {
      const match = STATE.vendors.find(v => v.email === vEmail);
      if (match) _db.collection('vendors').doc(match.id).update({ last_contacted: new Date().toISOString().split('T')[0] });
    }

    toast(`✅ ${consultant} submitted to ${job.company}!`, 'success');
    closeModal('submitModal');
    STATE.submissions.unshift({ ...record, id: 'new' });
    updateSubmissionBadge();

  } catch(e) {
    console.error('[3SBC] Submit error:', e);
    toast('Submission failed: ' + e.message, 'error');
  }
}

// ── Save Job ─────────────────────────────────────────────────
async function saveJob(jobJsonEsc) {
  const job = typeof jobJsonEsc === 'string'
    ? JSON.parse(jobJsonEsc.replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"'))
    : jobJsonEsc;

  try {
    const record = { ...job, user_id: STATE.user?.uid || 'demo', saved_at: Date.now() / 1000 };
    if (_db) await _db.collection('saved_jobs').add(record);
    STATE.savedJobs.unshift(record);
    toast(`⭐ Saved: ${job.title}`, 'success');
  } catch(e) {
    toast('Could not save job', 'error');
  }
}

// ═══════════════════════════════════════════════════════════
// ─────────────────────────────────────────────────────────
// BENCH TAB
// ─────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════
async function loadBenchData() {
  try {
    // Use embedded data first, fall back to API
    if (window.EMBEDDED_CANDIDATES && window.EMBEDDED_CANDIDATES.length > 0) {
      STATE.allCandidates = window.EMBEDDED_CANDIDATES;
    } else {
      const res  = await fetch('/api/candidates');
      STATE.allCandidates = await res.json();
    }
  } catch(e) {
    STATE.allCandidates = window.EMBEDDED_CANDIDATES || [];
  }
  renderBench();
  renderKPIs();
}

function renderKPIs() {
  const records = STATE.allCandidates;
  const total   = records.length;
  const scores  = records.map(r => parseInt(r['Match Score']) || 0);
  const topMatches = scores.filter(s => s >= 80).length;
  const teams   = new Set(records.map(r => r['Team Name'])).size;
  const avg     = scores.length ? Math.round(scores.reduce((a,b)=>a+b,0)/scores.length) : 0;
  const shortlisted = records.filter(r => r.Status === 'Shortlisted').length;

  const el = (id) => document.getElementById(id);
  if (el('kpiTotal'))      el('kpiTotal').textContent      = total;
  if (el('kpiTop'))        el('kpiTop').textContent        = topMatches;
  if (el('kpiTeams'))      el('kpiTeams').textContent      = teams;
  if (el('kpiAvgScore'))   el('kpiAvgScore').textContent   = avg + '%';
  if (el('kpiShortlisted'))el('kpiShortlisted').textContent= shortlisted;
}

let _benchFilter = '';
function renderBench(filter) {
  if (filter !== undefined) _benchFilter = filter.toLowerCase();
  const grid = document.getElementById('candidateGrid');
  if (!grid) return;

  const records = STATE.allCandidates.filter(r => {
    if (!_benchFilter) return true;
    const searchable = `${r['Consultant Name']}${r['Target Skill (AREA)']}${r['Target Location']}${r['Team Name']}`.toLowerCase();
    return searchable.includes(_benchFilter);
  });

  if (!records.length) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
      <div class="e-icon">👤</div><div class="e-title">No consultants found</div></div>`;
    return;
  }

  grid.innerHTML = records.map(r => {
    const name   = escHtml(r['Consultant Name'] || '');
    const team   = escHtml(r['Team Name'] || '');
    const skill  = escHtml(r['Target Skill (AREA)'] || '');
    const loc    = escHtml(r['Target Location'] || '');
    const score  = parseInt(r['Match Score']) || 0;
    const status = r.Status || 'New';
    const candName = escHtml(r['Candidate Name/Title'] || name);
    const linkedin = r['Candidate LinkedIn URL'] || '';
    const sc = scoreClass(score);

    return `
      <div class="candidate-card">
        <div class="candidate-header">
          <div class="candidate-avatar">${initials(candName)}</div>
          <div class="candidate-info">
            <div class="candidate-name">${candName}</div>
            <div class="candidate-team">📁 ${team}</div>
          </div>
          <div class="score-badge ${sc}">${score}</div>
        </div>
        <div class="flex items-center gap-2" style="flex-wrap:wrap">
          <span class="candidate-skill">🎯 ${skill}</span>
          ${statusBadge(status)}
        </div>
        <div class="candidate-location">📍 ${loc}</div>
        ${r['AI Reasoning'] ? `<div style="font-size:11px;color:var(--text-muted);line-height:1.5;border-top:1px solid var(--border);padding-top:8px">${escHtml((r['AI Reasoning']||'').substring(0,140))}${r['AI Reasoning']?.length > 140 ? '…' : ''}</div>` : ''}
        <div class="candidate-actions">
          <button class="cand-btn cand-btn-blue" onclick="findJobsForConsultant('${skill.replace(/'/g,"\\'")}','${loc.replace(/'/g,"\\'")}')">🔍 Find Jobs</button>
          ${linkedin ? `<a class="cand-btn cand-btn-ghost" href="${escHtml(linkedin)}" target="_blank">💼 LinkedIn</a>` : ''}
          <select class="cand-btn cand-btn-ghost" onchange="updateStatus('${escHtml(r['Team Name'])}::${candName}', this.value)" style="cursor:pointer">
            ${['New','Shortlisted','Interviewing','Offered','Placed','Rejected'].map(s =>
              `<option value="${s}" ${s===status?'selected':''}>${s}</option>`).join('')}
          </select>
        </div>
      </div>`;
  }).join('');
}

function findJobsForConsultant(skill, location) {
  switchTab('jobFinder');
  document.getElementById('jfSkill').value    = decodeURIComponent(skill);
  document.getElementById('jfLocation').value = decodeURIComponent(location);
  setTimeout(runJobSearch, 300);
}

async function updateStatus(candidateId, status) {
  try {
    await fetch('/api/update-status', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ candidate_id: candidateId, status }),
    });
    const rec = STATE.allCandidates.find(r => `${r['Team Name']}::${r['Candidate Name/Title']}` === candidateId);
    if (rec) rec.Status = status;
    toast(`Status updated to ${status}`, 'success');
  } catch(e) {
    toast('Status update failed', 'error');
  }
}

// ═══════════════════════════════════════════════════════════
// ─────────────────────────────────────────────────────────
// SUBMISSIONS TAB
// ─────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════
async function loadSubmissions() {
  const tbody = document.getElementById('submissionsBody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="9" class="text-muted" style="padding:24px;text-align:center"><div class="spinner" style="margin:auto"></div></td></tr>';

  try {
    if (_db) {
      let ref = _db.collection('submissions').orderBy('created_at', 'desc');
      if (STATE.userRole !== 'admin') ref = ref.where('user_id', '==', STATE.user?.uid || 'demo');
      const snap = await ref.get();
      STATE.submissions = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    }
  } catch(e) {
    console.warn('[3SBC] loadSubmissions:', e);
  }

  renderSubmissions();
  renderPipelineStats();
}

function renderPipelineStats() {
  const subs = STATE.submissions;
  const counts = { Submitted: 0, Interviewing: 0, Offered: 0, Placed: 0 };
  subs.forEach(s => { if (counts[s.status] !== undefined) counts[s.status]++; });

  ['Submitted','Interviewing','Offered','Placed'].forEach(key => {
    const el = document.getElementById('pStat' + key);
    if (el) el.textContent = counts[key];
  });
  updateSubmissionBadge();
}

function updateSubmissionBadge() {
  const badge = document.getElementById('submissionsBadge');
  const followUps = STATE.submissions.filter(s => s.follow_up).length;
  if (badge) {
    badge.textContent = followUps || '';
    badge.style.display = followUps ? 'inline' : 'none';
  }
}

function renderSubmissions() {
  const tbody = document.getElementById('submissionsBody');
  if (!tbody) return;

  const subs = STATE.submissions;
  if (!subs.length) {
    tbody.innerHTML = `<tr><td colspan="9" style="padding:40px;text-align:center;color:var(--text-muted)">No submissions yet. Submit a consultant from the Job Finder tab.</td></tr>`;
    return;
  }

  tbody.innerHTML = subs.map(s => `
    <tr>
      <td>${escHtml(s.consultant_name || '—')}</td>
      <td>
        <div style="font-weight:600">${escHtml(s.job_title || '—')}</div>
        <div style="font-size:11px;color:var(--text-muted)">${escHtml(s.board || '')}</div>
      </td>
      <td>${escHtml(s.company || '—')}</td>
      <td>${formatDate(s.created_at)}</td>
      <td>
        <select class="table-action-btn" style="background:var(--bg-card);color:var(--text-primary);border:1px solid var(--border)"
          onchange="updateSubmissionStatus('${s.id}', this.value)">
          ${['Submitted','Interviewing','Offered','Placed','Rejected'].map(st =>
            `<option value="${st}" ${st===s.status?'selected':''}>${st}</option>`).join('')}
        </select>
      </td>
      <td>${escHtml(s.rate_offered ? '$'+s.rate_offered+'/hr' : '—')}</td>
      <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escHtml(s.notes)}">
        ${escHtml(s.notes || '—')}
      </td>
      <td>
        <button class="table-action-btn flag-btn ${s.follow_up ? 'flagged' : ''}"
          onclick="toggleFollowUp('${s.id}', this)" title="Flag for follow-up">🔔</button>
      </td>
      <td>
        ${s.job_url ? `<a class="table-action-btn" style="background:var(--accent-glow);color:var(--accent);border:1px solid rgba(59,130,246,.3);text-decoration:none" href="${escHtml(s.job_url)}" target="_blank">🔗</a>` : ''}
        <button class="table-action-btn del-btn" onclick="deleteSubmission('${s.id}')">🗑</button>
      </td>
    </tr>`).join('');
}

async function updateSubmissionStatus(id, status) {
  try {
    if (_db) await _db.collection('submissions').doc(id).update({ status, updated_at: Date.now()/1000 });
    const s = STATE.submissions.find(s => s.id === id);
    if (s) s.status = status;
    renderPipelineStats();
    toast(`Status updated to ${status}`, 'success');
  } catch(e) { toast('Update failed', 'error'); }
}

async function toggleFollowUp(id, btn) {
  const s = STATE.submissions.find(s => s.id === id);
  if (!s) return;
  s.follow_up = !s.follow_up;
  btn.classList.toggle('flagged', s.follow_up);
  try {
    if (_db) await _db.collection('submissions').doc(id).update({ follow_up: s.follow_up });
    updateSubmissionBadge();
    toast(s.follow_up ? '🔔 Follow-up flagged' : 'Follow-up cleared', 'info');
  } catch(e) { console.warn('[3SBC] toggleFollowUp:', e); }
}

async function deleteSubmission(id) {
  if (!confirm('Delete this submission?')) return;
  try {
    if (_db) await _db.collection('submissions').doc(id).delete();
    STATE.submissions = STATE.submissions.filter(s => s.id !== id);
    renderSubmissions();
    renderPipelineStats();
    toast('Submission deleted', 'info');
  } catch(e) { toast('Delete failed', 'error'); }
}

function exportSubmissionsCSV() {
  const subs = STATE.submissions;
  if (!subs.length) { toast('No submissions to export', 'warn'); return; }

  const headers = ['Consultant','Skill','Job Title','Company','Board','Submitted On','Status','Rate','Vendor Email','Notes'];
  const rows = subs.map(s => [
    s.consultant_name, s.consultant_skill, s.job_title, s.company, s.board,
    formatDate(s.created_at), s.status, s.rate_offered ? `$${s.rate_offered}/hr` : '',
    s.vendor_email, s.notes,
  ].map(v => `"${String(v||'').replace(/"/g,'""')}"`).join(','));

  const csv = [headers.join(','), ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a'); a.href = url; a.download = '3SBC_Submissions.csv'; a.click();
  URL.revokeObjectURL(url);
  toast('Submissions exported!', 'success');
}

// ═══════════════════════════════════════════════════════════
// ─────────────────────────────────────────────────────────
// VENDORS TAB
// ─────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════
async function loadVendors() {
  try {
    if (_db) {
      const snap = await _db.collection('vendors').orderBy('company').get();
      STATE.vendors = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    }
  } catch(e) { console.warn('[3SBC] loadVendors:', e); }
  renderVendors();
}

function renderVendors() {
  const grid = document.getElementById('vendorGrid');
  if (!grid) return;

  if (!STATE.vendors.length) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
      <div class="e-icon">📞</div>
      <div class="e-title">No vendor contacts yet</div>
      <div class="e-sub">Add your first vendor contact to track relationships.</div>
    </div>`;
    return;
  }

  grid.innerHTML = STATE.vendors.map(v => {
    const skills = (v.skills || '').split(',').filter(Boolean);
    return `
      <div class="vendor-card">
        <div>
          <div class="vendor-name">${escHtml(v.name || '—')}</div>
          <div class="vendor-company">${escHtml(v.company || '—')}</div>
        </div>
        <div class="vendor-meta">
          ${v.email ? `<div class="vendor-meta-row">✉️ <a href="mailto:${escHtml(v.email)}">${escHtml(v.email)}</a></div>` : ''}
          ${v.phone ? `<div class="vendor-meta-row">📱 ${escHtml(v.phone)}</div>` : ''}
          ${v.location ? `<div class="vendor-meta-row">📍 ${escHtml(v.location)}</div>` : ''}
          ${v.last_contacted ? `<div class="vendor-meta-row" style="color:var(--text-muted)">🕐 Last: ${escHtml(v.last_contacted)}</div>` : ''}
        </div>
        ${skills.length ? `<div class="vendor-skills">${skills.map(s => `<span class="skill-chip">${escHtml(s.trim())}</span>`).join('')}</div>` : ''}
        ${v.notes ? `<div style="font-size:11px;color:var(--text-muted)">${escHtml(v.notes)}</div>` : ''}
        <div class="flex gap-2" style="margin-top:4px">
          <button class="cand-btn cand-btn-ghost" onclick="deleteVendor('${v.id}')">🗑 Delete</button>
        </div>
      </div>`;
  }).join('');
}

async function addVendor() {
  const name    = document.getElementById('vName').value.trim();
  const company = document.getElementById('vCompany').value.trim();
  const email   = document.getElementById('vEmail').value.trim();
  const phone   = document.getElementById('vPhone').value.trim();
  const skills  = document.getElementById('vSkills').value.trim();
  const loc     = document.getElementById('vLocation').value.trim();
  const notes   = document.getElementById('vNotes').value.trim();

  if (!name || !company) { toast('Name and company required', 'warn'); return; }

  const record = { name, company, email, phone, skills, location: loc, notes, last_contacted: '', created_at: Date.now()/1000 };

  try {
    if (_db) {
      const ref = await _db.collection('vendors').add(record);
      STATE.vendors.push({ id: ref.id, ...record });
    } else {
      STATE.vendors.push({ id: 'local_' + Date.now(), ...record });
    }
    toast(`✅ ${name} at ${company} added`, 'success');
    closeModal('vendorModal');
    renderVendors();
  } catch(e) { toast('Add failed: ' + e.message, 'error'); }
}

async function deleteVendor(id) {
  if (!confirm('Delete this contact?')) return;
  try {
    if (_db) await _db.collection('vendors').doc(id).delete();
    STATE.vendors = STATE.vendors.filter(v => v.id !== id);
    renderVendors();
    toast('Contact deleted', 'info');
  } catch(e) { toast('Delete failed', 'error'); }
}

// ═══════════════════════════════════════════════════════════
// ─────────────────────────────────────────────────────────
// ANALYTICS TAB
// ─────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════
function renderAnalytics() {
  const subs = STATE.submissions;
  const counts = { Submitted: 0, Interviewing: 0, Offered: 0, Placed: 0 };
  const byBoard = {};

  subs.forEach(s => {
    if (counts[s.status] !== undefined) counts[s.status]++;
    if (s.board) byBoard[s.board] = (byBoard[s.board] || 0) + 1;
  });

  const total   = subs.length || 1;
  const funnelEl = document.getElementById('funnelBars');
  if (funnelEl) {
    funnelEl.innerHTML = [
      { label: 'Submitted',    val: counts.Submitted,    color: '#06b6d4' },
      { label: 'Interviewing', val: counts.Interviewing, color: '#f59e0b' },
      { label: 'Offered',      val: counts.Offered,      color: '#8b5cf6' },
      { label: 'Placed',       val: counts.Placed,       color: '#10b981' },
    ].map(({ label, val, color }) => `
      <div class="funnel-item">
        <div class="funnel-label">${label}</div>
        <div class="funnel-track">
          <div class="funnel-fill" style="width:${Math.round((val/total)*100)}%;background:${color}">${val>0?val:''}</div>
        </div>
        <div class="funnel-count" style="color:${color}">${val}</div>
      </div>`).join('');
  }

  const boardColors = { dice:'#ef4444', indeed:'#2563eb', linkedin:'#0a66c2', ziprecruiter:'#22c55e', monster:'#7c3aed' };
  const maxBoard    = Math.max(...Object.values(byBoard), 1);
  const boardEl     = document.getElementById('boardPerf');
  if (boardEl) {
    boardEl.innerHTML = Object.entries(byBoard).sort((a,b)=>b[1]-a[1]).map(([board, count]) => `
      <div class="board-perf-row">
        <div class="board-perf-name" style="text-transform:capitalize">${board}</div>
        <div class="board-perf-track">
          <div class="board-perf-fill" style="width:${Math.round((count/maxBoard)*100)}%;background:${boardColors[board]||'#6b7280'}"></div>
        </div>
        <div class="board-perf-count">${count}</div>
      </div>`).join('') || '<div class="text-muted text-sm" style="padding:12px">Submit jobs to see board performance</div>';
  }

  // Consultant performance
  const byConsultant = {};
  subs.forEach(s => { byConsultant[s.consultant_name] = (byConsultant[s.consultant_name] || 0) + 1; });
  const topConsultants = Object.entries(byConsultant).sort((a,b)=>b[1]-a[1]).slice(0,5);
  const maxCand = Math.max(...topConsultants.map(c=>c[1]), 1);
  const candEl  = document.getElementById('topConsultants');
  if (candEl) {
    candEl.innerHTML = topConsultants.length
      ? topConsultants.map(([name, count]) => `
          <div class="board-perf-row">
            <div class="board-perf-name">${escHtml(name)}</div>
            <div class="board-perf-track">
              <div class="board-perf-fill" style="width:${Math.round((count/maxCand)*100)}%;background:var(--accent)"></div>
            </div>
            <div class="board-perf-count">${count}</div>
          </div>`).join('')
      : '<div class="text-muted text-sm" style="padding:12px">No submission data yet</div>';
  }

  // KPI cards
  const placed  = counts.Placed;
  const hitRate = subs.length ? Math.round((counts.Interviewing + counts.Offered + placed) / subs.length * 100) : 0;
  const placeRate = subs.length ? Math.round(placed / subs.length * 100) : 0;
  if (document.getElementById('aKpiTotal'))     document.getElementById('aKpiTotal').textContent     = subs.length;
  if (document.getElementById('aKpiPlaced'))    document.getElementById('aKpiPlaced').textContent    = placed;
  if (document.getElementById('aKpiHitRate'))   document.getElementById('aKpiHitRate').textContent   = hitRate + '%';
  if (document.getElementById('aKpiPlaceRate')) document.getElementById('aKpiPlaceRate').textContent = placeRate + '%';
}

// ═══════════════════════════════════════════════════════════
// MODAL HELPERS
// ═══════════════════════════════════════════════════════════
function closeModal(id) {
  document.getElementById(id)?.classList.add('hidden');
}

function openVendorModal() {
  document.getElementById('vendorModal').classList.remove('hidden');
}

// ═══════════════════════════════════════════════════════════
// INITIALISE
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  initFirebase();
  setupAuth();
  setupTabs();
  setupJobFinder();

  // Global close on overlay click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.add('hidden');
    });
  });

  // Bench search
  document.getElementById('benchSearch')?.addEventListener('input', e => renderBench(e.target.value));
  document.getElementById('benchTeamFilter')?.addEventListener('change', e => renderBench(e.target.value));

  // Submit modal buttons
  document.getElementById('checkDupBtn')?.addEventListener('click', checkDuplicate);
  document.getElementById('genEmailBtn')?.addEventListener('click', generateEmail);
  document.getElementById('copyEmailBtn')?.addEventListener('click', copyEmail);
  document.getElementById('confirmSubmitBtn')?.addEventListener('click', confirmSubmit);

  // Vendor add
  document.getElementById('confirmAddVendorBtn')?.addEventListener('click', addVendor);

  // Export
  document.getElementById('exportSubmissionsBtn')?.addEventListener('click', exportSubmissionsCSV);

  // Legacy export button
  const exportBtn = document.getElementById('exportBtn');
  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      const records = STATE.allCandidates;
      if (!records.length) { toast('No data to export', 'warn'); return; }
      const headers = Object.keys(records[0]);
      const rows    = records.map(r => headers.map(h => `"${String(r[h]||'').replace(/"/g,'""')}"`).join(','));
      const csv     = [headers.join(','), ...rows].join('\n');
      const blob    = new Blob([csv], { type: 'text/csv' });
      const url     = URL.createObjectURL(blob);
      const a       = document.createElement('a'); a.href = url; a.download = '3SBC_Candidates.csv'; a.click();
      toast('Candidates exported!', 'success');
    });
  }
});
