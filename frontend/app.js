/**
 * Queueflow — Queue Management Frontend Application
 * Clean, standard enterprise JavaScript implementation.
 */

const app = document.querySelector('#app');
const modalRoot = document.querySelector('#modal-root');

const icons = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  queue: '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3" cy="6" r=".7"/><circle cx="3" cy="12" r=".7"/><circle cx="3" cy="18" r=".7"/>',
  chart: '<path d="M4 3v17h17M8 15l4-5 4 2 5-7"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  up: '<path d="m6 14 6-6 6 6"/>',
  down: '<path d="m6 10 6 6 6-6"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/><circle cx="9" cy="7" r="4"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  checkCircle: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  layers: '<path d="m12 3 10 5-10 5L2 8l10-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  pause: '<path d="M8 5v14M16 5v14"/>',
  play: '<path d="m8 4 12 8-12 8V4Z"/>',
  logout: '<path d="M9 5H5v14h4M9 12h12m-4-4 4 4-4 4"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 1.5 1.5M5 19l1.5-1.5M17.5 6.5 19 5"/>',
  download: '<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.1"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-2l2 3M4 16l2 3a7 7 0 0 0 12-2"/>',
};

const icon = (name, cls = '') => {
  return `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.queue}</svg>`;
};

const escape = (value) => {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[c]));
};

const initials = (name) => {
  return name.trim().split(/\s+/).slice(0, 2).map((x) => x[0]).join('').toUpperCase();
};

const tokenLabel = (token, prefix) => {
  return `${prefix}-${String(token.number).padStart(3, '0')}`;
};

const minutesSince = (time) => {
  return Math.max(0, Math.floor((Date.now() - time) / 60_000));
};

const duration = (value) => (value == null ? '—' : `${value} min`);
const timeOf = (value) => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

const logo = () => {
  return '<a href="#overview" class="brand" aria-label="Queueflow Dashboard"><img src="/favicon.svg" alt="" width="30" height="30"><span>Queueflow</span></a>';
};

const state = {
  user: null,
  queues: [],
  detail: null,
  stats: null,
  activity: [],
  selected: '',
  view: 'overview',
  days: 7,
  search: '',
  busy: false,
  loading: false,
  request: 0,
  demoEnabled: false,
  authMode: 'login',
  chart: 'volume',
  activityFilter: 'all',
  activityMore: true,
  activityLoading: false,
};

let previousFocus;

async function api(path, options = {}) {
  const csrfCookie = document.cookie
    .split(';')
    .map((x) => x.trim())
    .find((x) => x.startsWith('csrftoken='));
  const csrfToken = csrfCookie ? decodeURIComponent(csrfCookie.slice('csrftoken='.length)) : '';

  const response = await fetch(`/api${path}`, {
    credentials: 'same-origin',
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
      ...options.headers,
    },
    ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}),
  });

  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error('Server connection error. Please try again.');
  }

  if (!response.ok) {
    if (response.status === 401 && state.user) {
      state.user = null;
      closeModal(true);
      renderAuth();
    }
    const error = new Error(result.error || 'An unexpected error occurred.');
    error.status = response.status;
    throw error;
  }
  return result;
}

function toast(message, error = false) {
  const element = document.createElement('div');
  element.className = `toast ${error ? 'toast-error' : ''}`;
  element.setAttribute('role', error ? 'alert' : 'status');
  element.innerHTML = `${icon(error ? 'info' : 'checkCircle')}<span>${escape(message)}</span>`;
  document.querySelector('#toast-container').append(element);
  setTimeout(() => element.remove(), 4500);
}

function renderAuth() {
  const register = state.authMode === 'register';
  app.innerHTML = `
    <div class="auth-layout">
      <section class="auth-main">
        ${logo()}
        <div class="auth-form-wrap">
          <div class="eyebrow">Enterprise Queue Management</div>
          <h1>${register ? 'Create Account' : 'Sign In'}</h1>
          <p class="auth-intro">${register ? 'Register a manager account to start organizing queues and tokens.' : 'Enter your credentials to access your queue management workspace.'}</p>
          
          <div class="auth-tabs" role="tablist">
            <button data-action="auth-mode" data-mode="login" class="${register ? '' : 'active'}" role="tab" aria-selected="${!register}">Sign In</button>
            <button data-action="auth-mode" data-mode="register" class="${register ? 'active' : ''}" role="tab" aria-selected="${register}">Create Account</button>
          </div>

          <form id="auth-form">
            ${register ? `
              <label for="auth-name">Full Name</label>
              <div class="input-icon">
                ${icon('user')}
                <input id="auth-name" name="name" autocomplete="name" required maxlength="80" placeholder="e.g. Alex Morgan">
              </div>
            ` : ''}
            
            <label for="auth-email">Email Address</label>
            <div class="input-icon">
              ${icon('mail')}
              <input id="auth-email" name="email" type="email" autocomplete="email" required maxlength="254" placeholder="name@company.com">
            </div>

            <label for="auth-password">Password ${register ? '<span>(minimum 8 characters)</span>' : ''}</label>
            <div class="input-icon">
              ${icon('lock')}
              <input id="auth-password" name="password" type="password" autocomplete="${register ? 'new-password' : 'current-password'}" required minlength="8" maxlength="256" placeholder="••••••••">
            </div>

            <p id="auth-error" class="form-error" role="alert"></p>

            <button class="btn btn-primary auth-submit" type="submit">
              ${register ? 'Complete Registration' : 'Sign In to Workspace'} ${icon('arrow')}
            </button>
          </form>

          ${state.demoEnabled ? `
            <div class="divider"><span>OR</span></div>
            <button class="btn btn-demo" data-action="demo">
              Open Demo Workspace ${icon('arrow')}
            </button>
            <p class="auth-note">Test all features immediately with pre-loaded sample queue data.</p>
          ` : ''}
        </div>

        <div class="auth-footer">
          <span>Queueflow Enterprise Edition</span>
          <span>&copy; ${new Date().getFullYear()} All rights reserved.</span>
        </div>
      </section>

      <section class="auth-art" aria-label="Product Overview">
        <div class="art-caption">
          <span class="tiny-pill">REAL-TIME DISPATCH</span>
          <h2>Queue Dispatch & Service Monitor</h2>
          <p>Monitor customer flow, dispatch tokens, and streamline desk queues in real time.</p>
        </div>

        <div class="preview-workspace">
          <div class="preview-top">
            <div><span class="live-dot"></span> General Reception</div>
            <span class="tiny-pill">ACTIVE</span>
          </div>
          <div class="preview-serving">
            <div>
              <span>NOW SERVING</span>
              <strong>GR-024</strong>
              <p>Emma Wilson</p>
            </div>
            <div>${icon('checkCircle')}</div>
          </div>
          <div class="preview-list">
            <div class="preview-list-head">
              <span>Next in Queue</span>
              <span>3 Waiting</span>
            </div>
            ${['Olivia Bennett', 'Liam Carter', 'Amelia Brooks']
              .map(
                (name, i) => `
              <div class="preview-person">
                <span class="avatar avatar-${i}">${initials(name)}</span>
                <div>
                  <strong>${name}</strong>
                  <span>GR-0${25 + i}</span>
                </div>
                <span class="preview-wait">${[4, 2, 1][i]} min</span>
              </div>
            `
              )
              .join('')}
          </div>
        </div>

        <div class="floating-metric">
          ${icon('clock')}
          <div>
            <strong>Reduced Average Wait Time</strong>
            <div>Continuous automated queue load balancing</div>
          </div>
        </div>

        <div class="art-bottom">
          <span>Multi-Queue Dispatch</span>
          <span>Live Metrics</span>
          <span>Audit Logs</span>
        </div>
      </section>
    </div>
  `;
}

function viewFromHash() {
  const view = location.hash.slice(1);
  return ['overview', 'queues', 'analytics', 'activity'].includes(view) ? view : 'overview';
}

function renderShell() {
  app.innerHTML = `
    <div class="workspace">
      <button class="sidebar-backdrop" data-action="toggle-menu" aria-label="Close navigation"></button>
      
      <aside class="sidebar">
        <div class="sidebar-brand">${logo()}</div>
        
        <div class="workspace-label">
          <span class="workspace-avatar">${initials(state.user.name)}</span>
          <div>
            <strong>${escape(state.user.name)}</strong>
            <span>${state.user.is_demo ? 'Demo Environment' : 'Manager Workspace'}</span>
          </div>
          <span class="workspace-label-dot"></span>
        </div>

        <div class="nav-caption">Main Navigation</div>
        <nav aria-label="Main navigation">
          ${[
            ['overview', 'grid', 'Overview'],
            ['queues', 'queue', 'Queue Manager'],
            ['analytics', 'chart', 'Analytics'],
            ['activity', 'activity', 'Activity Log'],
          ]
            .map(
              ([id, glyph, name]) => `
            <a href="#${id}" class="nav-link ${state.view === id ? 'active' : ''}" data-view="${id}">
              ${icon(glyph)}
              <span>${name}</span>
              ${id === 'overview' ? '<span class="nav-shortcut">01</span>' : ''}
            </a>
          `
            )
            .join('')}
        </nav>

        <div class="nav-caption queues-caption">
          <span>Active Queues</span>
          <button class="icon-btn" data-action="new-queue" title="Create queue" aria-label="Create queue">${icon('plus')}</button>
        </div>
        <div id="sidebar-queues"></div>

        <div class="sidebar-bottom">
          <div class="calm-card">
            <h3>Operations Guide</h3>
            <p>Learn how to manage tickets, handle multi-counter dispatch, and export logs.</p>
            <button data-action="help">Quick guide ${icon('arrow')}</button>
          </div>

          <div class="profile">
            <span class="avatar profile-avatar">${initials(state.user.name)}</span>
            <div>
              <strong>${escape(state.user.name)}</strong>
              <span>Manager</span>
            </div>
            <button class="icon-btn" title="Sign out" aria-label="Sign out" data-action="logout">${icon('logout')}</button>
          </div>
        </div>
      </aside>

      <div class="workspace-body">
        <header class="topbar">
          <div class="breadcrumb">
            <button class="icon-btn mobile-menu" data-action="toggle-menu" aria-label="Toggle navigation">${icon('menu')}</button>
            <span>Workspace</span>
            <span class="breadcrumb-sep">/</span>
            <strong id="breadcrumb-view">Overview</strong>
          </div>

          <div class="topbar-right">
            <span class="connection">
              <span class="live-dot"></span>
              <span id="connection-text">System Live</span>
            </span>
            <div class="topbar-divider"></div>
            <span class="top-date">
              ${icon('calendar')}
              ${new Date().toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}
            </span>
            <span class="avatar top-avatar">${initials(state.user.name)}</span>
          </div>
        </header>

        <main id="main-content" tabindex="-1">
          <div class="loading-state">
            <span class="spinner"></span>
            <p>Loading queue data…</p>
          </div>
        </main>

        <footer class="workspace-footer">
          <span><strong>Queueflow</strong> — Queue & Service Dispatch Management</span>
          <span>System status: Normal</span>
        </footer>
      </div>
    </div>
  `;
}

function updateSidebar() {
  const target = document.querySelector('#sidebar-queues');
  if (!target) return;

  target.innerHTML = state.queues.length
    ? state.queues
        .map(
          (q) => `
      <button class="queue-link ${state.selected === q.id ? 'selected' : ''}" data-action="select-queue" data-id="${q.id}">
        <span class="queue-dot" style="--queue-color:${q.color}"></span>
        <span>${escape(q.name)}</span>
        <span class="queue-count">${q.waiting}</span>
      </button>
    `
        )
        .join('')
    : '<p class="sidebar-empty">No queues created yet.</p>';

  document.querySelectorAll('[data-view]').forEach((x) => {
    const active = x.dataset.view === state.view;
    x.classList.toggle('active', active);
    if (active) x.setAttribute('aria-current', 'page');
    else x.removeAttribute('aria-current');
  });

  const titles = {
    overview: 'Overview',
    queues: 'Queue Manager',
    analytics: 'Analytics',
    activity: 'Activity Log',
  };
  const breadcrumb = document.querySelector('#breadcrumb-view');
  if (breadcrumb) breadcrumb.textContent = titles[state.view] || 'Dashboard';
}

async function loadWorkspace({ quiet = false } = {}) {
  const request = ++state.request;
  state.loading = true;

  try {
    const [{ queues }, stats, { activity }] = await Promise.all([
      api('/queues'),
      api(`/analytics?days=${state.days}&offset=${new Date().getTimezoneOffset()}`),
      api('/activity'),
    ]);

    if (request !== state.request || !state.user) return;

    const selected = queues.some((q) => q.id === state.selected) ? state.selected : queues[0]?.id || '';
    const detail = selected ? await api(`/queues/${selected}`) : null;

    if (request !== state.request || !state.user) return;

    Object.assign(state, { queues, stats, activity, selected, detail, activityMore: activity.length === 100 });
    sessionStorage.setItem(`queueflow.selected.${state.user.id}`, selected);

    updateSidebar();
    renderMain();

    document.querySelector('.connection')?.classList.remove('offline');
    const connection = document.querySelector('#connection-text');
    if (connection) connection.textContent = 'System Live';
  } catch (error) {
    if (request !== state.request || !state.user) return;
    document.querySelector('.connection')?.classList.add('offline');
    const connection = document.querySelector('#connection-text');
    if (connection) connection.textContent = 'Connection Disconnected';

    if (!quiet) toast(error.message, true);
    if (!state.stats) {
      document.querySelector('#main-content').innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">${icon('refresh')}</div>
          <h2>Unable to Load Workspace Data</h2>
          <p>${escape(error.message)}</p>
          <button class="btn btn-primary" data-action="refresh">Retry Connection</button>
        </div>
      `;
    }
  } finally {
    if (request === state.request) state.loading = false;
  }
}

async function enterWorkspace(user) {
  state.user = user;
  state.selected = sessionStorage.getItem(`queueflow.selected.${user.id}`) || '';
  state.view = viewFromHash();
  state.stats = null;
  state.detail = null;
  state.search = '';
  state.activityFilter = 'all';
  state.activity = [];
  renderShell();
  await loadWorkspace();
}

function periodControl() {
  return `
    <label class="period-control">
      ${icon('calendar')}
      <span class="sr-only">Date Range Filter</span>
      <select id="period-select" aria-label="Date range filter">
        <option value="1" ${state.days === 1 ? 'selected' : ''}>Today</option>
        <option value="7" ${state.days === 7 ? 'selected' : ''}>Last 7 Days</option>
        <option value="30" ${state.days === 30 ? 'selected' : ''}>Last 30 Days</option>
      </select>
      ${icon('down')}
    </label>
  `;
}

function statCard(label, value, unit, glyph, color, detail) {
  return `
    <article class="stat-card">
      <div class="stat-top">
        <span>${label}</span>
        <span class="stat-icon ${color}">${icon(glyph)}</span>
      </div>
      <div class="stat-value">${value}<span>${unit}</span></div>
      <div class="stat-note">${detail}</div>
    </article>
  `;
}

function statsCards() {
  const s = state.stats;
  const live = state.queues.filter((q) => !q.paused).length;
  return `
    <div class="stats-grid">
      ${statCard('Total Waiting', s.waiting, '', 'users', 'lavender', '<span class="mini-dot purple-dot"></span> Across all active queues')}
      ${statCard('Served Today', s.servedToday, '', 'checkCircle', 'mint', 'Successfully processed')}
      ${statCard('Average Wait', s.averageWait ?? '—', s.averageWait == null ? '' : 'min', 'clock', 'peach', `Prior to service initiation`)}
      ${statCard('Active Queues', live, `<em>/ ${state.queues.length}</em>`, 'layers', 'blue', `<span class="mini-dot green-dot"></span> ${live} queues open for tickets`)}
    </div>
  `;
}

function renderMain() {
  if (!state.user || !state.stats) return;

  const main = document.querySelector('#main-content');
  const focused = main.contains(document.activeElement) && document.activeElement.matches('button[data-action]')
    ? { action: document.activeElement.dataset.action, id: document.activeElement.dataset.id }
    : null;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const titles = {
    overview: [`${greeting}, ${escape(state.user.name.split(' ')[0])}`, 'Real-time overview of current queues and service activity.'],
    queues: ['Queue Operations & Dispatch', 'Manage visitor queues, call tickets, and reorder waiting lines.'],
    analytics: ['Performance & Analytics', 'Monitor wait times, arrival rates, and service throughput.'],
    activity: ['System Activity Log', 'Audit trail of tickets created, served, and completed.'],
  };

  main.innerHTML = `
    ${state.user.is_demo ? `
      <div class="paused-banner" style="margin: 0 0 1.5rem 0;">
        ${icon('info')}
        <span>You are exploring a demo environment with sample operational data.</span>
        <button class="btn btn-small btn-secondary" style="margin-left: auto;" data-action="new-account">Create Real Account ${icon('arrow')}</button>
      </div>
    ` : ''}

    <div class="page-heading">
      <div>
        <div class="eyebrow">Operations Dashboard</div>
        <h1>${titles[state.view][0]}</h1>
        <p>${titles[state.view][1]}</p>
      </div>
      <div class="heading-actions">
        ${['overview', 'analytics'].includes(state.view) ? periodControl() : ''}
        ${state.view === 'activity' ? `
          <button class="btn btn-secondary" data-action="refresh">${icon('refresh')} Refresh</button>
          <button class="btn btn-secondary" data-action="export">${icon('download')} Export CSV</button>
        ` : `
          <button class="btn btn-primary" data-action="add-person">${icon('plus')} Add Ticket</button>
        `}
      </div>
    </div>

    ${['overview', 'analytics'].includes(state.view) ? statsCards() : ''}

    ${state.view === 'overview' ? `
      <div class="work-grid">
        <div>${queuePanel()}</div>
        <aside class="service-column">
          ${servicePanel()}
          ${flowTip()}
        </aside>
      </div>
      <div class="insight-grid">
        ${chartPanel(false)}
        ${recentPanel()}
      </div>
    ` : ''}

    ${state.view === 'queues' ? `
      <div class="queue-summary-bar">
        <span>${icon('layers')} <b>${state.queues.length}</b> total queues</span>
        <span>${icon('users')} <b>${state.stats.waiting}</b> total waiting</span>
        <button class="btn btn-secondary" data-action="new-queue">${icon('plus')} Create Queue</button>
      </div>
      <div class="work-grid">
        <div>${queuePanel()}</div>
        <aside class="service-column">
          ${servicePanel()}
          ${flowTip()}
        </aside>
      </div>
    ` : ''}

    ${state.view === 'analytics' ? analyticsView() : ''}
    ${state.view === 'activity' ? activityView() : ''}
  `;

  updateSidebar();
  drawCharts();

  if (focused) {
    const selector = `[data-action="${CSS.escape(focused.action)}"]${focused.id ? `[data-id="${CSS.escape(focused.id)}"]` : ''}`;
    const button = main.querySelector(selector);
    if (button && !button.disabled) button.focus({ preventScroll: true });
  }
}

function queuePanel() {
  const detail = state.detail;
  if (!detail) {
    return `
      <section class="panel queue-panel">
        ${panelHead('Queue Management', 'Select or create a queue to begin dispatching tickets.')}
        <div class="empty-state">
          <div class="empty-icon">${icon('queue')}</div>
          <h2>No Queues Found</h2>
          <p>Create your first queue to start adding tickets and serving visitors.</p>
          <button class="btn btn-primary" data-action="new-queue">${icon('plus')} Create First Queue</button>
        </div>
      </section>
    `;
  }

  const { queue, waiting } = detail;
  return `
    <section class="panel queue-panel">
      <div class="panel-heading">
        <div>
          <h2>Current Queue <span class="live-badge"><span class="live-dot"></span> LIVE</span></h2>
          <p>Real-time queue monitoring and customer service dispatch.</p>
        </div>
        <button class="icon-btn" data-action="new-queue" title="Create queue" aria-label="Create queue">${icon('plus')}</button>
      </div>

      <div class="queue-toolbar">
        <label class="queue-select" style="--queue-color:${queue.color}">
          <span class="queue-dot"></span>
          <span class="sr-only">Switch Active Queue</span>
          <select id="queue-select">
            ${state.queues.map((q) => `<option value="${q.id}" ${q.id === queue.id ? 'selected' : ''}>${escape(q.name)} (${q.prefix})</option>`).join('')}
          </select>
          ${icon('down')}
        </label>
        <button class="btn btn-small ${queue.paused ? 'btn-resume' : 'btn-quiet'}" data-action="pause-queue">
          ${icon(queue.paused ? 'play' : 'pause')}
          ${queue.paused ? 'Resume Queue' : 'Pause Queue'}
        </button>
      </div>

      ${queue.paused ? `
        <div class="paused-banner">
          ${icon('pause')} Queue is currently paused. Resume this queue to issue new tokens or dispatch visitors.
        </div>
      ` : ''}

      <div class="queue-tabs">
        <span class="queue-tab active">Waiting <b>${waiting.length}</b></span>
        <span class="queue-tab">In Service <b>${detail.serving ? 1 : 0}</b></span>
        <div class="queue-search">
          ${icon('search')}
          <input id="queue-search" type="search" placeholder="Search by name or ticket…" aria-label="Search waiting visitors" value="${escape(state.search)}">
        </div>
      </div>

      <div class="queue-table-scroll">
        <table class="queue-table">
          <thead>
            <tr>
              <th class="position-cell">#</th>
              <th>Visitor</th>
              <th>Ticket</th>
              <th>Wait Duration</th>
              <th class="align-right" style="text-align: right;">Actions</th>
            </tr>
          </thead>
          <tbody id="queue-rows">
            ${queueRows()}
          </tbody>
        </table>
      </div>

      <div class="queue-table-footer">
        <span id="queue-count-label">${waiting.length} ${waiting.length === 1 ? 'visitor' : 'visitors'} currently waiting</span>
        <span>${icon('info')} Use up/down controls to adjust position priority</span>
      </div>

      <div class="queue-call">
        <div>
          <span class="next-label">Next in Line</span>
          <strong>${waiting.length ? escape(waiting[0].name) : 'Queue is empty'}</strong>
          <span>${waiting.length ? tokenLabel(waiting[0], queue.prefix) : 'All visitors in this queue have been served.'}</span>
        </div>
        <button class="btn btn-primary" data-action="serve-next" ${!waiting.length || detail.serving || queue.paused ? 'disabled' : ''}>
          Call Next Visitor ${icon('arrow')}
        </button>
      </div>

      ${detail.serving && waiting.length ? `
        <p class="call-helper">Please complete the active service at desk before calling the next visitor.</p>
      ` : ''}
    </section>
  `;
}

function queueRows() {
  const { queue, waiting } = state.detail;
  const search = state.search.trim().toLowerCase();
  const filtered = waiting.filter((t) =>
    `${t.name} ${t.note} ${tokenLabel(t, queue.prefix)}`.toLowerCase().includes(search)
  );

  if (!filtered.length) {
    return `
      <tr>
        <td colspan="5">
          <div class="table-empty">
            ${icon(search ? 'search' : 'checkCircle')}
            <h3>${search ? 'No Matching Tickets Found' : 'Queue is Clear'}</h3>
            <p>${search ? 'Try adjusting your search criteria.' : 'New visitors will appear here as soon as tickets are issued.'}</p>
            ${!search ? `<button class="btn btn-secondary btn-small" data-action="add-person">${icon('plus')} Add Ticket</button>` : ''}
          </div>
        </td>
      </tr>
    `;
  }

  return filtered
    .map((t) => {
      const index = waiting.findIndex((x) => x.id === t.id);
      return `
        <tr>
          <td class="position-cell">
            <span class="position ${index === 0 ? 'position-next' : ''}">${String(index + 1).padStart(2, '0')}</span>
          </td>
          <td>
            <div class="person-cell">
              <span class="avatar avatar-${index % 5}">${escape(initials(t.name))}</span>
              <div>
                <strong>${escape(t.name)}</strong>
                <span>${escape(t.note || 'Standard consultation')}</span>
              </div>
            </div>
          </td>
          <td>
            <span class="token-tag">${tokenLabel(t, queue.prefix)}</span>
            ${index === 0 ? '<span class="next-tag">Next</span>' : ''}
          </td>
          <td>
            <span class="wait-time ${minutesSince(t.created_at) >= 15 ? 'wait-long' : ''}">
              ${icon('clock')}
              <span data-wait="${t.created_at}">${minutesSince(t.created_at)} min</span>
            </span>
          </td>
          <td>
            <div class="row-actions">
              <button class="icon-btn" data-action="move-up" data-id="${t.id}" ${index === 0 ? 'disabled' : ''} title="Move ${escape(t.name)} up" aria-label="Increase priority for ${escape(t.name)}">
                ${icon('up')}
              </button>
              <button class="icon-btn" data-action="move-down" data-id="${t.id}" ${index === waiting.length - 1 ? 'disabled' : ''} title="Move ${escape(t.name)} down" aria-label="Decrease priority for ${escape(t.name)}">
                ${icon('down')}
              </button>
              <span class="action-sep"></span>
              <button class="icon-btn cancel-btn" data-action="cancel-token" data-id="${t.id}" title="Cancel ticket" aria-label="Cancel ticket for ${escape(t.name)}">
                ${icon('close')}
              </button>
            </div>
          </td>
        </tr>
      `;
    })
    .join('');
}

function servicePanel() {
  const token = state.detail?.serving;
  return `
    <section class="service-card ${token ? '' : 'service-idle'}">
      <div class="service-card-top">
        <span>${icon('activity')} ACTIVE SERVICE</span>
        <span class="live-dot" style="background-color: ${token ? '#20c997' : '#adb5bd'};"></span>
      </div>

      ${token ? `
        <div class="service-token">${tokenLabel(token, state.detail.queue.prefix)}</div>
        <h3>${escape(token.name)}</h3>
        <p>${escape(token.note || 'Service in progress.')}</p>

        <div class="service-timing">
          <span>${icon('clock')} In Service: <b data-wait="${token.started_at}">${minutesSince(token.started_at)} min</b></span>
          <span>Waited: ${Math.round((token.started_at - token.created_at) / 60_000)} min</span>
        </div>

        <button class="btn btn-white" data-action="complete-token" data-id="${token.id}">
          ${icon('check')} Complete Service
        </button>
      ` : `
        <div class="service-empty-icon">${icon('users')}</div>
        <h3>Counter Idle</h3>
        <p>No visitor currently in service. Call the next ticket when ready.</p>
        <button class="btn btn-primary" style="width: 100%; margin-top: 1rem;" data-action="serve-next" ${!state.detail?.waiting.length || state.detail?.queue.paused ? 'disabled' : ''}>
          Call Next Ticket ${icon('arrow')}
        </button>
      `}
    </section>
  `;
}

function flowTip() {
  const queue = state.detail;
  const longest = queue?.waiting.length ? Math.max(...queue.waiting.map((t) => minutesSince(t.created_at))) : 0;
  return `
    <section class="flow-tip">
      <span class="tip-icon">${icon('info')}</span>
      <div>
        <h3>${longest >= 15 ? 'Extended Wait Alert' : 'Queue Velocity: Normal'}</h3>
        <p>${longest >= 15 ? `Longest wait time is currently ${longest} minutes. Consider opening additional service counters.` : 'Service throughput is running steadily within target thresholds.'}</p>
      </div>
    </section>
  `;
}

function panelHead(title, subtitle, action = '') {
  return `
    <div class="panel-heading">
      <div>
        <h2>${title}</h2>
        ${subtitle ? `<p>${subtitle}</p>` : ''}
      </div>
      ${action}
    </div>
  `;
}

function chartPanel(full) {
  return `
    <section class="panel chart-panel ${full ? 'chart-full' : ''}">
      ${panelHead(
        'Throughput & Volume',
        state.chart === 'volume'
          ? 'Hourly ticket arrivals versus completed services.'
          : state.chart === 'length'
          ? 'Queue backlog at interval intervals.'
          : 'Average wait duration prior to service.',
        `
        <label class="chart-select">
          <span class="sr-only">Metric Selection</span>
          <select id="chart-select">
            <option value="volume" ${state.chart === 'volume' ? 'selected' : ''}>Arrivals & Completed</option>
            <option value="length" ${state.chart === 'length' ? 'selected' : ''}>Queue Length</option>
            <option value="wait" ${state.chart === 'wait' ? 'selected' : ''}>Average Wait Time</option>
          </select>
          ${icon('down')}
        </label>
      `
      )}

      <div class="chart-legend">
        ${state.chart === 'volume'
          ? '<span><i class="legend-purple"></i> Arrivals</span><span><i class="legend-mint"></i> Completed</span>'
          : `<span><i class="legend-purple"></i> ${state.chart === 'length' ? 'Waiting Count' : 'Wait Time (min)'}</span>`}
        <span class="legend-period">${state.days === 1 ? 'Today · Hourly' : `Last ${state.days} Days · Daily`}</span>
      </div>

      <div class="chart-container" id="main-chart"></div>
    </section>
  `;
}

const statusLabel = {
  waiting: 'Ticket Issued',
  serving: 'In Service',
  completed: 'Service Completed',
  cancelled: 'Ticket Cancelled',
};

function recentPanel() {
  return `
    <section class="panel recent-panel">
      ${panelHead('Recent Activity', 'Latest queue events and ticket transitions.', `<a class="btn btn-small btn-secondary" href="#activity">View All ${icon('arrow')}</a>`)}
      <div class="recent-list">
        ${state.activity.length
          ? state.activity.slice(0, 5).map(
              (t) => `
          <div class="recent-item">
            <span class="recent-symbol status-${t.status}">
              ${icon(t.status === 'completed' ? 'check' : t.status === 'cancelled' ? 'close' : t.status === 'serving' ? 'play' : 'plus')}
            </span>
            <div>
              <strong>${escape(t.name)}</strong>
              <p>${statusLabel[t.status] || t.status} <span>· ${escape(t.queue_name)}</span></p>
            </div>
            <time>${timeOf(t.event_at)}</time>
          </div>
        `
            ).join('')
          : '<div class="small-empty">No recent activity recorded.</div>'}
      </div>
    </section>
  `;
}

function analyticsView() {
  const s = state.stats;
  return `
    <div class="analytics-metrics">
      <div>
        <span>Total Issued</span>
        <strong>${s.arrivals}</strong>
      </div>
      <div>
        <span>Completed</span>
        <strong>${s.completed}</strong>
      </div>
      <div>
        <span>Avg Service Duration</span>
        <strong>${duration(s.averageService)}</strong>
      </div>
      <div>
        <span>Cancelled</span>
        <strong>${s.cancelled}</strong>
      </div>
    </div>

    ${chartPanel(true)}

    <div class="insight-grid analytics-bottom" style="margin-top: 1.5rem;">
      <section class="panel">
        ${panelHead('Queue Performance Breakdown', `Breakdown over ${state.days === 1 ? 'today' : `the last ${state.days} days`}.`)}
        <div class="queue-table-scroll">
          <table class="queue-table">
            <thead>
              <tr>
                <th>Queue</th>
                <th>Waiting</th>
                <th>Served</th>
                <th>Avg Wait</th>
              </tr>
            </thead>
            <tbody>
              ${s.breakdown.length
                ? s.breakdown
                    .map(
                      (q) => `
                <tr>
                  <td>
                    <span class="queue-dot" style="--queue-color:${q.color}; margin-right: 0.5rem;"></span>
                    <strong>${escape(q.name)}</strong>
                  </td>
                  <td>${q.waiting}</td>
                  <td>${q.served}</td>
                  <td>${duration(q.averageWait)}</td>
                </tr>
              `
                    )
                    .join('')
                : '<tr><td colspan="4" class="small-empty">No queue metrics available for this period.</td></tr>'}
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel analytics-note">
        <h2>Reporting Documentation</h2>
        <p><strong>Wait Duration:</strong> Calculated from ticket generation until caller is called to service counter.</p>
        <p><strong>Service Duration:</strong> Calculated from service initiation to completion.</p>
        <p><strong>Timezone:</strong> Metrics are rendered based on your local device timezone.</p>
      </section>
    </div>
  `;
}

function activityView() {
  return `
    <section class="panel activity-panel">
      ${panelHead(
        'Activity Audit Log',
        'Chronological record of tickets and desk actions.',
        `
        <label class="chart-select">
          <span class="sr-only">Filter by status</span>
          <select id="activity-filter">
            ${[
              ['all', 'All Statuses'],
              ['waiting', 'Waiting'],
              ['serving', 'In Service'],
              ['completed', 'Completed'],
              ['cancelled', 'Cancelled'],
            ]
              .map(([value, label]) => `<option value="${value}" ${value === state.activityFilter ? 'selected' : ''}>${label}</option>`)
              .join('')}
          </select>
          ${icon('down')}
        </label>
      `
      )}

      <div class="queue-table-scroll">
        <table class="queue-table activity-table">
          <thead>
            <tr>
              <th>Visitor</th>
              <th>Ticket</th>
              <th>Queue</th>
              <th>Status</th>
              <th>Wait Duration</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            ${activityRows()}
          </tbody>
        </table>
      </div>

      <div class="queue-table-footer">
        <span>Showing ${state.activityFilter === 'all' ? state.activity.length : state.activity.filter((t) => t.status === state.activityFilter).length} records</span>
        ${state.activityMore ? '<button class="btn btn-secondary btn-small" data-action="load-more">Load Older Records</button>' : '<span>End of log.</span>'}
      </div>
    </section>
  `;
}

function activityRows() {
  const filtered = state.activity.filter((t) => state.activityFilter === 'all' || state.activityFilter === t.status);
  if (!filtered.length) {
    return '<tr><td colspan="6" class="small-empty">No activity records match the selected filter.</td></tr>';
  }

  return filtered
    .map(
      (t, i) => `
    <tr>
      <td>
        <div class="person-cell">
          <span class="avatar avatar-${i % 5}">${escape(initials(t.name))}</span>
          <strong>${escape(t.name)}</strong>
        </div>
      </td>
      <td><span class="token-tag">${tokenLabel(t, t.prefix)}</span></td>
      <td>${escape(t.queue_name)}</td>
      <td>
        <span class="status-pill status-${t.status}">
          ${t.status === 'serving' ? 'In Service' : t.status[0].toUpperCase() + t.status.slice(1)}
        </span>
      </td>
      <td>
        ${t.started_at ? duration(Math.round((t.started_at - t.created_at) / 60_000)) : t.status === 'cancelled' ? '—' : `<span data-wait="${t.created_at}">${minutesSince(t.created_at)} min</span>`}
      </td>
      <td>
        ${new Date(t.event_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}
        <span style="color: var(--bs-text-muted); margin-left: 0.35rem;">${timeOf(t.event_at)}</span>
      </td>
    </tr>
  `
    )
    .join('');
}

function drawCharts() {
  const target = document.querySelector('#main-chart');
  if (!target) return;

  const points = state.stats.points;
  const series =
    state.chart === 'volume'
      ? [
          { key: 'arrivals', name: 'Arrivals', color: '#0d6efd' },
          { key: 'served', name: 'Completed', color: '#198754' },
        ]
      : [
          {
            key: state.chart === 'length' ? 'queueLength' : 'averageWait',
            name: state.chart === 'length' ? 'Queue Length' : 'Average Wait',
            color: '#0d6efd',
          },
        ];

  const maxValue = Math.max(4, ...points.flatMap((p) => series.map((s) => p[s.key] || 0)));
  const step = Math.max(1, Math.ceil(maxValue / 4));
  const top = step * 4;

  const width = Math.max(300, target.clientWidth - 20);
  const height = state.view === 'analytics' && width > 600 ? 280 : 220;
  const left = 40,
    right = 20,
    bottom = 35,
    padTop = 15;
  const plotHeight = height - bottom - padTop;
  const plotWidth = width - left - right;

  const x = (i) => left + (i + 0.5) * (plotWidth / points.length);
  const y = (val) => padTop + plotHeight * (1 - val / top);
  const label = (p) =>
    new Date(p.at).toLocaleString([], state.days === 1 ? { hour: 'numeric' } : { month: 'short', day: 'numeric' });

  const grids = Array.from(
    { length: 5 },
    (_, i) => `
    <line x1="${left}" y1="${y(i * step)}" x2="${width - right}" y2="${y(i * step)}" stroke="#dee2e6" stroke-dasharray="3 3"/>
    <text x="${left - 10}" y="${y(i * step) + 4}" text-anchor="end" fill="#6c757d" font-size="11">${i * step}</text>
  `
  ).join('');

  const interval = Math.max(1, Math.ceil(points.length / Math.max(2, Math.floor(plotWidth / 56))));
  const labels = points
    .map((p, i) =>
      i % interval === 0 || (i === points.length - 1 && i % interval >= interval * 0.7)
        ? `<text x="${x(i)}" y="${height - 10}" text-anchor="middle" fill="#6c757d" font-size="11">${escape(label(p))}</text>`
        : ''
    )
    .join('');

  let marks;
  if (state.chart === 'volume') {
    const barWidth = Math.min(22, (plotWidth / points.length) * 0.32);
    marks = points
      .map((p, i) =>
        series
          .map(
            (s, j) => `
        <rect x="${x(i) + (j === 0 ? -barWidth - 2 : 2)}" y="${y(p[s.key])}" width="${barWidth}" height="${Math.max(0, y(0) - y(p[s.key]))}" rx="2" fill="${s.color}">
          <title>${escape(label(p))} · ${s.name}: ${p[s.key]}</title>
        </rect>
      `
          )
          .join('')
      )
      .join('');
  } else {
    const s = series[0];
    let segments = [],
      current = [];
    points.forEach((p, i) => {
      if (p[s.key] == null) {
        if (current.length) segments.push(current);
        current = [];
      } else current.push([x(i), y(p[s.key])]);
    });
    if (current.length) segments.push(current);

    marks =
      segments
        .map(
          (seg) =>
            `<path d="M${seg.map((p) => p.join(',')).join(' L')}" fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`
        )
        .join('') +
      points
        .map((p, i) =>
          p[s.key] == null
            ? ''
            : `<circle cx="${x(i)}" cy="${y(p[s.key])}" r="3.5" fill="white" stroke="${s.color}" stroke-width="2"><title>${escape(label(p))} · ${s.name}: ${p[s.key]}${state.chart === 'wait' ? ' min' : ''}</title></circle>`
        )
        .join('');
  }

  const hasData = points.some((p) => series.some((s) => p[s.key] > 0));
  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Performance Chart">
      <title>${escape(series.map((s) => s.name).join(' and '))}</title>
      ${grids}${marks}${labels}
    </svg>
    ${!hasData ? '<span class="chart-empty">No throughput recorded for this interval.</span>' : ''}
  `;
}

function openModal(content) {
  previousFocus = document.activeElement;
  app.inert = true;
  modalRoot.innerHTML = `
    <div class="modal-backdrop">
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <button class="icon-btn modal-close" data-action="close-modal" aria-label="Close dialog">${icon('close')}</button>
        ${content}
      </section>
    </div>
  `;
  document.body.classList.add('modal-open');
  requestAnimationFrame(() => {
    (
      modalRoot.querySelector('input') ||
      modalRoot.querySelector('select') ||
      modalRoot.querySelector('.modal-actions .btn') ||
      modalRoot.querySelector('.modal-close')
    )?.focus();
  });
}

function closeModal(force = false) {
  if (state.busy && !force) return;
  modalRoot.innerHTML = '';
  app.inert = false;
  document.body.classList.remove('modal-open');
  if (previousFocus?.isConnected) previousFocus.focus();
}

function newQueueModal() {
  openModal(`
    <span class="modal-symbol">${icon('layers')}</span>
    <h2 id="modal-title">Create New Service Queue</h2>
    <p>Define a new queue for your location or department.</p>
    <form id="queue-form">
      <label for="queue-name">Queue Name</label>
      <input id="queue-name" name="name" placeholder="e.g. Counter A / Customer Support" required maxlength="60">
      <p class="field-hint">A unique prefix code and auto-incrementing token sequence will be created.</p>
      <p class="form-error" id="modal-error" role="alert"></p>
      <div class="modal-actions">
        <button type="button" class="btn btn-secondary" data-action="close-modal">Cancel</button>
        <button class="btn btn-primary" type="submit">${icon('plus')} Create Queue</button>
      </div>
    </form>
  `);
}

function addPersonModal() {
  if (!state.queues.length) return newQueueModal();
  const available = state.queues.filter((q) => !q.paused);
  if (!available.length) {
    toast('All queues are currently paused. Resume a queue before issuing tickets.', true);
    return;
  }

  openModal(`
    <span class="modal-symbol">${icon('user')}</span>
    <h2 id="modal-title">Issue New Ticket</h2>
    <p>Enter visitor details to issue a ticket and add them to the waiting list.</p>
    <form id="person-form">
      <label for="person-queue">Target Queue</label>
      <select id="person-queue" name="queueId">
        ${available.map((q) => `<option value="${q.id}" ${q.id === state.selected ? 'selected' : ''}>${escape(q.name)} (${q.prefix})</option>`).join('')}
      </select>
      
      <label for="person-name">Visitor Name</label>
      <input id="person-name" name="name" autocomplete="off" required maxlength="80" placeholder="e.g. John Doe">
      
      <label for="person-note">Service Reason <span>(optional)</span></label>
      <input id="person-note" name="note" maxlength="240" placeholder="e.g. Account verification / Inquiries">
      
      <p class="form-error" id="modal-error" role="alert"></p>
      <div class="modal-actions">
        <button type="button" class="btn btn-secondary" data-action="close-modal">Cancel</button>
        <button class="btn btn-primary" type="submit">${icon('plus')} Issue Ticket</button>
      </div>
    </form>
  `);
}

async function mutate(operation, message, { modal = false } = {}) {
  if (state.busy) return;
  state.busy = true;
  document.body.classList.add('is-working');

  const buttons = [...document.querySelectorAll('.modal button, #main-content [data-action], #sidebar-queues button')];
  buttons.forEach((x) => {
    x.dataset.wasDisabled = String(x.disabled);
    x.disabled = true;
  });

  try {
    const result = await operation();
    if (modal) closeModal(true);
    toast(typeof message === 'function' ? message(result) : message);
    await loadWorkspace();
    return result;
  } catch (error) {
    const field = document.querySelector('#modal-error');
    if (field && modal && error.status !== 401) field.textContent = error.message;
    else toast(error.message, true);
    if (error.status === 409 && state.user) await loadWorkspace({ quiet: true });
  } finally {
    state.busy = false;
    document.body.classList.remove('is-working');
    buttons
      .filter((x) => x.isConnected)
      .forEach((x) => {
        x.disabled = x.dataset.wasDisabled === 'true';
        delete x.dataset.wasDisabled;
      });
  }
}

function exportActivity() {
  const entries = state.activity.filter((t) => state.activityFilter === 'all' || t.status === state.activityFilter);
  const cell = (val) => {
    const text = String(val ?? '');
    return `"${(/^[=+\-@\t\r\n]/.test(text) ? "'" : '') + text.replaceAll('"', '""')}"`;
  };
  const rows = [
    ['Name', 'Token', 'Queue', 'Status', 'Created at', 'Started at', 'Ended at', 'Wait (minutes)'],
    ...entries.map((t) => [
      t.name,
      tokenLabel(t, t.prefix),
      t.queue_name,
      t.status,
      new Date(t.created_at).toISOString(),
      t.started_at ? new Date(t.started_at).toISOString() : '',
      t.ended_at ? new Date(t.ended_at).toISOString() : '',
      t.started_at ? Math.round((t.started_at - t.created_at) / 60_000) : '',
    ]),
  ];

  const blob = new Blob(['\uFEFF' + rows.map((r) => r.map(cell).join(',')).join('\r\n')], {
    type: 'text/csv;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `queueflow-activity-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast(`Exported ${entries.length} log records to CSV.`);
}

document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-action]');
  if (!button || button.disabled) return;

  const action = button.dataset.action;
  if (state.busy && !['toggle-menu', 'help'].includes(action)) return;

  if (action === 'auth-mode') {
    state.authMode = button.dataset.mode;
    renderAuth();
  }

  if (action === 'demo') {
    button.disabled = true;
    button.innerHTML = '<span class="spinner"></span> Initializing demo workspace…';
    try {
      const { user } = await api('/auth/demo', { method: 'POST', body: {} });
      history.replaceState(null, '', '#overview');
      await enterWorkspace(user);
    } catch (error) {
      toast(error.message, true);
      renderAuth();
    }
  }

  if (action === 'new-queue') newQueueModal();
  if (action === 'add-person') addPersonModal();
  if (action === 'close-modal') closeModal();
  if (action === 'refresh') await loadWorkspace();
  if (action === 'toggle-menu') document.querySelector('.workspace')?.classList.toggle('menu-open');

  if (action === 'logout' || action === 'new-account') {
    try {
      await api('/auth/logout', { method: 'POST', body: {} });
      state.user = null;
      state.stats = null;
      state.request++;
      state.authMode = action === 'new-account' ? 'register' : 'login';
      renderAuth();
    } catch (error) {
      toast(error.message, true);
    }
  }

  if (action === 'select-queue') {
    state.selected = button.dataset.id;
    state.search = '';
    document.querySelector('.workspace')?.classList.remove('menu-open');
    if (state.view !== 'queues') location.hash = 'queues';
    await loadWorkspace();
  }

  const queueId = state.detail?.queue.id;
  if (action === 'pause-queue') {
    const paused = !state.detail.queue.paused;
    await mutate(
      () => api(`/queues/${queueId}`, { method: 'PATCH', body: { paused, revision: state.detail.queue.revision } }),
      paused ? 'Queue paused.' : 'Queue resumed.'
    );
  }

  if (action === 'serve-next' && state.detail) {
    await mutate(
      () => api(`/queues/${queueId}/serve-next`, { method: 'POST', body: { revision: state.detail.queue.revision } }),
      (r) => `Ticket ${tokenLabel(r.token, state.detail.queue.prefix)} (${r.token.name}) called to service desk.`
    );
  }

  if (action === 'complete-token') {
    await mutate(
      () => api(`/queues/${queueId}/tokens/${button.dataset.id}/complete`, { method: 'POST', body: {} }),
      'Service ticket completed successfully.'
    );
  }

  if (['move-up', 'move-down'].includes(action)) {
    await mutate(
      () =>
        api(`/queues/${queueId}/tokens/${button.dataset.id}/move`, {
          method: 'POST',
          body: { direction: action === 'move-up' ? 'up' : 'down', revision: state.detail.queue.revision },
        }),
      'Queue priority updated.'
    );
  }

  if (action === 'cancel-token') {
    const token = state.detail.waiting.find((t) => t.id === button.dataset.id);
    if (!token) return;
    openModal(`
      <span class="modal-symbol symbol-danger">${icon('close')}</span>
      <h2 id="modal-title">Cancel Ticket?</h2>
      <p>Confirm cancellation of ticket <strong>${tokenLabel(token, state.detail.queue.prefix)}</strong> (${escape(token.name)}). This ticket will be removed from the active queue.</p>
      <p class="form-error" id="modal-error" role="alert"></p>
      <div class="modal-actions">
        <button class="btn btn-secondary" data-action="close-modal">Keep Ticket</button>
        <button class="btn btn-danger" data-action="confirm-cancel" data-id="${token.id}" data-queue="${queueId}">Confirm Cancellation</button>
      </div>
    `);
  }

  if (action === 'confirm-cancel') {
    await mutate(
      () => api(`/queues/${button.dataset.queue}/tokens/${button.dataset.id}/cancel`, { method: 'POST', body: {} }),
      'Ticket cancelled.',
      { modal: true }
    );
  }

  if (action === 'export') exportActivity();

  if (action === 'load-more' && !state.activityLoading) {
    state.activityLoading = true;
    button.disabled = true;
    try {
      const last = state.activity.at(-1);
      const { activity } = await api(`/activity?before=${last.event_at}&beforeId=${last.id}`);
      const ids = new Set(state.activity.map((t) => t.id));
      state.activity.push(...activity.filter((t) => !ids.has(t.id)));
      state.activityMore = activity.length === 100;
      renderMain();
    } catch (error) {
      toast(error.message, true);
      button.disabled = false;
    } finally {
      state.activityLoading = false;
    }
  }

  if (action === 'help') {
    openModal(`
      <span class="modal-symbol">${icon('info')}</span>
      <h2 id="modal-title">System Operations Guide</h2>
      <p>Standard operating procedures for managing visitor queues:</p>
      <ol class="help-steps">
        <li><strong>Queue Setup:</strong> Create queues for distinct departments or service desks.</li>
        <li><strong>Ticket Issuance:</strong> Click "Add Ticket" to generate sequentially numbered tokens.</li>
        <li><strong>Queue Dispatch:</strong> Click "Call Next Ticket" when desk is ready to receive visitor.</li>
        <li><strong>Service Completion:</strong> Mark ticket complete when transaction is finished to capture accurate service time.</li>
      </ol>
      <button class="btn btn-primary full-width" data-action="close-modal">Close Guide</button>
    `);
  }
});

document.addEventListener('submit', async (event) => {
  const form = event.target;
  if (!['auth-form', 'queue-form', 'person-form'].includes(form.id)) return;

  event.preventDefault();
  const data = Object.fromEntries(new FormData(form));

  if (form.id === 'auth-form') {
    const button = form.querySelector('button[type="submit"]');
    if (button.disabled) return;
    button.disabled = true;
    document.querySelector('#auth-error').textContent = '';

    try {
      const { user } = await api(`/auth/${state.authMode}`, { method: 'POST', body: data });
      if (state.authMode === 'register') history.replaceState(null, '', '#overview');
      await enterWorkspace(user);
    } catch (error) {
      const field = document.querySelector('#auth-error');
      if (field) field.textContent = error.message;
      button.disabled = false;
    }
  }

  if (form.id === 'queue-form') {
    await mutate(
      async () => {
        const result = await api('/queues', { method: 'POST', body: data });
        state.selected = result.queue.id;
        return result;
      },
      'Queue created successfully.',
      { modal: true }
    );
  }

  if (form.id === 'person-form') {
    await mutate(
      async () => {
        const result = await api(`/queues/${data.queueId}/tokens`, {
          method: 'POST',
          body: { name: data.name, note: data.note },
        });
        state.selected = data.queueId;
        return result;
      },
      (r) => `Ticket ${tokenLabel(r.token, state.detail.queue.prefix)} issued for ${r.token.name}.`,
      { modal: true }
    );
  }
});

document.addEventListener('change', async (event) => {
  if (event.target.id === 'period-select') {
    state.days = Number(event.target.value);
    await loadWorkspace();
  }
  if (event.target.id === 'queue-select') {
    state.selected = event.target.value;
    state.search = '';
    await loadWorkspace();
  }
  if (event.target.id === 'chart-select') {
    state.chart = event.target.value;
    renderMain();
  }
  if (event.target.id === 'activity-filter') {
    state.activityFilter = event.target.value;
    renderMain();
  }
});

document.addEventListener('input', (event) => {
  if (event.target.id === 'queue-search') {
    state.search = event.target.value;
    document.querySelector('#queue-rows').innerHTML = queueRows();
    const count = state.detail.waiting.filter((t) =>
      `${t.name} ${t.note} ${tokenLabel(t, state.detail.queue.prefix)}`.toLowerCase().includes(state.search.trim().toLowerCase())
    ).length;
    document.querySelector('#queue-count-label').textContent = state.search
      ? `${count} of ${state.detail.waiting.length} visitors`
      : `${count} ${count === 1 ? 'visitor' : 'visitors'} waiting`;
  }
});

window.addEventListener('hashchange', () => {
  if (!state.user) return;
  state.view = viewFromHash();
  state.search = '';
  document.querySelector('.workspace')?.classList.remove('menu-open');
  renderMain();
  window.scrollTo({ top: 0 });
});

let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(drawCharts, 100);
});

modalRoot.addEventListener('click', (event) => {
  if (event.target.classList.contains('modal-backdrop')) closeModal();
});

document.addEventListener('keydown', (event) => {
  if (!modalRoot.firstChild) return;
  if (event.key === 'Escape') closeModal();
  if (event.key === 'Tab') {
    const focusable = [...modalRoot.querySelectorAll('button, input, select, a[href]')].filter((x) => !x.disabled);
    const first = focusable[0],
      last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }
});

setInterval(() => {
  document.querySelectorAll('[data-wait]').forEach((x) => {
    x.textContent = `${minutesSince(Number(x.dataset.wait))} min`;
  });
}, 15_000);

setInterval(() => {
  if (
    !state.user ||
    state.busy ||
    state.loading ||
    state.activityLoading ||
    modalRoot.firstChild ||
    document.hidden ||
    state.view === 'activity'
  )
    return;
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
  loadWorkspace({ quiet: true });
}, 10_000);

try {
  const config = await api('/config');
  state.demoEnabled = config.demoEnabled;
  try {
    const { user } = await api('/auth/me');
    await enterWorkspace(user);
  } catch (error) {
    if (error.status !== 401) toast(error.message, true);
    renderAuth();
  }
} catch (error) {
  renderAuth();
  toast(error.message, true);
}
