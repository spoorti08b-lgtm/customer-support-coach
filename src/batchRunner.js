/**
 * Automated Batch Benchmark Runner
 * Benchmarks agent scripts or LLM policies against diverse customer personas and scenarios.
 */

const { DEFAULT_PERSONAS } = require('./data/personas');
const { DEFAULT_SCENARIOS } = require('./data/scenarios');
const { CustomerSimulatorAgent } = require('./simulator');

// Two sample agent strategies for automated testing:
const AGENT_STRATEGIES = {
  // Defensive / Policy-heavy agent strategy
  defensive_agent: [
    "Thank you for contacting support. Can you please state your full name and order number?",
    "I understand, but per company policy section 4.2, all sales are final once delivered.",
    "Unfortunately there is nothing more I can do. Please wait 10-14 business days for email review."
  ],
  // Empathetic, direct-action agent strategy
  empathetic_agent: [
    "I am so sorry to hear this happened! That is completely unacceptable, and I will personally get this resolved for you right now.",
    "I have pulled up your order details right here on my screen. I see the damaged ceramic espresso set.",
    "I have just processed a full refund of $149.99 directly back to your original payment method, and there is no need to return the broken shards. Once again, I am truly sorry for the trouble."
  ]
};

async function runBenchmark() {
  console.log(`=======================================================`);
  console.log(`🧪 CUSTOMER SIMULATOR BENCHMARK: BATCH EVALUATION`);
  console.log(`=======================================================\n`);

  const results = [];

  for (const [strategyName, script] of Object.entries(AGENT_STRATEGIES)) {
    console.log(`▶ Running Strategy: ${strategyName.toUpperCase()}`);
    
    for (const persona of DEFAULT_PERSONAS.slice(0, 3)) { // test first 3 personas
      const scenario = DEFAULT_SCENARIOS[0]; // damaged_delivery
      
      const simulator = new CustomerSimulatorAgent({
        persona,
        scenario,
        provider: 'local'
      });

      for (const msg of script) {
        if (simulator.currentState.status !== 'active') break;
        await simulator.processAgentMessage(msg);
      }

      const evalResult = simulator.evaluate();
      results.push({
        strategy: strategyName,
        persona: persona.name,
        personaRole: persona.role,
        status: evalResult.status,
        csat: evalResult.csat,
        isResolved: evalResult.isResolved,
        finalFrustration: evalResult.finalFrustration,
        initialFrustration: evalResult.initialFrustration,
        deEscalation: evalResult.deEscalationDelta,
        empathyIndex: evalResult.empathyIndex
      });

      console.log(`   Customer: ${persona.avatar} ${persona.name.padEnd(16)} | Status: ${evalResult.status.padEnd(10)} | CSAT: ${evalResult.csat}⭐ | Frustration: ${evalResult.initialFrustration}% ➡️ ${evalResult.finalFrustration}%`);
    }
    console.log('');
  }

  console.log(`=======================================================`);
  console.log(`📊 BENCHMARK SUMMARY TABLE`);
  console.log(`=======================================================`);
  console.table(results);
  return results;
}

if (require.main === module) {
  runBenchmark().catch(console.error);
}

module.exports = { runBenchmark };

