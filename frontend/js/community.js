/* =====================================================================
   community.js — feed, composer, likes, comments.
   ===================================================================== */

if (Auth.requireLogin()) {
  renderNav('community');
  initCommunity();
}

const feedAlertBox = document.getElementById('alertBox');
const feedEl = document.getElementById('feed');

let currentPage = 1;
let currentScope = 'all';
let currentFilters = { q: '', category: '', sort: 'recent' };

function initCommunity() {
  populateSkillDropdown();
  loadFeed(true);

  document.getElementById('postForm').addEventListener('submit', handleCreatePost);

  document.getElementById('filterSearch').addEventListener('input', debounce(() => {
    currentFilters.q = document.getElementById('filterSearch').value.trim();
    loadFeed(true);
  }, 450));

  document.getElementById('filterCategory').addEventListener('change', (e) => {
    currentFilters.category = e.target.value;
    loadFeed(true);
  });

  document.getElementById('filterSort').addEventListener('change', (e) => {
    currentFilters.sort = e.target.value;
    loadFeed(true);
  });

  document.getElementById('filterAll').addEventListener('click', () => {
    currentScope = 'all';
    loadFeed(true);
  });

  document.getElementById('filterFollowing').addEventListener('click', () => {
    currentScope = 'following';
    loadFeed(true);
  });

  document.getElementById('loadMore').addEventListener('click', () => {
    currentPage += 1;
    loadFeed(false);
  });
}

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

/* ---------------- Skill dropdown ---------------- */

async function populateSkillDropdown() {
  try {
    const data = await API.get('/skills');
    const select = document.getElementById('postSkill');
    select.innerHTML =
      '<option value="">— none —</option>' +
      (data.skills || [])
        .map((s) => `<option value="${s.skill_id}">${escapeHtml(s.skill_name)}</option>`)
        .join('');
  } catch (error) {
    /* Non-fatal: the user can still post without tagging a skill. */
  }
}

/* ---------------- Create post ---------------- */

async function handleCreatePost(event) {
  event.preventDefault();
  clearAlert(feedAlertBox);

  const content = document.getElementById('postContent').value.trim();
  if (!content) {
    showAlert(feedAlertBox, 'Please write something before posting.', 'error');
    return;
  }

  const skillId = document.getElementById('postSkill').value || null;
  const imageInput = document.getElementById('postImage');
  const submitButton = event.target.querySelector('button[type="submit"]');

  submitButton.disabled = true;
  submitButton.textContent = 'Posting…';

  try {
    let mediaUrl = null;

    // 1) Upload the image first (if any) to get a storage key
    if (imageInput.files.length > 0) {
      const formData = new FormData();
      formData.append('file', imageInput.files[0]);
      formData.append('folder', 'posts');
      formData.append('is_public', 'true');

      const uploadResult = await API.upload('/files/upload', formData);
      mediaUrl = uploadResult.file.storage_key;
    }

    // 2) Create the post referencing that storage key
    await API.post('/posts', {
      content,
      skill_id: skillId,
      media_url: mediaUrl,
    });

    document.getElementById('postForm').reset();
    showAlert(feedAlertBox, 'Posted to the community! 🎉', 'success');
    loadFeed(true);
  } catch (error) {
    showAlert(feedAlertBox, error.message, 'error');
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = 'Post to Community';
  }
}

/* ---------------- Feed ---------------- */

async function loadFeed(reset) {
  if (reset) currentPage = 1;

  const params = new URLSearchParams({
    scope: currentScope,
    page: currentPage,
    limit: 10,
    sort: currentFilters.sort,
  });
  if (currentFilters.category) params.set('category', currentFilters.category);
  if (currentFilters.q) params.set('q', currentFilters.q);

  try {
    const data = await API.get(`/feed?${params.toString()}`);
    const posts = data.posts || [];

    if (reset) feedEl.innerHTML = '';

    if (posts.length === 0 && reset) {
      feedEl.innerHTML = `
        <div class="card empty">
          <div class="empty-icon">🌱</div>
          <h3 style="color:var(--text);text-transform:none;font-size:1rem">Nothing here yet</h3>
          <p class="mt-1">Be the first to share an achievement!</p>
        </div>`;
      return;
    }

    feedEl.insertAdjacentHTML('beforeend', posts.map(postHtml).join(''));
    attachPostHandlers();

    // Hide "Load More" when we've reached the end
    const loaded = feedEl.querySelectorAll('.post').length;
    document.getElementById('loadMore').style.display = loaded >= data.total ? 'none' : 'inline-flex';
  } catch (error) {
    showAlert(feedAlertBox, error.message, 'error');
  }
}

function postHtml(post) {
  const mediaHtml = post.media_url
    ? `<img class="post-media" src="/api/files/raw/${escapeHtml(post.media_url)}"
             alt="Achievement proof" loading="lazy"
             onerror="this.style.display='none'">`
    : '';

  const skillHtml = post.skill
    ? `<span class="badge badge-primary">${escapeHtml(post.skill.skill_name)}</span>`
    : '';

  const deleteHtml = post.is_mine
    ? `<button class="action-btn js-delete-post" data-id="${post.post_id}"
               style="margin-left:auto;color:var(--danger)">🗑 Delete</button>`
    : '';

  return `
    <article class="post" data-post-id="${post.post_id}">
      <div class="post-header">
        ${avatarHtml(post.author)}
        <div style="flex:1">
          <div style="font-weight:600;font-size:.94rem">${escapeHtml(post.author.name)}</div>
          <div style="color:var(--text-muted);font-size:.8rem">
            @${escapeHtml(post.author.username)} · ${timeAgo(post.created_at)}
          </div>
        </div>
        ${skillHtml}
      </div>

      <div class="post-content">${escapeHtml(post.content)}</div>
      ${mediaHtml}

      <div class="post-actions">
        <button class="action-btn js-like ${post.liked_by_me ? 'liked' : ''}"
                data-id="${post.post_id}">
          ${post.liked_by_me ? '❤️' : '🤍'}
          <span class="like-count">${post.like_count}</span>
        </button>
        <button class="action-btn js-toggle-comments" data-id="${post.post_id}">
          💬 <span class="comment-count">${post.comment_count}</span> Comments
        </button>
        ${deleteHtml}
      </div>

      <div class="comments-section hidden mt-2" data-comments-for="${post.post_id}">
        <div class="comments-list"></div>
        <div class="flex mt-2">
          <input class="comment-input" placeholder="Write a comment…" maxlength="1000" />
          <button class="btn btn-primary btn-sm js-add-comment" data-id="${post.post_id}">Send</button>
        </div>
      </div>
    </article>`;
}

function attachPostHandlers() {
  document.querySelectorAll('.js-like').forEach((button) => {
    button.addEventListener('click', () => toggleLike(button));
  });

  document.querySelectorAll('.js-toggle-comments').forEach((button) => {
    button.addEventListener('click', () => toggleComments(button.dataset.id));
  });

  document.querySelectorAll('.js-add-comment').forEach((button) => {
    button.addEventListener('click', () => addComment(button.dataset.id));
  });

  document.querySelectorAll('.js-delete-post').forEach((button) => {
    button.addEventListener('click', () => deletePost(button.dataset.id));
  });
}

/* ---------------- Likes ---------------- */

async function toggleLike(button) {
  const postId = button.dataset.id;
  const isLiked = button.classList.contains('liked');

  // Optimistic UI update — feels instant, corrected by the server response
  const countSpan = button.querySelector('.like-count');
  const originalCount = parseInt(countSpan.textContent, 10);
  button.classList.toggle('liked', !isLiked);
  button.firstChild.textContent = !isLiked ? '❤️' : '🤍';
  countSpan.textContent = originalCount + (isLiked ? -1 : 1);

  try {
    const result = await API.request
      ? await (isLiked ? API.del(`/posts/${postId}/like`) : API.post(`/posts/${postId}/like`, {}))
      : null;
    countSpan.textContent = result.like_count;
  } catch (error) {
    // Roll back on failure
    button.classList.toggle('liked', isLiked);
    button.firstChild.textContent = isLiked ? '❤️' : '🤍';
    countSpan.textContent = originalCount;
    showAlert(feedAlertBox, error.message, 'error');
  }
}

/* ---------------- Comments ---------------- */

async function toggleComments(postId) {
  const section = document.querySelector(`[data-comments-for="${postId}"]`);
  if (!section) return;

  const isHidden = section.classList.contains('hidden');
  section.classList.toggle('hidden', !isHidden);

  if (isHidden) await loadComments(postId);
}

async function loadComments(postId) {
  const section = document.querySelector(`[data-comments-for="${postId}"]`);
  const list = section.querySelector('.comments-list');

  try {
    const data = await API.get(`/posts/${postId}/comments`);
    const comments = data.comments || [];

    if (comments.length === 0) {
      list.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">No comments yet. Be the first!</p>';
      return;
    }

    list.innerHTML = comments
      .map(
        (c) => `
        <div class="comment">
          <div class="flex" style="gap:8px;align-items:flex-start">
            ${avatarHtml(c)}
            <div style="flex:1">
              <div style="font-weight:600;font-size:.85rem">
                ${escapeHtml(c.name)}
                <span style="color:var(--text-muted);font-weight:400">
                  @${escapeHtml(c.username)} · ${timeAgo(c.created_at)}
                </span>
              </div>
              <div style="font-size:.88rem">${escapeHtml(c.content)}</div>
            </div>
            ${c.is_mine ? `<button class="action-btn js-delete-comment" data-id="${c.comment_id}"
                                    data-post="${postId}" style="color:var(--danger)">🗑</button>` : ''}
          </div>
        </div>`
      )
      .join('');

    list.querySelectorAll('.js-delete-comment').forEach((button) => {
      button.addEventListener('click', () => deleteComment(button.dataset.id, button.dataset.post));
    });
  } catch (error) {
    list.innerHTML = `<p style="color:var(--danger);font-size:.85rem">${escapeHtml(error.message)}</p>`;
  }
}

async function addComment(postId) {
  const section = document.querySelector(`[data-comments-for="${postId}"]`);
  const input = section.querySelector('.comment-input');
  const content = input.value.trim();

  if (!content) return;

  try {
    const result = await API.post(`/posts/${postId}/comments`, { content });
    input.value = '';

    const countSpan = document.querySelector(`[data-post-id="${postId}"] .comment-count`);
    if (countSpan) countSpan.textContent = result.comment_count;

    await loadComments(postId);
  } catch (error) {
    showAlert(feedAlertBox, error.message, 'error');
  }
}

async function deleteComment(commentId, postId) {
  try {
    await API.del(`/comments/${commentId}`);
    await loadComments(postId);
    const countSpan = document.querySelector(`[data-post-id="${postId}"] .comment-count`);
    if (countSpan) countSpan.textContent = Math.max(0, parseInt(countSpan.textContent, 10) - 1);
  } catch (error) {
    showAlert(feedAlertBox, error.message, 'error');
  }
}

/* ---------------- Delete post ---------------- */

async function deletePost(postId) {
  if (!window.confirm('Delete this post permanently?')) return;

  try {
    await API.del(`/posts/${postId}`);
    const article = document.querySelector(`[data-post-id="${postId}"]`);
    if (article) article.remove();
    showAlert(feedAlertBox, 'Post deleted.', 'success');
  } catch (error) {
    showAlert(feedAlertBox, error.message, 'error');
  }
}