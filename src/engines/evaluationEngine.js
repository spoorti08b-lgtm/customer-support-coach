/**
 * Evaluation Engine
 * Evaluates support agent performance across empathy, resolution,
 * de-escalation, and provides an end-of-simulation scorecard.
 */

class EvaluationEngine {
  /**
   * Generate complete scorecard for a session.
   */
  static evaluateSession({
    persona,
    scenario,
    trajectory = [],
    history = [],
    finalState
  }) {
    if (!trajectory || trajectory.length === 0) {
      return { csat: 3.0, status: 'incomplete', feedback: 'No turns recorded.' };
    }

    const totalTurns = trajectory.length;
    const finalFrustration = finalState?.frustration ?? 50;
    const finalSatisfaction = finalState?.satisfaction ?? 50;
    const finalTrust = finalState?.trust ?? 50;
    const status = finalState?.status || 'active';

    // 1. Calculate CSAT (1.0 to 5.0)
    // Formula weighting satisfaction (50%), trust (30%), inverted frustration (20%)
    const rawScore = (finalSatisfaction * 0.5) + (finalTrust * 0.3) + ((100 - finalFrustration) * 0.2);
    const csat = Math.max(1.0, Math.min(5.0, Number((1 + (rawScore / 100) * 4).toFixed(1))));

    // 2. First Contact Resolution (FCR)
    const isResolved = status === 'resolved';

    // 3. Peak and De-escalation calculation
    const frustrationHistory = trajectory.map(t => t.frustration);
    const initialFrustration = frustrationHistory[0] || 50;
    const peakFrustration = Math.max(...frustrationHistory);
    const deEscalationDelta = peakFrustration - finalFrustration;
    const deEscalationSuccessful = deEscalationDelta > 15;

    // 4. Empathy Index
    let empathyTriggerCount = 0;
    let policyShieldCount = 0;
    let repetitiveQueryCount = 0;

    trajectory.forEach(t => {
      const triggers = t.triggersDetected || [];
      if (triggers.includes('empathy')) empathyTriggerCount++;
      if (triggers.includes('policy_shield')) policyShieldCount++;
      if (triggers.includes('repeated_order_query') || triggers.includes('repeated_email_query')) repetitiveQueryCount++;
    });

    const empathyIndex = Math.min(100, Math.round((empathyTriggerCount / Math.max(1, totalTurns)) * 100));

    // 5. Critical Moments / Inflection Points
    const inflectionPoints = [];
    for (let i = 1; i < trajectory.length; i++) {
      const prev = trajectory[i - 1];
      const curr = trajectory[i];
      const frustrationDiff = curr.frustration - prev.frustration;
      const satisfactionDiff = curr.satisfaction - prev.satisfaction;

      if (frustrationDiff >= 15) {
        inflectionPoints.push({
          turn: curr.turnIndex,
          type: 'negative_spike',
          title: 'Frustration Surge (+ ' + frustrationDiff + '%)',
          description: `Customer frustration spiked due to triggers: ${(curr.triggersDetected || []).join(', ') || 'unhelpful response'}`,
          agentMessage: history.find(h => h.turnIndex === curr.turnIndex && h.speaker === 'agent')?.text || ''
        });
      } else if (satisfactionDiff >= 20 || frustrationDiff <= -15) {
        inflectionPoints.push({
          turn: curr.turnIndex,
          type: 'positive_breakthrough',
          title: 'De-escalation Breakthrough',
          description: `Customer calmed down significantly due to constructive resolution or empathy`,
          agentMessage: history.find(h => h.turnIndex === curr.turnIndex && h.speaker === 'agent')?.text || ''
        });
      }
    }

    // 6. Actionable Coaching Feedback
    const strengths = [];
    const improvements = [];

    if (isResolved) {
      strengths.push(`Successfully satisfied customer's core goal (${scenario.goals?.primary || 'Resolution achieved'}).`);
    } else if (status === 'rage_quit') {
      improvements.push('Customer abandoned the conversation due to unresolved frustration. Prioritize immediate action over procedural explanations.');
    }

    if (empathyIndex >= 60) {
      strengths.push('Excellent active listening and empathetic acknowledgment throughout the interaction.');
    } else {
      improvements.push('Incorporate more validating empathy statements early on before requesting administrative details.');
    }

    if (policyShieldCount > 0) {
      improvements.push('Avoid citing "company policy" directly without offering an immediate alternative solution or escalation.');
    }

    if (repetitiveQueryCount > 0) {
      improvements.push('Carefully check customer’s earlier messages before asking for details they have already supplied.');
    }

    if (totalTurns <= 4 && isResolved) {
      strengths.push('High turn efficiency: Resolved the inquiry promptly without unnecessary back-and-forth.');
    }

    return {
      csat,
      status,
      isResolved,
      totalTurns,
      empathyIndex,
      initialFrustration,
      peakFrustration,
      finalFrustration,
      deEscalationDelta,
      deEscalationSuccessful,
      inflectionPoints,
      coaching: {
        strengths,
        improvements
      },
      evaluationDate: new Date().toISOString()
    };
  }
}

module.exports = {
  EvaluationEngine
};

