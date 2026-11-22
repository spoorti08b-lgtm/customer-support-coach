/**
 * Local Heuristic Engine
 * Generates rich, persona-specific, scenario-consistent replies and internal monologues
 * without requiring an external LLM API key.
 */

class HeuristicEngine {
  /**
   * Generate turn-by-turn customer message, internal monologue, and reactions.
   */
  static generateTurn({
    persona,
    scenario,
    agentMessage,
    emotionalState,
    turnIndex,
    newlyDisclosed = [],
    history = []
  }) {
    const text = (agentMessage || '').toLowerCase();
    const { frustration, satisfaction, trust, primary, status } = emotionalState;
    const personaId = persona.id || 'impatient_executive';

    // 1. Generate Internal Monologue (private thoughts before speaking)
    const internalMonologue = this.generateInternalMonologue({
      persona,
      scenario,
      agentMessage,
      emotionalState,
      turnIndex
    });

    // 2. Generate Customer Spoken Reply
    let customerMessage = '';

    // Check status overrides:
    if (status === 'resolved') {
      customerMessage = this.generateResolutionMessage(persona, emotionalState, scenario);
    } else if (status === 'rage_quit') {
      customerMessage = this.generateRageQuitMessage(persona, emotionalState, scenario);
    } else if (status === 'escalated') {
      customerMessage = this.generateEscalationMessage(persona, emotionalState, scenario);
    } else {
      // Normal conversation turn
      customerMessage = this.generateInFlightMessage({
        persona,
        scenario,
        agentMessage,
        emotionalState,
        turnIndex,
        newlyDisclosed
      });
    }

    // 3. Apply persona-specific stylistic filters (typos, caps, punctuation)
    customerMessage = this.applyStylisticFilter(customerMessage, persona, emotionalState);

    return {
      customerMessage,
      internalMonologue,
      provider: 'local-heuristic'
    };
  }

  /**
   * Synthesize customer's hidden thoughts.
   */
  static generateInternalMonologue({ persona, scenario, agentMessage, emotionalState }) {
    const { frustration, trust, primary } = emotionalState;
    const text = (agentMessage || '').toLowerCase();

    if (frustration > 80) {
      if (/policy/i.test(text)) {
        return `They are hiding behind 'company policy' instead of taking accountability. My blood is boiling. They don't care at all.`;
      }
      if (/wait|business days/i.test(text)) {
        return `Wait days? Are they kidding me?! I don't have days! I am this close to contacting my bank or filing a complaint.`;
      }
      return `This is unacceptable. They are giving me runarounds. I need someone with actual decision-making power.`;
    }

    if (trust > 70 && emotionalState.satisfaction > 50) {
      return `Okay, this person is actually taking care of it instead of reading from an unhelpful script. What a relief.`;
    }

    if (/sorry|apologize/i.test(text)) {
      if (persona.traits.patience < 4) {
        return `Apologies are nice, but words don't fix my problem. Show me the solution, not the sympathy.`;
      } else {
        return `At least they acknowledge it's messed up. Let's see if they can actually follow through.`;
      }
    }

    if (/order|email|phone|account/i.test(text)) {
      return `They need my details to look it up. Let me give it to them so we can move this forward.`;
    }

    return `Listening to what they say. Hoping this gets sorted out quickly without more friction.`;
  }

  /**
   * Generate message when in active conversation.
   */
  static generateInFlightMessage({ persona, scenario, agentMessage, emotionalState, turnIndex, newlyDisclosed }) {
    const text = (agentMessage || '').toLowerCase();
    const pid = persona.id;
    const discloses = newlyDisclosed.map(d => `${d.label}: ${d.value}`).join(', ');

    // Handle disclosure if agent asked for details
    if (newlyDisclosed.length > 0) {
      if (pid === 'confused_senior') {
        return `Yes, let me see... I wrote it down on my notepad here. Here it is: ${discloses}. I hope that's what you need dear, please let me know if I need to find anything else.`;
      }
      if (pid === 'impatient_executive') {
        return `Here: ${discloses}. Can we please move to the fix now? Time is critical.`;
      }
      if (pid === 'sarcastic_techie') {
        return `Sure, ${discloses}. It's also visible in the telemetry logs, but there you go. What's the ETA on the resolution?`;
      }
      if (pid === 'escalate_or_bust') {
        return `Fine! ${discloses}! Now that you have that, what are you doing about this disaster?!`;
      }
      if (pid === 'anxious_first_timer') {
        return `Oh of course! Here you go: ${discloses}. Is there anything else you need from my end to check this?`;
      }
      return `Here are the details you asked for: ${discloses}. Please look into this right away.`;
    }

    // If agent gave an excuse or policy shield
    if (/policy|cannot|unable to|terms/i.test(text)) {
      if (pid === 'impatient_executive') {
        return `Look, I don't care about your internal policy. Your company caused this issue, and I expect you to make it right today. Who can authorize this?`;
      }
      if (pid === 'escalate_or_bust') {
        return `Do not quote your policy to me! I am the customer! I want your supervisor on the line right this second or I will make sure everyone hears about this!`;
      }
      if (pid === 'sarcastic_techie') {
        return `Ah, the classic 'policy' excuse when the system breaks. You do realize that's not acceptable when the error is entirely on your side, right?`;
      }
      if (pid === 'confused_senior') {
        return `Oh goodness... but nobody explained that policy when I bought it. Is there really nothing you can do to help an old person out?`;
      }
      return `That is really frustrating to hear. Surely an exception can be made given these circumstances?`;
    }

    // If agent asked generic question or offered partial step
    if (/let me check|looking into|one moment/i.test(text)) {
      if (pid === 'impatient_executive') {
        return `Alright, go ahead, but please be quick. I have another call starting in five minutes.`;
      }
      if (pid === 'confused_senior') {
        return `Take your time dear, I'll be right here. Thank you for checking for me.`;
      }
      if (pid === 'escalate_or_bust') {
        return `You better be fixing this. I have already spent too much time dealing with your mistakes today.`;
      }
      return `Thank you, I'll wait while you check.`;
    }

    // Default turn response based on persona and emotion
    if (emotionalState.frustration > 60) {
      if (pid === 'impatient_executive') {
        return `This is taking too long. Can you give me a direct answer on when this will be resolved?`;
      }
      if (pid === 'escalate_or_bust') {
        return `You are dodging my question! Are you going to fix this or do I need to talk to someone with actual authority?`;
      }
      if (pid === 'sarcastic_techie') {
        return `We're going in circles here. Let's get straight to the point: what is the actual remediation plan?`;
      }
      return `I'm really unhappy with how this is going. What are the next concrete steps?`;
    }

    // Moderate/polite default
    if (pid === 'confused_senior') {
      return `I see. I just want to make sure my account and money are safe. Could you explain what will happen next in simple terms?`;
    }
    if (pid === 'anxious_first_timer') {
      return `Thank you for explaining that. Just to be completely sure, does this mean I won't be charged extra?`;
    }
    if (pid === 'pragmatic_bargainer') {
      return `Understood. So if we proceed with this, what is the exact timeline and reference number for this ticket?`;
    }

    return `Okay, understood. Please let me know what needs to happen next to get this resolved.`;
  }

  /**
   * Generate message when resolved.
   */
  static generateResolutionMessage(persona, emotionalState, scenario) {
    const pid = persona.id;
    if (pid === 'impatient_executive') {
      return `Thank you. That is the outcome I expected. Appreciate you getting it processed without further delay. Have a good day.`;
    }
    if (pid === 'confused_senior') {
      return `Oh bless you! Thank you so much for being so patient and explaining everything so clearly to me. You made my day so much easier!`;
    }
    if (pid === 'sarcastic_techie') {
      return `Fair enough. Glad we got that sorted out. Much appreciated, have a good one.`;
    }
    if (pid === 'escalate_or_bust') {
      return `Finally! That should have been done from the start without all this arguing, but I'm glad it's taken care of now.`;
    }
    if (pid === 'anxious_first_timer') {
      return `Oh wonderful, thank you so so much! I was so stressed about this. You were so helpful, have a wonderful week!`;
    }
    return `Thank you for taking care of this for me. That solves my issue completely.`;
  }

  /**
   * Generate rage quit / walk-away message.
   */
  static generateRageQuitMessage(persona, emotionalState, scenario) {
    const pid = persona.id;
    if (pid === 'impatient_executive') {
      return `I have wasted enough time on this nonsense. I'm disputing the transaction with American Express and canceling all corporate accounts with your firm. Goodbye.`;
    }
    if (pid === 'escalate_or_bust') {
      return `THIS IS DISGRACEFUL! I am done dealing with you. I am contacting the Better Business Bureau, disputing the charges, and leaving reviews on every platform. Goodbye!`;
    }
    if (pid === 'sarcastic_techie') {
      return `Spectacular customer service masterclass. I'll just write a script to migrate our workloads elsewhere. Closing this chat.`;
    }
    return `I cannot continue this conversation. This has been completely unhelpful and frustrating. I will seek resolution through my bank. Goodbye.`;
  }

  /**
   * Generate escalation message.
   */
  static generateEscalationMessage(persona, emotionalState, scenario) {
    return `Yes, please connect me with your supervisor or Tier-2 lead immediately. I will wait.`;
  }

  /**
   * Apply stylistic persona adjustments (typos, caps, quirks).
   */
  static applyStylisticFilter(text, persona, emotionalState) {
    let result = text;
    const style = persona.communicationStyle || {};

    // Angry caps injection
    if (style.allCapsWhenAngry && emotionalState.frustration > 75) {
      // Uppercase key words or phrases
      result = result.replace(/(unacceptable|immediately|now|fix this|terrible|horrible|manager)/gi, match => match.toUpperCase());
      if (persona.traits.assertiveness >= 9 && emotionalState.frustration > 85) {
        // Upper case entire sentences or outbursts
        result = result.replace(/(!+|\?+)/g, '!!??');
      }
    }

    // Punctuation style
    if (style.punctuationStyle === 'excessive_punctuation' && emotionalState.frustration > 60) {
      result = result.replace(/\?/g, '???').replace(/!/g, '!!!');
    }

    return result;
  }
}

module.exports = {
  HeuristicEngine
};

