/**
 * LLM Engine
 * Connects to Google Gemini API (via @google/genai or REST) and OpenAI-compatible providers
 * with structured JSON output and automatic fallback.
 */

const { HeuristicEngine } = require('./heuristicEngine');

class LLMEngine {
  /**
   * Generate turn message using LLM or fallback to Heuristic.
   */
  static async generateTurn({
    apiKey,
    provider = 'gemini', // 'gemini' | 'openai' | 'local'
    model = 'gemini-2.5-flash',
    persona,
    scenario,
    agentMessage,
    emotionalState,
    turnIndex,
    revealedContext = [],
    newlyDisclosed = [],
    history = []
  }) {
    // If provider is local or no key is present, use HeuristicEngine
    const effectiveKey = apiKey || process.env.GEMINI_API_KEY || process.env.OPENAI_API_KEY;

    if (provider === 'local' || !effectiveKey) {
      return HeuristicEngine.generateTurn({
        persona,
        scenario,
        agentMessage,
        emotionalState,
        turnIndex,
        newlyDisclosed,
        history
      });
    }

    try {
      if (provider === 'gemini') {
        return await this.callGemini({
          apiKey: effectiveKey,
          model: model || 'gemini-2.5-flash',
          persona,
          scenario,
          agentMessage,
          emotionalState,
          turnIndex,
          revealedContext,
          newlyDisclosed,
          history
        });
      } else if (provider === 'openai') {
        return await this.callOpenAI({
          apiKey: effectiveKey,
          model: model || 'gpt-4o-mini',
          persona,
          scenario,
          agentMessage,
          emotionalState,
          turnIndex,
          revealedContext,
          newlyDisclosed,
          history
        });
      }
    } catch (err) {
      console.warn(`[LLMEngine] Error with ${provider} API (${err.message}). Falling back to HeuristicEngine.`);
      const fallbackResult = HeuristicEngine.generateTurn({
        persona,
        scenario,
        agentMessage,
        emotionalState,
        turnIndex,
        newlyDisclosed,
        history
      });
      fallbackResult.fallbackWarning = `LLM call failed (${err.message}), used local fallback.`;
      return fallbackResult;
    }
  }

  /**
   * Call Google Gemini API
   */
  static async callGemini({
    apiKey,
    model,
    persona,
    scenario,
    agentMessage,
    emotionalState,
    turnIndex,
    revealedContext,
    newlyDisclosed,
    history
  }) {
    const prompt = this.buildPrompt({
      persona,
      scenario,
      agentMessage,
      emotionalState,
      turnIndex,
      revealedContext,
      newlyDisclosed,
      history
    });

    // Try Google Gen AI SDK or direct fetch
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
    
    const body = {
      contents: [
        {
          role: 'user',
          parts: [{ text: prompt }]
        }
      ],
      generationConfig: {
        responseMimeType: 'application/json',
        temperature: 0.7,
        maxOutputTokens: 1024
      }
    };

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Gemini API returned ${response.status}: ${errText}`);
    }

    const data = await response.json();
    const candidateText = data.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!candidateText) {
      throw new Error('No candidate content returned by Gemini API');
    }

    const parsed = JSON.parse(candidateText);
    return {
      customerMessage: parsed.customerMessage || parsed.message,
      internalMonologue: parsed.internalMonologue || parsed.thoughts,
      provider: 'gemini',
      modelUsed: model,
      llmFeedback: parsed.assessment
    };
  }

  /**
   * Call OpenAI-compatible endpoint
   */
  static async callOpenAI({
    apiKey,
    model,
    persona,
    scenario,
    agentMessage,
    emotionalState,
    turnIndex,
    revealedContext,
    newlyDisclosed,
    history
  }) {
    const prompt = this.buildPrompt({
      persona,
      scenario,
      agentMessage,
      emotionalState,
      turnIndex,
      revealedContext,
      newlyDisclosed,
      history
    });

    const endpoint = process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1/chat/completions';
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: model || 'gpt-4o-mini',
        messages: [
          { role: 'system', content: 'You are an advanced Customer Simulator Agent. Always output valid JSON.' },
          { role: 'user', content: prompt }
        ],
        response_format: { type: 'json_object' },
        temperature: 0.7
      })
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`OpenAI API returned ${response.status}: ${errText}`);
    }

    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;
    const parsed = JSON.parse(content);

    return {
      customerMessage: parsed.customerMessage || parsed.message,
      internalMonologue: parsed.internalMonologue || parsed.thoughts,
      provider: 'openai',
      modelUsed: model
    };
  }

  /**
   * Construct detailed prompt enforcing role, consistency, and persona voice.
   */
  static buildPrompt({
    persona,
    scenario,
    agentMessage,
    emotionalState,
    turnIndex,
    revealedContext,
    newlyDisclosed,
    history
  }) {
    return `
You are an expert actor playing the role of a realistic CUSTOMER in a Customer Support interaction.
DO NOT assist the agent. DO NOT sound like an AI assistant. You are ONLY the customer. Stay 100% in character.

### CUSTOMER PERSONA:
- Name: ${persona.name} (${persona.role}, age ${persona.age})
- Archetype / Persona ID: ${persona.id}
- Core Traits:
  * Patience: ${persona.traits.patience}/10
  * Emotional Sensitivity: ${persona.traits.emotionalSensitivity}/10
  * Verbosity: ${persona.traits.verbosity}
  * Skepticism: ${persona.traits.skepticism}/10
  * Tech Literacy: ${persona.traits.techLiteracy}/10
  * Assertiveness: ${persona.traits.assertiveness}/10
- Communication Style:
  * Formality: ${persona.communicationStyle.formality}
  * Punctuation Style: ${persona.communicationStyle.punctuationStyle}
  * Typo Frequency: ${persona.communicationStyle.typoFrequency}
  * All Caps When Angry: ${persona.communicationStyle.allCapsWhenAngry}
  * Favorite Expressions: ${JSON.stringify(persona.communicationStyle.fillerWords)}
  * Pet Peeves: ${JSON.stringify(persona.communicationStyle.petPeeves)}

### SCENARIO CONTEXT (GROUND TRUTH):
- Scenario Title: ${scenario.title} (${scenario.domain})
- Customer's Goal: ${scenario.goals.primary}
- Context Data: ${JSON.stringify(scenario.context, null, 2)}
- Hidden Knowledge: ${JSON.stringify(scenario.hiddenKnowledge, null, 2)}
- Information already revealed to agent: ${JSON.stringify(revealedContext)}
- Information requested this turn to disclose: ${JSON.stringify(newlyDisclosed)}
- Unacceptable offers that cause outrage: ${JSON.stringify(scenario.goals.unacceptableOffers)}

### CURRENT EMOTIONAL STATE (Turn #${turnIndex + 1}):
- Frustration Level: ${emotionalState.frustration}/100
- Satisfaction Level: ${emotionalState.satisfaction}/100
- Trust Level: ${emotionalState.trust}/100
- Arousal/Urgency: ${emotionalState.arousal}/100
- Primary Emotion: "${emotionalState.primary}"
- Current Status: "${emotionalState.status}"

### CONVERSATION HISTORY SO FAR:
${history.map(h => `${h.speaker.toUpperCase()}: ${h.text}`).join('\n')}

### AGENT JUST SAID:
"${agentMessage}"

### INSTRUCTIONS:
1. Speak strictly in the persona's authentic voice, matching their verbosity, vocabulary, and quirks.
2. If the customer's frustration is very high (>70), reflect irritation, shortness, or caps lock according to their traits.
3. If the agent asked for information and it matches the scenario context, disclose it naturally. If the agent repeated a question for something already provided, react with annoyance.
4. If status is "resolved", express genuine resolution/satisfaction in persona voice.
5. If status is "rage_quit", walk away angrily and end the chat.
6. Provide "internalMonologue": What the customer is thinking privately in their head about the agent's message vs what they say aloud.

### OUTPUT FORMAT:
Output MUST be a valid JSON object with EXACTLY this structure:
{
  "customerMessage": "String with the exact words the customer says back to the agent",
  "internalMonologue": "String with the customer's private candid inner thoughts",
  "assessment": {
    "agentHelpfulness": "String evaluating agent's turn",
    "emotionShiftReason": "Short sentence explaining why customer feels this way"
  }
}
`;
  }
}

module.exports = {
  LLMEngine
};

