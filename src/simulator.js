/**
 * Customer Simulator Agent (CSA)
 * Orchestrates persona, scenario, emotional progression, and turn generation.
 */

const { DEFAULT_PERSONAS } = require('./data/personas');
const { DEFAULT_SCENARIOS } = require('./data/scenarios');
const { EmotionalEngine } = require('./engines/emotionalEngine');
const { ScenarioEngine } = require('./engines/scenarioEngine');
const { LLMEngine } = require('./engines/llmEngine');
const { EvaluationEngine } = require('./engines/evaluationEngine');

class CustomerSimulatorAgent {
  constructor(config = {}) {
    this.sessionId = config.sessionId || ('csa_' + Math.random().toString(36).substring(2, 9));
    this.setPersona(config.persona || DEFAULT_PERSONAS[0]);
    this.setScenario(config.scenario || DEFAULT_SCENARIOS[0]);
    
    this.provider = config.provider || 'local'; // 'gemini' | 'openai' | 'local'
    this.apiKey = config.apiKey || process.env.GEMINI_API_KEY || process.env.OPENAI_API_KEY || '';
    this.model = config.model || (this.provider === 'gemini' ? 'gemini-2.5-flash' : 'gpt-4o-mini');

    this.history = [];
    this.trajectory = [];
    this.turnIndex = 0;
    this.isInitialized = false;

    this.initializeSession();
  }

  /**
   * Set or update persona
   */
  setPersona(personaOrId) {
    if (typeof personaOrId === 'string') {
      const found = DEFAULT_PERSONAS.find(p => p.id === personaOrId);
      this.persona = found || DEFAULT_PERSONAS[0];
    } else {
      this.persona = personaOrId;
    }
  }

  /**
   * Set or update scenario
   */
  setScenario(scenarioOrId) {
    if (typeof scenarioOrId === 'string') {
      const found = DEFAULT_SCENARIOS.find(s => s.id === scenarioOrId);
      this.scenario = found || DEFAULT_SCENARIOS[0];
    } else {
      this.scenario = scenarioOrId;
    }
  }

  /**
   * Initialize a new session
   */
  initializeSession() {
    this.history = [];
    this.trajectory = [];
    this.turnIndex = 0;

    // Initialize context tracker
    this.contextTracker = ScenarioEngine.initializeContext(this.scenario);

    // Initial baseline emotional state
    const base = this.persona.baselineEmotion || {
      frustration: 40,
      satisfaction: 20,
      trust: 40,
      arousal: 50,
      primary: 'impatient'
    };

    this.currentState = {
      frustration: base.frustration,
      satisfaction: base.satisfaction,
      trust: base.trust,
      arousal: base.arousal,
      primary: base.primary,
      status: 'active',
      turnIndex: 0,
      patienceTurnsLeft: (this.persona.traits?.patience || 5) * 2,
      triggersDetected: ['initial_scenario_load'],
      deltas: { frustration: 0, trust: 0, satisfaction: 0, arousal: 0 }
    };

    // Store baseline snapshot in trajectory
    this.trajectory.push({
      turnIndex: 0,
      frustration: this.currentState.frustration,
      satisfaction: this.currentState.satisfaction,
      trust: this.currentState.trust,
      arousal: this.currentState.arousal,
      primary: this.currentState.primary,
      triggersDetected: ['initial_state']
    });

    // Opening customer message
    const initialMessage = this.scenario.initialCustomerMessage || 'Hello, I need help with an issue on my account.';
    this.history.push({
      speaker: 'customer',
      text: initialMessage,
      turnIndex: 0,
      timestamp: new Date().toISOString(),
      emotionalState: { ...this.currentState },
      internalMonologue: `Starting this support request. I need ${this.scenario.goals?.primary || 'my problem fixed quickly'}.`
    });

    this.isInitialized = true;
    return this.getStateSnapshot();
  }

  /**
   * Execute one conversation turn in response to an agent message.
   */
  async processAgentMessage(agentMessage) {
    if (!agentMessage || !agentMessage.trim()) {
      throw new Error('Agent message cannot be empty');
    }

    if (this.currentState.status !== 'active') {
      return {
        ...this.getStateSnapshot(),
        message: `Conversation already ended with status: ${this.currentState.status}`,
        customerMessage: this.history[this.history.length - 1]?.text || ''
      };
    }

    this.turnIndex += 1;

    // 1. Record agent's message in history
    this.history.push({
      speaker: 'agent',
      text: agentMessage,
      turnIndex: this.turnIndex,
      timestamp: new Date().toISOString()
    });

    // 2. Progressive information disclosure
    const disclosureResult = ScenarioEngine.evaluateDisclosure(agentMessage, this.contextTracker, this.scenario);
    this.contextTracker = disclosureResult.updatedTracker;

    // 3. Goal evaluation
    const goalResult = ScenarioEngine.evaluateGoalProgress(agentMessage, this.contextTracker, this.scenario);

    // 4. Emotional state progression
    const emotionResult = EmotionalEngine.processTurn({
      currentState: this.currentState,
      persona: this.persona,
      scenario: this.scenario,
      agentMessage,
      turnIndex: this.turnIndex,
      revealedContext: this.contextTracker.revealed,
      history: this.history
    });

    this.currentState = emotionResult.nextState;

    // If goal was met, ensure status reflects resolution
    if (goalResult.isGoalMet) {
      this.currentState.status = 'resolved';
      this.currentState.satisfaction = Math.max(85, this.currentState.satisfaction);
      this.currentState.frustration = Math.min(15, this.currentState.frustration);
      this.currentState.primary = 'delighted';
      this.currentState.resolvedGoal = goalResult.resolvedGoal;
    }

    // 5. Generate turn-by-turn customer message & internal monologue
    const generationResult = await LLMEngine.generateTurn({
      apiKey: this.apiKey,
      provider: this.provider,
      model: this.model,
      persona: this.persona,
      scenario: this.scenario,
      agentMessage,
      emotionalState: this.currentState,
      turnIndex: this.turnIndex,
      revealedContext: this.contextTracker.revealed,
      newlyDisclosed: disclosureResult.newlyDisclosed,
      history: this.history
    });

    const customerMessage = generationResult.customerMessage;
    const internalMonologue = generationResult.internalMonologue;

    // 6. Record customer's response
    this.history.push({
      speaker: 'customer',
      text: customerMessage,
      turnIndex: this.turnIndex,
      timestamp: new Date().toISOString(),
      emotionalState: { ...this.currentState },
      internalMonologue,
      provider: generationResult.provider
    });

    // 7. Record trajectory data point
    this.trajectory.push({
      turnIndex: this.turnIndex,
      frustration: this.currentState.frustration,
      satisfaction: this.currentState.satisfaction,
      trust: this.currentState.trust,
      arousal: this.currentState.arousal,
      primary: this.currentState.primary,
      triggersDetected: this.currentState.triggersDetected
    });

    return {
      turnIndex: this.turnIndex,
      customerMessage,
      internalMonologue,
      emotionalState: { ...this.currentState },
      trajectory: this.trajectory,
      newlyDisclosed: disclosureResult.newlyDisclosed,
      goalResult,
      isResolved: this.currentState.status === 'resolved',
      isRageQuit: this.currentState.status === 'rage_quit',
      status: this.currentState.status,
      provider: generationResult.provider,
      fallbackWarning: generationResult.fallbackWarning
    };
  }

  /**
   * Evaluate the complete simulation session
   */
  evaluate() {
    return EvaluationEngine.evaluateSession({
      persona: this.persona,
      scenario: this.scenario,
      trajectory: this.trajectory,
      history: this.history,
      finalState: this.currentState
    });
  }

  /**
   * Get full state snapshot
   */
  getStateSnapshot() {
    return {
      sessionId: this.sessionId,
      persona: this.persona,
      scenario: this.scenario,
      turnIndex: this.turnIndex,
      currentState: { ...this.currentState },
      trajectory: this.trajectory,
      revealedContext: this.contextTracker?.revealed || [],
      history: this.history,
      provider: this.provider,
      model: this.model,
      status: this.currentState.status
    };
  }
}

module.exports = {
  CustomerSimulatorAgent
};

