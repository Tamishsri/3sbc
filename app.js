/**
 * app.js — Production Talent Intelligence ATS Frontend Logic
 */

document.addEventListener('DOMContentLoaded', async () => {
  let allCandidates = [];
  let currentScoreFilter = 'ALL';
  let activeViewMode = 'GRID';

  // DOM Elements
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

  // Load Dashboard Data (Tries live API first, falls back to candidates_data.json)
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
      try {
        const staticRes = await fetch('candidates_data.json');
        if (staticRes.ok) {
          allCandidates = await staticRes.json();
        }
      } catch (staticErr) {
        console.error('Static data load error:', staticErr);
      }

      const computedStats = computeLocalStats(allCandidates);
      updateStats(computedStats);
      renderTeamAnalytics(computedStats.team_breakdown || {});
    }

    populateTeamFilter(allCandidates);
    applyFilters();
  }

  // Compute stats for static fallback
  function computeLocalStats(records) {
    if (!records || !records.length) {
      return { total_candidates: 0, top_matches: 0, teams_count: 0, avg_score: 0, team_breakdown: {} };
    }

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

    return {
      total_candidates: records.length,
      top_matches: top_count,
      teams_count: teams.size,
      avg_score: avg,
      team_breakdown
    };
  }

  // Update Stats Header
  function updateStats(stats) {
    statTotal.textContent = stats.total_candidates || 0;
    statTopMatches.textContent = stats.top_matches || 0;
    statTeams.textContent = stats.teams_count || 0;
    statAvgScore.textContent = (stats.avg_score || 0) + '%';
  }

  // Render Team Performance Summary Cards
  function renderTeamAnalytics(breakdown) {
    const teams = Object.keys(breakdown).sort();
    if (!teams.length) {
      teamsGrid.innerHTML = '<div style="color: var(--text-slate-400); font-size: 0.85rem;">No team metrics available.</div>';
      return;
    }

    teamsGrid.innerHTML = teams.map(t => {
      const data = breakdown[t];
      return `
        <div class="team-stat-card">
          <h4>${escapeHtml(t)}</h4>
          <div class="team-metrics-row">
            <span>Sourced: <strong>${data.count}</strong></span>
            <span>Top Matches: <strong>${data.top_matches}</strong></span>
            <span>Avg Fit: <strong style="color: var(--emerald-text);">${data.avg_score}%</strong></span>
          </div>
        </div>
      `;
    }).join('');
  }

  // Populate Teams Dropdown
  function populateTeamFilter(candidates) {
    const teams = Array.from(new Set(candidates.map(c => c['Team Name']).filter(Boolean))).sort();
    teamFilter.innerHTML = '<option value="ALL">All Consultant Teams</option>';
    teams.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t;
      opt.textContent = t;
      teamFilter.appendChild(opt);
    });
  }

  // Render Candidates Cards & Table
  function renderCandidates(list) {
    if (!list.length) {
      cardGrid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-slate-400); padding: 4rem;">No matching candidate records found.</div>';
      tableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-slate-400); padding: 3rem;">No matching candidate records found.</td></tr>';
      return;
    }

    // Render Cards View
    cardGrid.innerHTML = list.map(c => {
      const score = parseInt(c['Match Score']) || 0;
      const scoreClass = score >= 80 ? 'score-high' : 'score-medium';

      const nameTitle = c['Candidate Name/Title'] || 'Candidate';
      const role = c['Target Skill (AREA)'] || 'General Role';
      const team = c['Team Name'] || 'Unassigned';
      const location = c['Target Location'] || 'USA';
      const reasoning = c['AI Reasoning'] || 'No AI reasoning available.';
      const linkedinUrl = c['Candidate LinkedIn URL'] || '#';
      const status = c['Status'] || 'New';
      const candId = `${team}::${nameTitle}`.trim();

      return `
        <article class="candidate-card">
          <div>
            <div class="card-header-row">
              <span class="team-tag-pill">${escapeHtml(team)}</span>
              <div class="score-badge-box ${scoreClass}">${score}% Match</div>
            </div>

            <h3 class="candidate-name">${escapeHtml(nameTitle)}</h3>
            <div class="candidate-role">🎯 Target Role: ${escapeHtml(role)}</div>
            <div class="candidate-location">📍 Location: ${escapeHtml(location)}</div>

            <div class="evaluation-box">
              <div class="evaluation-title">AI Recruiter Evaluation</div>
              ${escapeHtml(reasoning)}
            </div>
          </div>

          <div class="card-footer-row">
            ${linkedinUrl !== '#' ? `<a href="${escapeHtml(linkedinUrl)}" target="_blank" rel="noopener" class="linkedin-link-btn">🔗 LinkedIn Profile</a>` : '<span style="font-size:0.775rem; color:var(--text-slate-400);">Profile Link</span>'}
            
            <select class="status-select-control" data-id="${escapeHtml(candId)}">
              <option value="New" ${status === 'New' ? 'selected' : ''}>New</option>
              <option value="Shortlisted" ${status === 'Shortlisted' ? 'selected' : ''}>⭐️ Shortlisted</option>
              <option value="Interviewing" ${status === 'Interviewing' ? 'selected' : ''}>📅 Interviewing</option>
              <option value="Hired" ${status === 'Hired' ? 'selected' : ''}>✅ Hired</option>
            </select>
          </div>
        </article>
      `;
    }).join('');

    // Render Data Table View
    tableBody.innerHTML = list.map(c => {
      const score = parseInt(c['Match Score']) || 0;
      const scoreClass = score >= 80 ? 'score-high' : 'score-medium';
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
          <td><span class="team-tag-pill">${escapeHtml(team)}</span></td>
          <td>${escapeHtml(role)}</td>
          <td>${escapeHtml(location)}</td>
          <td><span class="score-badge-box ${scoreClass}">${score}%</span></td>
          <td>
            <select class="status-select-control" data-id="${escapeHtml(candId)}">
              <option value="New" ${status === 'New' ? 'selected' : ''}>New</option>
              <option value="Shortlisted" ${status === 'Shortlisted' ? 'selected' : ''}>⭐️ Shortlisted</option>
              <option value="Interviewing" ${status === 'Interviewing' ? 'selected' : ''}>📅 Interviewing</option>
              <option value="Hired" ${status === 'Hired' ? 'selected' : ''}>✅ Hired</option>
            </select>
          </td>
          <td>
            ${linkedinUrl !== '#' ? `<a href="${escapeHtml(linkedinUrl)}" target="_blank" rel="noopener" class="linkedin-link-btn" style="padding: 0.25rem 0.6rem;">LinkedIn</a>` : '-'}
          </td>
        </tr>
      `;
    }).join('');

    // Attach Status Selectors Handlers
    document.querySelectorAll('.status-select-control').forEach(sel => {
      sel.addEventListener('change', async (e) => {
        const candId = e.target.getAttribute('data-id');
        const newStatus = e.target.value;
        try {
          await fetch('/api/update-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ candidate_id: candId, status: newStatus })
          });
        } catch (err) {
          console.log('Status updated in local client state');
        }
        const found = allCandidates.find(c => `${c['Team Name']}::${c['Candidate Name/Title']}`.trim() === candId);
        if (found) found['Status'] = newStatus;
        applyFilters();
      });
    });
  }

  // Filter Logic
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

  // Helper XSS prevention
  function escapeHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Tab Switcher
  scoreTabs.addEventListener('click', (e) => {
    if (e.target.classList.contains('filter-tab-btn')) {
      document.querySelectorAll('.filter-tab-btn').forEach(btn => btn.classList.remove('active'));
      e.target.classList.add('active');
      currentScoreFilter = e.target.getAttribute('data-score') || e.target.getAttribute('data-status');
      applyFilters();
    }
  });

  // View Mode Switcher
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

  // Trigger Pipeline POST
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
      terminalOutput.textContent = 'ℹ️ Pipeline execution triggered. If running on Vercel static, run python main.py locally to update cloud records.';
    } finally {
      runBtn.disabled = false;
      runBtn.innerHTML = '🚀 Run Pipeline';
    }
  });

  // Modal Handlers
  handoffBtn.addEventListener('click', () => handoffModal.classList.add('active'));
  closeHandoffBtn.addEventListener('click', () => handoffModal.classList.remove('active'));
  closeTerminalBtn.addEventListener('click', () => terminalModal.classList.remove('active'));

  [handoffModal, terminalModal].forEach(m => {
    m.addEventListener('click', (e) => {
      if (e.target === m) m.classList.remove('active');
    });
  });

  // Initial Load
  loadDashboard();
});
