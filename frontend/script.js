'use strict';

/* ═══════════════════════════════════════════════════════════
   GLOBALS & CONFIG
   ═══════════════════════════════════════════════════════════ */
const API_ROOT = (window.NEXUS_API || 'https://nexus-backend-ffn4.onrender.com/api/v1').replace(/\/$/, '');
let TOKEN = localStorage.getItem('nexus_token') || '';
let REFRESH_TOKEN = localStorage.getItem('nexus_refresh') || '';

let monacoEditor = null;
let swarmSSE = null;
let termSSE = null;
let isRefreshing = false;
let refreshSubscribers = [];
let visualGraph = null;
let visualCanvas = null;

/* ═══════════════════════════════════════════════════════════
   UTILITIES
   ═══════════════════════════════════════════════════════════ */
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

function onTokenFetched(token) {
  refreshSubscribers.forEach(callback => callback(token));
  refreshSubscribers = [];
}

function addRefreshSubscriber(callback) {
  refreshSubscribers.push(callback);
}

async function apiFetch(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (TOKEN) headers['Authorization'] = 'Bearer ' + TOKEN;
  
  let response = await fetch(API_ROOT + path, { ...opts, headers });

  // Handle 401 Unauthorized - Attempt Refresh
  if (response.status === 401 && REFRESH_TOKEN) {
    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const fd = new URLSearchParams();
        fd.append('refresh_token', REFRESH_TOKEN);
        const r = await fetch(API_ROOT + '/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: fd.toString()
        });
        
        if (r.ok) {
          const data = await r.json();
          TOKEN = data.access_token;
          REFRESH_TOKEN = data.refresh_token;
          localStorage.setItem('nexus_token', TOKEN);
          localStorage.setItem('nexus_refresh', REFRESH_TOKEN);
          isRefreshing = false;
          onTokenFetched(TOKEN);
        } else {
          doLogout();
          throw new Error('Refresh failed');
        }
      } catch (err) {
        isRefreshing = false;
        doLogout();
        throw err;
      }
    }

    // Wait for refresh to complete
    const retryToken = await new Promise(resolve => addRefreshSubscriber(resolve));
    headers['Authorization'] = 'Bearer ' + retryToken;
    return fetch(API_ROOT + path, { ...opts, headers });
  }

  return response;
}

function appendTerminal(elId, text, cls = '') {
  const el = $(elId);
  const line = document.createElement('div');
  line.className = cls;
  line.innerHTML = esc(text);
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

function clearTerminal(elId, placeholder = '') {
  const el = $(elId);
  el.innerHTML = placeholder ? `<span class="t-dim">${esc(placeholder)}</span>` : '';
}

function setKPI(id, val) {
  const el = $(id);
  if (el) el.textContent = val;
}

function fmtDate(s) {
  if (!s) return '—';
  try { return new Date(s).toLocaleString(); } catch { return s; }
}

function fmtNum(n) {
  if (n === null || n === undefined) return '—';
  return Number(n).toLocaleString();
}

function fmtMoney(n) {
  if (n === null || n === undefined) return '—';
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/* ═══════════════════════════════════════════════════════════
   AUTH
   ═══════════════════════════════════════════════════════════ */
async function doLogin() {
  const user = $('inp-user').value.trim();
  const pass = $('inp-pass').value;
  $('login-err').textContent = '';
  if (!user || !pass) { $('login-err').textContent = 'Username and password required.'; return; }

  try {
    const fd = new URLSearchParams();
    fd.append('username', user);
    fd.append('password', pass);
    const r = await fetch(API_ROOT + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: fd.toString()
    });
    
    if (r.ok) {
      const data = await r.json();
      TOKEN = data.access_token;
      REFRESH_TOKEN = data.refresh_token;
      localStorage.setItem('nexus_token', TOKEN);
      localStorage.setItem('nexus_refresh', REFRESH_TOKEN);
      
      $('login-overlay').style.display = 'none';
      $('app').style.display = 'flex';
      initApp();
    } else {
      const err = await r.json();
      $('login-err').textContent = err.detail || 'Invalid credentials.';
    }
  } catch (e) {
    $('login-err').textContent = 'Backend unreachable. (Check CORS/URL)';
  }
}

function doLogout() {
  TOKEN = '';
  REFRESH_TOKEN = '';
  localStorage.removeItem('nexus_token');
  localStorage.removeItem('nexus_refresh');
  $('app').style.display = 'none';
  $('login-overlay').style.display = 'flex';
  $('inp-pass').value = '';
}

/* ═══════════════════════════════════════════════════════════
   NAVIGATION
   ═══════════════════════════════════════════════════════════ */
function activateTab(name) {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.tab === name));
  document.querySelectorAll('.tab-pane').forEach(p => {
    const id = p.id.replace('tab-', '');
    p.classList.toggle('active', id === name);
  });
  
  // Close sidebar on mobile after selection
  if (window.innerWidth <= 768) {
    $('sidebar').classList.add('collapsed');
  }

  if (name === 'overview') loadOverview();
  if (name === 'users') loadUsers();
  if (name === 'logs') loadLogs();
  if (name === 'billing') loadBilling();
  if (name === 'swarm') loadSwarmNodes();
  if (name === 'models') loadModelRegistry();
  if (name === 'singularity') loadSingularityStatus();
  if (name === 'judge') { /* no-op */ }
  if (name === 'automator') { /* no-op */ }
  if (name === 'sandbox') { 
    setTimeout(() => { if (monacoEditor) monacoEditor.layout(); }, 50);
    loadWorkspaces(); 
  }
}

/* ═══════════════════════════════════════════════════════════
   FUNCTIONAL TABS
   ═══════════════════════════════════════════════════════════ */

// --- WORKSPACES ---
async function loadWorkspaces() {
  try {
    const r = await apiFetch('/workspaces');
    if (r.ok) {
      const data = await r.json();
      // Logic to update a workspace dropdown if it existed
      console.log("Workspaces loaded:", data);
    }
  } catch {}
}

// --- SETTINGS ---
async function updatePassword() {
  const pass = prompt("Enter new password:");
  if (!pass) return;
  const fd = new URLSearchParams();
  fd.append('password', pass);
  const r = await apiFetch('/user/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: fd.toString()
  });
  if (r.ok) alert("Password updated.");
}
  try {
    const r = await apiFetch('/user/me');
    if (r.ok) {
      const d = await r.json();
      $('credit-val').textContent = fmtNum(d.credits);
      $('badge-admin').style.display = d.is_admin ? 'inline-block' : 'none';
      $('credit-display').style.display = 'inline-block';
    }
  } catch {}
}

// --- OVERVIEW ---
async function loadOverview() {
  try {
    const r = await apiFetch('/admin/stats');
    if (r.ok) {
      const d = await r.json();
      setKPI('ov-users', fmtNum(d.total_users));
      setKPI('ov-mrr', fmtMoney(d.arr_estimate / 12));
      setKPI('ov-arr', fmtMoney(d.arr_estimate));
      setKPI('ov-api-cost', fmtMoney(d.total_spend_usd));
      setKPI('ov-requests', fmtNum(d.recent_logs?.length || 0));

      // Plan table
      $('ov-plan-tbl').innerHTML = d.plan_breakdown.map(p => 
        `<tr><td><span class="badge badge-${p.plan.toLowerCase()}">${p.plan}</span></td>
        <td>${fmtNum(p.users)}</td><td>${fmtMoney(p.mrr)}</td>
        <td>—</td></tr>`
      ).join('');

      // Model usage table
      $('ov-model-tbl').innerHTML = d.models.map(m =>
        `<tr><td style="color:var(--neon)">${esc(m.model)}</td>
        <td>${fmtNum(m.count)}</td><td>—</td>
        <td>${fmtMoney(m.cost_usd)}</td></tr>`
      ).join('');
    }
  } catch {}
}

// --- USERS ---
async function loadUsers() {
  try {
    const r = await apiFetch('/admin/users');
    if (r.ok) {
      const users = await r.json();
      $('users-tbl').innerHTML = users.map(u => `
        <tr>
          <td>${u.id}</td>
          <td style="color:var(--neon)">${esc(u.username)}</td>
          <td>—</td>
          <td><span class="badge badge-${u.plan.toLowerCase()}">${u.plan}</span></td>
          <td style="color:var(--amber)">${fmtNum(u.credits)}</td>
          <td>${fmtDate(u.expires)}</td>
          <td>
            <button class="btn btn-neon btn-sm" onclick="grantCredits(${u.id})">+CR</button>
          </td>
        </tr>`).join('');
    }
  } catch {}
}

async function grantCredits(uid) {
  const amt = prompt("Amount of credits to grant:");
  if (!amt) return;
  const r = await apiFetch(`/admin/users/${uid}/grant?amount=${amt}`, { method: 'POST' });
  if (r.ok) loadUsers();
}

// --- LOGS ---
async function loadLogs() {
  try {
    const r = await apiFetch('/admin/stats'); // current backend returns recent logs here
    if (r.ok) {
      const d = await r.json();
      $('logs-tbl').innerHTML = d.recent_logs.map(l => `
        <tr>
          <td><button onclick="toggleStar(${l.id})">☆</button></td>
          <td>${l.id}</td>
          <td>—</td>
          <td style="color:var(--neon)">${esc(l.model)}</td>
          <td>—</td>
          <td style="color:var(--amber)">${fmtMoney(l.cost_usd)}</td>
          <td>${fmtDate(l.time)}</td>
          <td style="color:${l.status==='ok'?'var(--neon)':'var(--red)'}">${l.status}</td>
        </tr>`).join('');
    }
  } catch {}
}

async function toggleStar(id) {
  await apiFetch(`/admin/star/${id}`, { method: 'POST' });
  loadLogs();
}

// --- BILLING ---
async function loadBilling() {
  try {
    const [rp, rk] = await Promise.all([apiFetch('/billing/plans'), apiFetch('/billing/packs')]);
    if (rp.ok) {
      const plans = await rp.json();
      $('billing-plans-tbl').innerHTML = Object.entries(plans).map(([name, p]) => `
        <tr>
          <td><span class="badge badge-${name.toLowerCase()}">${name}</span></td>
          <td>${fmtMoney(p.price)}</td>
          <td>${fmtNum(p.credits)}</td>
          <td>${p.models.join(', ')}</td>
        </tr>`).join('');
    }
  } catch {}
}

// --- MAGIC AUTOMATOR ---
const MAGIC_STEPS = {
  architect: "Architecting Tech Stack...",
  devops: "Configuring Cloud Infrastructure...",
  planner: "Decomposing Goals...",
  hive: "Multi-Model Hive Consensus...",
  coder: "Generating Source Code...",
};

$('btn-magic-build').onclick = async () => {
  const promptText = $('magic-prompt').value.trim();
  if (!promptText) return alert("Please enter a build prompt.");

  // UI Setup
  $('magic-progress-wrap').style.display = 'block';
  $('magic-steps').innerHTML = '';
  clearTerminal('magic-terminal', 'Establishing Nexus uplink...');
  $('magic-status-text').textContent = "AUTONOMOUS BUILD IN PROGRESS";
  
  const stepEls = {};
  Object.keys(MAGIC_STEPS).forEach(key => {
    const div = document.createElement('div');
    div.className = 'flex-row';
    div.innerHTML = `<span class="dot dot-amber"></span><span style="color:var(--text2)">${MAGIC_STEPS[key]}</span>`;
    $('magic-steps').appendChild(div);
    stepEls[key] = div;
  });

  const url = `${API_ROOT}/nexus/app-build?task=${encodeURIComponent(promptText)}&token=${encodeURIComponent(TOKEN)}`;
  const es = new EventSource(url);

  es.onmessage = (e) => {
    const d = JSON.parse(e.data);
    
    if (d.type === 'agent_start') {
      const el = stepEls[d.agent];
      if (el) {
        el.querySelector('.dot').className = 'dot dot-green';
        el.style.color = 'var(--neon)';
      }
      appendTerminal('magic-terminal', `[${d.agent.toUpperCase()}] Initiated.`, 't-info');
    } else if (d.type === 'log') {
      appendTerminal('magic-terminal', d.message, 't-ok');
    } else if (d.type === 'complete') {
      es.close();
      $('magic-status-text').textContent = "BUILD SUCCESSFUL";
      appendTerminal('magic-terminal', "✅ Full-stack project generated successfully!", 't-ok');
      
      if ($('magic-deploy').checked) {
        triggerAutoDeployFromMagic();
      }
    } else if (d.type === 'error') {
      es.close();
      $('magic-status-text').textContent = "BUILD FAILED";
      $('magic-status-text').style.color = 'var(--red)';
      appendTerminal('magic-terminal', `❌ ERROR: ${d.message}`, 't-err');
    }
  };

  es.onerror = () => {
    es.close();
    appendTerminal('magic-terminal', "⚠ Connection lost. Build may still be running on server.", 't-warn');
  };
};

async function triggerAutoDeployFromMagic() {
  appendTerminal('magic-terminal', "🚀 Initiating Auto-Deploy to Cloud...", 't-info');
  const r = await apiFetch('/autodeploy/trigger', { method: 'POST' });
  if (r.ok) {
    const d = await r.json();
    d.logs.forEach(l => appendTerminal('magic-terminal', l, 't-ok'));
    appendTerminal('magic-terminal', "✅ Deployment pipeline triggered.", 't-ok');
  } else {
    appendTerminal('magic-terminal', "❌ Deployment failed.", 't-err');
  }
}

// --- JUDGE ---
$('btn-run-judge').onclick = async () => {
  const prompt = $('judge-prompt').value;
  const res_a = $('judge-res-a').value;
  const res_b = $('judge-res-b').value;
  if (!prompt || !res_a || !res_b) return alert("Fill all judge fields.");
  
  clearTerminal('judge-output', 'Judging in progress...');
  const r = await apiFetch('/judge', {
    method: 'POST',
    body: JSON.stringify({ prompt, res_a, res_b })
  });
  if (r.ok) {
    const verdict = await r.json();
    clearTerminal('judge-output');
    appendTerminal('judge-output', `WINNER: ${verdict.winner}`, 't-ok');
    appendTerminal('judge-output', `Score A: ${verdict.score_a} | Score B: ${verdict.score_b}`, 't-info');
    appendTerminal('judge-output', `Reasoning: ${verdict.reasoning}`, 't-dim');
  } else {
    appendTerminal('judge-output', 'Error running judge.', 't-err');
  }
};

// --- SWARM ---
async function loadSwarmNodes() {
  try {
    const r = await apiFetch('/swarm/nodes');
    if (r.ok) {
      const nodes = await r.json();
      $('swarm-node-grid').innerHTML = nodes.map(n => `
        <div class="node-card ${n.status==='active'?'active':''}">
          <div style="color:var(--cyan)">${esc(n.id)}</div>
          <div>${esc(n.role)}</div>
          <div class="dot ${n.status==='active'?'dot-green':'dot-amber'}"></div>${n.status}
        </div>`).join('');
    }
  } catch {}
}

$('btn-swarm-activate').addEventListener('click', () => {
  const goal = $('swarm-goal').value;
  const num = $('swarm-nodes').value;
  clearTerminal('swarm-log');
  appendTerminal('swarm-log', `Activating swarm: ${goal}`, 't-info');
  const url = `${API_ROOT}/swarm/stream?goal=${encodeURIComponent(goal)}&num_nodes=${num}&token=${encodeURIComponent(TOKEN)}`;
  swarmSSE = new EventSource(url);
  swarmSSE.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.type === 'log') appendTerminal('swarm-log', d.message, 't-ok');
    if (d.type === 'consensus') appendTerminal('swarm-consensus', d.message, 't-info');
  };
});

// --- MODELS ---
async function loadModelRegistry() {
  try {
    const r = await apiFetch('/models/registry');
    if (r.ok) {
      const data = await r.json();
      $('models-registry-tbl').innerHTML = Object.entries(data.models || {}).map(([id, m]) => `
        <tr>
          <td>${esc(m.provider)}</td>
          <td style="color:var(--neon)">${esc(id)}</td>
          <td>${m.context_window}</td>
          <td>—</td><td>—</td>
          <td><span class="dot dot-green"></span>ACTIVE</td>
        </tr>`).join('');
    }
  } catch {}
}

$('btn-scan-models').addEventListener('click', async () => {
  appendTerminal('models-disc-log', 'Scanning providers...', 't-info');
  const r = await apiFetch('/models/discover', { method: 'POST' });
  if (r.ok) {
    const d = await r.json();
    d.logs.forEach(l => appendTerminal('models-disc-log', l, 't-ok'));
    loadModelRegistry();
  }
});

// --- DEPLOY ---
$('btn-deploy-trigger').addEventListener('click', async () => {
  $('deploy-status-badge').innerHTML = '<span class="spin">⚙</span> DEPLOYING';
  const r = await apiFetch('/autodeploy/trigger', { method: 'POST' });
  if (r.ok) {
    const d = await r.json();
    d.logs.forEach(l => appendTerminal('deploy-log', l, 't-ok'));
  }
});

// --- SINGULARITY ---
async function loadSingularityStatus() {
  try {
    const r = await apiFetch('/singularity/status');
    if (r.ok) {
      const d = await r.json();
      setKPI('sing-error-rate', (d.error_rate * 100).toFixed(2) + '%');
      setKPI('sing-evo-count', d.evolution_count);
      setKPI('sing-status-kpi', d.status);
    }
  } catch {}
}

$('btn-sing-evolve').addEventListener('click', async () => {
  appendTerminal('sing-log', 'Initiating evolution...', 't-info');
  const r = await apiFetch('/singularity/evolve', { method: 'POST' });
  if (r.ok) {
    const d = await r.json();
    d.log.forEach(l => appendTerminal('sing-log', l, 't-ok'));
    loadSingularityStatus();
  }
});

// --- TERMINAL ---
$('btn-term-run').addEventListener('click', () => {
  const task = $('term-task').value;
  clearTerminal('term-output');
  $('term-status').textContent = 'STREAMING';
  const url = `${API_ROOT}/nexus/app-build?task=${encodeURIComponent(task)}&token=${encodeURIComponent(TOKEN)}`;
  termSSE = new EventSource(url);
  termSSE.onmessage = e => {
    const d = JSON.parse(e.data);
    appendTerminal('term-output', d.message || d.agent || '', d.type==='error'?'t-err':'t-ok');
    if (d.type === 'complete') termSSE.close();
  };
});

// --- SANDBOX ---
function initVisualEditor() {
  if (visualGraph) return;
  visualGraph = new LiteGraph.LGraph();
  visualCanvas = new LiteGraph.LGraphCanvas("#visual-canvas", visualGraph);
  
  // Custom LLM Node
  function LLMNode() {
    this.addInput("prompt", "string");
    this.addOutput("response", "string");
    this.properties = { provider: "groq", model: "llama-3.3-70b-versatile" };
  }
  LLMNode.title = "LLM Engine";
  LiteGraph.registerNodeType("nexus/llm", LLMNode);

  // Researcher Node
  function ResearcherNode() {
    this.addInput("query", "string");
    this.addOutput("findings", "string");
  }
  ResearcherNode.title = "Researcher Agent";
  LiteGraph.registerNodeType("nexus/researcher", ResearcherNode);

  // Coder Node
  function CoderNode() {
    this.addInput("task", "string");
    this.addOutput("code", "string");
  }
  CoderNode.title = "Coder Agent";
  LiteGraph.registerNodeType("nexus/coder", CoderNode);

  // Reviewer Node
  function ReviewerNode() {
    this.addInput("code", "string");
    this.addOutput("audit", "string");
  }
  ReviewerNode.title = "Reviewer Agent";
  LiteGraph.registerNodeType("nexus/reviewer", ReviewerNode);

  visualGraph.start();
}

$('btn-visual-run').onclick = async () => {
  const data = visualGraph.serialize();
  const nodes = data.nodes.map(n => ({
    id: n.id,
    type: n.type.split('/')[1], // nexus/llm -> llm
    provider: n.properties?.provider || 'groq',
    model: n.properties?.model || 'llama-3.3-70b-versatile'
  }));
  
  const input = prompt("Enter initial input for graph:");
  if (!input) return;
  
  clearTerminal('sb-console', 'Executing graph...');
  const r = await apiFetch('/orchestrator/run', {
    method: 'POST',
    body: JSON.stringify({ chain: nodes, input })
  });
  
  if (r.ok) {
    const res = await r.json();
    clearTerminal('sb-console');
    res.results.forEach(step => {
      appendTerminal('sb-console', `[NODE: ${step.node_id}] (${step.type})`, 't-info');
      appendTerminal('sb-console', step.output || step.error, step.error ? 't-err' : 't-ok');
    });
  } else {
    appendTerminal('sb-console', 'Graph execution failed.', 't-err');
  }
};

$('sb-visual-toggle').addEventListener('change', e => {
  const visual = e.target.checked;
  $('editor-wrap').style.display = visual ? 'none' : 'block';
  $('visual-editor-wrap').style.display = visual ? 'flex' : 'none';
  if (visual) initVisualEditor();
});

function initMonaco() {
  if (monacoEditor) return;
  require(['vs/editor/editor.main'], function () {
    monacoEditor = monaco.editor.create($('editor-wrap'), {
      value: '// Project Nexus v9.0\nconst res = await ai.chat.complete({ messages: [{role:"user", content:"Hi!"}] });\nconsole.log(res);',
      language: 'javascript', theme: 'vs-dark', automaticLayout: true
    });
  });
}

const ai = {
  chat: {
    complete: async (opts) => {
      const r = await apiFetch('/chat/completions', {
        method: 'POST',
        body: JSON.stringify({
          provider: $('sb-provider').value,
          model: $('sb-model').value,
          ...opts
        })
      });
      return r.json();
    }
  }
};

$('btn-sb-run').addEventListener('click', async () => {
  const code = monacoEditor.getValue();
  clearTerminal('sb-console');
  try {
    const fn = new Function('ai', 'console', `(async () => { ${code} })()`);
    await fn(ai, { log: (m) => appendTerminal('sb-console', JSON.stringify(m, null, 2), 't-ok') });
  } catch (e) { appendTerminal('sb-console', e.message, 't-err'); }
});

/* ═══════════════════════════════════════════════════════════
   INIT
   ═══════════════════════════════════════════════════════════ */
function initApp() {
  loadMe();
  initMonaco();
  activateTab('automator');
}

$('btn-login').onclick = doLogin;
$('btn-logout').onclick = doLogout;
$('menu-toggle').onclick = () => $('sidebar').classList.toggle('collapsed');

document.querySelectorAll('.nav-item').forEach(i => i.onclick = () => activateTab(i.dataset.tab));

if (TOKEN) {
  $('login-overlay').style.display = 'none';
  $('app').style.display = 'flex';
  initApp();
}
