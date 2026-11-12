// PPC Product Catalog — interaksi UI

const AUTH_KEY = 'ppc-auth';
const AUTH_USER = 'ppc';
const AUTH_PASS = 'catalog2024';

let materialsLoaded = false;
let materialsData = null;
let isAuthenticated = false;

/* ---------- Theme ---------- */
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme === 'dark' ? 'dark' : 'light';
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = theme === 'dark' ? '#171b20' : '#f5f6f7';
  localStorage.setItem('ppc-theme', theme);
  const btn = document.getElementById('theme-toggle');
  if (btn) btn.textContent = theme === 'dark' ? '☀ Mode terang' : '☾ Mode gelap';
}

function initTheme() {
  // Theme already set in <head> inline script to avoid flash.
  // Only sync the button label here.
  const current = document.documentElement.dataset.theme || localStorage.getItem('ppc-theme') || 'light';
  applyTheme(current);

  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  btn.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
  });
}

/* ---------- Typewriter slogan ---------- */
function typeWriter(element, text, speed = 38) {
  if (!element) return;
  element.textContent = '';
  let i = 0;
  function tick() {
    if (i < text.length) {
      element.textContent += text.charAt(i);
      i++;
      setTimeout(tick, speed);
    }
  }
  tick();
}

/* ---------- Auth / Login ---------- */
function checkAuth() {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (!raw) return false;
    const data = JSON.parse(raw);
    return data && data.ok === true && data.user === AUTH_USER;
  } catch {
    return false;
  }
}

function setAuth(ok) {
  if (ok) {
    localStorage.setItem(AUTH_KEY, JSON.stringify({
      ok: true,
      user: AUTH_USER,
      ts: Date.now()
    }));
  } else {
    localStorage.removeItem(AUTH_KEY);
  }
  isAuthenticated = ok;
}

function openLogin() {
  const overlay = document.getElementById('login-overlay');
  if (!overlay) return;
  overlay.classList.add('is-open');
  overlay.setAttribute('aria-hidden', 'false');
  const err = document.getElementById('login-error');
  if (err) err.hidden = true;
  const form = document.getElementById('login-form');
  if (form) form.reset();
  setTimeout(() => {
    const user = document.getElementById('login-user');
    if (user) user.focus();
  }, 50);
}

function closeLogin() {
  const overlay = document.getElementById('login-overlay');
  if (overlay) {
    overlay.classList.remove('is-open');
    overlay.setAttribute('aria-hidden', 'true');
  }
  const err = document.getElementById('login-error');
  if (err) err.hidden = true;
}

/** Login diganti Logout saat sudah masuk; Logout disembunyikan saat belum login */
function updateLoginButton() {
  const loginBtn = document.getElementById('btn-login');
  const logoutBtn = document.getElementById('btn-logout');

  if (isAuthenticated) {
    if (loginBtn) {
      loginBtn.hidden = true;
      loginBtn.setAttribute('aria-hidden', 'true');
    }
    if (logoutBtn) {
      logoutBtn.hidden = false;
      logoutBtn.removeAttribute('aria-hidden');
      logoutBtn.textContent = 'Logout';
    }
  } else {
    if (loginBtn) {
      loginBtn.hidden = false;
      loginBtn.removeAttribute('aria-hidden');
      loginBtn.disabled = false;
      loginBtn.textContent = 'Login';
    }
    if (logoutBtn) {
      logoutBtn.hidden = true;
      logoutBtn.setAttribute('aria-hidden', 'true');
    }
  }
}

function handleLogin(e) {
  e.preventDefault();
  e.stopPropagation();

  const userEl = document.getElementById('login-user');
  const passEl = document.getElementById('login-pass');
  const err = document.getElementById('login-error');

  const user = (userEl?.value || '').trim();
  const pass = passEl?.value || '';

  if (user === AUTH_USER && pass === AUTH_PASS) {
    setAuth(true);
    closeLogin();
    updateLoginButton();
    if (materialsData) {
      renderMaterials(materialsData);
    } else if (document.getElementById('material-body')) {
      loadMaterials();
    }
  } else {
    if (err) {
      err.hidden = false;
      err.textContent = 'Username atau password salah.';
    }
    if (passEl) {
      passEl.value = '';
      passEl.focus();
    }
  }
}

function handleLogout() {
  setAuth(false);
  updateLoginButton();
  if (materialsData) renderMaterials(materialsData);
}

/* ---------- Materials ---------- */
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
  );
}

function formatPrice(value) {
  const number = Number(String(value).replace(',', '.'));
  if (!Number.isFinite(number)) return escapeHtml(value);
  return '$' + (number >= 1 ? number.toFixed(2) : number >= .01 ? number.toFixed(4) : number.toFixed(6));
}

function isNomatItem(item) {
  const name = String(item.name || '').toLowerCase();
  return name.includes('nomat');
}

async function loadMaterials() {
  const body = document.getElementById('material-body');
  if (!body) return;
  try {
    const response = await fetch('product-data.json');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    materialsData = data;
    renderMaterials(data);
    materialsLoaded = true;
  } catch (error) {
    body.innerHTML = '<p class="error-message">Data material tidak dapat dimuat. Pastikan product-data.json tersedia dan akses melalui server lokal (bukan file://).</p>';
    console.error(error);
  }
}

function renderMaterials(data) {
  const product = data.product || {};
  const meta = document.getElementById('product-meta');
  if (meta) {
    const chips = [
      product['Brand Desc'],
      product.Size,
      product.GSM ? `${product.GSM} gsm` : '',
      product.SKU ? `SKU ${product.SKU}` : ''
    ].filter(Boolean);
    meta.innerHTML = chips.map(v => `<span class="meta-chip">${escapeHtml(v)}</span>`).join('');
  }

  const body = document.getElementById('material-body');
  if (!body) return;

  const showSensitive = isAuthenticated;
  const headerPrice = showSensitive ? '<th>Harga satuan (USD)</th>' : '';

  body.innerHTML = (data.materials || []).map(category => {
    const rows = (category.items || []).map(item => {
      const isNomat = isNomatItem(item);
      let displayValue = item.value || '—';
      if (!showSensitive && isNomat) {
        displayValue = '••••••••';
      }

      let priceCell = '';
      if (showSensitive) {
        priceCell = item.unitPrice
          ? `<td><span class="price">${formatPrice(item.unitPrice)}</span></td>`
          : '<td><span class="muted">—</span></td>';
      }

      return `<tr>
        <td>${escapeHtml(item.name)}</td>
        <td>${escapeHtml(displayValue)}</td>
        ${priceCell}
      </tr>`;
    }).join('');

    return `
      <section class="material-category">
        <h3>${escapeHtml(category.category)}</h3>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Material</th>
                <th>Nilai / spesifikasi</th>
                ${headerPrice}
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </section>`;
  }).join('') + (
    showSensitive
      ? '<p class="material-footnote">Harga dan spesifikasi ditampilkan sesuai data sumber. Nilai yang belum tersedia tidak diestimasi.</p>'
      : '<p class="material-footnote muted">Harga dan nomor material disembunyikan. Login untuk melihat data lengkap.</p>'
  );
}

/* ---------- Layer pallet 2D ---------- */
// Vertikal = putar 90° clockwise dari 5×3 horizontal → 3 kolom × 5 baris
const LAYER_COLS = 3;
const LAYER_ROWS = 5;
const BOXES_PER_LAYER = LAYER_COLS * LAYER_ROWS;
const TOTAL_LAYERS = 4;

function renderLayerGrid(layerNum) {
  const canvas = document.getElementById('layer-canvas');
  const caption = document.getElementById('layer-caption');
  if (!canvas) return;

  const cells = [];
  for (let r = 0; r < LAYER_ROWS; r++) {
    for (let c = 0; c < LAYER_COLS; c++) {
      const n = r * LAYER_COLS + c + 1;
      cells.push(`<div class="layer-cell" title="Carton ${n}"><span>${n}</span></div>`);
    }
  }

  canvas.style.gridTemplateColumns = `repeat(${LAYER_COLS}, 1fr)`;
  canvas.style.gridTemplateRows = `repeat(${LAYER_ROWS}, 1fr)`;
  canvas.innerHTML = cells.join('');
  canvas.dataset.layer = String(layerNum);

  if (caption) {
    caption.textContent = `Menampilkan Layer ${layerNum} · ${BOXES_PER_LAYER} carton (${LAYER_COLS} × ${LAYER_ROWS}) · total pallet ${BOXES_PER_LAYER * TOTAL_LAYERS} carton`;
  }
}

function initLayerControls() {
  const buttons = document.querySelectorAll('.layer-btn');
  if (!buttons.length) return;

  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      const layer = Number(btn.dataset.layer) || 1;
      buttons.forEach(b => {
        b.classList.toggle('is-active', b === btn);
        b.setAttribute('aria-selected', b === btn ? 'true' : 'false');
      });
      renderLayerGrid(layer);
    });
  });

  renderLayerGrid(1);
}

/* ---------- Magnifier ---------- */
function initMagnifier() {
  document.querySelectorAll('.magnify-frame').forEach(frame => {
    frame.addEventListener('pointermove', event => {
      const rect = frame.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) * 100;
      const y = ((event.clientY - rect.top) / rect.height) * 100;
      frame.style.setProperty('--zoom-x', `${x}%`);
      frame.style.setProperty('--zoom-y', `${y}%`);
    });
    frame.addEventListener('click', () => frame.classList.toggle('zoomed'));
  });
}

/* ---------- Init ---------- */
function initPage() {
  initTheme();
  isAuthenticated = checkAuth();
  updateLoginButton();

  const sloganEl = document.getElementById('hero-slogan');
  if (sloganEl) {
    typeWriter(
      sloganEl,
      'multi purpose quality paper.',
      32
    );
  }

  const loginBtn = document.getElementById('btn-login');
  const logoutBtn = document.getElementById('btn-logout');
  const loginForm = document.getElementById('login-form');
  const loginCancel = document.getElementById('login-cancel');
  const loginOverlay = document.getElementById('login-overlay');

  if (loginBtn) {
    loginBtn.addEventListener('click', () => {
      if (isAuthenticated) return;
      openLogin();
    });
  }

  if (logoutBtn) {
    logoutBtn.addEventListener('click', handleLogout);
  }

  if (loginForm) {
    loginForm.addEventListener('submit', handleLogin);
  }

  if (loginCancel) {
    loginCancel.addEventListener('click', (e) => {
      e.preventDefault();
      closeLogin();
    });
  }

  if (loginOverlay) {
    loginOverlay.addEventListener('click', (e) => {
      if (e.target === loginOverlay) closeLogin();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLogin();
  });

  const toggle = document.getElementById('material-toggle');
  if (toggle) {
    toggle.hidden = false;
    toggle.addEventListener('click', async () => {
      const body = document.getElementById('material-body');
      const expanded = toggle.getAttribute('aria-expanded') === 'true';
      if (!materialsLoaded && !expanded) await loadMaterials();
      if (body) body.hidden = expanded;
      toggle.setAttribute('aria-expanded', String(!expanded));
      toggle.textContent = expanded ? 'Tampilkan daftar material' : 'Sembunyikan daftar material';
    });
  }

  initMagnifier();
  initLayerControls();

  if (document.getElementById('material-body')) {
    loadMaterials();
  }
}

document.addEventListener('DOMContentLoaded', initPage);