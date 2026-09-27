/* =====================================================================
   nav.js — renders the top navigation and wires up logout.
   ===================================================================== */

function renderNav(activePage) {
  const user = Auth.getUser();
  const links = [
    { href: '/dashboard.html', label: 'Dashboard', key: 'dashboard' },
    { href: '/skills.html', label: 'My Skills', key: 'skills' },
    { href: '/community.html', label: 'Community', key: 'community' },
    { href: '/profile.html', label: 'Profile', key: 'profile' },
  ];

  const linksHtml = links
    .map(
      (l) =>
        `<a href="${l.href}" class="${activePage === l.key ? 'active' : ''}">${l.label}</a>`
    )
    .join('');

  const nav = document.createElement('nav');
  nav.className = 'navbar';
  nav.innerHTML = `
    <div class="inner">
      <div class="flex" style="gap:14px">
        <a href="/dashboard.html" class="brand" style="text-decoration:none">
          🎯 Hobby<span>Tracker</span>
        </a>
        <div class="nav-links">${linksHtml}</div>
      </div>
      <div class="flex" style="gap:10px">
        <span style="font-size:.85rem;color:var(--text-muted)" class="hide-sm">
          ${escapeHtml(user ? user.username : '')}
        </span>
        <button class="btn btn-secondary btn-sm" id="logoutBtn">Logout</button>
      </div>
    </div>
  `;

  document.body.prepend(nav);

  document.getElementById('logoutBtn').addEventListener('click', async () => {
    try {
      await API.post('/logout', {});
    } catch (e) {
      /* Logout is best-effort; the client discards the token regardless. */
    }
    Auth.clear();
    window.location.href = '/index.html';
  });
}