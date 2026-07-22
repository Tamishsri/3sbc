/**
 * app.js — Enterprise Talent Platform Frontend Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  let allCandidates = [];
  let currentScoreFilter = 'ALL';

  // DOM Elements
  const grid = document.getElementById('candidateGrid');
  const searchInput = document.getElementById('searchInput');
  const teamFilter = document.getElementById('teamFilter');
  const scoreTabs = document.getElementById('scoreTabs');

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

  // Load Dashboard Data
  async function loadDashboard() {
    try {
      const [candRes, statsRes] = await Promise.all([
        fetch('/api/candidates'),
        fetch('/api/stats')
      ]);

      allCandidates = await candRes.json();
      const stats = await statsRes.json();

      updateStats(stats);
      populateTeamFilter(allCandidates);
      applyFilters();
    } catch (err) {
      console.error('Error loading dashboard data:', err);
      grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 4rem;">Unable to connect to server API. Ensure python server.py is running.</div>';
    }
  }

  // Update Stats Header
  function updateStats(stats) {
    statTotal.textContent = stats.total_candidates || 0;
    statTopMatches.textContent = stats.top_matches || 0;
    statTeams.textContent = stats.teams_count || 0;
    statAvgScore.textContent = (stats.avg_score || 0) + '%';
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

  // Render Candidate Cards Grid
  function renderCandidates(list) {
    if (!list.length) {
      grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 4rem;">No matching candidate records found.</div>';
      return;
    }

    grid.innerHTML = list.map(c => {
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
        <article class="candidate-card">
          <div>
            <div class="card-header">
              <span class="team-pill">${escapeHtml(team)}</span>
              <div class="score-badge ${scoreClass}">${score}% Match</div>
            </div>

            <h3 class="cand-name">${escapeHtml(nameTitle)}</h3>
            <div class="cand-role">🎯 ${escapeHtml(role)}</div>
            <div class="location-tag">📍 ${escapeHtml(location)}</div>

            <div class="verdict-box">
              <strong>AI Recruiter Evaluation</strong>
              ${escapeHtml(reasoning)}
            </div>
          </div>

          <div class="card-footer">
            ${linkedinUrl !== '#' ? `<a href="${escapeHtml(linkedinUrl)}" target="_blank" rel="noopener" class="btn-link">🔗 LinkedIn Profile</a>` : '<span style="font-size:0.8rem; color:var(--text-dim);">Profile Link</span>'}
            
            <select class="status-selector" data-id="${escapeHtml(candId)}">
              <option value="New" ${status === 'New' ? 'selected' : ''}>New</option>
              <option value="Shortlisted" ${status === 'Shortlisted' ? 'selected' : ''}>⭐️ Shortlisted</option>
              <option value="Interviewing" ${status === 'Interviewing' ? 'selected' : ''}>📅 Interviewing</option>
              <option value="Hired" ${status === 'Hired' ? 'selected' : ''}>✅ Hired</option>
            </select>
          </div>
        </article>
      `;
    }).join('');

    // Attach Status Change Handlers
    document.querySelectorAll('.status-selector').forEach(sel => {
      sel.addEventListener('change', async (e) => {
        const candId = e.target.getAttribute('data-id');
        const newStatus = e.target.value;
        try {
          await fetch('/api/update-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ candidate_id: candId, status: newStatus })
          });
          const found = allCandidates.find(c => `${c['Team Name']}::${c['Candidate Name/Title']}`.trim() === candId);
          if (found) found['Status'] = newStatus;
          applyFilters();
        } catch (err) {
          console.error('Failed to update candidate status:', err);
        }
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
    if (e.target.classList.contains('tab-btn')) {
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      e.target.classList.add('active');
      currentScoreFilter = e.target.getAttribute('data-score') || e.target.getAttribute('data-status');
      applyFilters();
    }
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
      terminalOutput.textContent = '❌ Error triggering pipeline: ' + err;
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
