/**
 * Emotional Progression Engine
 * Simulates dynamic affective state transitions, triggers, and decay
 * based on customer persona traits and agent interaction patterns.
 */

class EmotionalEngine {
  /**
   * Evaluate the agent message and compute the next emotional state.
   */
  static processTurn({
    currentState,
    persona,
    scenario,
    agentMessage,
    turnIndex,
    revealedContext = [],
    history = []
  }) {
    const text = (agentMessage || '').toLowerCase();
    const traits = persona.traits || { patience: 5, emotionalSensitivity: 5, skepticism: 5, assertiveness: 5 };
    
    // 1. Analyze Agent Message Behavioral Triggers
    const analysis = this.analyzeAgentBehavior(text, scenario, revealedContext, history);

    // 2. Sensitivity multipliers
    const sensMultiplier = traits.emotionalSensitivity / 5.0; // 0.2 to 2.0
    const patienceFactor = (11 - traits.patience) / 5.0; // Low patience = higher frustration ramp

    // 3. Compute Frustration Shift
    let frustrationDelta = 0;

    // Empathy reduces frustration
    if (analysis.hasEmpathy) {
      frustrationDelta -= 15 * (traits.emotionalSensitivity / 6);
    }
    // Concrete positive action / resolution reduces frustration significantly
    if (analysis.hasResolutionOffer) {
      frustrationDelta -= 38;
    } else if (analysis.hasConstructiveStep) {
      frustrationDelta -= 12;
    }

    // Negative triggers that raise frustration:
    if (analysis.isRepetitiveQuestion) {
      frustrationDelta += 18 * patienceFactor;
    }
    if (analysis.isDeflectiveOrPolicyShield) {
      frustrationDelta += 20 * sensMultiplier;
    }
    if (analysis.isDismissiveOrRobotic) {
      frustrationDelta += 14 * sensMultiplier;
    }
    if (analysis.hasUnacceptableOffer) {
      frustrationDelta += 22 * sensMultiplier;
    }
    if (analysis.hasLongDelayIndication) {
      frustrationDelta += 16 * patienceFactor;
    }

    // Turn decay: each unresolved turn slowly chips away at customer patience
    const basePatienceDecay = (10 - traits.patience) * 0.8;
    if (!analysis.hasResolutionOffer) {
      frustrationDelta += basePatienceDecay;
    }

    // 4. Compute Trust Shift
    let trustDelta = 0;
    if (analysis.hasEmpathy) trustDelta += 12;
    if (analysis.hasResolutionOffer) trustDelta += 30;
    if (analysis.hasConstructiveStep) trustDelta += 10;
    if (analysis.isDeflectiveOrPolicyShield) trustDelta -= 18;
    if (analysis.isDismissiveOrRobotic) trustDelta -= 12;
    if (analysis.isRepetitiveQuestion) trustDelta -= 14;
    if (analysis.hasUnacceptableOffer) trustDelta -= 20;

    // Skepticism dampens trust gains
    if (trustDelta > 0) {
      trustDelta *= (11 - traits.skepticism) / 8.0;
    }

    // 5. Compute Satisfaction Shift
    let satisfactionDelta = 0;
    if (analysis.hasResolutionOffer) {
      satisfactionDelta += 45;
    } else if (analysis.hasConstructiveStep) {
      satisfactionDelta += 10;
    }
    if (analysis.isDeflectiveOrPolicyShield || analysis.hasUnacceptableOffer) {
      satisfactionDelta -= 18;
    }
    if (analysis.isDismissiveOrRobotic) {
      satisfactionDelta -= 10;
    }

    // 6. Calculate New State Values clamped to [0, 100]
    const newFrustration = this.clamp(currentState.frustration + frustrationDelta, 0, 100);
    const newTrust = this.clamp(currentState.trust + trustDelta, 0, 100);
    const newSatisfaction = this.clamp(currentState.satisfaction + satisfactionDelta, 0, 100);

    // Arousal shifts with frustration and urgency
    let arousalDelta = (frustrationDelta * 0.5) - (satisfactionDelta * 0.3);
    const newArousal = this.clamp(currentState.arousal + arousalDelta, 10, 100);

    // 7. Determine Primary Emotion
    const primaryEmotion = this.derivePrimaryEmotion(newFrustration, newSatisfaction, newTrust, newArousal, persona);
    
    // Consecutive high frustration counter to give customer an ultimatum warning before hard rage quit
    const prevHighFrustrationTurns = currentState.highFrustrationTurns || 0;
    const isCurrentlyExtremeFrustration = newFrustration >= 92;
    const highFrustrationTurns = isCurrentlyExtremeFrustration ? (prevHighFrustrationTurns + 1) : 0;

    // Check outcome statuses:
    let status = 'active';
    let outcomeReason = '';

    if (newSatisfaction >= 80 || (analysis.hasResolutionOffer && newFrustration < 50)) {
      status = 'resolved';
      outcomeReason = 'Customer issue resolved satisfactorily';
    } else if (highFrustrationTurns >= 2 && !analysis.hasResolutionOffer) {
      // 2 consecutive turns of >= 92% frustration without a resolution leads to walking away
      status = 'rage_quit';
      outcomeReason = 'Customer walked away due to repeated unhelpful turns and peak frustration';
    } else if (currentState.patienceTurnsLeft <= 0 && newFrustration > 80 && !analysis.hasResolutionOffer) {
      status = 'rage_quit';
      outcomeReason = 'Patience exhausted without meaningful resolution';
    } else if (analysis.hasEscalationToManager) {
      status = 'escalated';
      outcomeReason = 'Interaction escalated to supervisor/tier-2';
    }

    const patienceTurnsLeft = Math.max(0, (currentState.patienceTurnsLeft ?? traits.patience * 2) - 1);

    const nextState = {
      frustration: Math.round(newFrustration),
      satisfaction: Math.round(newSatisfaction),
      trust: Math.round(newTrust),
      arousal: Math.round(newArousal),
      primary: primaryEmotion,
      status,
      outcomeReason,
      patienceTurnsLeft,
      highFrustrationTurns,
      turnIndex: turnIndex + 1,
      triggersDetected: analysis.tags,
      deltas: {
        frustration: Math.round(frustrationDelta),
        trust: Math.round(trustDelta),
        satisfaction: Math.round(satisfactionDelta),
        arousal: Math.round(arousalDelta)
      }
    };

    return {
      nextState,
      analysis
    };
  }

  /**
   * Analyze agent text for specific psychological triggers.
   */
  static analyzeAgentBehavior(text, scenario, revealedContext = [], history = []) {
    const tags = [];

    // Empathy patterns
    const empathyPatterns = [
      /sorry for/i, /apologize/i, /completely understand/i, /must be (so )?frustrating/i,
      /hear how difficult/i, /can imagine how/i, /terrible experience/i, /glad you reached out/i,
      /take care of this/i, /my sincere apologies/i, /thank you for your patience/i
    ];
    const hasEmpathy = empathyPatterns.some(p => p.test(text));
    if (hasEmpathy) tags.push('empathy');

    // Resolution / action patterns
    const resolutionPatterns = [
      /refund(ed)?/i, /rebook(ed)?/i, /waive(d)?/i, /sent a replacement/i,
      /issued a credit/i, /credited your/i, /overnight/i, /hotel voucher/i,
      /bypass/i, /temporary access/i, /escalat(ed|ing) to tier/i, /priority ticket/i
    ];
    const hasResolutionOffer = resolutionPatterns.some(p => p.test(text));
    if (hasResolutionOffer) tags.push('resolution_offer');

    // Constructive progress steps
    const constructivePatterns = [
      /let me check/i, /looking into/i, /pulling up your/i, /investigating/i,
      /let's get this fixed/i, /can help you with/i, /on my screen now/i, /i can arrange/i
    ];
    const hasConstructiveStep = constructivePatterns.some(p => p.test(text)) && !hasResolutionOffer;
    if (hasConstructiveStep) tags.push('constructive_step');

    // Deflection / Policy shielding
    const policyShieldPatterns = [
      /company policy/i, /terms (and|&) conditions/i, /against our policy/i,
      /nothing (we|i) can do/i, /out of my hands/i, /not our responsibility/i,
      /all sales are final/i, /cannot make an exception/i
    ];
    const isDeflectiveOrPolicyShield = policyShieldPatterns.some(p => p.test(text));
    if (isDeflectiveOrPolicyShield) tags.push('policy_shield');

    // Dismissive or purely robotic canned responses
    const cannedPatterns = [
      /as per my previous/i, /refer to FAQ/i, /read our documentation/i,
      /it is what it is/i, /calm down/i, /relax/i, /you need to understand/i
    ];
    const isDismissiveOrRobotic = cannedPatterns.some(p => p.test(text));
    if (isDismissiveOrRobotic) tags.push('robotic_or_dismissive');

    // Unacceptable offer checks against scenario
    let hasUnacceptableOffer = false;
    if (scenario?.goals?.unacceptableOffers) {
      for (const unacc of scenario.goals.unacceptableOffers) {
        const keywords = unacc.toLowerCase().split(/\s+/).filter(w => w.length > 4);
        const matchCount = keywords.filter(k => text.includes(k)).length;
        if (matchCount >= 2 || (keywords.length <= 2 && matchCount >= 1)) {
          hasUnacceptableOffer = true;
          tags.push('unacceptable_offer');
          break;
        }
      }
    }

    // Delay indicators
    const delayPatterns = [
      /10(-|\s*to\s*)14 (days|business days)/i, /wait 5(-|\s*to\s*)7 business days/i,
      /48(-|\s*to\s*)72 hours/i, /expect a response in a few weeks/i, /backlog/i
    ];
    const hasLongDelayIndication = delayPatterns.some(p => p.test(text));
    if (hasLongDelayIndication) tags.push('unacceptable_delay');

    // Repetitive questions (e.g. asking for order number or email when already provided)
    let isRepetitiveQuestion = false;
    const askingForOrder = /order (number|#|id)/i.test(text);
    const askingForEmail = /email (address|id)/i.test(text);
    const askingForPhone = /phone (number|#)/i.test(text);

    if (askingForOrder && revealedContext.includes('orderId')) {
      isRepetitiveQuestion = true;
      tags.push('repeated_order_query');
    }
    if (askingForEmail && revealedContext.includes('accountEmail')) {
      isRepetitiveQuestion = true;
      tags.push('repeated_email_query');
    }
    if (askingForPhone && revealedContext.includes('stolenPhoneNumber')) {
      isRepetitiveQuestion = true;
      tags.push('repeated_phone_query');
    }

    // Manager / Escalation trigger
    const hasEscalationToManager = /transfer(ring)? you to (my|a) (manager|supervisor|lead)/i.test(text);
    if (hasEscalationToManager) tags.push('escalated_to_manager');

    return {
      hasEmpathy,
      hasResolutionOffer,
      hasConstructiveStep,
      isDeflectiveOrPolicyShield,
      isDismissiveOrRobotic,
      hasUnacceptableOffer,
      hasLongDelayIndication,
      isRepetitiveQuestion,
      hasEscalationToManager,
      tags
    };
  }

  /**
   * Derive primary emotion label from numerical dimensions.
   */
  static derivePrimaryEmotion(frustration, satisfaction, trust, arousal, persona) {
    if (satisfaction >= 80) return 'delighted';
    if (satisfaction >= 60 && frustration < 30) return 'relieved';
    if (satisfaction >= 50 && trust >= 50) return 'satisfied';

    if (frustration >= 85) return 'infuriated';
    if (frustration >= 70) return 'enraged';
    if (frustration >= 55) {
      if (persona.traits.assertiveness >= 8) return 'confrontational';
      return 'frustrated';
    }
    if (frustration >= 40) {
      if (persona.traits.skepticism >= 7) return 'skeptical';
      return 'impatient';
    }

    if (trust >= 60 && frustration <= 30) return 'cooperative';
    if (trust < 30 && frustration >= 30) return 'suspicious';
    if (arousal >= 60) return 'anxious';

    return 'neutral';
  }

  static clamp(val, min, max) {
    return Math.max(min, Math.min(max, val));
  }
}

module.exports = {
  EmotionalEngine
};
