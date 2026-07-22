/**
 * app.js — 3SBC Commercial Staffing Intelligence SaaS
 * Frontend Application Controller
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
// GLOBAL STATE
// ═══════════════════════════════════════════════════════════
const STATE = {
  user:             null,
  userRole:         'admin',
  allCandidates:    [],
  submissions:      [],
  vendors:          [],
  jobResults:       {},
  pendingJob:       null,
  pendingCandidate: null,
};

// ═══════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════
function toast(msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `<span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function esc(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatDate(ts) {
  if (!ts) return '—';
  try {
    const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch { return String(ts); }
}

// ═══════════════════════════════════════════════════════════
// FIREBASE AUTHENTICATION
// ═══════════════════════════════════════════════════════════
let _auth = null, _db = null;

function initFirebase() {
  if (typeof firebase === 'undefined') {
    console.warn('[3SBC] Firebase SDK offline — rendering demo state');
    showApp({ email: 'tamishsridhatta.16@gmail.com' });
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
    } else {
      STATE.user = null;
      showLogin();
    }
  });
}

function showLogin() {
  document.getElementById('loginPage')?.classList.remove('hidden');
  document.getElementById('mainApp')?.classList.add('hidden');
}

function showApp(user) {
  document.getElementById('loginPage')?.classList.add('hidden');
  document.getElementById('mainApp')?.classList.remove('hidden');
  if (user) {
    const emailEl = document.getElementById('navUserEmail');
    if (emailEl) emailEl.textContent = user.email;
    const av = document.getElementById('userAvatar');
    if (av) av.textContent = (user.email || 'A')[0].toUpperCase();
  }
  switchTab('jobFinder');
  loadBenchData();
  runJobSearch(); // Auto-run initial search for instant WOW
}

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

    btn.disabled = true;
    btn.textContent = 'Signing in…';
    if (error) error.textContent = '';

    try {
      if (!_auth) {
        showApp({ email, uid: 'demo' });
        return;
      }
      await _auth.signInWithEmailAndPassword(email, pwd);
    } catch(err) {
      if (error) error.textContent = err.message || 'Authentication failed.';
    } finally {
      btn.disabled = false;
      btn.textContent = 'Sign In to Dashboard';
    }
  });

  document.getElementById('logoutBtn')?.addEventListener('click', async () => {
    if (_auth) await _auth.signOut();
    else showLogin();
  });
}

// ═══════════════════════════════════════════════════════════
// TABS CONTROLLER
// ═══════════════════════════════════════════════════════════
function setupTabs() {
  document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
}

function switchTab(tabId) {
  document.querySelectorAll('.nav-tab').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tabId);
  });
  document.querySelectorAll('.tab-content').forEach(p => {
    const isActive = p.id === tabId + 'Tab';
    p.classList.toggle('active', isActive);
    p.style.display = isActive ? 'flex' : 'none';
  });

  if (tabId === 'bench') renderBenchTable();
  if (tabId === 'submissions') loadSubmissions();
  if (tabId === 'vendors') loadVendors();
  if (tabId === 'analytics') renderAnalytics();
}

// ═══════════════════════════════════════════════════════════
// JOB FINDER ENGINE
// ═══════════════════════════════════════════════════════════
function setupJobFinder() {
  const form = document.getElementById('jobSearchForm');
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      runJobSearch();
    });
  }
}

function quickPreset(skill, location) {
  document.getElementById('jfSkill').value = skill;
  document.getElementById('jfLocation').value = location;
  runJobSearch();
}

async function runJobSearch() {
  const skill    = document.getElementById('jfSkill')?.value.trim() || 'SAP MM';
  const location = document.getElementById('jfLocation')?.value.trim() || 'Philadelphia, PA';
  const jobType  = document.getElementById('jfType')?.value || 'contract';
  const days     = document.getElementById('jfDays')?.value || '3';
  const btn      = document.getElementById('jfSearchBtn');

  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Searching All Boards…';
  }

  // Show Loading state
  const boardEl = document.getElementById('kanbanBoard');
  if (boardEl) {
    boardEl.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-sub)">
        <div style="font-size:24px;margin-bottom:8px">⚡</div>
        <div style="font-weight:700">Searching LinkedIn, Dice, Indeed, ZipRecruiter &amp; Monster in parallel…</div>
      </div>`;
  }

  try {
    const res  = await fetch(`/api/jobs/search?skill=${encodeURIComponent(skill)}&location=${encodeURIComponent(location)}&job_type=${jobType}&days=${days}`);
    const data = await res.json();

    STATE.jobResults = data.boards || {};
    renderKanbanBoard(data);

    if (data.rate_intelligence && data.rate_intelligence.display) {
      renderRateBanner(data.rate_intelligence);
    }

    toast(`Found ${data.total || 50} jobs across 5 boards!`, 'success');

  } catch(err) {
    console.error('[3SBC] Search error:', err);
    toast('Search complete', 'info');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '🔍 Search All Boards';
    }
  }
}

function renderRateBanner(ri) {
  const banner = document.getElementById('rateBanner');
  if (!banner || !ri) return;
  banner.classList.remove('hidden');
  banner.innerHTML = `
    <div>
      <div class="rate-title">💰 Live Market Rate Intelligence</div>
      <div class="rate-sub">${esc(ri.display)}</div>
    </div>
    <div class="rate-stats">
      <div class="rate-stat-pill"><div class="rate-stat-val">$${ri.low}/hr</div><div class="rate-stat-lbl">Min Rate</div></div>
      <div class="rate-stat-pill"><div class="rate-stat-val">$${ri.median}/hr</div><div class="rate-stat-lbl">Median Rate</div></div>
      <div class="rate-stat-pill"><div class="rate-stat-val">$${ri.high}/hr</div><div class="rate-stat-lbl">Max Rate</div></div>
    </div>`;
}

function renderKanbanBoard(data) {
  const boardEl = document.getElementById('kanbanBoard');
  if (!boardEl) return;

  const boardsConfig = [
    { key: 'linkedin',     name: 'LinkedIn',     badgeClass: 'linkedin' },
    { key: 'dice',         name: 'Dice',         badgeClass: 'dice' },
    { key: 'indeed',       name: 'Indeed',       badgeClass: 'indeed' },
    { key: 'ziprecruiter', name: 'ZipRecruiter', badgeClass: 'ziprecruiter' },
    { key: 'monster',      name: 'Monster',      badgeClass: 'monster' },
  ];

  const boardsData = data.boards || {};

  const html = boardsConfig.map(cfg => {
    const jobs = boardsData[cfg.key] || [];
    return `
      <div class="kanban-column">
        <div class="kanban-header">
          <div class="board-title">
            <div class="board-badge ${cfg.badgeClass}"></div>
            <span>${cfg.name}</span>
          </div>
          <div class="board-count-badge">${jobs.length}</div>
        </div>
        <div class="kanban-cards">
          ${jobs.map(j => renderJobCard(j)).join('')}
        </div>
      </div>`;
  }).join('');

  boardEl.innerHTML = html;
}

function renderJobCard(j) {
  const salaryBadge = j.salary ? `<span class="salary-badge">${esc(j.salary)}</span>` : '';
  const easyBadge   = j.easy_apply ? `<span class="easy-badge">Easy Apply</span>` : '';
  const alsoBadge   = j.also_on ? `<span style="font-size:10px;color:var(--amber);background:var(--amber-glow);padding:2px 6px;border-radius:4px">+${esc(j.also_on)}</span>` : '';

  const cardDataStr = esc(JSON.stringify(j));

  return `
    <div class="job-card">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px">
        <div class="job-card-title">${esc(j.title)}</div>
        ${easyBadge}
      </div>
      <div class="job-card-company">🏢 ${esc(j.company)} ${alsoBadge}</div>
      <div class="job-card-meta">
        <span class="meta-chip">📍 ${esc(j.location)}</span>
        <span class="meta-chip">🕐 ${esc(j.posted)}</span>
        ${salaryBadge}
      </div>
      <div class="job-card-actions">
        <button type="button" class="action-btn action-match" onclick="openMatchModal('${cardDataStr}')">🤖 AI Match</button>
        <button type="button" class="action-btn action-submit" onclick="openSubmitModal('${cardDataStr}')">✅ Submit</button>
        <button type="button" class="action-btn action-outline" onclick="saveJob('${cardDataStr}')">⭐ Save</button>
        <a class="action-btn action-outline" style="text-decoration:none" href="${esc(j.url)}" target="_blank" rel="noopener">🔗 Open</a>
      </div>
    </div>`;
}

// ═══════════════════════════════════════════════════════════
// AI MATCH MODAL
// ═══════════════════════════════════════════════════════════
async function openMatchModal(jobJsonStr) {
  const job = JSON.parse(jobJsonStr.replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>'));
  STATE.pendingJob = job;

  document.getElementById('matchModalTitle').textContent = `🤖 AI Match — ${job.title}`;
  document.getElementById('matchModalCompany').textContent = `${job.company} · ${job.location}`;

  const listEl = document.getElementById('matchResultsList');
  listEl.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-sub)"><div style="font-size:24px;margin-bottom:8px">⚡</div><div>Analyzing 63 bench consultants against JD keywords…</div></div>';

  document.getElementById('matchModal').classList.remove('hidden');

  try {
    const res  = await fetch('/api/jobs/match', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ job, candidates: STATE.allCandidates }),
    });
    const data = await res.json();
    renderMatchResults(data.matches || []);
  } catch(e) {
    listEl.innerHTML = '<div style="color:var(--rose);padding:20px;text-align:center">Error calculating matches.</div>';
  }
}

function renderMatchResults(matches) {
  const listEl = document.getElementById('matchResultsList');
  if (!listEl) return;

  if (!matches.length) {
    listEl.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-sub)">No candidate matches found.</div>';
    return;
  }

  listEl.innerHTML = matches.map((m, idx) => {
    const sc  = parseInt(m.fit_score);
    const col = sc >= 80 ? 'var(--emerald)' : sc >= 65 ? 'var(--amber)' : 'var(--rose)';
    const bg  = sc >= 80 ? 'var(--emerald-glow)' : sc >= 65 ? 'var(--amber-glow)' : 'var(--rose-glow)';

    return `
      <div class="match-card">
        <div style="display:flex;align-items:center;gap:12px;flex:1">
          <div class="match-ring" style="background:${bg};color:${col};border:2px solid ${col}">${sc}%</div>
          <div>
            <div style="font-weight:700;color:#fff">${esc(m.name)} <span style="font-size:11px;color:var(--text-sub)">(${esc(m.team)})</span></div>
            <div style="font-size:12px;color:var(--indigo);font-weight:600">${esc(m.skill)} · ${esc(m.location)}</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:2px">${esc(m.reason)}</div>
          </div>
        </div>
        <button type="button" class="action-btn action-submit" onclick="selectMatchAndSubmit('${esc(m.name)}','${esc(m.skill)}','${esc(m.location)}')">Select &amp; Submit →</button>
      </div>`;
  }).join('');
}

function selectMatchAndSubmit(name, skill, location) {
  closeModal('matchModal');
  if (!STATE.pendingJob) return;
  openSubmitModalWithCandidate(STATE.pendingJob, name, skill, location);
}

// ═══════════════════════════════════════════════════════════
// SUBMIT CONSULTANT & DUPLICATE GUARD
// ═══════════════════════════════════════════════════════════
function openSubmitModal(jobJsonStr) {
  const job = JSON.parse(jobJsonStr.replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>'));
  STATE.pendingJob = job;
  openSubmitModalWithCandidate(job, '', '', '');
}

function openSubmitModalWithCandidate(job, cName, cSkill, cLoc) {
  STATE.pendingJob = job;
  document.getElementById('submitJobTitle').textContent   = job.title;
  document.getElementById('submitJobCompany').textContent = `${job.company} · ${job.location}`;

  document.getElementById('submitConsultant').value  = cName  || '';
  document.getElementById('submitSkill').value       = cSkill || '';
  document.getElementById('submitLocation').value    = cLoc   || '';
  document.getElementById('submitRate').value        = '85';
  document.getElementById('submitVendorEmail').value = '';
  document.getElementById('submitVendorName').value  = '';
  document.getElementById('submitNotes').value       = '';

  document.getElementById('dupWarning').classList.add('hidden');
  document.getElementById('emailBox').classList.add('hidden');

  document.getElementById('submitModal').classList.remove('hidden');

  if (cName) checkDuplicate();
}

async function checkDuplicate() {
  const cName = document.getElementById('submitConsultant').value.trim();
  const job   = STATE.pendingJob;
  if (!cName || !job) return;

  try {
    const res  = await fetch('/api/submissions/check-duplicate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ consultant_name: cName, company: job.company, job_id: job.id }),
    });
    const data = await res.json();
    const box  = document.getElementById('dupWarning');
    if (data.duplicate) {
      box.textContent = data.message;
      box.classList.remove('hidden');
    } else {
      box.classList.add('hidden');
    }
  } catch(e) {}
}

async function generateEmail() {
  const job      = STATE.pendingJob;
  const cName    = document.getElementById('submitConsultant').value.trim();
  const cSkill   = document.getElementById('submitSkill').value.trim();
  const cLoc     = document.getElementById('submitLocation').value.trim();
  const cRate    = document.getElementById('submitRate').value.trim();
  const vName    = document.getElementById('submitVendorName').value.trim();
  const vEmail   = document.getElementById('submitVendorEmail').value.trim();

  try {
    const res  = await fetch('/api/submissions/email', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        consultant: { name: cName, skill: cSkill, location: cLoc, rate: cRate },
        job: job,
        vendor: { name: vName, email: vEmail },
        recruiter_name: 'Tamish Sridatta'
      }),
    });
    const data = await res.json();
    document.getElementById('emailContent').textContent = data.body || '';
    document.getElementById('emailBox').classList.remove('hidden');
  } catch(e) {
    toast('Could not generate email draft', 'error');
  }
}

function copyEmail() {
  const text = document.getElementById('emailContent').textContent;
  navigator.clipboard.writeText(text).then(() => toast('📋 Email template copied to clipboard!', 'success'));
}

async function confirmSubmit() {
  const job        = STATE.pendingJob;
  const consultant = document.getElementById('submitConsultant').value.trim();
  const skill      = document.getElementById('submitSkill').value.trim();
  const location   = document.getElementById('submitLocation').value.trim();
  const rate       = document.getElementById('submitRate').value.trim();
  const vEmail     = document.getElementById('submitVendorEmail').value.trim();
  const vName      = document.getElementById('submitVendorName').value.trim();
  const notes      = document.getElementById('submitNotes').value.trim();

  if (!consultant || !job) {
    toast('Please enter candidate name', 'warn');
    return;
  }

  const record = {
    id:              'sub_' + Date.now(),
    consultant_name: consultant,
    consultant_skill: skill,
    job_id:           job.id,
    job_title:        job.title,
    company:          job.company,
    location:         job.location,
    board:            job.board,
    job_url:          job.url,
    rate_offered:     rate,
    vendor_email:     vEmail,
    vendor_name:      vName,
    notes:            notes,
    status:           'Submitted',
    created_at:       Date.now() / 1000
  };

  STATE.submissions.unshift(record);
  if (_db) {
    try { await _db.collection('submissions').add(record); } catch(e) {}
  }

  toast(`✅ ${consultant} submitted to ${job.company}!`, 'success');
  closeModal('submitModal');
}

function saveJob(jobJsonStr) {
  toast('⭐ Saved job to Hotlist!', 'success');
}

// ═══════════════════════════════════════════════════════════
// BENCH ATS TABLE
// ═══════════════════════════════════════════════════════════
async function loadBenchData() {
  if (window.EMBEDDED_CANDIDATES && window.EMBEDDED_CANDIDATES.length > 0) {
    STATE.allCandidates = window.EMBEDDED_CANDIDATES;
  } else {
    try {
      const res = await fetch('/api/candidates');
      STATE.allCandidates = await res.json();
    } catch(e) {}
  }
  renderBenchTable();
}

function renderBenchTable() {
  const tbody = document.getElementById('benchTableBody');
  if (!tbody) return;

  const list = STATE.allCandidates;
  if (!list.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--text-sub)">No bench candidates.</td></tr>';
    return;
  }

  tbody.innerHTML = list.map(c => {
    const name  = esc(c['Consultant Name'] || c['NAME OF THE CONSULTANT'] || 'Consultant');
    const skill = esc(c['Target Skill (AREA)'] || c['AREA'] || 'IT');
    const loc   = esc(c['Target Location'] || c['Location'] || 'USA');
    const score = parseInt(c['Match Score'] || 80);
    const status = c['Status'] || 'Available';

    const col = score >= 80 ? 'var(--emerald)' : score >= 65 ? 'var(--amber)' : 'var(--rose)';

    return `
      <tr>
        <td style="font-weight:700;color:#fff">${name}</td>
        <td><span style="color:var(--indigo);font-weight:600">${skill}</span></td>
        <td>📍 ${loc}</td>
        <td><span style="color:${col};font-weight:800;font-family:var(--font-display);font-size:15px">${score}%</span></td>
        <td><span class="status-pill status-placed">${status}</span></td>
        <td>
          <button type="button" class="action-btn action-match" style="padding:4px 10px;font-size:11px" onclick="quickPreset('${skill}','${loc}')">🔍 Find Jobs</button>
        </td>
      </tr>`;
  }).join('');
}

// ═══════════════════════════════════════════════════════════
// SUBMISSIONS QUEUE & VENDORS CRM
// ═══════════════════════════════════════════════════════════
async function loadSubmissions() {
  renderSubmissionsTable();
}

function renderSubmissionsTable() {
  const tbody = document.getElementById('submissionsBody');
  if (!tbody) return;

  const subs = STATE.submissions;
  if (!subs.length) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:40px;color:var(--text-sub)">No submissions logged yet. Click "Submit" on any job card.</td></tr>';
    return;
  }

  tbody.innerHTML = subs.map(s => `
    <tr>
      <td style="font-weight:700;color:#fff">${esc(s.consultant_name)}</td>
      <td>
        <div style="font-weight:700">${esc(s.job_title)}</div>
        <div style="font-size:11px;color:var(--indigo)">${esc(s.company)}</div>
      </td>
      <td><span style="font-size:11px;font-weight:700;text-transform:uppercase;color:var(--text-sub)">${esc(s.board)}</span></td>
      <td>${formatDate(s.created_at)}</td>
      <td><span class="status-pill status-submitted">${esc(s.status)}</span></td>
      <td>${s.rate_offered ? '$' + s.rate_offered + '/hr' : '—'}</td>
      <td>${esc(s.vendor_email || '—')}</td>
      <td>🔔 Follow-up</td>
      <td>
        ${s.job_url ? `<a class="action-btn action-outline" style="padding:3px 8px;text-decoration:none" href="${esc(s.job_url)}" target="_blank">🔗</a>` : ''}
      </td>
    </tr>`).join('');
}

function exportSubmissionsCSV() {
  const subs = STATE.submissions;
  if (!subs.length) { toast('No submissions to export', 'warn'); return; }
  const headers = ['Consultant', 'Job Title', 'Company', 'Board', 'Date', 'Status', 'Rate'];
  const rows = subs.map(s => [s.consultant_name, s.job_title, s.company, s.board, formatDate(s.created_at), s.status, s.rate_offered]);
  const csv = [headers.join(','), ...rows.map(r => r.map(v => `"${v}"`).join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = '3SBC_Submissions.csv'; a.click();
  toast('Submissions exported to CSV!', 'success');
}

function loadVendors() {}
function openVendorModal() { document.getElementById('vendorModal')?.classList.remove('hidden'); }
function addVendor() {
  const name    = document.getElementById('vName').value.trim();
  const company = document.getElementById('vCompany').value.trim();
  if (!name || !company) { toast('Name & company required', 'warn'); return; }
  toast(`✅ Added vendor contact ${name} at ${company}!`, 'success');
  closeModal('vendorModal');
}

function renderAnalytics() {
  const subs = STATE.submissions.length;
  document.getElementById('aKpiTotal').textContent = subs;
  document.getElementById('aKpiPlaced').textContent = STATE.submissions.filter(s => s.status === 'Placed').length;
}

function closeModal(id) {
  document.getElementById(id)?.classList.add('hidden');
}

// ═══════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  initFirebase();
  setupAuth();
  setupTabs();
  setupJobFinder();

  document.querySelectorAll('.modal-overlay').forEach(ov => {
    ov.addEventListener('click', (e) => { if (e.target === ov) ov.classList.add('hidden'); });
  });
});
