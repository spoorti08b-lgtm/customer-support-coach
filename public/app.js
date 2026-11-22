/**
 * Customer Simulator Agent - Client Web App
 */

let state = {
  sessionId: null,
  personas: [],
  scenarios: [],
  selectedPersona: null,
  selectedScenario: null,
  currentState: null,
  trajectory: [],
  revealedContext: [],
  provider: 'local',
  apiKey: localStorage.getItem('csa_api_key') || '',
  model: localStorage.getItem('csa_model') || ''
};

// DOM Elements
const personaSelect = document.getElementById('personaSelect');
const scenarioSelect = document.getElementById('scenarioSelect');
const messagesContainer = document.getElementById('messagesContainer');
const agentInput = document.getElementById('agentInput');
const btnSend = document.getElementById('btnSend');
const btnNewSession = document.getElementById('btnNewSession');
const btnEvaluate = document.getElementById('btnEvaluate');
const btnSettings = document.getElementById('btnSettings');
const btnExport = document.getElementById('btnExport');
const btnEditPersona = document.getElementById('btnEditPersona');

// Modals
const evalModal = document.getElementById('evalModal');
const settingsModal = document.getElementById('settingsModal');
const personaModal = document.getElementById('personaModal');

// Init application
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await loadCatalog();
  await startNewSession();
});

function setupEventListeners() {
  personaSelect.addEventListener('change', (e) => {
    const p = state.personas.find(item => item.id === e.target.value);
    if (p) {
      state.selectedPersona = p;
      updatePersonaPreview(p);
      startNewSession();
    }
  });

  scenarioSelect.addEventListener('change', (e) => {
    const s = state.scenarios.find(item => item.id === e.target.value);
    if (s) {
      state.selectedScenario = s;
      updateScenarioPreview(s);
      startNewSession();
    }
  });

  btnSend.addEventListener('click', handleSendMessage);
  agentInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  btnNewSession.addEventListener('click', () => startNewSession());
  btnEvaluate.addEventListener('click', showScorecard);

  // Quick Chips
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      agentInput.value = chip.getAttribute('data-prompt');
      agentInput.focus();
    });
  });

  // Modal Closures
  document.getElementById('btnCloseEval').addEventListener('click', () => evalModal.classList.remove('open'));
  document.getElementById('btnDoneEval').addEventListener('click', () => evalModal.classList.remove('open'));
  document.getElementById('btnCloseSettings').addEventListener('click', () => settingsModal.classList.remove('open'));
  document.getElementById('btnClosePersonaModal').addEventListener('click', () => personaModal.classList.remove('open'));

  // Open Settings
  btnSettings.addEventListener('click', () => {
    document.getElementById('settingProvider').value = state.provider;
    document.getElementById('settingApiKey').value = state.apiKey;
    document.getElementById('settingModel').value = state.model;
    settingsModal.classList.add('open');
  });

  document.getElementById('btnSaveSettings').addEventListener('click', () => {
    state.provider = document.getElementById('settingProvider').value;
    state.apiKey = document.getElementById('settingApiKey').value.trim();
    state.model = document.getElementById('settingModel').value.trim();

    localStorage.setItem('csa_api_key', state.apiKey);
    localStorage.setItem('csa_model', state.model);

    updateProviderBadge();
    settingsModal.classList.remove('open');
    startNewSession();
  });

  // Export Transcript
  btnExport.addEventListener('click', exportTranscript);
  document.getElementById('btnExportEval').addEventListener('click', exportTranscript);

  // Custom Persona Sliders
  btnEditPersona.addEventListener('click', () => {
    if (state.selectedPersona) {
      document.getElementById('customName').value = state.selectedPersona.name;
      document.getElementById('customRole').value = state.selectedPersona.role;
      document.getElementById('rngPatience').value = state.selectedPersona.traits.patience;
      document.getElementById('rngSens').value = state.selectedPersona.traits.emotionalSensitivity;
      document.getElementById('rngSkep').value = state.selectedPersona.traits.skepticism;
      document.getElementById('customVerbosity').value = state.selectedPersona.traits.verbosity;

      document.getElementById('lblCustomPatience').innerText = state.selectedPersona.traits.patience;
      document.getElementById('lblCustomSens').innerText = state.selectedPersona.traits.emotionalSensitivity;
      document.getElementById('lblCustomSkep').innerText = state.selectedPersona.traits.skepticism;
    }
    personaModal.classList.add('open');
  });

  ['Patience', 'Sens', 'Skep'].forEach(key => {
    const rng = document.getElementById(`rng${key}`);
    const lbl = document.getElementById(`lblCustom${key}`);
    rng.addEventListener('input', () => lbl.innerText = rng.value);
  });

  document.getElementById('btnApplyCustomPersona').addEventListener('click', () => {
    const custom = {
      id: 'custom_' + Date.now(),
      name: document.getElementById('customName').value,
      role: document.getElementById('customRole').value,
      avatar: '🎭',
      description: 'Custom adjusted persona',
      traits: {
        patience: parseInt(document.getElementById('rngPatience').value),
        emotionalSensitivity: parseInt(document.getElementById('rngSens').value),
        skepticism: parseInt(document.getElementById('rngSkep').value),
        techLiteracy: 6,
        assertiveness: 7,
        verbosity: document.getElementById('customVerbosity').value
      },
      communicationStyle: {
        formality: 'casual',
        punctuationStyle: 'normal',
        allCapsWhenAngry: true,
        fillerWords: ['Look,', 'Actually,'],
        petPeeves: ['Unhelpful answers']
      },
      baselineEmotion: {
        frustration: 40,
        satisfaction: 20,
        trust: 40,
        arousal: 50,
        primary: 'impatient'
      }
    };

    state.selectedPersona = custom;
    updatePersonaPreview(custom);
    personaModal.classList.remove('open');
    startNewSession();
  });
}

async function loadCatalog() {
  try {
    const [pRes, sRes] = await Promise.all([
      fetch('/api/personas').then(r => r.json()),
      fetch('/api/scenarios').then(r => r.json())
    ]);

    state.personas = pRes.personas || [];
    state.scenarios = sRes.scenarios || [];

    // Populate Persona dropdown
    personaSelect.innerHTML = '';
    state.personas.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.avatar} ${p.name} (${p.role})`;
      personaSelect.appendChild(opt);
    });
    state.selectedPersona = state.personas[0];

    // Populate Scenario dropdown
    scenarioSelect.innerHTML = '';
    state.scenarios.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = `${s.title} [${s.domain}]`;
      scenarioSelect.appendChild(opt);
    });
    state.selectedScenario = state.scenarios[0];

    updatePersonaPreview(state.selectedPersona);
    updateScenarioPreview(state.selectedScenario);
  } catch (err) {
    console.error('Failed to load personas/scenarios:', err);
  }
}

function updatePersonaPreview(p) {
  if (!p) return;
  document.getElementById('pAvatar').innerText = p.avatar || '👤';
  document.getElementById('pName').innerText = p.name;
  document.getElementById('pRole').innerText = p.role;
  document.getElementById('pDesc').innerText = p.description;

  const t = p.traits || {};
  document.getElementById('traitPatience').style.width = `${(t.patience || 5) * 10}%`;
  document.getElementById('valPatience').innerText = `${t.patience || 5}/10`;

  document.getElementById('traitSensitivity').style.width = `${(t.emotionalSensitivity || 5) * 10}%`;
  document.getElementById('valSensitivity').innerText = `${t.emotionalSensitivity || 5}/10`;

  document.getElementById('traitSkepticism').style.width = `${(t.skepticism || 5) * 10}%`;
  document.getElementById('valSkepticism').innerText = `${t.skepticism || 5}/10`;

  document.getElementById('traitTech').style.width = `${(t.techLiteracy || 5) * 10}%`;
  document.getElementById('valTech').innerText = `${t.techLiteracy || 5}/10`;
}

function updateScenarioPreview(s) {
  if (!s) return;
  document.getElementById('sDomain').innerText = s.domain || 'Support';
  document.getElementById('sDifficulty').innerText = s.difficulty || 'Normal';
  document.getElementById('sDesc').innerText = s.description;
  document.getElementById('sGoal').innerText = s.goals?.primary || 'Issue resolution';
}

function updateProviderBadge() {
  const lbl = document.getElementById('providerLabel');
  if (state.provider === 'gemini') {
    lbl.innerText = `Engine: Gemini (${state.model || '2.5-flash'})`;
  } else if (state.provider === 'openai') {
    lbl.innerText = `Engine: OpenAI (${state.model || 'gpt-4o-mini'})`;
  } else {
    lbl.innerText = 'Engine: Local Heuristic (Offline)';
  }
}

async function startNewSession() {
  try {
    messagesContainer.innerHTML = '';
    agentInput.value = '';
    agentInput.disabled = false;
    btnSend.disabled = false;

    const res = await fetch('/api/simulator/init', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        persona: state.selectedPersona,
        scenario: state.selectedScenario,
        provider: state.provider,
        apiKey: state.apiKey,
        model: state.model
      })
    }).then(r => r.json());

    if (!res.success) throw new Error(res.error);

    state.sessionId = res.sessionId;
    state.currentState = res.initialState.currentState;
    state.trajectory = res.initialState.trajectory || [];
    state.revealedContext = res.initialState.revealedContext || [];

    updateProviderBadge();
    updateAffectiveDashboard(state.currentState);
    updateDisclosureList(state.selectedScenario, state.revealedContext);
    renderChart(state.trajectory);

    // Render initial customer opening message
    const initialMsg = res.initialState.history?.[0];
    if (initialMsg) {
      appendMessageBubble('customer', initialMsg.text, state.selectedPersona, initialMsg.emotionalState, initialMsg.internalMonologue);
      document.getElementById('latestMonologue').innerText = `"${initialMsg.internalMonologue}"`;
    }

    document.getElementById('sessionStatusBadge').innerText = 'Active';
    document.getElementById('sessionStatusBadge').style.background = 'rgba(16, 185, 129, 0.2)';
    document.getElementById('sessionStatusBadge').style.color = '#6ee7b7';
    document.getElementById('turnDisplay').innerText = `Turn 1`;
  } catch (err) {
    console.error('Failed to initialize session:', err);
    alert('Error starting simulation: ' + err.message);
  }
}

async function handleSendMessage() {
  const text = agentInput.value.trim();
  if (!text || !state.sessionId) return;

  // Append Agent Message
  appendMessageBubble('agent', text, { name: 'Support Agent', avatar: '🎧' });
  agentInput.value = '';
  agentInput.disabled = true;
  btnSend.disabled = true;

  // Show typing indicator
  const typingId = showTypingIndicator();

  try {
    const res = await fetch('/api/simulator/turn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionId: state.sessionId,
        agentMessage: text
      })
    }).then(r => r.json());

    removeTypingIndicator(typingId);

    if (!res.success) throw new Error(res.error);

    state.currentState = res.emotionalState;
    state.trajectory = res.trajectory;
    if (res.newlyDisclosed) {
      state.revealedContext.push(...res.newlyDisclosed.map(d => d.key));
    }

    // Append Customer Response
    appendMessageBubble('customer', res.customerMessage, state.selectedPersona, res.emotionalState, res.internalMonologue);
    document.getElementById('latestMonologue').innerText = `"${res.internalMonologue}"`;

    // Update UI
    updateAffectiveDashboard(res.emotionalState);
    updateDisclosureList(state.selectedScenario, state.revealedContext);
    renderChart(res.trajectory);
    document.getElementById('turnDisplay').innerText = `Turn ${res.turnIndex + 1}`;

    // Handle session resolution or rage quit
    if (res.status === 'resolved' || res.status === 'rage_quit' || res.status === 'escalated') {
      agentInput.disabled = true;
      btnSend.disabled = true;
      
      const badge = document.getElementById('sessionStatusBadge');
      badge.innerText = res.status.toUpperCase();
      if (res.status === 'resolved') {
        badge.style.background = 'rgba(16, 185, 129, 0.3)';
        badge.style.color = '#6ee7b7';
      } else if (res.status === 'rage_quit') {
        badge.style.background = 'rgba(244, 63, 94, 0.3)';
        badge.style.color = '#fda4af';
      }

      // Prompt to view scorecard
      setTimeout(() => {
        showScorecard();
      }, 1200);
    } else {
      agentInput.disabled = false;
      btnSend.disabled = false;
      agentInput.focus();
    }
  } catch (err) {
    removeTypingIndicator(typingId);
    agentInput.disabled = false;
    btnSend.disabled = false;
    console.error('Error during turn:', err);
    alert('Turn Error: ' + err.message);
  }
}

function appendMessageBubble(speaker, text, entity, emotionalState = null, monologue = null) {
  const row = document.createElement('div');
  row.className = `message-row ${speaker}`;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.innerText = entity.avatar || (speaker === 'agent' ? '🎧' : '👤');

  const body = document.createElement('div');
  body.className = 'message-body';

  const meta = document.createElement('div');
  meta.className = 'message-meta';
  meta.innerHTML = `<span>${entity.name}</span> • <span>${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>`;

  if (speaker === 'customer' && emotionalState) {
    const emoTag = document.createElement('span');
    emoTag.className = `emotion-tag ${emotionalState.primary || 'neutral'}`;
    emoTag.innerText = emotionalState.primary || 'Neutral';
    meta.appendChild(emoTag);
  }

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.innerText = text;

  body.appendChild(meta);
  body.appendChild(bubble);

  if (speaker === 'customer' && monologue) {
    const thoughts = document.createElement('div');
    thoughts.className = 'inner-thoughts';
    thoughts.innerHTML = `<span class="inner-thoughts-label">💭 Inner Thoughts:</span> <span>${escapeHtml(monologue)}</span>`;
    body.appendChild(thoughts);
  }

  row.appendChild(avatar);
  row.appendChild(body);

  messagesContainer.appendChild(row);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showTypingIndicator() {
  const id = 'typing_' + Date.now();
  const row = document.createElement('div');
  row.id = id;
  row.className = 'message-row customer';
  row.innerHTML = `
    <div class="message-avatar">${state.selectedPersona?.avatar || '👤'}</div>
    <div class="message-body">
      <div class="message-bubble" style="color: var(--text-muted); font-style: italic;">
        Customer is formulating thoughts...
      </div>
    </div>
  `;
  messagesContainer.appendChild(row);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
  return id;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function updateAffectiveDashboard(s) {
  if (!s) return;

  // Frustration
  document.getElementById('metricFrustration').innerText = `${s.frustration}%`;
  document.getElementById('fillFrustration').style.width = `${s.frustration}%`;
  const fDelta = s.deltas?.frustration || 0;
  document.getElementById('deltaFrustration').innerText = fDelta ? (fDelta > 0 ? `+${fDelta}% 🔺` : `${fDelta}% 🔻`) : '0%';

  // Trust
  document.getElementById('metricTrust').innerText = `${s.trust}%`;
  document.getElementById('fillTrust').style.width = `${s.trust}%`;
  const tDelta = s.deltas?.trust || 0;
  document.getElementById('deltaTrust').innerText = tDelta ? (tDelta > 0 ? `+${tDelta}% 🔺` : `${tDelta}% 🔻`) : '0%';

  // Satisfaction
  document.getElementById('metricSatisfaction').innerText = `${s.satisfaction}%`;
  document.getElementById('fillSatisfaction').style.width = `${s.satisfaction}%`;
  const sDelta = s.deltas?.satisfaction || 0;
  document.getElementById('deltaSatisfaction').innerText = sDelta ? (sDelta > 0 ? `+${sDelta}% 🔺` : `${sDelta}% 🔻`) : '0%';

  // Emotion card
  const emotionName = (s.primary || 'NEUTRAL').toUpperCase();
  document.getElementById('currentEmotionName').innerText = emotionName;
  document.getElementById('urgencyPill').innerText = `Arousal: ${s.arousal || 50}%`;

  const emojis = {
    impatient: '⚡', frustrated: '😠', infuriated: '🔥', enraged: '🤬',
    sarcastic: '😏', anxious: '😰', hopeful: '🌸', relieved: '😌',
    delighted: '🎉', satisfied: '😊', cooperative: '🤝', suspicious: '🤨',
    neutral: '😐', pragmatic: '⚖️'
  };
  document.getElementById('currentEmotionEmoji').innerText = emojis[s.primary] || '👤';

  // Triggers cloud
  const triggersContainer = document.getElementById('triggersCloud');
  triggersContainer.innerHTML = '';
  const triggers = s.triggersDetected || [];
  if (triggers.length === 0) {
    triggersContainer.innerHTML = '<span class="tag-trigger neutral">No specific triggers</span>';
  } else {
    triggers.forEach(tr => {
      const tag = document.createElement('span');
      const isPositive = ['empathy', 'resolution_offer', 'constructive_step'].includes(tr);
      const isNegative = ['policy_shield', 'robotic_or_dismissive', 'unacceptable_offer', 'unacceptable_delay', 'repeated_order_query', 'repeated_email_query'].includes(tr);
      tag.className = `tag-trigger ${isPositive ? 'positive' : isNegative ? 'negative' : 'neutral'}`;
      tag.innerText = tr.replace(/_/g, ' ');
      triggersContainer.appendChild(tag);
    });
  }
}

function updateDisclosureList(scenario, revealed = []) {
  const container = document.getElementById('disclosureList');
  if (!container || !scenario?.context) return;

  container.innerHTML = '';
  for (const [key, val] of Object.entries(scenario.context)) {
    const isDisclosed = revealed.includes(key);
    const li = document.createElement('li');
    li.className = isDisclosed ? 'disclosed' : 'withheld';
    li.innerHTML = isDisclosed
      ? `✓ <strong>${key}</strong>: ${escapeHtml(String(val))} <small>(Revealed)</small>`
      : `🔒 <strong>${key}</strong> <small>(Withheld until asked)</small>`;
    container.appendChild(li);
  }
}

/**
 * Render Interactive SVG Multi-Line Trajectory Chart
 */
function renderChart(trajectory = []) {
  const svg = document.getElementById('trajectoryChart');
  if (!svg || trajectory.length === 0) return;

  const width = 340;
  const height = 140;
  const pad = { top: 15, right: 15, bottom: 25, left: 30 };

  const turns = trajectory.length;
  const xStep = turns > 1 ? (width - pad.left - pad.right) / (turns - 1) : 0;

  const getY = (val) => height - pad.bottom - ((val / 100) * (height - pad.top - pad.bottom));
  const getX = (idx) => pad.left + (idx * xStep);

  // Build Paths for Frustration, Trust, Satisfaction
  const buildPath = (prop) => {
    return trajectory.map((point, idx) => {
      const x = getX(idx);
      const y = getY(point[prop] || 0);
      return `${idx === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    }).join(' ');
  };

  const fPath = buildPath('frustration');
  const tPath = buildPath('trust');
  const sPath = buildPath('satisfaction');

  // Build gridlines
  let gridSvg = `
    <line x1="${pad.left}" y1="${getY(0)}" x2="${width - pad.right}" y2="${getY(0)}" stroke="#2b3648" stroke-width="1"/>
    <line x1="${pad.left}" y1="${getY(50)}" x2="${width - pad.right}" y2="${getY(50)}" stroke="#2b3648" stroke-width="1" stroke-dasharray="3 3"/>
    <line x1="${pad.left}" y1="${getY(100)}" x2="${width - pad.right}" y2="${getY(100)}" stroke="#2b3648" stroke-width="1"/>
    <text x="5" y="${getY(100) + 4}" fill="#64748b" font-size="9">100%</text>
    <text x="5" y="${getY(50) + 4}" fill="#64748b" font-size="9">50%</text>
    <text x="5" y="${getY(0) + 4}" fill="#64748b" font-size="9">0%</text>
  `;

  // Draw points
  let pointsSvg = '';
  trajectory.forEach((pt, idx) => {
    const x = getX(idx);
    pointsSvg += `
      <circle cx="${x}" cy="${getY(pt.frustration)}" r="3" fill="#f43f5e" />
      <circle cx="${x}" cy="${getY(pt.trust)}" r="3" fill="#10b981" />
      <circle cx="${x}" cy="${getY(pt.satisfaction)}" r="3" fill="#6366f1" />
      <text x="${x}" y="${height - 8}" fill="#64748b" font-size="9" text-anchor="middle">T${idx}</text>
    `;
  });

  svg.innerHTML = `
    ${gridSvg}
    <path d="${fPath}" fill="none" stroke="#f43f5e" stroke-width="2.5" stroke-linecap="round" />
    <path d="${tPath}" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" />
    <path d="${sPath}" fill="none" stroke="#6366f1" stroke-width="2" stroke-linecap="round" />
    ${pointsSvg}
  `;
}

async function showScorecard() {
  if (!state.sessionId) return;

  try {
    const res = await fetch('/api/simulator/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId: state.sessionId })
    }).then(r => r.json());

    if (!res.success) throw new Error(res.error);

    const evalData = res.evaluation;
    const body = document.getElementById('evalModalBody');

    const stars = '★'.repeat(Math.round(evalData.csat)) + '☆'.repeat(5 - Math.round(evalData.csat));

    body.innerHTML = `
      <div class="scorecard-header">
        <div>
          <span class="text-xs text-muted">PREDICTED CSAT SCORE</span>
          <div class="csat-display">
            <span class="csat-number">${evalData.csat}</span>
            <span class="csat-stars">${stars}</span>
          </div>
        </div>
        <div>
          <span class="tag ${evalData.isResolved ? 'domain-tag' : 'diff-tag'}" style="font-size: 13px; padding: 6px 14px;">
            ${evalData.isResolved ? '✓ Resolution Achieved' : '⚠ Issue Unresolved'}
          </span>
        </div>
      </div>

      <div class="scorecard-stats">
        <div class="stat-box">
          <div class="stat-box-label">Empathy Index</div>
          <div class="stat-box-val" style="color: #6ee7b7;">${evalData.empathyIndex}%</div>
        </div>
        <div class="stat-box">
          <div class="stat-box-label">De-escalation Shift</div>
          <div class="stat-box-val" style="color: ${evalData.deEscalationSuccessful ? '#6ee7b7' : '#fcd34d'};">
            ${evalData.deEscalationDelta > 0 ? `-${evalData.deEscalationDelta}% Frustration` : 'No De-escalation'}
          </div>
        </div>
        <div class="stat-box">
          <div class="stat-box-label">Initial Frustration</div>
          <div class="stat-box-val">${evalData.initialFrustration}% ➡️ ${evalData.finalFrustration}% (Peak ${evalData.peakFrustration}%)</div>
        </div>
        <div class="stat-box">
          <div class="stat-box-label">Total Conversation Turns</div>
          <div class="stat-box-val">${evalData.totalTurns} turns</div>
        </div>
      </div>

      ${evalData.coaching.strengths.length > 0 ? `
        <div class="feedback-box">
          <h4 style="color: #6ee7b7;">✓ Key Agent Strengths:</h4>
          <ul>
            ${evalData.coaching.strengths.map(s => `<li>${escapeHtml(s)}</li>`).join('')}
          </ul>
        </div>
      ` : ''}

      ${evalData.coaching.improvements.length > 0 ? `
        <div class="feedback-box">
          <h4 style="color: #fcd34d;">⚠ Areas for Coaching & Improvement:</h4>
          <ul>
            ${evalData.coaching.improvements.map(i => `<li>${escapeHtml(i)}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
    `;

    evalModal.classList.add('open');
  } catch (err) {
    console.error('Failed to get scorecard:', err);
    alert('Evaluation error: ' + err.message);
  }
}

function exportTranscript() {
  if (!state.sessionId) return;

  const exportData = {
    sessionId: state.sessionId,
    timestamp: new Date().toISOString(),
    persona: state.selectedPersona,
    scenario: state.selectedScenario,
    trajectory: state.trajectory,
    finalState: state.currentState
  };

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `csa_session_${state.sessionId}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function escapeHtml(str) {
  return (str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

