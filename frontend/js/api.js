/* =====================================================================
   api.js — the ONLY place in the frontend that talks to the backend.
   Every request automatically attaches the JWT and normalises errors.
   ===================================================================== */

const API_BASE = '/api';
const TOKEN_KEY = 'hst_token';
const USER_KEY = 'hst_user';

const Auth = {
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },
  setSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  getUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
    } catch (e) {
      return null;
    }
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
  isLoggedIn() {
    return Boolean(this.getToken());
  },
  requireLogin() {
    if (!this.isLoggedIn()) {
      window.location.href = '/index.html';
      return false;
    }
    return true;
  },
};

/** Custom error carrying the HTTP status and field-level details. */
class ApiError extends Error {
  constructor(message, status, details) {
    super(message);
    this.status = status;
    this.details = details || null;
  }
}

/**
 * Core request function.
 * @param {string} path   e.g. '/skills'
 * @param {object} opts   { method, body, isForm, auth }
 */
async function request(path, opts = {}) {
  const { method = 'GET', body = null, isForm = false, auth = true } = opts;

  const headers = {};
  if (auth) {
    const token = Auth.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }
  if (body && !isForm) headers['Content-Type'] = 'application/json';

  const config = { method, headers };

  if (body) {
    config.body = isForm ? body : JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, config);
  } catch (networkError) {
    throw new ApiError('Network error. Please check your connection.', 0);
  }

  // 401 -> token expired or invalid; force re-login
  if (response.status === 401 && auth) {
    Auth.clear();
    if (!window.location.pathname.endsWith('index.html') && window.location.pathname !== '/') {
      window.location.href = '/index.html';
    }
    throw new ApiError('Your session has expired. Please log in again.', 401);
  }

  // 204 or empty body
  const text = await response.text();
  let payload = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (e) {
      payload = { error: 'Unexpected server response.' };
    }
  }

  if (!response.ok) {
    throw new ApiError(payload.error || `Request failed (${response.status})`, response.status, payload.details);
  }

  return payload;
}

/* ---------- Convenience wrappers ---------- */
const API = {
  get: (path, opts = {}) => request(path, { ...opts, method: 'GET' }),
  post: (path, body, opts = {}) => request(path, { ...opts, method: 'POST', body }),
  put: (path, body, opts = {}) => request(path, { ...opts, method: 'PUT', body }),
  del: (path, opts = {}) => request(path, { ...opts, method: 'DELETE' }),

  upload(path, formData) {
    return request(path, { method: 'POST', body: formData, isForm: true });
  },
};

/* ---------- UI helpers shared by every page ---------- */

/** Escape untrusted text before inserting it into innerHTML (XSS defence). */
function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/** Render a user's avatar: their picture if present, otherwise initials. */
function avatarHtml(user, extraClass = '') {
  const cls = `avatar ${extraClass}`.trim();
  if (user && user.profile_picture) {
    const url = user.profile_picture.startsWith('http')
      ? user.profile_picture
      : `/api/files/raw/${user.profile_picture}`;
    return `<img class="${cls}" src="${escapeHtml(url)}" alt="avatar"
                 onerror="this.outerHTML='<div class=\\'${cls}\\'>${escapeHtml((user.name || '?')[0].toUpperCase())}</div>'">`;
  }
  const initial = ((user && (user.name || user.username)) || '?').charAt(0).toUpperCase();
  return `<div class="${cls}">${escapeHtml(initial)}</div>`;
}

/** "3 hours ago" style relative timestamps. */
function timeAgo(isoString) {
  if (!isoString) return '';
  const then = new Date(isoString.endsWith('Z') ? isoString : isoString + 'Z');
  const seconds = Math.floor((Date.now() - then.getTime()) / 1000);

  if (seconds < 60) return 'just now';
  const units = [
    ['year', 31536000], ['month', 2592000], ['day', 86400],
    ['hour', 3600], ['minute', 60],
  ];
  for (const [name, secs] of units) {
    const value = Math.floor(seconds / secs);
    if (value >= 1) return `${value} ${name}${value > 1 ? 's' : ''} ago`;
  }
  return 'just now';
}

/** Show an alert inside a container element. */
function showAlert(container, message, type = 'error') {
  if (!container) return;
  container.innerHTML = `<div class="alert alert-${type}">${escapeHtml(message)}</div>`;
  setTimeout(() => {
    if (container.firstChild) container.innerHTML = '';
  }, 6000);
}

function clearAlert(container) {
  if (container) container.innerHTML = '';
}

/** Read a query-string parameter. */
function getParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

/** Format hours nicely: 2.5 -> "2.5 h" */
function formatHours(value) {
  const n = Number(value || 0);
  return `${n.toFixed(1)} h`;
}