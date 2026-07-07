/* ============================================================
   FONTESIN – Main JavaScript
   ============================================================ */

// ---- Active nav link ----
document.addEventListener('DOMContentLoaded', () => {
  const currentPage = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.navbar__nav a').forEach(link => {
    const href = link.getAttribute('href');
    if (href === currentPage || (currentPage === '' && href === 'index.html')) {
      link.classList.add('active');
    }
  });

  // Animate on scroll
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('animate-in');
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.card, .data-card, .job-card, .team-card, .value-item').forEach(el => {
    observer.observe(el);
  });

  // Progress bars
  document.querySelectorAll('.progress-bar-fill').forEach(bar => {
    const width = bar.getAttribute('data-width');
    setTimeout(() => { bar.style.width = width + '%'; }, 300);
  });

  // Password toggle — icon mirrors current state:
  //   password hidden (type="password")  → eye-slash icon
  //   password visible (type="text")     → eye icon
  document.querySelectorAll('.password-toggle__btn').forEach(btn => {
    const input = btn.previousElementSibling;
    // Normalize legacy emoji buttons to a Font Awesome icon on first render.
    if (!btn.querySelector('i.fa-eye, i.fa-eye-slash')) {
      btn.innerHTML = (input && input.type === 'text')
        ? '<i class="fas fa-eye"></i>'
        : '<i class="fas fa-eye-slash"></i>';
    }
    btn.addEventListener('click', () => {
      if (input.type === 'password') {
        input.type = 'text';
        btn.innerHTML = '<i class="fas fa-eye"></i>';
      } else {
        input.type = 'password';
        btn.innerHTML = '<i class="fas fa-eye-slash"></i>';
      }
    });
  });

  // Form submit handlers
  // NOTE: the contact form (#contact-form) deliberately has NO JS submit
  // handler — it posts natively to the `contact` view so (a) the browser's
  // built-in "required" validation popups fire on empty required fields and
  // (b) the message is actually saved + the admin notified. A previous
  // Pre-MVP stub here called e.preventDefault() and faked a success toast,
  // which silently swallowed every real submission.

  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', (e) => {
      e.preventDefault();
      showNotification('Login functionality coming soon. Platform is in Pre-MVP phase.', 'info');
    });
  }

  const registerForm = document.getElementById('register-form');
  if (registerForm) {
    registerForm.addEventListener('submit', (e) => {
      e.preventDefault();
      showNotification('Registration submitted! We will review your application shortly.', 'success');
      registerForm.reset();
    });
  }
});

// ---- Toast Notification System ----
function getToastContainer() {
  let container = document.querySelector('.app-toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'app-toast-container';
    document.body.appendChild(container);
  }
  return container;
}

const TOAST_ICONS = {
  error: '!', success: '\u2713', warning: '\u26A0', info: 'i'
};

function _toastTitle(type) {
  var titles = {
    error: 'Error', success: 'Success', warning: 'Warning', info: 'Info'
  };
  var fallback = titles[type] || titles.info;
  return (typeof gettext === 'function') ? gettext(fallback) : fallback;
}

const TOAST_TITLES = {
  get error() { return _toastTitle('error'); },
  get success() { return _toastTitle('success'); },
  get warning() { return _toastTitle('warning'); },
  get info() { return _toastTitle('info'); }
};

function showToast(message, type, duration) {
  type = type || 'info';
  duration = duration || 3500;
  var container = getToastContainer();

  // Belt-and-braces dismissal: setTimeout is the primary trigger, but
  // browsers throttle setTimeout in inactive/background tabs — so a toast
  // shown right before the user switches tabs can get stuck visible until
  // they come back. The progress-bar `animationend` event fires on
  // rAF-driven CSS animations and survives that throttling, so attaching
  // it as a fallback guarantees the toast eventually clears.
  function armDismiss(toastEl, dur) {
    if (toastEl._dismissTimer) clearTimeout(toastEl._dismissTimer);
    toastEl._dismissTimer = setTimeout(function () { dismissToast(toastEl); }, dur);
    var bar = toastEl.querySelector('.app-toast__progress');
    if (bar) {
      bar.addEventListener('animationend', function onEnd() {
        bar.removeEventListener('animationend', onEnd);
        dismissToast(toastEl);
      });
    }
  }

  // Deduplicate: if a toast with the same message+type is already showing,
  // reset its dismiss timer (and replay the slide-in + progress-bar
  // animation so the user gets visual feedback the action registered)
  // instead of stacking another copy. Stops a misbehaving form from
  // spawning a column of identical errors.
  var existing = container.querySelectorAll('.app-toast--' + type);
  for (var i = 0; i < existing.length; i++) {
    var t = existing[i];
    var msgEl = t.querySelector('.app-toast__msg');
    if (msgEl && msgEl.textContent === message) {
      // Re-trigger CSS animations by clearing them, forcing a reflow,
      // then reapplying — without the reflow the browser keeps the old
      // animation state and the keyframes don't replay.
      var progress = t.querySelector('.app-toast__progress');
      t.style.animation = 'none';
      if (progress) progress.style.animation = 'none';
      void t.offsetWidth;
      t.style.animation = 'toastSlideIn .35s cubic-bezier(.21,1.02,.73,1)';
      if (progress) progress.style.animation = 'toastProgress ' + (duration / 1000) + 's linear forwards';
      armDismiss(t, duration);
      return;
    }
  }

  var toast = document.createElement('div');
  toast.className = 'app-toast app-toast--' + type;
  toast.innerHTML =
    '<span class="app-toast__icon">' + TOAST_ICONS[type] + '</span>' +
    '<div class="app-toast__body">' +
      '<div class="app-toast__title">' + TOAST_TITLES[type] + '</div>' +
      '<div class="app-toast__msg">' + message + '</div>' +
    '</div>' +
    '<button class="app-toast__close">&times;</button>' +
    '<div class="app-toast__progress"></div>';

  toast.querySelector('.app-toast__close').addEventListener('click', function() {
    if (toast._dismissTimer) clearTimeout(toast._dismissTimer);
    dismissToast(toast);
  });

  container.appendChild(toast);

  // Sync the progress-bar duration to the dismissal timeout so the visual
  // countdown always matches the actual time-to-dismiss. The CSS default
  // is 5s, so anything other than 5s would visually drift without this.
  var newProgress = toast.querySelector('.app-toast__progress');
  if (newProgress) newProgress.style.animation = 'toastProgress ' + (duration / 1000) + 's linear forwards';

  armDismiss(toast, duration);
}

function dismissToast(toast) {
  if (!toast || !toast.parentElement) return;
  toast.style.animation = 'toastFadeOut .3s ease forwards';
  setTimeout(function() { if (toast.parentElement) toast.remove(); }, 300);
}

// Backward compatibility
function showNotification(message, type) {
  showToast(message, type);
}

// ── Mobile navbar toggle ──────────────────────────────────────────
function toggleMobileNav() {
  const nav = document.querySelector('.navbar__nav');
  const btn = document.querySelector('.navbar__hamburger');
  if (!nav) return;
  const isOpen = nav.classList.toggle('mobile-open');
  if (btn) btn.textContent = isOpen ? '✕' : '☰';
  // Close on outside click
  if (isOpen) {
    document.addEventListener('click', function handler(e) {
      if (!nav.contains(e.target) && !e.target.closest('.navbar__hamburger')) {
        nav.classList.remove('mobile-open');
        if (btn) btn.textContent = '☰';
        document.removeEventListener('click', handler);
      }
    });
  }
}
// Close mobile nav on link click
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.navbar__nav a').forEach(function(a) {
    a.addEventListener('click', function() {
      const nav = document.querySelector('.navbar__nav');
      const btn = document.querySelector('.navbar__hamburger');
      if (nav) nav.classList.remove('mobile-open');
      if (btn) btn.textContent = '☰';
    });
  });
});
