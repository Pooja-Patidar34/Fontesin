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

// ---- Notification ----
function showNotification(message, type = 'info') {
  const existing = document.querySelector('.notification');
  if (existing) existing.remove();

  const n = document.createElement('div');
  n.className = `notification notification--${type}`;
  n.innerHTML = `<span>${message}</span><button onclick="this.parentElement.remove()">✕</button>`;
  n.style.cssText = `
    position: fixed; bottom: 24px; right: 24px; z-index: 9999;
    background: ${type === 'success' ? '#16a34a' : '#253D51'};
    color: #fff; padding: 14px 20px; border-radius: 8px;
    box-shadow: 0 8px 32px rgba(0,0,0,.2);
    display: flex; align-items: center; gap: 12px;
    font-family: 'Inter', sans-serif; font-size: .9rem;
    max-width: 380px; animation: fadeInUp .3s ease;
  `;
  n.querySelector('button').style.cssText = 'background:none;border:none;color:#fff;cursor:pointer;font-size:1rem;opacity:.7;';
  document.body.appendChild(n);
  setTimeout(() => { if (n.parentElement) n.remove(); }, 5000);
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
