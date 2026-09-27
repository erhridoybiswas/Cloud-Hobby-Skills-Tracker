/* =====================================================================
   auth.js — login / registration page controller.
   ===================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  // Already logged in? Skip straight to the dashboard.
  if (Auth.isLoggedIn()) {
    window.location.href = '/dashboard.html';
    return;
  }

  const alertBox = document.getElementById('alertBox');
  const loginForm = document.getElementById('loginForm');
  const registerForm = document.getElementById('registerForm');
  const tabLogin = document.getElementById('tabLogin');
  const tabRegister = document.getElementById('tabRegister');

  function switchTab(mode) {
    const isLogin = mode === 'login';
    tabLogin.classList.toggle('active', isLogin);
    tabRegister.classList.toggle('active', !isLogin);
    loginForm.classList.toggle('hidden', !isLogin);
    registerForm.classList.toggle('hidden', isLogin);
    clearAlert(alertBox);
  }

  tabLogin.addEventListener('click', () => switchTab('login'));
  tabRegister.addEventListener('click', () => switchTab('register'));

  /* ---------------- LOGIN ---------------- */
  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearAlert(alertBox);

    const identifier = document.getElementById('loginIdentifier').value.trim();
    const password = document.getElementById('loginPassword').value;
    const button = document.getElementById('loginBtn');

    button.disabled = true;
    button.textContent = 'Logging in…';

    try {
      const data = await API.post('/login', { identifier, password }, { auth: false });
      Auth.setSession(data.token, data.user);
      window.location.href = '/dashboard.html';
    } catch (error) {
      showAlert(alertBox, error.message, 'error');
      button.disabled = false;
      button.textContent = 'Log In';
    }
  });

  /* ---------------- REGISTER ---------------- */
  registerForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearAlert(alertBox);

    const payload = {
      name: document.getElementById('regName').value.trim(),
      username: document.getElementById('regUsername').value.trim().toLowerCase(),
      email: document.getElementById('regEmail').value.trim().toLowerCase(),
      password: document.getElementById('regPassword').value,
    };

    const button = document.getElementById('registerBtn');
    button.disabled = true;
    button.textContent = 'Creating account…';

    try {
      const data = await API.post('/register', payload, { auth: false });
      Auth.setSession(data.token, data.user);
      window.location.href = '/dashboard.html';
    } catch (error) {
      // Show field-level validation details when the backend provides them
      if (error.details) {
        const messages = Object.entries(error.details)
          .map(([field, msg]) => `${field}: ${msg}`)
          .join(' | ');
        showAlert(alertBox, messages, 'error');
      } else {
        showAlert(alertBox, error.message, 'error');
      }
      button.disabled = false;
      button.textContent = 'Create Account';
    }
  });
});