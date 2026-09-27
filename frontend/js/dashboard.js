/* =====================================================================
   dashboard.js — personal analytics dashboard.
   ===================================================================== */

if (Auth.requireLogin()) {
  renderNav('dashboard');
  loadDashboard();
}

const CHART_COLORS = [
  '#5b8def', '#34d399', '#fbbf24', '#f87171', '#a78bfa',
  '#22d3ee', '#fb923c', '#4ade80', '#f472b6', '#94a3b8',
];

const chartRegistry = {};

/** Create or update a chart in place (avoids duplicate canvases on reload). */
function drawChart(canvasId, config) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  if (chartRegistry[canvasId]) {
    chartRegistry[canvasId].destroy();
  }
  chartRegistry[canvasId] = new Chart(canvas.getContext('2d'), config);
}

const baseOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { labels: { color: '#93a1bd', font: { size: 11 } } } },
  scales: {
    x: { ticks: { color: '#93a1bd', font: { size: 11 } }, grid: { color: 'rgba(255,255,255,0.05)' } },
    y: { beginAtZero: true, ticks: { color: '#93a1bd', font: { size: 11 } }, grid: { color: 'rgba(255,255,255,0.05)' } },
  },
};

async function loadDashboard() {
  const alertBox = document.getElementById('alertBox');

  try {
    const data = await API.get('/analytics/dashboard');
    const { summary, charts, recent_activity, recent_achievements } = data;

    const user = Auth.getUser();
    document.getElementById('userName').textContent = user ? user.name : 'there';
    document.getElementById('streakLine').textContent =
      `🔥 ${summary.current_streak}-day streak · longest ${summary.longest_streak} days`;

    // ---- KPIs ----
    setText('kpiTotalHours', formatHours(summary.total_practice_hours));
    setText('kpiWeekly', formatHours(summary.weekly_practice_hours));
    setText('kpiStreak', `${summary.current_streak} d`);
    setText('kpiGoals', summary.goals_completed);
    setText('kpiActiveSkills', summary.active_skills);
    setText('kpiMilestones', `${summary.milestones_achieved}/${summary.milestones_total}`);
    setText('kpiPosts', summary.posts_count);
    setText('kpiLikes', summary.likes_received);

    // ---- Chart 1: hours by skill (bar) ----
    const bySkill = charts.practice_by_skill || [];
    drawChart('chartBySkill', {
      type: 'bar',
      data: {
        labels: bySkill.map((r) => r.label),
        datasets: [{
          label: 'Hours',
          data: bySkill.map((r) => r.value),
          backgroundColor: bySkill.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]),
          borderRadius: 6,
        }],
      },
      options: baseOptions,
    });

    // ---- Chart 2: weekly trend (line) ----
    const weekly = charts.weekly_trend || [];
    drawChart('chartWeekly', {
      type: 'line',
      data: {
        labels: weekly.map((r) => r.label.replace(/^\d+-/, '')),
        datasets: [{
          label: 'Hours',
          data: weekly.map((r) => r.value),
          borderColor: '#5b8def',
          backgroundColor: 'rgba(91,141,239,.16)',
          fill: true,
          tension: 0.35,
          pointRadius: 4,
        }],
      },
      options: baseOptions,
    });

    // ---- Chart 3: monthly trend (bar) ----
    const monthly = charts.monthly_trend || [];
    drawChart('chartMonthly', {
      type: 'bar',
      data: {
        labels: monthly.map((r) => r.label),
        datasets: [{
          label: 'Hours',
          data: monthly.map((r) => r.value),
          backgroundColor: '#34d399',
          borderRadius: 6,
        }],
      },
      options: baseOptions,
    });

    // ---- Chart 4: goal completion (doughnut) ----
    const gc = charts.goal_completion || { labels: [], values: [] };
    drawChart('chartGoals', {
      type: 'doughnut',
      data: {
        labels: gc.labels,
        datasets: [{
          data: gc.values,
          backgroundColor: ['#34d399', '#5b8def', '#fbbf24'],
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { color: '#93a1bd', font: { size: 11 } } } },
      },
    });

    // ---- Chart 5: skill distribution (pie) ----
    const dist = charts.skill_distribution || [];
    drawChart('chartDistribution', {
      type: 'pie',
      data: {
        labels: dist.map((r) => r.label),
        datasets: [{
          data: dist.map((r) => r.value),
          backgroundColor: dist.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]),
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { color: '#93a1bd', font: { size: 11 } } } },
      },
    });

    renderAchievements(recent_achievements);
    renderActivity(recent_activity);
  } catch (error) {
    showAlert(alertBox, error.message, 'error');
  }
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function renderAchievements(items) {
  const container = document.getElementById('achievementsList');
  if (!items || items.length === 0) return;

  container.innerHTML = items
    .map(
      (a) => `
      <div class="list-item">
        <div>
          <div style="font-weight:600;font-size:.92rem">🏅 ${escapeHtml(a.title)}</div>
          <div style="color:var(--text-muted);font-size:.8rem">${escapeHtml(a.goal_title)}</div>
        </div>
        <span class="badge badge-success">${timeAgo(a.achieved_at)}</span>
      </div>`
    )
    .join('');
}

function renderActivity(items) {
  const container = document.getElementById('activityList');
  if (!items || items.length === 0) return;

  container.innerHTML = items
    .map(
      (s) => `
      <div class="list-item">
        <div>
          <div style="font-weight:600;font-size:.92rem">
            ${escapeHtml(s.skill_name)}
            <span class="badge badge-primary">${s.duration_minutes} min</span>
          </div>
          <div style="color:var(--text-muted);font-size:.82rem">
            ${escapeHtml(s.activity || 'Practice session')}
          </div>
        </div>
        <span style="color:var(--text-muted);font-size:.8rem">${escapeHtml(s.practiced_at)}</span>
      </div>`
    )
    .join('');
}