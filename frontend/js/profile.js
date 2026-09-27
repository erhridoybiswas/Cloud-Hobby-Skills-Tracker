/* =====================================================================
   profile.js — profile display, edit, and avatar upload.
   ===================================================================== */

if (Auth.requireLogin()) {
  renderNav('profile');
  loadProfile();
}

const profileAlertBox = document.getElementById('alertBox');

async function loadProfile() {
  try {
    const { user } = await API.get('/profile');

    document.getElementById('profileName').textContent = user.name;
    document.getElementById('profileUsername').textContent = `@${user.username}`;
    document.getElementById('profileEmail').textContent = user.email;
    document.getElementById('profileAvatar').innerHTML = avatarHtml(user, 'avatar-lg');

    document.getElementById('editName').value = user.name || '';
    document.getElementById('editBio').value = user.bio || '';
    document.getElementById('editInterests').value = user.interests || '';

    // Public stats
    const publicData = await API.get(`/users/${user.username}`, { auth: false });
    const stats = publicData.stats || {};
    document.getElementById('statSkills').textContent = stats.skills || 0;
    document.getElementById('statPosts').textContent = stats.posts || 0;
    document.getElementById('statHours').textContent =
      ((stats.total_practice_minutes || 0) / 60).toFixed(1);
  } catch (error) {
    showAlert(profileAlertBox, error.message, 'error');
  }
}

/* ---------------- Save profile ---------------- */

document.getElementById('profileForm').addEventListener('submit', async (event) => {
  event.preventDefault();

  const payload = {
    name: document.getElementById('editName').value.trim(),
    bio: document.getElementById('editBio').value.trim(),
    interests: document.getElementById('editInterests').value.trim(),
  };

  try {
    const { user } = await API.put('/profile', payload);

    // Keep the cached user in sync so the navbar/profile stay correct
    const cached = Auth.getUser() || {};
    Auth.setSession(Auth.getToken(), { ...cached, ...user });

    showAlert(profileAlertBox, 'Profile updated successfully!', 'success');
    loadProfile();
  } catch (error) {
    showAlert(profileAlertBox, error.message, 'error');
  }
});

/* ---------------- Avatar upload ---------------- */

document.getElementById('uploadAvatar').addEventListener('click', async () => {
  const input = document.getElementById('avatarInput');
  if (!input.files || input.files.length === 0) {
    showAlert(profileAlertBox, 'Please choose an image first.', 'error');
    return;
  }

  const button = document.getElementById('uploadAvatar');
  button.disabled = true;
  button.textContent = 'Uploading…';

  try {
    // 1) Upload the image to object storage
    const formData = new FormData();
    formData.append('file', input.files[0]);
    formData.append('folder', 'profile');
    formData.append('is_public', 'true');

    const uploadResult = await API.upload('/files/upload', formData);

    // 2) Point the profile at the returned storage key
    const { user } = await API.put('/profile', {
      profile_picture: uploadResult.file.storage_key,
    });

    const cached = Auth.getUser() || {};
    Auth.setSession(Auth.getToken(), { ...cached, ...user });

    showAlert(profileAlertBox, 'Profile picture updated!', 'success');
    loadProfile();
  } catch (error) {
    showAlert(profileAlertBox, error.message, 'error');
  } finally {
    button.disabled = false;
    button.textContent = 'Upload';
  }
});