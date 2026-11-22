/**
 * Scenario Engine
 * Tracks ground truth knowledge, progressive disclosure, and goal satisfaction.
 */

class ScenarioEngine {
  /**
   * Initialize context tracker for a scenario.
   */
  static initializeContext(scenario) {
    const revealed = [];
    // If the initial customer message already contains specific info, mark it as revealed
    const initMsg = scenario.initialCustomerMessage || '';

    if (scenario.context) {
      for (const [key, val] of Object.entries(scenario.context)) {
        if (typeof val === 'string' && val.length > 2 && initMsg.includes(val)) {
          revealed.push(key);
        }
      }
    }

    return {
      revealed,
      unrevealed: Object.keys(scenario.context || {}).filter(k => !revealed.includes(k)),
      groundTruth: scenario.context || {},
      hiddenKnowledge: scenario.hiddenKnowledge || {},
      goals: scenario.goals || {},
      resolvedGoal: null,
      isGoalMet: false
    };
  }

  /**
   * Determine what new context the customer will disclose this turn based on agent request.
   */
  static evaluateDisclosure(agentMessage, currentTracker, scenario) {
    const text = (agentMessage || '').toLowerCase();
    const newlyDisclosed = [];

    // Order ID query
    if (/order (number|#|id)|what('s| is) your order/i.test(text) && !currentTracker.revealed.includes('orderId')) {
      if (currentTracker.groundTruth.orderId) {
        newlyDisclosed.push({ key: 'orderId', value: currentTracker.groundTruth.orderId, label: 'Order ID' });
      }
    }

    // Email query
    if (/email (address|id)|what('s| is) your email/i.test(text) && !currentTracker.revealed.includes('accountEmail')) {
      if (currentTracker.groundTruth.accountEmail) {
        newlyDisclosed.push({ key: 'accountEmail', value: currentTracker.groundTruth.accountEmail, label: 'Account Email' });
      }
    }

    // Flight number / PNR query
    if (/flight|pnr|booking (ref|reference|code)/i.test(text) && !currentTracker.revealed.includes('pnr')) {
      if (currentTracker.groundTruth.pnr) {
        newlyDisclosed.push({ key: 'pnr', value: currentTracker.groundTruth.pnr, label: 'PNR Booking Reference' });
      }
    }

    // Photo inquiry
    if (/photo|picture|image|damage/i.test(text) && !currentTracker.revealed.includes('photosAvailable')) {
      if (currentTracker.groundTruth.photosAvailable) {
        newlyDisclosed.push({ key: 'photosAvailable', value: 'Customer sent 3 photos of damaged goods', label: 'Photo Evidence' });
      }
    }

    // Phone inquiry
    if (/phone (number|#)/i.test(text) && !currentTracker.revealed.includes('stolenPhoneNumber')) {
      if (currentTracker.groundTruth.stolenPhoneNumber) {
        newlyDisclosed.push({ key: 'stolenPhoneNumber', value: currentTracker.groundTruth.stolenPhoneNumber, label: 'Phone Number' });
      }
    }

    // Identity / tax deadline query
    if (/id|driver|passport|deadline/i.test(text) && !currentTracker.revealed.includes('deadline')) {
      if (currentTracker.groundTruth.deadline) {
        newlyDisclosed.push({ key: 'deadline', value: currentTracker.groundTruth.deadline, label: 'Tax Filing Deadline' });
      }
    }

    const updatedRevealed = [...currentTracker.revealed, ...newlyDisclosed.map(d => d.key)];
    const updatedUnrevealed = currentTracker.unrevealed.filter(k => !updatedRevealed.includes(k));

    return {
      newlyDisclosed,
      updatedTracker: {
        ...currentTracker,
        revealed: updatedRevealed,
        unrevealed: updatedUnrevealed
      }
    };
  }

  /**
   * Check if the agent's message satisfies the primary or alternative scenario goals.
   */
  static evaluateGoalProgress(agentMessage, tracker, scenario) {
    const text = (agentMessage || '').toLowerCase();
    let isGoalMet = false;
    let resolvedGoal = null;

    // Detect refund commitment
    const offersRefund = /(issue|process|refunded|crediting)\s+(a\s+)?(full\s+)?refund/i.test(text) ||
                         /refund.*(card|account|balance)/i.test(text) ||
                         /refund.*\$?\d+/i.test(text);

    // Detect replacement commitment
    const offersReplacement = /(send|sending|ship|shipping)\s+(out\s+)?(a\s+)?(free\s+)?(overnight\s+)?replacement/i.test(text);

    // Detect rebooking + accommodation
    const offersFlightSolution = /(rebook(ed)?|seat\s+confirmed).*6:?00\s*am/i.test(text) ||
                                (/(rebook(ed)?|flight)/i.test(text) && /(hotel|voucher)/i.test(text));

    // Detect bypass / emergency ID verification
    const offersBypass = /(bypass|manual\s+override|send\s+your\s+forms\s+directly|verified\s+your\s+id)/i.test(text);

    // Detect engineering escalation / incident bridge
    const offersTechEscalation = /(incident\s+bridge|tier\s*2|engineering\s+team\s+is\s+actively|ticket\s*#?\s*inc)/i.test(text);

    if (scenario.id === 'damaged_delivery' && (offersRefund || offersReplacement)) {
      isGoalMet = true;
      resolvedGoal = offersRefund ? 'Full refund granted' : 'Replacement dispatched';
    } else if (scenario.id === 'unauthorized_subscription_charge' && offersRefund) {
      isGoalMet = true;
      resolvedGoal = 'Subscription fee refunded & canceled';
    } else if (scenario.id === 'flight_cancellation_stranded' && (offersFlightSolution || (offersRefund && /voucher/i.test(text)))) {
      isGoalMet = true;
      resolvedGoal = 'Rebooked or compensated with lodging';
    } else if (scenario.id === 'production_api_outage' && offersTechEscalation) {
      isGoalMet = true;
      resolvedGoal = 'Incident acknowledged with active L2 engineering bridge';
    } else if (scenario.id === 'stolen_phone_account_lockout' && offersBypass) {
      isGoalMet = true;
      resolvedGoal = 'Emergency document access provided';
    }

    return {
      isGoalMet,
      resolvedGoal
    };
  }
}

module.exports = {
  ScenarioEngine
};

