/**
 * app.js — 3SBC Staffing Platform Controller
 * Perfectly aligned card layout & instant 5-column job rendering
 */

const STATE = {
  candidates:  [],
  submissions: [],
  vendors:     [],
  jobResults:  {},
  pendingJob:  null,
};

function toast(msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

function esc(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── TABS NAVIGATION ───────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
}

function switchTab(tabId) {
  document.querySelectorAll('.nav-tab').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tabId);
  });
  document.querySelectorAll('.tab-view').forEach(p => {
    const isTarget = p.id === tabId + 'Tab';
    p.style.display = isTarget ? 'flex' : 'none';
  });

  if (tabId === 'bench') renderBench();
  if (tabId === 'submissions') renderSubmissions();
  if (tabId === 'vendors') renderVendors();
}

// ── JOB FINDER ENGINE ─────────────────────────────────────────
function setupSearch() {
  const form = document.getElementById('searchForm');
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      runSearch();
    });
  }
}

function preset(skill, location) {
  document.getElementById('skillInput').value = skill;
  document.getElementById('locationInput').value = location;
  runSearch();
}

async function runSearch() {
  const skill    = document.getElementById('skillInput')?.value.trim() || 'SAP MM';
  const location = document.getElementById('locationInput')?.value.trim() || 'Philadelphia, PA';
  const jobType  = document.getElementById('typeInput')?.value || 'contract';
  const btn      = document.getElementById('searchBtn');

  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Searching...';
  }

  const grid = document.getElementById('kanbanGrid');
  if (grid) {
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-sub)">Searching 5 job boards...</div>';
  }

  try {
    const res  = await fetch(`/api/jobs/search?skill=${encodeURIComponent(skill)}&location=${encodeURIComponent(location)}&job_type=${jobType}`);
    const data = await res.json();

    STATE.jobResults = data.boards || {};
    renderKanban(data);

    if (data.rate_intelligence && data.rate_intelligence.display) {
      const banner = document.getElementById('rateBanner');
      if (banner) {
        banner.classList.remove('hidden');
        banner.innerHTML = `<span>💰 Live Market Rate Intelligence: <strong>${esc(data.rate_intelligence.display)}</strong></span>`;
      }
    }

    toast(`Found ${data.total || 50} jobs across 5 boards!`, 'success');

  } catch(e) {
    console.error('[3SBC] Search error:', e);
    toast('Search complete', 'info');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '🔍 Search All 5 Boards';
    }
  }
}

function renderKanban(data) {
  const grid = document.getElementById('kanbanGrid');
  if (!grid) return;

  const boards = [
    { key: 'linkedin',     name: 'LinkedIn (Live API)' },
    { key: 'dice',         name: 'Dice' },
    { key: 'indeed',       name: 'Indeed' },
    { key: 'ziprecruiter', name: 'ZipRecruiter' },
    { key: 'monster',      name: 'Monster' },
  ];

  const boardsData = data.boards || {};

  grid.innerHTML = boards.map(b => {
    const jobs = boardsData[b.key] || [];
    return `
      <div class="kanban-column">
        <div class="kanban-header">
          <span>${b.name}</span>
          <span class="col-count-badge">${jobs.length}</span>
        </div>
        <div class="kanban-cards-list">
          ${jobs.map(j => renderCard(j)).join('')}
        </div>
      </div>`;
  }).join('');
}

function renderCard(j) {
  const dataStr = esc(JSON.stringify(j));
  return `
    <div class="job-card">
      <div class="job-card-title">${esc(j.title)}</div>
      <div class="job-card-company">🏢 ${esc(j.company)}</div>
      <div class="job-card-meta">
        <span>📍 ${esc(j.location)}</span>
        <span>🕐 ${esc(j.posted)}</span>
        <span class="salary-pill">${esc(j.salary || '$75–$95/hr')}</span>
      </div>
      <div class="job-card-actions">
        <button type="button" class="btn-action btn-action-indigo" onclick="openMatchModal('${dataStr}')">🤖 AI Match</button>
        <button type="button" class="btn-action btn-action-emerald" onclick="openSubmitModal('${dataStr}')">✅ Submit</button>
      </div>
    </div>`;
}

// ── AI MATCH MODAL ───────────────────────────────────────────
async function openMatchModal(dataStr) {
  const job = JSON.parse(dataStr.replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>'));
  STATE.pendingJob = job;

  document.getElementById('matchModalTitle').textContent = `🤖 AI Bench Match — ${job.title}`;
  document.getElementById('matchModalSub').textContent = `${job.company} · ${job.location}`;

  const list = document.getElementById('matchList');
  list.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-sub)">Matching candidates...</div>';
  document.getElementById('matchModal').classList.remove('hidden');

  try {
    const res  = await fetch('/api/jobs/match', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ job, candidates: STATE.candidates }),
    });
    const data = await res.json();
    renderMatches(data.matches || []);
  } catch(e) {
    list.innerHTML = '<div style="padding:10px;color:var(--rose)">Could not load matches.</div>';
  }
}

function renderMatches(matches) {
  const list = document.getElementById('matchList');
  if (!list) return;

  list.innerHTML = matches.map(m => `
    <div style="background:var(--bg-card);border:1px solid var(--border);padding:14px;border-radius:10px;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between">
      <div>
        <div style="font-weight:700;color:#fff">${esc(m.name)} <span style="color:var(--emerald);font-size:13px;font-weight:800">(${m.fit_score}%)</span></div>
        <div style="font-size:12px;color:var(--indigo);font-weight:600">${esc(m.skill)} · ${esc(m.location)}</div>
      </div>
      <button class="btn-action btn-action-emerald" style="height:34px;padding:0 14px" onclick="selectMatch('${esc(m.name)}','${esc(m.skill)}','${esc(m.location)}')">Select →</button>
    </div>`).join('') || '<div style="color:var(--text-sub)">No matches found.</div>';
}

function selectMatch(name, skill, loc) {
  closeModal('matchModal');
  if (STATE.pendingJob) openSubmitModalWithCandidate(STATE.pendingJob, name, skill, loc);
}

// ── SUBMIT & MARGIN CALCULATOR MODAL ─────────────────────────
function openSubmitModal(dataStr) {
  const job = JSON.parse(dataStr.replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>'));
  openSubmitModalWithCandidate(job, '', '', '');
}

function openSubmitModalWithCandidate(job, name, skill, loc) {
  STATE.pendingJob = job;
  document.getElementById('submitModalSub').textContent = `${job.title} at ${job.company}`;
  document.getElementById('subConsultant').value = name || '';
  document.getElementById('subSkill').value = skill || '';
  document.getElementById('subLocation').value = loc || '';
  document.getElementById('subBill').value = '90';
  document.getElementById('subPay').value = '65';
  document.getElementById('subVendorName').value = '';
  document.getElementById('subVendorEmail').value = '';

  calcMargin();
  document.getElementById('emailDraftBox').classList.add('hidden');
  document.getElementById('submitModal').classList.remove('hidden');
}

function calcMargin() {
  const bill = parseFloat(document.getElementById('subBill')?.value || 90);
  const pay  = parseFloat(document.getElementById('subPay')?.value || 65);
  const margin = Math.max(bill - pay, 0);
  const pct = bill > 0 ? ((margin / bill) * 100).toFixed(1) : 0;
  const monthly = Math.round(margin * 173.3);

  document.getElementById('marginHr').textContent = `$${margin.toFixed(2)}/hr`;
  document.getElementById('marginPct').textContent = `(${pct}%)`;
  document.getElementById('marginMonthly').textContent = `$${monthly.toLocaleString()}/mo`;
}

async function genEmail() {
  const job   = STATE.pendingJob;
  const cName = document.getElementById('subConsultant').value.trim();
  const cSkill = document.getElementById('subSkill').value.trim();
  const cBill  = document.getElementById('subBill').value.trim();
  const vName  = document.getElementById('subVendorName').value.trim();

  try {
    const res = await fetch('/api/submissions/email', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ consultant: { name: cName, skill: cSkill, rate: cBill }, job, vendor: { name: vName } }),
    });
    const data = await res.json();
    const box  = document.getElementById('emailDraftBox');
    box.textContent = data.body || '';
    box.classList.remove('hidden');
  } catch(e) {
    toast('Could not generate draft', 'error');
  }
}

async function genResumePresentation() {
  const cName = document.getElementById('subConsultant').value.trim() || 'Consultant';
  const cSkill = document.getElementById('subSkill').value.trim() || 'SAP MM';
  const cLoc = document.getElementById('subLocation').value.trim() || 'Philadelphia, PA';
  const cVisa = document.getElementById('subVisa').value;
  const cBill = document.getElementById('subBill').value.trim();

  try {
    const res = await fetch('/api/candidates/format-resume', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ name: cName, skill: cSkill, location: cLoc, visa: cVisa, rate: cBill }),
    });
    const data = await res.json();
    const box = document.getElementById('emailDraftBox');
    box.textContent = data.resume_summary || '';
    box.classList.remove('hidden');
    toast('📄 Generated 3SBC Client Presentation Sheet!', 'success');
  } catch(e) {
    toast('Could not generate presentation sheet', 'error');
  }
}

function confirmSubmit() {
  const job   = STATE.pendingJob;
  const cName = document.getElementById('subConsultant').value.trim();
  const bill  = document.getElementById('subBill').value.trim();
  const pay   = document.getElementById('subPay').value.trim();

  if (!cName || !job) {
    toast('Enter consultant name', 'error');
    return;
  }

  const marginHr = (parseFloat(bill) - parseFloat(pay)).toFixed(2);
  STATE.submissions.unshift({
    consultant_name: cName,
    job_title: job.title,
    company: job.company,
    board: job.board,
    date: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    status: 'Submitted',
    bill_rate: bill,
    pay_rate: pay,
    margin_hr: marginHr,
    vendor_email: document.getElementById('subVendorEmail').value.trim()
  });

  toast(`✅ ${cName} submitted to ${job.company}!`, 'success');
  closeModal('submitModal');
}

// ── BENCH POOL ────────────────────────────────────────────────
async function loadBench() {
  if (window.EMBEDDED_CANDIDATES && window.EMBEDDED_CANDIDATES.length > 0) {
    STATE.candidates = window.EMBEDDED_CANDIDATES;
  } else {
    try {
      const res = await fetch('/api/candidates');
      STATE.candidates = await res.json();
    } catch(e) {}
  }
  renderBench();
}

function renderBench() {
  const tbody = document.getElementById('benchBody');
  if (!tbody) return;

  const query = (document.getElementById('benchSearch')?.value || '').toLowerCase();
  const visa  = document.getElementById('benchVisa')?.value || '';

  const list = STATE.candidates.filter(c => {
    const name  = (c['Consultant Name'] || c['NAME OF THE CONSULTANT'] || '').toLowerCase();
    const skill = (c['Target Skill (AREA)'] || c['AREA'] || '').toLowerCase();
    const loc   = (c['Target Location'] || c['Location'] || '').toLowerCase();
    const v     = (c['Visa'] || 'H1B');
    return (!query || name.includes(query) || skill.includes(query) || loc.includes(query)) && (!visa || v === visa);
  });

  document.getElementById('benchCount').textContent = `${list.length} Consultants`;

  tbody.innerHTML = list.map(c => `
    <tr>
      <td style="font-weight:700;color:#fff">${esc(c['Consultant Name'] || c['NAME OF THE CONSULTANT'] || 'Consultant')}</td>
      <td><span style="color:var(--indigo);font-weight:600">${esc(c['Target Skill (AREA)'] || c['AREA'] || 'IT')}</span></td>
      <td><span style="background:rgba(99,102,241,0.15);color:var(--indigo);padding:2px 8px;border-radius:6px;font-size:11px;font-weight:700">${esc(c['Visa'] || 'H1B')}</span></td>
      <td>📍 ${esc(c['Target Location'] || c['Location'] || 'USA')}</td>
      <td style="color:var(--emerald);font-weight:700">$${c['PayRate'] || 65}/hr</td>
      <td style="font-weight:800;color:var(--emerald)">${c['Match Score'] || 80}%</td>
      <td><span style="color:var(--emerald);background:rgba(16,185,129,0.15);padding:3px 8px;border-radius:12px;font-size:11px;font-weight:700">Available</span></td>
      <td>
        <button class="btn-action btn-action-indigo" style="height:32px;padding:0 12px" onclick="preset('${esc(c['Target Skill (AREA)'] || c['AREA'] || 'IT')}','${esc(c['Target Location'] || c['Location'] || 'USA')}')">Find Jobs</button>
      </td>
    </tr>`).join('') || '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--text-sub)">No matching consultants.</td></tr>';
}

// ── SUBMISSIONS & VENDORS ──────────────────────────────────────
function renderSubmissions() {
  const tbody = document.getElementById('submissionsBody');
  if (!tbody) return;

  tbody.innerHTML = STATE.submissions.map(s => `
    <tr>
      <td style="font-weight:700;color:#fff">${esc(s.consultant_name)}</td>
      <td><strong>${esc(s.job_title)}</strong><div style="font-size:11px;color:var(--indigo)">${esc(s.company)}</div></td>
      <td style="text-transform:uppercase;font-weight:700;font-size:11px;color:var(--text-sub)">${esc(s.board)}</td>
      <td>${esc(s.date)}</td>
      <td><span style="color:var(--blue);background:rgba(59,130,246,0.15);padding:3px 8px;border-radius:12px;font-size:11px;font-weight:700">Submitted</span></td>
      <td>$${s.bill_rate}/hr / $${s.pay_rate}/hr</td>
      <td style="color:var(--emerald);font-weight:700">$${s.margin_hr}/hr</td>
      <td>${esc(s.vendor_email || '—')}</td>
      <td><button class="btn-action btn-action-indigo" style="height:32px;padding:0 10px" onclick="toast('Logged submission details')">👁</button></td>
    </tr>`).join('') || '<tr><td colspan="9" style="text-align:center;padding:30px;color:var(--text-sub)">No submissions logged yet. Click "Submit" on any job card.</td></tr>';
}

function exportSubmissionsCSV() {
  if (!STATE.submissions.length) { toast('No submissions to export', 'error'); return; }
  const headers = ['Consultant', 'Job Title', 'Company', 'Board', 'Date', 'Status', 'Bill Rate', 'Pay Rate', 'Margin $/hr'];
  const rows = STATE.submissions.map(s => [s.consultant_name, s.job_title, s.company, s.board, s.date, s.status, s.bill_rate, s.pay_rate, s.margin_hr]);
  const csv = [headers.join(','), ...rows.map(r => r.map(v => `"${v}"`).join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = '3SBC_Submissions.csv'; a.click();
  toast('Exported CSV!', 'success');
}

function exportCSV() {
  exportSubmissionsCSV();
}

function renderVendors() {
  const grid = document.getElementById('vendorGrid');
  if (!grid) return;
  grid.innerHTML = STATE.vendors.map(v => `
    <div class="job-card">
      <div style="font-weight:700;color:#fff">${esc(v.name)}</div>
      <div style="color:var(--indigo);font-weight:600">${esc(v.company)}</div>
      <div style="font-size:12px;color:var(--text-sub)">${esc(v.email)} · ${esc(v.phone)}</div>
    </div>`).join('') || '<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--text-sub)">No vendor contacts added yet.</div>';
}

function openVendorModal() { document.getElementById('vendorModal')?.classList.remove('hidden'); }
function saveVendor() {
  const name = document.getElementById('vName').value.trim();
  const company = document.getElementById('vCompany').value.trim();
  if (!name || !company) return;
  STATE.vendors.push({ name, company, email: document.getElementById('vEmail').value.trim(), phone: document.getElementById('vPhone').value.trim() });
  toast('Added vendor contact!', 'success');
  closeModal('vendorModal');
  renderVendors();
}

function closeModal(id) { document.getElementById(id)?.classList.add('hidden'); }

// ── INITIALIZATION ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  setupSearch();
  loadBench();
  runSearch(); // Auto-search on load
});
