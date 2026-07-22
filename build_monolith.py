import json

def build():
    with open('candidates_data.json', 'r', encoding='utf-8') as f:
        cand_json = f.read()

    template = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Talent ATS & Candidate Match Platform</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
      --bg-main: #090d16;
      --bg-card: #111827;
      --bg-card-hover: #1f2937;
      --bg-surface: #1a2234;
      --bg-input: #0f172a;
      
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-focus: rgba(59, 130, 246, 0.5);

      --brand-blue: #3b82f6;
      --brand-blue-hover: #2563eb;

      --emerald-bg: rgba(16, 185, 129, 0.12);
      --emerald-text: #34d399;
      --emerald-border: rgba(16, 185, 129, 0.3);

      --amber-bg: rgba(245, 158, 11, 0.12);
      --amber-text: #fbbf24;
      --amber-border: rgba(245, 158, 11, 0.3);

      --purple-bg: rgba(168, 85, 247, 0.12);
      --purple-text: #c084fc;
      --cyan-bg: rgba(6, 182, 212, 0.12);
      --cyan-text: #38bdf8;

      --text-main: #f9fafb;
      --text-secondary: #9ca3af;
      --text-muted: #6b7280;

      --font-heading: 'Plus Jakarta Sans', sans-serif;
      --font-body: 'Inter', sans-serif;
      --font-mono: 'JetBrains Mono', monospace;

      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 16px;
      --radius-full: 9999px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background-color: var(--bg-main); color: var(--text-main); font-family: var(--font-body); min-height: 100vh; line-height: 1.5; }
    .app-wrapper { max-width: 1440px; margin: 0 auto; padding: 1.5rem 2rem 4rem 2rem; }

    .top-navbar { display: flex; align-items: center; justify-content: space-between; padding: 1rem 1.75rem; background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); margin-bottom: 2rem; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
    .brand-group { display: flex; align-items: center; gap: 1rem; }
    .brand-icon { width: 42px; height: 42px; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; font-size: 1.25rem; color: #fff; font-weight: 800; }
    .brand-text h1 { font-family: var(--font-heading); font-size: 1.25rem; font-weight: 700; }
    .brand-text p { font-size: 0.8rem; color: var(--text-secondary); }
    .header-right { display: flex; align-items: center; gap: 1rem; }

    .status-badge-live { display: flex; align-items: center; gap: 0.5rem; padding: 0.35rem 0.9rem; background: var(--emerald-bg); border: 1px solid var(--emerald-border); border-radius: var(--radius-full); font-size: 0.8rem; color: var(--emerald-text); font-weight: 600; }
    .dot-pulse { width: 7px; height: 7px; background-color: var(--emerald-text); border-radius: 50%; box-shadow: 0 0 8px var(--emerald-text); }

    .btn-primary { padding: 0.6rem 1.25rem; background: var(--brand-blue); color: #fff; border-radius: var(--radius-md); border: none; font-family: var(--font-body); font-size: 0.875rem; font-weight: 600; cursor: pointer; transition: background 0.2s ease; text-decoration: none; }
    .btn-primary:hover { background: var(--brand-blue-hover); }
    .btn-secondary { padding: 0.6rem 1.25rem; background: rgba(255,255,255,0.05); border: 1px solid var(--border-subtle); color: var(--text-main); border-radius: var(--radius-md); font-family: var(--font-body); font-size: 0.875rem; font-weight: 500; cursor: pointer; transition: all 0.2s ease; text-decoration: none; }
    .btn-secondary:hover { background: rgba(255,255,255,0.1); }

    .metrics-banner { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }
    .metric-card { background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 1.35rem 1.5rem; }
    .metric-title { font-size: 0.8rem; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.4rem; }
    .metric-value { font-family: var(--font-heading); font-size: 2.1rem; font-weight: 800; color: var(--text-main); line-height: 1; }

    .teams-section { margin-bottom: 2rem; }
    .section-title { font-family: var(--font-heading); font-size: 1rem; font-weight: 700; margin-bottom: 1rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; }
    .teams-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }
    .team-summary-card { background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem 1.25rem; }
    .team-summary-card h4 { font-size: 0.95rem; font-weight: 700; color: var(--text-main); margin-bottom: 0.4rem; }
    .team-stats-row { display: flex; justify-content: space-between; font-size: 0.825rem; color: var(--text-secondary); }

    .toolbar-card { background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 1.25rem 1.5rem; margin-bottom: 2rem; display: flex; flex-direction: column; gap: 1.1rem; }
    .search-input-wrapper { position: relative; }
    .search-input-wrapper input { width: 100%; padding: 0.8rem 1.25rem 0.8rem 3rem; background: var(--bg-input); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); color: var(--text-main); font-family: var(--font-body); font-size: 0.9rem; outline: none; }
    .search-input-wrapper input:focus { border-color: var(--brand-blue); }
    .search-icon-svg { position: absolute; left: 1.1rem; top: 50%; transform: translateY(-50%); color: var(--text-muted); }

    .filters-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
    .tabs-group { display: flex; gap: 0.5rem; }
    .tab-btn { padding: 0.45rem 1rem; background: rgba(255,255,255,0.04); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); color: var(--text-secondary); font-size: 0.825rem; font-weight: 500; cursor: pointer; }
    .tab-btn.active { background: var(--brand-blue); border-color: var(--brand-blue); color: #ffffff; font-weight: 600; }
    .view-switcher { display: flex; gap: 0.35rem; background: var(--bg-input); padding: 0.25rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); }
    .view-btn { padding: 0.35rem 0.75rem; background: none; border: none; color: var(--text-muted); font-size: 0.8rem; font-weight: 600; border-radius: var(--radius-sm); cursor: pointer; }
    .view-btn.active { background: var(--bg-card); color: var(--text-main); }

    .candidate-grid-view { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 1.5rem; }
    .candidate-card-box { background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 1.5rem; display: flex; flex-direction: column; justify-content: space-between; }
    .candidate-card-box:hover { border-color: var(--border-focus); }
    .card-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; }
    .team-pill-badge { font-size: 0.75rem; font-weight: 600; padding: 0.25rem 0.75rem; background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); color: var(--cyan-text); border-radius: var(--radius-full); }
    .score-badge { font-family: var(--font-heading); font-weight: 800; font-size: 1.05rem; padding: 0.25rem 0.75rem; border-radius: var(--radius-sm); }
    .score-high { background: var(--emerald-bg); color: var(--emerald-text); border: 1px solid var(--emerald-border); }
    .score-med { background: var(--amber-bg); color: var(--amber-text); border: 1px solid var(--amber-border); }
    .cand-name-title { font-family: var(--font-heading); font-size: 1.15rem; font-weight: 700; margin-bottom: 0.25rem; }
    .cand-role-sub { font-size: 0.85rem; color: var(--cyan-text); margin-bottom: 0.75rem; font-weight: 500; }

    .verdict-container { background: var(--bg-input); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 0.85rem; font-size: 0.825rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 1.25rem; }
    .verdict-header { font-size: 0.68rem; font-weight: 800; letter-spacing: 0.05em; color: var(--brand-blue); margin-bottom: 0.35rem; }

    .card-bottom { display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--border-subtle); padding-top: 1rem; }
    .linkedin-btn-link { font-size: 0.825rem; font-weight: 600; color: var(--cyan-text); text-decoration: none; padding: 0.4rem 0.85rem; background: rgba(6, 182, 212, 0.1); border: 1px solid rgba(6, 182, 212, 0.3); border-radius: var(--radius-sm); transition: all 0.2s ease; }
    .linkedin-btn-link:hover { background: var(--cyan-text); color: #000; }
    .status-dropdown { background: var(--bg-input); border: 1px solid var(--border-subtle); color: var(--text-secondary); font-size: 0.78rem; padding: 0.35rem 0.6rem; border-radius: var(--radius-sm); outline: none; cursor: pointer; }

    .table-container { background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); overflow-x: auto; display: none; }
    .ats-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.875rem; }
    .ats-table th { background: var(--bg-surface); padding: 0.9rem 1.25rem; font-family: var(--font-heading); font-size: 0.8rem; font-weight: 700; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border-subtle); }
    .ats-table td { padding: 1rem 1.25rem; border-bottom: 1px solid var(--border-subtle); }
    .ats-table tr:hover td { background: var(--bg-card-hover); }

    .modal-overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.85); display: flex; align-items: center; justify-content: center; z-index: 1000; opacity: 0; pointer-events: none; transition: opacity 0.25s ease; }
    .modal-overlay.active { opacity: 1; pointer-events: auto; }
    .modal-window { background: var(--bg-card); border: 1px solid var(--border-strong); border-radius: var(--radius-lg); padding: 2rem; width: 90%; max-width: 700px; max-height: 85vh; overflow-y: auto; }
    .modal-header-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.25rem; }
    .modal-header-row h3 { font-family: var(--font-heading); font-size: 1.25rem; }
    .btn-close { background: none; border: none; color: var(--text-muted); font-size: 1.5rem; cursor: pointer; }
    .terminal-logs { background: #020617; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem; font-family: var(--font-mono); font-size: 0.825rem; color: #38bdf8; height: 320px; overflow-y: auto; white-space: pre-wrap; }
  </style>
</head>
<body>

  <div class="app-wrapper">
    <header class="top-navbar">
      <div class="brand-group">
        <div class="brand-icon">SBC</div>
        <div class="brand-text">
          <h1>Enterprise Talent Intelligence ATS</h1>
          <p>Automated Sourcing & AI Recruiter Evaluation System</p>
        </div>
      </div>

      <div class="header-right">
        <div class="status-badge-live">
          <span class="dot-pulse"></span>
          <span>Firestore Live Sync</span>
        </div>

        <button id="runPipelineBtn" class="btn-primary">
          <span>🚀 Run Pipeline</span>
        </button>
        <a href="/api/download" class="btn-secondary">
          <span>📊 Export Report (.xlsx)</span>
        </a>
        <button id="handoffBtn" class="btn-secondary">
          <span>📦 Package & Deliver</span>
        </button>
      </div>
    </header>

    <section class="metrics-banner">
      <div class="metric-card">
        <div class="metric-title">Total Candidates Sourced</div>
        <div id="statTotal" class="metric-value">--</div>
      </div>

      <div class="metric-card">
        <div class="metric-title">High Fit Matches (&ge; 80%)</div>
        <div id="statTopMatches" class="metric-value" style="color: #34d399;">--</div>
      </div>

      <div class="metric-card">
        <div class="metric-title">Active Consultant Teams</div>
        <div id="statTeams" class="metric-value" style="color: #60a5fa;">--</div>
      </div>

      <div class="metric-card">
        <div class="metric-title">Average Match Score</div>
        <div id="statAvgScore" class="metric-value" style="color: #fbbf24;">--</div>
      </div>
    </section>

    <section class="teams-section">
      <div class="section-title">Consultant Team Analytics & Sourcing Yield</div>
      <div id="teamsGrid" class="teams-grid"></div>
    </section>

    <section class="toolbar-card">
      <div class="search-input-wrapper">
        <span class="search-icon-svg">🔍</span>
        <input type="text" id="searchInput" placeholder="Search candidate, role, technology (e.g. SAP MM, Azure, DevOps), location, or team...">
      </div>

      <div class="filters-row">
        <div class="tabs-group" id="scoreTabs">
          <button class="tab-btn active" data-score="ALL">All Candidates</button>
          <button class="tab-btn" data-score="HIGH">Top Matches (&ge; 80%)</button>
          <button class="tab-btn" data-score="MED">Good Fits (50-79%)</button>
          <button class="tab-btn" data-status="Shortlisted">⭐️ Shortlisted</button>
        </div>

        <div style="display: flex; gap: 0.75rem; align-items: center;">
          <select id="teamFilter" class="select-box" style="padding: 0.4rem 0.9rem; background: var(--bg-input); border: 1px solid var(--border-subtle); color: var(--text-main); border-radius: var(--radius-sm); outline: none;">
            <option value="ALL">All Teams</option>
          </select>

          <div class="view-switcher">
            <button id="viewGridBtn" class="view-btn active">🪟 Cards View</button>
            <button id="viewTableBtn" class="view-btn">📋 Data Table</button>
          </div>
        </div>
      </div>
    </section>

    <section id="candidateGrid" class="candidate-grid-view"></section>

    <section id="candidateTableContainer" class="table-container">
      <table class="ats-table">
        <thead>
          <tr>
            <th>Candidate Name / Headline</th>
            <th>Consultant Team</th>
            <th>Target Skill (Role)</th>
            <th>Location</th>
            <th>Match Score</th>
            <th>Recruiter Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody id="candidateTableBody"></tbody>
      </table>
    </section>
  </div>

  <div id="terminalModal" class="modal-overlay">
    <div class="modal-window">
      <div class="modal-header-row">
        <h3>🚀 Pipeline Orchestrator Terminal Output</h3>
        <button id="closeTerminalBtn" class="btn-close">&times;</button>
      </div>
      <div id="terminalOutput" class="terminal-logs">Initializing pipeline run execution...</div>
    </div>
  </div>

  <div id="handoffModal" class="modal-overlay">
    <div class="modal-window">
      <div class="modal-header-row">
        <h3>📦 Client & Evaluator Delivery Guide</h3>
        <button id="closeHandoffBtn" class="btn-close">&times;</button>
      </div>
      <div style="font-size: 0.875rem; color: var(--text-secondary); line-height: 1.6;">
        <p style="margin-bottom: 1rem;">To hand over this platform to clients or evaluators:</p>
        <ol style="margin-left: 1.25rem; margin-bottom: 1rem;">
          <li><strong>ZIP the project folder</strong> containing <code>main.py</code>, <code>server.py</code>, <code>excel_parser.py</code>, <code>linkedin_sourcer.py</code>, <code>ai_evaluator.py</code>, <code>firebase_db.py</code>, <code>report_generator.py</code>, <code>requirements.txt</code>, and <code>firebase-key.json</code>.</li>
          <li>Receiver installs dependencies: <code>pip install -r requirements.txt</code></li>
          <li>Receiver launches the Enterprise ATS Web Server: <code>python server.py</code> (opens on <code>http://localhost:5000</code>).</li>
        </ol>
      </div>
    </div>
  </div>

  <script>
    const EMBEDDED_CANDIDATES = __CAND_DATA__;

    document.addEventListener('DOMContentLoaded', () => {
      let allCandidates = [];
      let currentScoreFilter = 'ALL';
      let activeViewMode = 'GRID';

      const cardGrid = document.getElementById('candidateGrid');
      const tableContainer = document.getElementById('candidateTableContainer');
      const tableBody = document.getElementById('candidateTableBody');

      const searchInput = document.getElementById('searchInput');
      const teamFilter = document.getElementById('teamFilter');
      const scoreTabs = document.getElementById('scoreTabs');
      const teamsGrid = document.getElementById('teamsGrid');

      const viewGridBtn = document.getElementById('viewGridBtn');
      const viewTableBtn = document.getElementById('viewTableBtn');

      const statTotal = document.getElementById('statTotal');
      const statTopMatches = document.getElementById('statTopMatches');
      const statTeams = document.getElementById('statTeams');
      const statAvgScore = document.getElementById('statAvgScore');

      const runBtn = document.getElementById('runPipelineBtn');
      const handoffBtn = document.getElementById('handoffBtn');
      const handoffModal = document.getElementById('handoffModal');
      const closeHandoffBtn = document.getElementById('closeHandoffBtn');

      const terminalModal = document.getElementById('terminalModal');
      const closeTerminalBtn = document.getElementById('closeTerminalBtn');
      const terminalOutput = document.getElementById('terminalOutput');

      async function loadDashboard() {
        try {
          const candRes = await fetch('/api/candidates');
          if (!candRes.ok) throw new Error('Static host fallback');
          allCandidates = await candRes.json();
          const statsRes = await fetch('/api/stats');
          const stats = await statsRes.json();
          updateStats(stats);
          renderTeamAnalytics(stats.team_breakdown || {});
        } catch (err) {
          allCandidates = EMBEDDED_CANDIDATES;
          const computedStats = computeLocalStats(allCandidates);
          updateStats(computedStats);
          renderTeamAnalytics(computedStats.team_breakdown || {});
        }

        populateTeamFilter(allCandidates);
        applyFilters();
      }

      function computeLocalStats(records) {
        if (!records || !records.length) return { total_candidates: 0, top_matches: 0, teams_count: 0, avg_score: 0, team_breakdown: {} };
        const scores = [];
        const teams = new Set();
        const team_breakdown = {};

        records.forEach(r => {
          const team_name = (r['Team Name'] || 'Unassigned').trim();
          const score = parseInt(r['Match Score']) || 0;
          scores.push(score);
          teams.add(team_name);

          if (!team_breakdown[team_name]) {
            team_breakdown[team_name] = { count: 0, top_matches: 0, total_score: 0 };
          }
          team_breakdown[team_name].count++;
          team_breakdown[team_name].total_score += score;
          if (score >= 80) team_breakdown[team_name].top_matches++;
        });

        Object.keys(team_breakdown).forEach(t => {
          const tb = team_breakdown[t];
          tb.avg_score = Math.round((tb.total_score / tb.count) * 10) / 10;
        });

        const top_count = scores.filter(s => s >= 80).length;
        const avg = scores.length ? Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 10) / 10 : 0;

        return { total_candidates: records.length, top_matches: top_count, teams_count: teams.size, avg_score: avg, team_breakdown };
      }

      function updateStats(stats) {
        statTotal.textContent = stats.total_candidates || 0;
        statTopMatches.textContent = stats.top_matches || 0;
        statTeams.textContent = stats.teams_count || 0;
        statAvgScore.textContent = (stats.avg_score || 0) + '%';
      }

      function renderTeamAnalytics(breakdown) {
        const teams = Object.keys(breakdown).sort();
        if (!teams.length) {
          teamsGrid.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No team metrics available.</div>';
          return;
        }

        teamsGrid.innerHTML = teams.map(t => {
          const data = breakdown[t];
          return `
            <div class="team-summary-card">
              <h4>${escapeHtml(t)}</h4>
              <div class="team-stats-row">
                <span>Candidates: <strong>${data.count}</strong></span>
                <span>Top Matches: <strong>${data.top_matches}</strong></span>
                <span>Avg Fit: <strong style="color: var(--emerald-text);">${data.avg_score}%</strong></span>
              </div>
            </div>
          `;
        }).join('');
      }

      function populateTeamFilter(candidates) {
        const teams = Array.from(new Set(candidates.map(c => c['Team Name']).filter(Boolean))).sort();
        teamFilter.innerHTML = '<option value="ALL">All Teams</option>';
        teams.forEach(t => {
          const opt = document.createElement('option');
          opt.value = t;
          opt.textContent = t;
          teamFilter.appendChild(opt);
        });
      }

      function renderCandidates(list) {
        if (!list.length) {
          cardGrid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 4rem;">No matching candidate records found.</div>';
          tableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 3rem;">No matching candidate records found.</td></tr>';
          return;
        }

        cardGrid.innerHTML = list.map(c => {
          const score = parseInt(c['Match Score']) || 0;
          const scoreClass = score >= 80 ? 'score-high' : 'score-med';
          const nameTitle = c['Candidate Name/Title'] || 'Candidate';
          const role = c['Target Skill (AREA)'] || 'General Role';
          const team = c['Team Name'] || 'Unassigned';
          const location = c['Target Location'] || 'USA';
          const reasoning = c['AI Reasoning'] || 'No AI reasoning available.';
          const linkedinUrl = c['Candidate LinkedIn URL'] || '#';
          const status = c['Status'] || 'New';
          const candId = `${team}::${nameTitle}`.trim();

          return `
            <article class="candidate-card-box">
              <div>
                <div class="card-top">
                  <span class="team-pill-badge">${escapeHtml(team)}</span>
                  <div class="score-badge ${scoreClass}">${score}% Match</div>
                </div>

                <h3 class="cand-name-title">${escapeHtml(nameTitle)}</h3>
                <div class="cand-role-sub">🎯 Target Role: ${escapeHtml(role)}</div>
                <div style="font-size:0.8rem; color:var(--text-muted); margin-bottom: 0.85rem;">📍 Location: ${escapeHtml(location)}</div>

                <div class="verdict-container">
                  <div class="verdict-header">AI Recruiter Evaluation</div>
                  ${escapeHtml(reasoning)}
                </div>
              </div>

              <div class="card-bottom">
                ${linkedinUrl !== '#' ? `<a href="${escapeHtml(linkedinUrl)}" target="_blank" rel="noopener" class="linkedin-btn-link">🔗 LinkedIn Profile</a>` : '<span style="font-size:0.8rem; color:var(--text-muted);">Profile Link</span>'}
                <select class="status-dropdown" data-id="${escapeHtml(candId)}">
                  <option value="New" ${status === 'New' ? 'selected' : ''}>New</option>
                  <option value="Shortlisted" ${status === 'Shortlisted' ? 'selected' : ''}>⭐️ Shortlisted</option>
                  <option value="Interviewing" ${status === 'Interviewing' ? 'selected' : ''}>📅 Interviewing</option>
                  <option value="Hired" ${status === 'Hired' ? 'selected' : ''}>✅ Hired</option>
                </select>
              </div>
            </article>
          `;
        }).join('');

        tableBody.innerHTML = list.map(c => {
          const score = parseInt(c['Match Score']) || 0;
          const scoreClass = score >= 80 ? 'score-high' : 'score-med';
          const nameTitle = c['Candidate Name/Title'] || 'Candidate';
          const role = c['Target Skill (AREA)'] || 'General Role';
          const team = c['Team Name'] || 'Unassigned';
          const location = c['Target Location'] || 'USA';
          const linkedinUrl = c['Candidate LinkedIn URL'] || '#';
          const status = c['Status'] || 'New';
          const candId = `${team}::${nameTitle}`.trim();

          return `
            <tr>
              <td><strong>${escapeHtml(nameTitle)}</strong></td>
              <td><span class="team-pill-badge">${escapeHtml(team)}</span></td>
              <td>${escapeHtml(role)}</td>
              <td>${escapeHtml(location)}</td>
              <td><span class="score-badge ${scoreClass}">${score}%</span></td>
              <td>
                <select class="status-dropdown" data-id="${escapeHtml(candId)}">
                  <option value="New" ${status === 'New' ? 'selected' : ''}>New</option>
                  <option value="Shortlisted" ${status === 'Shortlisted' ? 'selected' : ''}>⭐️ Shortlisted</option>
                  <option value="Interviewing" ${status === 'Interviewing' ? 'selected' : ''}>📅 Interviewing</option>
                  <option value="Hired" ${status === 'Hired' ? 'selected' : ''}>✅ Hired</option>
                </select>
              </td>
              <td>
                ${linkedinUrl !== '#' ? `<a href="${escapeHtml(linkedinUrl)}" target="_blank" rel="noopener" class="linkedin-btn-link" style="padding: 0.25rem 0.6rem;">LinkedIn</a>` : '-'}
              </td>
            </tr>
          `;
        }).join('');

        document.querySelectorAll('.status-dropdown').forEach(sel => {
          sel.addEventListener('change', async (e) => {
            const candId = e.target.getAttribute('data-id');
            const newStatus = e.target.value;
            try {
              await fetch('/api/update-status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ candidate_id: candId, status: newStatus })
              });
            } catch (err) {}
            const found = allCandidates.find(c => `${c['Team Name']}::${c['Candidate Name/Title']}`.trim() === candId);
            if (found) found['Status'] = newStatus;
            applyFilters();
          });
        });
      }

      function applyFilters() {
        const q = searchInput.value.toLowerCase().trim();
        const selectedTeam = teamFilter.value;

        const filtered = allCandidates.filter(c => {
          const name = (c['Candidate Name/Title'] || '').toLowerCase();
          const role = (c['Target Skill (AREA)'] || '').toLowerCase();
          const team = (c['Team Name'] || '').toLowerCase();
          const loc = (c['Target Location'] || '').toLowerCase();
          const score = parseInt(c['Match Score']) || 0;
          const status = c['Status'] || 'New';

          const matchesSearch = !q || name.includes(q) || role.includes(q) || team.includes(q) || loc.includes(q);
          const matchesTeam = selectedTeam === 'ALL' || c['Team Name'] === selectedTeam;
          
          let matchesScore = true;
          if (currentScoreFilter === 'HIGH') matchesScore = (score >= 80);
          else if (currentScoreFilter === 'MED') matchesScore = (score >= 50 && score < 80);
          else if (currentScoreFilter === 'Shortlisted') matchesScore = (status === 'Shortlisted');

          return matchesSearch && matchesTeam && matchesScore;
        });

        renderCandidates(filtered);
      }

      function escapeHtml(str) {
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
      }

      scoreTabs.addEventListener('click', (e) => {
        if (e.target.classList.contains('tab-btn')) {
          document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
          e.target.classList.add('active');
          currentScoreFilter = e.target.getAttribute('data-score') || e.target.getAttribute('data-status');
          applyFilters();
        }
      });

      viewGridBtn.addEventListener('click', () => {
        activeViewMode = 'GRID';
        viewGridBtn.classList.add('active');
        viewTableBtn.classList.remove('active');
        cardGrid.style.display = 'grid';
        tableContainer.style.display = 'none';
      });

      viewTableBtn.addEventListener('click', () => {
        activeViewMode = 'TABLE';
        viewTableBtn.classList.add('active');
        viewGridBtn.classList.remove('active');
        cardGrid.style.display = 'none';
        tableContainer.style.display = 'block';
      });

      searchInput.addEventListener('input', applyFilters);
      teamFilter.addEventListener('change', applyFilters);

      runBtn.addEventListener('click', async () => {
        runBtn.disabled = true;
        runBtn.innerHTML = '⏳ Running Pipeline ...';
        terminalModal.classList.add('active');
        terminalOutput.textContent = '🚀 Executing main.py pipeline orchestrator...\n\n[Step 1] Verifying environment & credentials...\n[Step 2] Reading Excel consultant roster...\n[Step 3] Sourcing candidate profiles...\n[Step 4] Scoring candidates with Gemini AI...\n[Step 5] Syncing live records to Cloud Firestore...\n[Step 6] Generating Excel report...\n\nPlease wait...';

        try {
          const res = await fetch('/api/run-pipeline', { method: 'POST' });
          const data = await res.json();
          if (data.success) {
            terminalOutput.textContent = data.output || '✅ Pipeline Execution Complete!\nAll records synced to Firestore and Excel generated.';
            loadDashboard();
          } else {
            terminalOutput.textContent = '⚠️ Pipeline Output:\n\n' + (data.output || data.error);
          }
        } catch (err) {
          terminalOutput.textContent = 'ℹ️ Pipeline triggered on local server. Check local console or rerun python main.py.';
        } finally {
          runBtn.disabled = false;
          runBtn.innerHTML = '🚀 Run Pipeline';
        }
      });

      handoffBtn.addEventListener('click', () => handoffModal.classList.add('active'));
      closeHandoffBtn.addEventListener('click', () => handoffModal.classList.remove('active'));
      closeTerminalBtn.addEventListener('click', () => terminalModal.classList.remove('active'));

      [handoffModal, terminalModal].forEach(m => {
        m.addEventListener('click', (e) => {
          if (e.target === m) m.classList.remove('active');
        });
      });

      loadDashboard();
    });
  </script>
</body>
</html>'''

    final_html = template.replace('__CAND_DATA__', cand_json)
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(final_html)
    print('[OK] Monolithic index.html built successfully!')

if __name__ == '__main__':
    build()
