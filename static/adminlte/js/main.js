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

  // Password toggle
  document.querySelectorAll('.password-toggle__btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = btn.previousElementSibling;
      if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🙈';
      } else {
        input.type = 'password';
        btn.textContent = '👁';
      }
    });
  });

  // Form submit handlers
  const contactForm = document.getElementById('contact-form');
  if (contactForm) {
    contactForm.addEventListener('submit', (e) => {
      e.preventDefault();
      showNotification('Your message has been sent. We will get back to you shortly.', 'success');
      contactForm.reset();
    });
  }

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
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  return container;
}

const TOAST_ICONS = {
  error: '!', success: '\u2713', warning: '\u26A0', info: 'i'
};
const TOAST_TITLES = {
  error: 'Error', success: 'Success', warning: 'Warning', info: 'Info'
};

function showToast(message, type) {
  type = type || 'info';
  var container = getToastContainer();
  var toast = document.createElement('div');
  toast.className = 'toast toast--' + type;
  toast.innerHTML =
    '<span class="toast__icon">' + TOAST_ICONS[type] + '</span>' +
    '<div class="toast__body">' +
      '<div class="toast__title">' + TOAST_TITLES[type] + '</div>' +
      '<div class="toast__msg">' + message + '</div>' +
    '</div>' +
    '<button class="toast__close">&times;</button>' +
    '<div class="toast__progress"></div>';

  toast.querySelector('.toast__close').addEventListener('click', function() {
    dismissToast(toast);
  });

  container.appendChild(toast);

  setTimeout(function() { dismissToast(toast); }, 5000);
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
