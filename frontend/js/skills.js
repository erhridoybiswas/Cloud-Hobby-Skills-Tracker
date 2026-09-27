/* =====================================================================
   skills.js — skill / goal / practice management.
   ===================================================================== */

if (Auth.requireLogin()) {
  renderNav('skills');
  loadSkills();
}

const alertBox = document.getElementById('alertBox');
let skillsCache = [];

/* ---------------- Loading & rendering ---------------- */

async function loadSkills() {
  const container = document.getElementById('skillList');
  try {
    const data = await API.get('/skills');
    skillsCache = data.skills || [];

    if (skillsCache.length === 0) {
      container.innerHTML = `
        <div class="card empty" style="grid-column:1/-1">
          <div class="empty-icon">🎯</div>
          <h3 style="color:var(--text);text-transform:none;font-size:1rem">No skills yet</h3>
          <p class="mt-1">Click <strong>+ Add Skill</strong> to start tracking your first hobby.</p>
        </div>`;
      return;
    }

    container.innerHTML = skillsCache.map(skillCardHtml).join('');
    attachCardHandlers();
  } catch (error) {
    showAlert(alertBox, error.message, 'error');
  }
}

function skillCardHtml(skill) {
  const statusClass =
    skill.status === 'COMPLETED' ? 'badge-success'
    : skill.status === 'PAUSED' ? 'badge-warning'
    : 'badge-primary';

  return `
    <div class="card" data-skill-id="${escapeHtml(skill.skill_id)}">
      <div class="flex-between mb-1">
        <div>
          <h2 style="margin:0">${escapeHtml(skill.skill_name)}</h2>
          <span class="badge">${escapeHtml(skill.category)}</span>
          <span class="badge ${statusClass}">${escapeHtml(skill.status)}</span>
        </div>
        <div style="text-align:right">
          <div class="stat-value" style="font-size:1.3rem">
            ${skill.total_practice_hours}h
          </div>
          <div class="stat-label">practiced</div>
        </div>
      </div>

      <div style="font-size:.85rem;color:var(--text-muted);margin-bottom:10px">
        ${escapeHtml(skill.current_level)} → ${escapeHtml(skill.target_level)}
      </div>

      <div class="flex-between" style="font-size:.8rem;color:var(--text-muted);margin-bottom:6px">
        <span>Goal progress</span>
        <span>${skill.progress_percent}%</span>
      </div>
      <div class="progress-track mb-2">
        <div class="progress-fill ${skill.progress_percent >= 100 ? 'done' : ''}"
             style="width:${Math.min(skill.progress_percent, 100)}%"></div>
      </div>

      <div class="flex" style="flex-wrap:wrap;gap:8px">
        <button class="btn btn-primary btn-sm js-log" data-id="${skill.skill_id}"
                data-name="${escapeHtml(skill.skill_name)}">Log Practice</button>
        <button class="btn btn-secondary btn-sm js-goal" data-id="${skill.skill_id}"
                data-name="${escapeHtml(skill.skill_name)}">Set Goal</button>
        <button class="btn btn-secondary btn-sm js-detail" data-id="${skill.skill_id}">Details</button>
        <button class="btn btn-danger btn-sm js-delete" data-id="${skill.skill_id}">Delete</button>
      </div>
    </div>`;
}

function attachCardHandlers() {
  document.querySelectorAll('.js-log').forEach((button) => {
    button.addEventListener('click', () => openPracticeModal(button.dataset.id, button.dataset.name));
  });
  document.querySelectorAll('.js-goal').forEach((button) => {
    button.addEventListener('click', () => openGoalModal(button.dataset.id, button.dataset.name));
  });
  document.querySelectorAll('.js-detail').forEach((button) => {
    button.addEventListener('click', () => showSkillDetail(button.dataset.id));
  });
  document.querySelectorAll('.js-delete').forEach((button) => {
    button.addEventListener('click', () => deleteSkill(button.dataset.id));
  });
}

/* ---------------- Add skill ---------------- */

document.getElementById('openAddSkill').addEventListener('click', () => {
  document.getElementById('skillModal').classList.remove('hidden');
});
document.getElementById('cancelSkill').addEventListener('click', () => {
  document.getElementById('skillModal').classList.add('hidden');
});

document.getElementById('skillForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    skill_name: document.getElementById('skillName').value.trim(),
    category: document.getElementById('skillCategory').value,
    current_level: document.getElementById('skillCurrentLevel').value,
    target_level: document.getElementById('skillTargetLevel').value,
    description: document.getElementById('skillDescription').value.trim(),
  };

  try {
    await API.post('/skills', payload);
    document.getElementById('skillModal').classList.add('hidden');
    document.getElementById('skillForm').reset();
    showAlert(alertBox, 'Skill created successfully!', 'success');
    loadSkills();
  } catch (error) {
    showAlert(alertBox, error.message, 'error');
  }
});

/* ---------------- Goal modal ---------------- */

function openGoalModal(skillId, skillName) {
  document.getElementById('goalSkillId').value = skillId;
  document.getElementById('goalSkillName').textContent = `For skill: ${skillName}`;
  document.getElementById('goalModal').classList.remove('hidden');
}
document.getElementById('cancelGoal').addEventListener('click', () => {
  document.getElementById('goalModal').classList.add('hidden');
});

document.getElementById('goalForm').addEventListener('submit', async (event) => {
  event.preventDefault();

  const target = parseFloat(document.getElementById('goalTarget').value);
  const milestones = document
    .getElementById('goalMilestones')
    .value.split(',')
    .map((v) => parseFloat(v.trim()))
    .filter((v) => !Number.isNaN(v) && v > 0 && v <= target)
    .map((v) => ({ title: `${v} reached`, target_value: v }));

  const payload = {
    skill_id: document.getElementById('goalSkillId').value,
    title: document.getElementById('goalTitle').value.trim(),
    target_value: target,
    unit: document.getElementById('goalUnit').value,
    deadline: document.getElementById('goalDeadline').value || null,
    milestones,
  };

  try {
    await API.post('/goals', payload);
    document.getElementById('goalModal').classList.add('hidden');
    document.getElementById('goalForm').reset();
    showAlert(alertBox, 'Goal created!', 'success');
    loadSkills();
  } catch (error) {
    showAlert(alertBox, error.message, 'error');
  }
});

/* ---------------- Practice modal ---------------- */

function openPracticeModal(skillId, skillName) {
  document.getElementById('practiceSkillId').value = skillId;
  document.getElementById('practiceSkillName').textContent = `For skill: ${skillName}`;
  document.getElementById('practiceDate').value = new Date().toISOString().slice(0, 10);
  document.getElementById('practiceModal').classList.remove('hidden');
}
document.getElementById('cancelPractice').addEventListener('click', () => {
  document.getElementById('practiceModal').classList.add('hidden');
});

document.getElementById('practiceForm').addEventListener('submit', async (event) => {
  event.preventDefault();

  const payload = {
    skill_id: document.getElementById('practiceSkillId').value,
    duration_minutes: parseInt(document.getElementById('practiceDuration').value, 10),
    practiced_at: document.getElementById('practiceDate').value,
    activity: document.getElementById('practiceActivity').value.trim(),
    notes: document.getElementById('practiceNotes').value.trim(),
  };

  try {
    const result = await API.post('/practice', payload);
    document.getElementById('practiceModal').classList.add('hidden');
    document.getElementById('practiceForm').reset();

    let message = `Logged ${payload.duration_minutes} minutes! 🎉`;
    if (result.new_milestones && result.new_milestones.length > 0) {
      const titles = result.new_milestones.map((m) => m.title).join(', ');
      message += ` Milestone achieved: ${titles}`;
    }
    showAlert(alertBox, message, 'success');
    loadSkills();
  } catch (error) {
    showAlert(alertBox, error.message, 'error');
  }
});

/* ---------------- Details & delete ---------------- */

async function showSkillDetail(skillId) {
  try {
    const data = await API.get(`/skills/${skillId}`);
    const skill = data.skill;
    const goals = data.goals || [];

    const goalsHtml = goals.length
      ? goals.map((g) => `
          <div class="list-item">
            <div style="flex:1">
              <div style="font-weight:600;font-size:.9rem">${escapeHtml(g.title)}</div>
              <div style="color:var(--text-muted);font-size:.8rem">
                ${g.current_value} / ${g.target_value} ${escapeHtml(g.unit)}
                ${g.deadline ? ' · due ' + escapeHtml(g.deadline) : ''}
              </div>
              <div class="progress-track mt-1">
                <div class="progress-fill ${g.progress_percent >= 100 ? 'done' : ''}"
                     style="width:${Math.min(g.progress_percent, 100)}%"></div>
              </div>
            </div>
            <span class="badge ${g.status === 'COMPLETED' ? 'badge-success' : 'badge-primary'}">
              ${g.progress_percent}%
            </span>
          </div>`).join('')
      : '<p style="color:var(--text-muted);font-size:.88rem">No goals set for this skill yet.</p>';

    alert(`${skill.skill_name}\n\nTotal practice: ${skill.total_practice_hours} hours\n\nGoals:\n` +
          goals.map((g) => `• ${g.title}: ${g.current_value}/${g.target_value} ${g.unit} (${g.progress_percent}%)`).join('\n'));

    // Also render inline for a nicer UX
    const card = document.querySelector(`[data-skill-id="${skillId}"]`);
    if (card && !card.querySelector('.detail-panel')) {
      const panel = document.createElement('div');
      panel.className = 'detail-panel mt-2';
      panel.style.borderTop = '1px solid var(--border)';
      panel.style.paddingTop = '12px';
      panel.innerHTML = `<h3>Goals</h3>${goalsHtml}`;
      card.appendChild(panel);
    }
  } catch (error) {
    showAlert(alertBox, error.message, 'error');
  }
}

async function deleteSkill(skillId) {
  if (!window.confirm('Delete this skill? All its goals and practice history will be removed.')) {
    return;
  }
  try {
    await API.del(`/skills/${skillId}`);
    showAlert(alertBox, 'Skill deleted.', 'success');
    loadSkills();
  } catch (error) {
    showAlert(alertBox, error.message, 'error');
  }
}