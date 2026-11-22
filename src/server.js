/**
 * Customer Simulator Agent - Express Server & REST API
 */

const express = require('express');
const cors = require('cors');
const path = require('path');
require('dotenv').config();

const { DEFAULT_PERSONAS } = require('./data/personas');
const { DEFAULT_SCENARIOS } = require('./data/scenarios');
const { CustomerSimulatorAgent } = require('./simulator');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../public')));

// In-memory sessions store
const sessions = new Map();

/**
 * Health check
 */
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    geminiKeyConfigured: !!process.env.GEMINI_API_KEY,
    openaiKeyConfigured: !!process.env.OPENAI_API_KEY
  });
});

/**
 * Get available personas
 */
app.get('/api/personas', (req, res) => {
  res.json({
    success: true,
    personas: DEFAULT_PERSONAS
  });
});

/**
 * Get available scenarios
 */
app.get('/api/scenarios', (req, res) => {
  res.json({
    success: true,
    scenarios: DEFAULT_SCENARIOS
  });
});

/**
 * Initialize a new simulation session
 */
app.post('/api/simulator/init', (req, res) => {
  try {
    const { persona, scenario, provider, apiKey, model } = req.body;

    const simulator = new CustomerSimulatorAgent({
      persona,
      scenario,
      provider: provider || (apiKey ? 'gemini' : (process.env.GEMINI_API_KEY ? 'gemini' : 'local')),
      apiKey: apiKey || process.env.GEMINI_API_KEY || process.env.OPENAI_API_KEY || '',
      model
    });

    sessions.set(simulator.sessionId, simulator);

    res.json({
      success: true,
      sessionId: simulator.sessionId,
      initialState: simulator.getStateSnapshot()
    });
  } catch (err) {
    console.error('Error initializing simulator:', err);
    res.status(500).json({ success: false, error: err.message });
  }
});

/**
 * Send an agent message and receive customer turn response
 */
app.post('/api/simulator/turn', async (req, res) => {
  try {
    const { sessionId, agentMessage } = req.body;

    if (!sessionId || !sessions.has(sessionId)) {
      return res.status(404).json({ success: false, error: 'Session not found. Please initialize a new session.' });
    }

    const simulator = sessions.get(sessionId);
    const turnResult = await simulator.processAgentMessage(agentMessage);

    res.json({
      success: true,
      ...turnResult
    });
  } catch (err) {
    console.error('Error processing turn:', err);
    res.status(500).json({ success: false, error: err.message });
  }
});

/**
 * Evaluate session and generate scorecard
 */
app.post('/api/simulator/evaluate', (req, res) => {
  try {
    const { sessionId } = req.body;

    if (!sessionId || !sessions.has(sessionId)) {
      return res.status(404).json({ success: false, error: 'Session not found.' });
    }

    const simulator = sessions.get(sessionId);
    const evaluation = simulator.evaluate();

    res.json({
      success: true,
      evaluation
    });
  } catch (err) {
    console.error('Error evaluating session:', err);
    res.status(500).json({ success: false, error: err.message });
  }
});

/**
 * Run automated batch test of an agent script against a persona & scenario
 */
app.post('/api/simulator/batch', async (req, res) => {
  try {
    const { personaId, scenarioId, agentMessages = [] } = req.body;

    const simulator = new CustomerSimulatorAgent({
      persona: personaId,
      scenario: scenarioId,
      provider: 'local'
    });

    const turnsLog = [];

    for (const msg of agentMessages) {
      if (simulator.currentState.status !== 'active') break;
      const turnResult = await simulator.processAgentMessage(msg);
      turnsLog.push({
        agentMessage: msg,
        customerMessage: turnResult.customerMessage,
        internalMonologue: turnResult.internalMonologue,
        emotionalState: turnResult.emotionalState
      });
    }

    const evaluation = simulator.evaluate();

    res.json({
      success: true,
      sessionId: simulator.sessionId,
      turns: turnsLog,
      evaluation
    });
  } catch (err) {
    console.error('Error running batch simulation:', err);
    res.status(500).json({ success: false, error: err.message });
  }
});

// Start listening
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`=======================================================`);
    console.log(`🚀 Customer Simulator Agent Server running!`);
    console.log(`📡 URL: http://localhost:${PORT}`);
    console.log(`🤖 Provider: ${process.env.GEMINI_API_KEY ? 'Gemini (configured)' : 'Local Heuristic (ready)'}`);
    console.log(`=======================================================`);
  });
}

module.exports = { app, sessions };

