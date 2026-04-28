/* =====================================================================
   app.js — PBI DocGen SPA
   Comunicação com FastAPI backend via fetch + SSE
===================================================================== */

'use strict';

// ── Session ID (persiste enquanto a aba estiver aberta) ──────────────
const SESSION_ID = crypto.randomUUID();

// ── Estado global ────────────────────────────────────────────────────
const state = {
  fileSelected: null,
  metadata: null,
  docResultado: null,
  serviceToken: null,
  currentSubTab: 'tables',
  chatHistory: [],
};

// ── DOM refs ─────────────────────────────────────────────────────────
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

// =====================================================================
// INIT
// =====================================================================
document.addEventListener('DOMContentLoaded', () => {
  loadModels();
  setupNavigation();
  setupUpload();
  setupService();
  setupSubTabs();
  setupGenerate();
  setupDownloads();
  setupChat();
  setupSidebarToggle();
});

// =====================================================================
// NAVIGATION
// =====================================================================
function setupNavigation() {
  $$('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.disabled) return;
      const tab = btn.dataset.tab;
      switchTab(tab);
    });
  });
}

function switchTab(tabId) {
  $$('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
  $$('.tab-panel').forEach(p => p.classList.toggle('active', p.id === `tab-${tabId}`));
  const titles = {
    upload: 'Upload de Arquivo',
    service: 'Power BI Service',
    metadata: 'Metadados Extraídos',
    docs: 'Documentação',
    chat: 'Chat IA',
  };
  $('#page-title').textContent = titles[tabId] || tabId;
}

function enableTab(tabId) {
  const btn = $(`#nav-${tabId}`);
  if (btn) btn.disabled = false;
}

// =====================================================================
// MODELS
// =====================================================================
async function loadModels() {
  try {
    const data = await apiFetch('/api/models');
    const sel = $('#model-select');
    sel.innerHTML = '';
    data.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m;
      if (m === data.default) opt.selected = true;
      sel.appendChild(opt);
    });
  } catch (e) {
    console.warn('Erro ao carregar modelos:', e);
  }
}

// =====================================================================
// UPLOAD TAB
// =====================================================================
function setupUpload() {
  const dropZone  = $('#drop-zone');
  const fileInput = $('#file-input');
  const btnUpload = $('#btn-upload');
  const btnClear  = $('#btn-clear-file');

  // Click na drop zone
  dropZone.addEventListener('click', () => fileInput.click());

  // Drag events
  dropZone.addEventListener('dragover', e => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) selectFile(file);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) selectFile(fileInput.files[0]);
  });

  btnClear.addEventListener('click', clearFile);
  btnUpload.addEventListener('click', uploadFile);
}

function selectFile(file) {
  const allowed = ['.pbix', '.pbit', '.zip'];
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    showToast(`Formato não suportado: ${ext}. Use .pbix, .pbit ou .zip`, 'error');
    return;
  }
  state.fileSelected = file;
  $('#file-info-name').textContent = file.name;
  $('#file-info-size').textContent = formatBytes(file.size);
  $('#file-info').classList.remove('hidden');
  $('#btn-upload').disabled = false;
}

function clearFile() {
  state.fileSelected = null;
  $('#file-info').classList.add('hidden');
  $('#btn-upload').disabled = true;
  $('#file-input').value = '';
}

async function uploadFile() {
  if (!state.fileSelected) return;

  const formData = new FormData();
  formData.append('file', state.fileSelected);
  formData.append('session_id', SESSION_ID);

  setStatus('working', 'Processando arquivo...');
  setUploadProgress(0, 'Enviando arquivo...');
  showProgress(true);

  try {
    // Simula progresso visual durante o upload
    animateProgress(0, 40, 800);

    const data = await apiFetch('/api/upload', {
      method: 'POST',
      body: formData,
    });

    animateProgress(40, 100, 500);
    await sleep(500);

    state.metadata = data;
    renderMetadata(data);
    enableTab('metadata');
    enableTab('docs');
    setStatus('ready', `${data.report_name} carregado`);
    showToast(`✅ Arquivo processado: ${data.report_name}`, 'success');
    switchTab('metadata');

  } catch (e) {
    setStatus('error', 'Erro no processamento');
    showToast(`Erro: ${e.message}`, 'error');
  } finally {
    showProgress(false);
  }
}

function showProgress(show) {
  $('#upload-progress').classList.toggle('hidden', !show);
}

function setUploadProgress(pct, label) {
  $('#upload-progress-bar').style.width = `${pct}%`;
  $('#upload-progress-label').textContent = label;
}

function animateProgress(from, to, ms) {
  const steps = 20;
  const interval = ms / steps;
  const inc = (to - from) / steps;
  let current = from;
  const timer = setInterval(() => {
    current += inc;
    if (current >= to) { clearInterval(timer); current = to; }
    $('#upload-progress-bar').style.width = `${current}%`;
  }, interval);
}

// =====================================================================
// SERVICE TAB
// =====================================================================
function setupService() {
  $('#btn-connect').addEventListener('click', connectService);
  $('#workspace-select').addEventListener('change', onWorkspaceChange);
  $('#dataset-select').addEventListener('change', () => {
    $('#btn-extract-service').disabled = !$('#dataset-select').value;
  });
  $('#btn-extract-service').addEventListener('click', extractService);
}

async function connectService() {
  const tenantId     = $('#tenant-id').value.trim();
  const clientId     = $('#client-id').value.trim();
  const clientSecret = $('#client-secret').value.trim();

  if (!tenantId || !clientId || !clientSecret) {
    showToast('Preencha todos os campos de credenciais.', 'error');
    return;
  }

  setStatus('working', 'Autenticando...');
  const btn = $('#btn-connect');
  btn.disabled = true;
  btn.textContent = 'Conectando...';

  try {
    const data = await apiFetch('/api/connect-service', {
      method: 'POST',
      json: { tenant_id: tenantId, client_id: clientId, client_secret: clientSecret, session_id: SESSION_ID },
    });

    // Popula workspaces
    const wsSel = $('#workspace-select');
    wsSel.innerHTML = '<option value="">Selecione um workspace...</option>';
    data.workspaces.forEach(ws => {
      const opt = document.createElement('option');
      opt.value = ws.id;
      opt.textContent = ws.name;
      wsSel.appendChild(opt);
    });

    $('#service-selectors').classList.remove('hidden');
    setStatus('ready', 'Conectado ao Power BI Service');
    showToast('✅ Conectado com sucesso!', 'success');
  } catch (e) {
    setStatus('error', 'Falha na autenticação');
    showToast(`Erro de autenticação: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M5 12h14M12 5l7 7-7 7"/></svg> Conectar ao Power BI Service`;
  }
}

async function onWorkspaceChange() {
  const workspaceId = $('#workspace-select').value;
  const dsSel = $('#dataset-select');
  dsSel.innerHTML = '<option value="">Carregando...</option>';
  dsSel.disabled = true;

  if (!workspaceId) return;

  try {
    const data = await apiFetch(`/api/workspaces/${SESSION_ID}/datasets?workspace_id=${workspaceId}`);
    dsSel.innerHTML = '<option value="">Selecione um dataset...</option>';
    data.datasets.forEach(ds => {
      const opt = document.createElement('option');
      opt.value = ds.id;
      opt.textContent = ds.name;
      dsSel.appendChild(opt);
    });
    dsSel.disabled = false;
  } catch (e) {
    showToast('Erro ao carregar datasets: ' + e.message, 'error');
    dsSel.innerHTML = '<option value="">Erro ao carregar</option>';
  }
}

async function extractService() {
  const workspaceId = $('#workspace-select').value;
  const datasetId   = $('#dataset-select').value;
  const reportName  = $('#service-report-name').value.trim() || 'PBI Report';

  if (!workspaceId || !datasetId) {
    showToast('Selecione workspace e dataset.', 'error');
    return;
  }

  setStatus('working', 'Extraindo metadados...');
  $('#btn-extract-service').disabled = true;

  try {
    const data = await apiFetch('/api/extract-service', {
      method: 'POST',
      json: {
        session_id: SESSION_ID,
        workspace_id: workspaceId,
        dataset_id: datasetId,
        report_name: reportName,
      },
    });

    state.metadata = data;
    renderMetadata(data);
    enableTab('metadata');
    enableTab('docs');
    setStatus('ready', `${data.report_name} carregado`);
    showToast(`✅ Metadados extraídos: ${data.report_name}`, 'success');
    switchTab('metadata');
  } catch (e) {
    setStatus('error', 'Erro na extração');
    showToast('Erro: ' + e.message, 'error');
  } finally {
    $('#btn-extract-service').disabled = false;
  }
}

// =====================================================================
// METADATA TAB
// =====================================================================
function renderMetadata(data) {
  // Stats
  $('#stat-tables').textContent   = data.stats.n_tables;
  $('#stat-measures').textContent = data.stats.n_measures;
  $('#stat-columns').textContent  = data.stats.n_columns;
  $('#stat-rels').textContent     = data.stats.n_relationships;
  $('#metadata-report-name').textContent = `Relatório: ${data.report_name}`;

  // Render default sub-tab
  renderSubTab('tables');
}

function setupSubTabs() {
  $$('.tab-sub').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.tab-sub').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.currentSubTab = btn.dataset.sub;
      renderSubTab(state.currentSubTab);
    });
  });
}

const SUB_TAB_COLS = {
  tables:        ['NomeTabela', 'FonteDados'],
  measures:      ['NomeMedida', 'NomeTabela', 'ExpressaoMedida'],
  columns:       ['NomeTabela', 'NomeColuna', 'TipoDadoColuna', 'TipoColuna', 'ExpressaoColuna'],
  relationships: ['FromTable', 'FromColumn', 'ToTable', 'ToColumn'],
};

const SUB_TAB_KEY = {
  tables: 'tables',
  measures: 'measures',
  columns: 'columns',
  relationships: 'relationships',
};

const CODE_COLS = new Set(['FonteDados', 'ExpressaoMedida', 'ExpressaoColuna']);

function renderSubTab(sub) {
  if (!state.metadata) return;
  const rows = state.metadata[SUB_TAB_KEY[sub]] || [];
  const cols = SUB_TAB_COLS[sub];
  const thead = $('#metadata-thead');
  const tbody = $('#metadata-tbody');

  thead.innerHTML = `<tr>${cols.map(c => `<th>${formatColName(c)}</th>`).join('')}</tr>`;
  tbody.innerHTML = rows.length === 0
    ? `<tr><td colspan="${cols.length}" style="color:var(--text-3);text-align:center;padding:24px">Nenhum dado encontrado</td></tr>`
    : rows.map(row =>
        `<tr>${cols.map(c => {
          const val = row[c] ?? '';
          const cls = CODE_COLS.has(c) ? ' class="cell-code"' : '';
          const display = val.length > 120 ? val.slice(0, 120) + '…' : val;
          return `<td${cls} title="${escHtml(val)}">${escHtml(display)}</td>`;
        }).join('')}</tr>`
      ).join('');
}

function formatColName(key) {
  const map = {
    NomeTabela: 'Tabela', NomeMedida: 'Medida', NomeColuna: 'Coluna',
    ExpressaoMedida: 'Expressão DAX', ExpressaoColuna: 'Expressão',
    FonteDados: 'Fonte M', TipoDadoColuna: 'Tipo de Dado',
    TipoColuna: 'Tipo Col.', FromTable: 'De (Tabela)', FromColumn: 'De (Coluna)',
    ToTable: 'Para (Tabela)', ToColumn: 'Para (Coluna)',
  };
  return map[key] || key;
}

// =====================================================================
// GENERATE (SSE)
// =====================================================================
function setupGenerate() {
  $('#btn-generate').addEventListener('click', startGeneration);
}

function startGeneration() {
  const modelo   = $('#model-select').value;
  const language = $('#language-select').value;

  if (!modelo) {
    showToast('Selecione um modelo LLM.', 'error');
    return;
  }

  switchTab('docs');
  $('#generation-progress').style.display = 'flex';
  $('#doc-result').classList.add('hidden');
  $('#download-bar').classList.add('hidden');
  setStatus('working', 'Gerando documentação...');
  setProgress(0, 'Conectando...');

  const url = `/api/generate?session_id=${SESSION_ID}&modelo=${encodeURIComponent(modelo)}&language=${encodeURIComponent(language)}`;
  const es = new EventSource(url);

  es.addEventListener('progress', e => {
    const ev = JSON.parse(e.data);
    const pct = Math.round((ev.step / ev.total) * 100);
    setProgress(pct, ev.message);
  });

  es.addEventListener('done', e => {
    es.close();
    const ev = JSON.parse(e.data);
    state.docResultado = ev.doc_resultado;
    renderDocResult(ev.doc_resultado);
    setProgress(100, 'Concluído!');
    setTimeout(() => {
      $('#generation-progress').style.display = 'none';
      $('#doc-result').classList.remove('hidden');
      $('#download-bar').classList.remove('hidden');
      enableTab('chat');
    }, 800);
    setStatus('ready', 'Documentação pronta');
    showToast('🎉 Documentação gerada com sucesso!', 'success');
  });

  es.addEventListener('error', e => {
    es.close();
    let msg = 'Erro desconhecido';
    try { msg = JSON.parse(e.data).detail; } catch {}
    setStatus('error', 'Erro na geração');
    showToast('Erro: ' + msg, 'error');
    setProgress(0, 'Erro: ' + msg);
  });

  es.onerror = () => {
    es.close();
    setStatus('error', 'Conexão perdida');
    showToast('Conexão SSE perdida. Tente novamente.', 'error');
  };
}

function setProgress(pct, msg) {
  const circumference = 213.6;
  const offset = circumference - (pct / 100) * circumference;
  const fill = $('#progress-ring-fill');
  if (fill) fill.style.strokeDashoffset = offset;
  const pctEl = $('#progress-ring-pct');
  if (pctEl) pctEl.textContent = `${pct}%`;
  const msgEl = $('#progress-msg');
  if (msgEl) msgEl.textContent = msg;
}

function renderDocResult(doc) {
  const info     = doc.info || {};
  const tables   = doc.tables || [];
  const measures = doc.measures || [];
  const sources  = doc.sources || [];

  // Info section
  const kpis = (info.Principais_KPIs_e_Metricas || []).map(k => `<span class="doc-chip">${escHtml(k)}</span>`).join('');
  const usos = (info.Exemplos_de_Uso || []).map(u => `<span class="doc-chip">${escHtml(u)}</span>`).join('');

  $('#doc-info-section').innerHTML = `
    <div class="doc-section-title">📋 Informações do Relatório</div>
    <div class="doc-info-grid">
      <div class="doc-info-item full">
        <div class="doc-info-label">Título</div>
        <div class="doc-info-value" style="font-size:1.05rem;font-weight:600">${escHtml(info.Titulo || '')}</div>
      </div>
      <div class="doc-info-item full">
        <div class="doc-info-label">Descrição</div>
        <div class="doc-info-value">${escHtml(info.Descricao || '')}</div>
      </div>
      <div class="doc-info-item">
        <div class="doc-info-label">Público-Alvo</div>
        <div class="doc-info-value">${escHtml(info.Publico_Alvo || '')}</div>
      </div>
      <div class="doc-info-item">
        <div class="doc-info-label">Principais KPIs</div>
        <div class="doc-chips">${kpis || '<span style="color:var(--text-3)">—</span>'}</div>
      </div>
      <div class="doc-info-item full">
        <div class="doc-info-label">Exemplos de Uso</div>
        <div class="doc-chips">${usos || '<span style="color:var(--text-3)">—</span>'}</div>
      </div>
    </div>`;

  // Tables
  $('#doc-tables-section').innerHTML = `
    <div class="doc-section-title">🗂️ Tabelas (${tables.length})</div>
    ${renderSimpleTable(['Tabela', 'Descrição'], tables.map(t => [t.Nome, t.Descricao]))}`;

  // Measures
  $('#doc-measures-section').innerHTML = `
    <div class="doc-section-title">⚡ Medidas DAX (${measures.length})</div>
    ${renderSimpleTable(['Medida', 'Descrição'], measures.map(m => [m.Nome, m.Descricao]))}`;

  // Sources
  $('#doc-sources-section').innerHTML = `
    <div class="doc-section-title">🔌 Fontes de Dados (${sources.length})</div>
    ${renderSimpleTable(['Fonte', 'Descrição', 'Tabelas'], sources.map(s => [
      s.Nome,
      s.Descricao,
      Array.isArray(s.Tabelas_Contidas_no_M) ? s.Tabelas_Contidas_no_M.join(', ') : (s.Tabelas_Contidas_no_M || ''),
    ]))}`;
}

function renderSimpleTable(headers, rows) {
  if (!rows.length) return '<p style="color:var(--text-3);font-size:.85rem">Nenhum item.</p>';
  return `
    <div class="data-table-container">
      <table class="data-table">
        <thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
        <tbody>${rows.map(r =>
          `<tr>${r.map(c => `<td title="${escHtml(c || '')}">${escHtml(c || '')}</td>`).join('')}</tr>`
        ).join('')}</tbody>
      </table>
    </div>`;
}

// =====================================================================
// DOWNLOADS
// =====================================================================
function setupDownloads() {
  $('#btn-download-excel').addEventListener('click', () => triggerDownload('excel'));
  $('#btn-download-word').addEventListener('click', () => triggerDownload('word'));
  $('#btn-to-chat').addEventListener('click', () => switchTab('chat'));
}

async function triggerDownload(format) {
  const url = `/api/download/${format}?session_id=${SESSION_ID}`;
  try {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(await resp.text());
    const blob = await resp.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    const disp = resp.headers.get('Content-Disposition') || '';
    const match = disp.match(/filename=(.+)/);
    a.download = match ? match[1] : `documentacao.${format === 'excel' ? 'xlsx' : 'docx'}`;
    a.click();
    URL.revokeObjectURL(a.href);
    showToast(`📥 Download iniciado: ${a.download}`, 'success');
  } catch (e) {
    showToast('Erro no download: ' + e.message, 'error');
  }
}

// =====================================================================
// CHAT
// =====================================================================
function setupChat() {
  const input  = $('#chat-input');
  const btn    = $('#btn-chat-send');

  btn.addEventListener('click', sendChat);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChat();
    }
  });
  // Auto-resize textarea
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
  });
}

async function sendChat() {
  const input   = $('#chat-input');
  const pergunta = input.value.trim();
  if (!pergunta) return;

  const modelo   = $('#model-select').value;
  const language = $('#language-select').value;

  addChatMessage('user', pergunta);
  input.value = '';
  input.style.height = 'auto';

  // Typing indicator
  const typingId = 'typing-' + Date.now();
  addTypingIndicator(typingId);

  try {
    const data = await apiFetch('/api/chat', {
      method: 'POST',
      json: { session_id: SESSION_ID, pergunta, modelo, language },
    });
    removeTypingIndicator(typingId);
    addChatMessage('assistant', data.resposta);
  } catch (e) {
    removeTypingIndicator(typingId);
    addChatMessage('assistant', `⚠️ Erro: ${e.message}`);
  }
}

function addChatMessage(role, text) {
  const container = $('#chat-messages');
  const div = document.createElement('div');
  div.className = `chat-message ${role}`;
  div.innerHTML = `
    <div class="chat-avatar">${role === 'assistant' ? 'AI' : 'EU'}</div>
    <div class="chat-bubble">${escHtml(text)}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function addTypingIndicator(id) {
  const container = $('#chat-messages');
  const div = document.createElement('div');
  div.className = 'chat-message assistant chat-typing';
  div.id = id;
  div.innerHTML = `
    <div class="chat-avatar">AI</div>
    <div class="chat-bubble">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// =====================================================================
// SIDEBAR TOGGLE (mobile)
// =====================================================================
function setupSidebarToggle() {
  $('#sidebar-toggle').addEventListener('click', () => {
    $('#sidebar').classList.toggle('open');
  });
}

// =====================================================================
// STATUS
// =====================================================================
function setStatus(type, text) {
  const dot  = $('.status-dot');
  const span = $('.status-text');
  dot.className = `status-dot ${type}`;
  span.textContent = text;
}

// =====================================================================
// TOAST
// =====================================================================
function showToast(msg, type = 'info', duration = 4000) {
  const container = $('#toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  toast.innerHTML = `<span>${icons[type] || ''}</span><span>${escHtml(msg)}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = '.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// =====================================================================
// API FETCH HELPER
// =====================================================================
async function apiFetch(url, options = {}) {
  const init = { ...options };
  if (options.json) {
    init.headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    init.body = JSON.stringify(options.json);
    delete init.json;
  }
  const resp = await fetch(url, init);
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const err = await resp.json();
      detail = err.detail || JSON.stringify(err);
    } catch {}
    throw new Error(detail);
  }
  return resp.json();
}

// =====================================================================
// UTILS
// =====================================================================
function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 ** 2) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1024 ** 2).toFixed(1) + ' MB';
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
