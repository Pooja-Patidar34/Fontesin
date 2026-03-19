/* ============================================================
   FONTESIN – World Map Module
   SVG-based interactive world map
   ============================================================ */

const COUNTRY_STATUS = {
  // ACTIVE (Year 1)
  'US': { status: 'active', year: 1, name: 'United States',         page: 'region-us.html' },
  'DE': { status: 'active', year: 1, name: 'Germany',               page: 'region-de.html' },
  'CZ': { status: 'active', year: 1, name: 'Czech Republic',        page: 'region-cz.html' },
  'GB': { status: 'active', year: 1, name: 'United Kingdom',        page: 'region-gb.html' },
  'FR': { status: 'active', year: 1, name: 'France',                page: null },
  'NL': { status: 'active', year: 1, name: 'Netherlands',           page: null },
  'PL': { status: 'active', year: 1, name: 'Poland',                page: null },
  'AT': { status: 'active', year: 1, name: 'Austria',               page: null },
  'CH': { status: 'active', year: 1, name: 'Switzerland',           page: null },
  'SE': { status: 'active', year: 1, name: 'Sweden',                page: null },
  // PLANNED (Year 2)
  'AE': { status: 'planned', year: 2, name: 'United Arab Emirates', page: 'region-ae.html' },
  'JP': { status: 'planned', year: 3, name: 'Japan',                page: 'region-jp.html' },
  'SG': { status: 'planned', year: 2, name: 'Singapore',            page: null },
  'CA': { status: 'planned', year: 2, name: 'Canada',               page: null },
  'AU': { status: 'planned', year: 2, name: 'Australia',            page: null },
  'BR': { status: 'planned', year: 3, name: 'Brazil',               page: null },
  'IN': { status: 'planned', year: 3, name: 'India',                page: null },
  'ZA': { status: 'planned', year: 4, name: 'South Africa',         page: null },
  'MX': { status: 'planned', year: 3, name: 'Mexico',               page: null },
  'KR': { status: 'planned', year: 3, name: 'South Korea',          page: null },
};

// Petroleum-blue palette on white/light background
const STATUS_COLORS = {
  active:   '#253D51',   // darkest petroleum blue – active regions
  planned:  '#5F8FAA',   // medium petroleum blue – planned regions
  inactive: '#D8E4EC',   // very light blue-grey – inactive
};
const HOVER_COLORS = {
  active:  '#1B2E3F',    // even darker on hover
  planned: '#4a7a96',    // slightly darker medium blue on hover
};

document.addEventListener('DOMContentLoaded', () => {
  const svg = document.getElementById('world-map-svg');
  if (!svg) return;

  const tooltip = document.getElementById('map-tooltip');

  // Apply status classes & colors to all paths
  svg.querySelectorAll('[data-iso]').forEach(path => {
    const iso = path.getAttribute('data-iso');
    const info = COUNTRY_STATUS[iso];

    if (info) {
      path.setAttribute('data-status', info.status);
      path.style.fill = STATUS_COLORS[info.status];
      if (info.status === 'planned') {
        path.style.stroke = '#4a7a96';
        path.style.strokeWidth = '0.5';
        path.style.strokeDasharray = 'none';
      } else if (info.status === 'active') {
        path.style.stroke = '#1B2E3F';
        path.style.strokeWidth = '0.5';
        path.style.strokeDasharray = 'none';
      }
      path.style.cursor = 'pointer';

      path.addEventListener('mouseenter', (e) => {
        path.style.fill = HOVER_COLORS[info.status] || '#3a5a72';
        showTooltip(e, info);
      });
      path.addEventListener('mousemove', (e) => {
        moveTooltip(e);
      });
      path.addEventListener('mouseleave', () => {
        path.style.fill = STATUS_COLORS[info.status];
        hideTooltip();
      });
      path.addEventListener('click', () => {
        if (info.page) {
          window.location.href = info.page;
        }
      });
    } else {
      path.style.fill = STATUS_COLORS.inactive;
      path.style.stroke = '#b8cdd9';
      path.style.strokeWidth = '0.3';
    }
  });

  function showTooltip(e, info) {
    if (!tooltip) return;
    const statusLabel = info.status === 'active' ? 'Active' : info.status === 'planned' ? `Planned – Year ${info.year}` : 'Inactive';
    const statusClass = info.status === 'active' ? 'map-tooltip__status--active' : info.status === 'planned' ? 'map-tooltip__status--planned' : '';
    tooltip.innerHTML = `
      <div class="map-tooltip__name">${info.name}</div>
      <div class="map-tooltip__status ${statusClass}">${statusLabel}</div>
      ${info.page ? '<div style="font-size:.72rem;color:rgba(199,204,209,.6);margin-top:4px;">Click for details →</div>' : ''}
    `;
    tooltip.classList.add('visible');
    moveTooltip(e);
  }

  function moveTooltip(e) {
    if (!tooltip) return;
    const x = e.clientX + 14;
    const y = e.clientY - 10;
    tooltip.style.left = Math.min(x, window.innerWidth - 200) + 'px';
    tooltip.style.top  = Math.max(y, 10) + 'px';
  }

  function hideTooltip() {
    if (!tooltip) return;
    tooltip.classList.remove('visible');
  }
});
