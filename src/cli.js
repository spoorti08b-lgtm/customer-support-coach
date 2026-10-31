#!/usr/bin/env node

/**
 * Customer Simulator Agent - Interactive Terminal CLI
 * Run: node src/cli.js
 */

const readline = require('readline');
const { DEFAULT_PERSONAS } = require('./data/personas');
const { DEFAULT_SCENARIOS } = require('./data/scenarios');
const { CustomerSimulatorAgent } = require('./simulator');

// ANSI Color Helpers
const colors = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  bgRed: '\x1b[41m',
  bgGreen: '\x1b[42m',
  bgYellow: '\x1b[43m'
};

function renderBar(val, max = 100, width = 16, color = colors.cyan) {
  const filled = Math.round((val / max) * width);
  const empty = width - filled;
  return `${color}[${'█'.repeat(filled)}${'░'.repeat(empty)}] ${val}%${colors.reset}`;
}

async function runCli() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  const question = (q) => new Promise(resolve => rl.question(q, resolve));

  console.clear();
  console.log(`${colors.cyan}${colors.bold}================================================================${colors.reset}`);
  console.log(`${colors.cyan}${colors.bold}       🤖 CUSTOMER SIMULATOR AGENT (CSA) - CLI SIMULATOR       ${colors.reset}`);
  console.log(`${colors.cyan}${colors.bold}================================================================${colors.reset}\n`);

  // 1. Select Persona
  console.log(`${colors.bold}Available Customer Personas:${colors.reset}`);
  DEFAULT_PERSONAS.forEach((p, idx) => {
    console.log(`  [${idx + 1}] ${p.avatar} ${colors.bold}${p.name}${colors.reset} (${p.role}) - ${p.description}`);
  });

  const pChoice = await question(`\nSelect Persona [1-${DEFAULT_PERSONAS.length}] (Default: 1): `);
  const selectedPersona = DEFAULT_PERSONAS[parseInt(pChoice) - 1] || DEFAULT_PERSONAS[0];

  // 2. Select Scenario
  console.log(`\n${colors.bold}Available Support Scenarios:${colors.reset}`);
  DEFAULT_SCENARIOS.forEach((s, idx) => {
    console.log(`  [${idx + 1}] ${colors.bold}${s.title}${colors.reset} [${s.domain}] - ${s.description}`);
  });

  const sChoice = await question(`\nSelect Scenario [1-${DEFAULT_SCENARIOS.length}] (Default: 1): `);
  const selectedScenario = DEFAULT_SCENARIOS[parseInt(sChoice) - 1] || DEFAULT_SCENARIOS[0];

  console.log(`\n${colors.green}Initializing customer simulation session...${colors.reset}\n`);

  const simulator = new CustomerSimulatorAgent({
    persona: selectedPersona,
    scenario: selectedScenario,
    provider: process.env.GEMINI_API_KEY ? 'gemini' : 'local'
  });

  // Display Briefing
  console.log(`${colors.yellow}------------------------ BRIEFING ------------------------${colors.reset}`);
  console.log(`👤 Customer: ${selectedPersona.avatar} ${colors.bold}${selectedPersona.name}${colors.reset} (${selectedPersona.role})`);
  console.log(`   Patience: ${selectedPersona.traits.patience}/10 | Skepticism: ${selectedPersona.traits.skepticism}/10 | Style: ${selectedPersona.traits.verbosity}`);
  console.log(`📋 Scenario: ${colors.bold}${selectedScenario.title}${colors.reset}`);
  console.log(`🎯 Customer Goal: ${selectedScenario.goals.primary}`);
  console.log(`${colors.yellow}----------------------------------------------------------${colors.reset}\n`);

  // Initial customer turn
  const initial = simulator.history[0];
  printEmotionalDashboard(simulator.currentState);
  console.log(`\n${colors.bold}${colors.magenta}👤 Customer (${selectedPersona.name}):${colors.reset}`);
  console.log(`   "${initial.text}"\n`);
  console.log(`${colors.dim}💭 [Inner Thoughts]: "${initial.internalMonologue}"${colors.reset}\n`);

  // Interactive conversation loop
  while (simulator.currentState.status === 'active') {
    const agentInput = await question(`${colors.bold}${colors.green}🎧 Agent (You): ${colors.reset}`);

    if (agentInput.trim().toLowerCase() === 'exit' || agentInput.trim().toLowerCase() === 'quit') {
      console.log(`\n${colors.yellow}Ending simulation early...${colors.reset}`);
      break;
    }

    if (!agentInput.trim()) continue;

    console.log(`\n${colors.dim}Simulating customer cognitive reaction...${colors.reset}`);
    const turnResult = await simulator.processAgentMessage(agentInput);

    console.clear();
    printEmotionalDashboard(turnResult.emotionalState);

    // Delta badges
    const d = turnResult.emotionalState.deltas;
    const fDeltaStr = d.frustration >= 0 ? `+${d.frustration}% 🔺` : `${d.frustration}% 🔻`;
    const tDeltaStr = d.trust >= 0 ? `+${d.trust}% 🔺` : `${d.trust}% 🔻`;
    console.log(`\n${colors.dim}Shift: Frustration (${fDeltaStr}), Trust (${tDeltaStr})${colors.reset}`);
    if (turnResult.emotionalState.triggersDetected.length > 0) {
      console.log(`${colors.dim}Triggers detected: [${turnResult.emotionalState.triggersDetected.join(', ')}]${colors.reset}`);
    }

    console.log(`\n${colors.bold}${colors.magenta}👤 Customer (${selectedPersona.name}):${colors.reset}`);
    console.log(`   "${turnResult.customerMessage}"\n`);
    console.log(`${colors.dim}💭 [Inner Thoughts]: "${turnResult.internalMonologue}"${colors.reset}\n`);

    if (turnResult.status === 'resolved') {
      console.log(`${colors.bgGreen}${colors.bold} 🎉 ISSUE RESOLVED! Customer achieved their goal. ${colors.reset}\n`);
      break;
    } else if (turnResult.status === 'rage_quit') {
      console.log(`${colors.bgRed}${colors.bold} 💥 CUSTOMER RAGE QUIT! Frustration threshold breached. ${colors.reset}\n`);
      break;
    }
  }

  // Final evaluation
  const evaluation = simulator.evaluate();
  console.log(`${colors.cyan}${colors.bold}================== AGENT PERFORMANCE SCORECARD ==================${colors.reset}`);
  console.log(`⭐ Overall CSAT: ${colors.bold}${evaluation.csat} / 5.0${colors.reset}`);
  console.log(`🎯 First Contact Resolution (FCR): ${evaluation.isResolved ? colors.green + 'YES' : colors.red + 'NO'}${colors.reset}`);
  console.log(`❤️  Empathy Index: ${evaluation.empathyIndex}%`);
  console.log(`📉 De-escalation Success: ${evaluation.deEscalationSuccessful ? colors.green + 'SUCCESS' : colors.yellow + 'NEUTRAL/FAILED'}${colors.reset}`);
  console.log(`📊 Initial Frustration: ${evaluation.initialFrustration}% ➡️ Final: ${evaluation.finalFrustration}% (Peak: ${evaluation.peakFrustration}%)`);
  console.log(`⏱️  Total Conversation Turns: ${evaluation.totalTurns}`);
  
  if (evaluation.coaching.strengths.length > 0) {
    console.log(`\n${colors.green}${colors.bold}Strengths:${colors.reset}`);
    evaluation.coaching.strengths.forEach(s => console.log(`  ✓ ${s}`));
  }
  if (evaluation.coaching.improvements.length > 0) {
    console.log(`\n${colors.yellow}${colors.bold}Areas for Coaching:${colors.reset}`);
    evaluation.coaching.improvements.forEach(i => console.log(`  ⚠ ${i}`));
  }
  console.log(`${colors.cyan}=================================================================${colors.reset}\n`);

  rl.close();
}

function printEmotionalDashboard(state) {
  console.log(`${colors.bold}┌───────────────────────── LIVE EMOTIONAL STATE ─────────────────────────┐${colors.reset}`);
  console.log(`│ Frustration : ${renderBar(state.frustration, 100, 16, colors.red)}  │ Emotion: ${colors.bold}${state.primary.toUpperCase()}${colors.reset}`);
  console.log(`│ Trust       : ${renderBar(state.trust, 100, 16, colors.green)}  │ Status : ${state.status.toUpperCase()}`);
  console.log(`│ Satisfaction: ${renderBar(state.satisfaction, 100, 16, colors.blue)}  │ Urgency: ${state.arousal}%`);
  console.log(`${colors.bold}└────────────────────────────────────────────────────────────────────────┘${colors.reset}`);
}

if (require.main === module) {
  runCli().catch(console.error);
}

module.exports = { runCli };

