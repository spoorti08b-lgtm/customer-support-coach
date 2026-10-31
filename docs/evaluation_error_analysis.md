# Knowledge Retrieval Evaluation: Error Analysis & Root Cause Study

**Module:** Knowledge Recommendation Agent (`backend.services.knowledge_agent`)
**Evaluation Dataset:** `data/evaluation/agent_eval_dataset.json` (22 labeled queries)
**Evaluation Results:** `data/evaluation/agent_eval_results.json`
**Evaluation Metric Suite:** `backend.evaluation.eval_metrics`
**Evaluator Runner:** `backend.evaluation.eval_runner`

---

## 1. Executive Summary

In the Knowledge Retrieval Benchmark, a comprehensive evaluation framework was designed and executed against the live local ChromaDB knowledge base (`data/chroma/`) using `SentenceTransformer('all-MiniLM-L6-v2')`.

The empirical evaluation of 22 realistic customer support queries yielded:
- **Information Retrieval (Answerable Queries, N=14):**
  - **Recall@3 (Doc-level):** 100.00%
  - **Recall@3 (Chunk-level):** 100.00%
  - **Precision@3 (Doc-level):** 33.33% (1 target document per query over $k=3$ retrieved items)
  - **Precision@3 (Chunk-level):** 38.09% (capturing multi-chunk policies where applicable)
  - **Mean Reciprocal Rank (MRR):** 1.0000 (Target document at Rank 1 for 100% of answerable queries)
  - **NDCG@3:** 1.0000 (Ideal ranking across all answerable queries)
  - **Source Attribution Accuracy:** 100.00%
- **Classification of Unanswerable Queries (N=8):**
  - **True Positives (TP):** 4 (All 4 out-of-domain queries rejected as `NO_MATCH`)
  - **False Positives (FP):** 0 (0 answerable queries falsely rejected)
  - **True Negatives (TN):** 14 (All 14 answerable queries correctly retrieved)
  - **False Negatives (FN):** 4 (All 4 in-domain unanswerable queries accepted as matches)
  - **No-Match Precision:** 100.00%
  - **No-Match Recall:** 50.00%
  - **No-Match F1-Score:** 66.67%
  - **Overall Classification Accuracy:** 81.82%
- **Retrieval Latency:**
  - **Median (p50):** 39.1 ms
  - **95th Percentile (p95):** 61.3 ms
  - **Mean:** 198.0 ms (including cold-start model weight initialization)

---

## 2. In-Depth Analysis of the Four False Negatives

The four false negative queries represent cases where the customer query is **in-domain** (asking about orders, returns, shipping, or payments), but the existing sample knowledge base **genuinely lacks supporting evidence**. In all four cases, the agent returned `status = "success"` instead of `NO_MATCH`.

### Case 1: `eval_19` — International Shipping Policy
- **Customer Message:** `"Do you ship internationally to Canada, Australia, or the UK?"`
- **Detected Intent:** `Delivery / order`
- **Contextual Query:** `Delivery / order - Do you ship internationally to Canada, Australia, or the UK?`
- **Top Retrieved Document:** `shipping_and_delivery.pdf` (Page 1)
- **Top Chunk ID & Score:** `e11e1dd62150604a_p1_c0` (Score: **0.3370**)
- **Retrieved Chunk Text:**
  > *"ACME GADGETS - SHIPPING AND DELIVERY (SAMPLE DATA) Delivery times Standard delivery takes 3 to 5 business days. Express delivery takes 1 to 2 business days and is available for orders placed before 2 pm. Remote areas can add up to 3 extra days. Tracking your order A tracking number is emailed when the parcel leaves the warehouse. Tracking can take up to 24 hours to show its first update."*
- **Why Agent Accepted:** $0.3370 \ge 0.20$ (threshold).
- **Does the Passage Support the Query?** **NO.** The document only describes domestic standard and express delivery options. International destinations (Canada, Australia, UK) are completely absent.
- **Root Cause:**
  1. *Lexical & Semantic Proximity:* The query contains "ship", "Delivery / order", which have high semantic similarity to "SHIPPING AND DELIVERY", "Delivery times", and "Standard delivery".
  2. *Absence of Knowledge:* The knowledge base does not define an international shipping policy. Dense bi-encoders map related topics together, even when the specific sub-topic is missing.

---

### Case 2: `eval_20` — In-Store Pickup & Physical Lockers
- **Customer Message:** `"Can I pick up my online order at a local retail store or physical locker?"`
- **Detected Intent:** `Delivery / order`
- **Contextual Query:** `Delivery / order - Can I pick up my online order at a local retail store or physical locker?`
- **Top Retrieved Document:** `account_and_password_faq.pdf` (Page 1)
- **Top Chunk ID & Score:** `40127cfe9c0a26e5_p1_c1` (Score: **0.3629**)
- **Retrieved Chunk Text:**
  > *"o unlock it after verifying the customer's name and order number."*
- **Second Retrieved Document:** `shipping_and_delivery.pdf` (`e11e1dd62150604a_p2_c0`, Score: **0.3160**)
- **Why Agent Accepted:** $0.3629 \ge 0.20$ (threshold).
- **Does the Passage Support the Query?** **NO.** Chunk `40127cfe9c0a26e5_p1_c1` is a 64-character text fragment about customer identity verification for account unlocking. It has zero information about physical lockers or retail pickup.
- **Root Cause:**
  1. *Fragment Chunk Artifact:* During ingestion chunking (`chunk_size=500, overlap=50`), `account_and_password_faq.pdf` page 1 text was split unevenly, creating a trailing 64-character chunk that happens to contain the words `"order number"`.
  2. *Keyword Collision:* The phrase `"online order"` matched `"order number"` in the small chunk, creating an artificially high cosine similarity ($0.3629$).

---

### Case 3: `eval_21` — Electronics Trade-In / Trade-Up Program
- **Customer Message:** `"Do you offer an electronics trade-in or trade-up program for old smartphones?"`
- **Detected Intent:** `Refund / billing`
- **Contextual Query:** `Refund / billing - Do you offer an electronics trade-in or trade-up program for old smartphones?`
- **Top Retrieved Document:** `returns_and_refunds.pdf` (Page 1)
- **Top Chunk ID & Score:** `a2ce9b7bd3c12470_p1_c0` (Score: **0.4760**)
- **Retrieved Chunk Text:**
  > *"ACME GADGETS - RETURNS AND REFUNDS POLICY (SAMPLE DATA) Return window Unused items can be returned within 30 days of delivery. Items must be in the original packaging with all accessories included. Software and gift cards cannot be returned once opened or redeemed. How refunds are issued Refunds go back to the original payment method within 5 to 7 business days after the warehouse receives the parcel. Shipping fees are refunded only when the item arrived damaged or was sent by mistake. Damaged o"*
- **Why Agent Accepted:** $0.4760 \ge 0.20$ (threshold).
- **Does the Passage Support the Query?** **NO.** The policy covers returning unused purchased merchandise for a refund. It contains no trade-in program, upgrade credit, or smartphone recycling policy.
- **Root Cause:**
  1. *High Category Similarity:* E-commerce returns, refunds, and trade-in programs share dense vector space clusters in `all-MiniLM-L6-v2`.
  2. *Intent Amplification:* Prepending `"Refund / billing - "` pushed the query vector even closer to `returns_and_refunds.pdf`, boosting cosine similarity to $0.4760$.

---

### Case 4: `eval_22` — Cryptocurrency Payment Methods
- **Customer Message:** `"Can I pay for my order using cryptocurrency like Bitcoin or Ethereum?"`
- **Detected Intent:** `Refund / billing`
- **Contextual Query:** `Refund / billing - Can I pay for my order using cryptocurrency like Bitcoin or Ethereum?"`
- **Top Retrieved Document:** `shipping_and_delivery.pdf` (Page 2)
- **Top Chunk ID & Score:** `e11e1dd62150604a_p2_c0` (Score: **0.2931**)
- **Second Document:** `returns_and_refunds.pdf` (`a2ce9b7bd3c12470_p1_c0`, Score: **0.2862**)
- **Why Agent Accepted:** $0.2931 \ge 0.20$ (threshold).
- **Does the Passage Support the Query?** **NO.** The passage discusses missing parcels and delivery address changes. The second passage discusses refunds issued to the original payment method. Neither specifies accepted payment methods.
- **Root Cause:**
  1. *Semantic Overlap:* "pay for my order" overlaps with order delivery and refund payment methods.
  2. *Missing Payment Policy Document:* Acme Gadgets' sample documentation does not include a payment methods FAQ or checkout policy.

---

## 3. Comparison with Correctly Rejected Queries (True Positives)

| Query ID | Customer Message | Contextual Query | Top Score | Top Document | Outcome |
|---|---|---|---|---|---|
| `eval_15` | "What is the boiling point of water at 3000 meters altitude?" | (no intent) | **0.0729** | None (filtered) | `NO_MATCH` ✅ |
| `eval_16` | "How do I tune the carburetor on a chainsaw engine?" | (no intent) | **0.0410** | None (filtered) | `NO_MATCH` ✅ |
| `eval_17` | "Who wrote the ancient Greek epic poems the Iliad and the Odyssey?" | (no intent) | **-0.0096** | None (filtered) | `NO_MATCH` ✅ |
| `eval_18` | "What is the current stock market price of Apple and Google shares?" | (no intent) | **0.0630** | None (filtered) | `NO_MATCH` ✅ |

### Why Did the True Positives Succeed While False Negatives Failed?

1. **Semantic Vector Distance:**
   Out-of-domain queries have zero lexical or semantic connection to customer support or e-commerce. Their embeddings are nearly orthogonal to the document embeddings, producing cosine similarity scores strictly below $0.10$. The threshold of $0.20$ cleanly and decisively eliminates them.
2. **The Bi-Encoder Entailment Boundary:**
   Dense bi-encoders (`SentenceTransformer`) project entire sentences into a shared metric space. They are optimized for **topical relevance** (i.e., "is this text about shipping?"), NOT **factual entailment** (i.e., "does this text state whether international shipping is available?").
   When a customer asks an unsupported shipping question, the text is genuinely about shipping, so the bi-encoder assigns a score $> 0.25$. Without an entailment model or cross-encoder, a bi-encoder cannot know that the specific answer is missing.

---

## 4. Metric Verification and Integrity Audit

1. **Zero Inflation via Deduplication:**
   `compute_recall_at_k` and `compute_precision_at_k` deduplicate retrieved results. If a document or chunk appears multiple times in the top $K$, it is counted exactly once.
2. **Standard IR Cutoff:**
   `compute_precision_at_k` divides strictly by $K=3$. For single-document targets, maximum precision is $1/3 \approx 0.3333$.
3. **No-Match Precision and Recall:**
   - Treating **unanswerable** as the positive class ($y=1$):
     - $\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}} = \frac{4}{4 + 0} = 100\%$ (When agent predicts `NO_MATCH`, it is always correct).
     - $\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}} = \frac{4}{4 + 4} = 50\%$ (Agent catches 4 of the 8 unanswerable queries).
     - $\text{F1} = 2 \cdot \frac{1.0 \cdot 0.5}{1.0 + 0.5} = 66.67\%$.
4. **Separation of Errors from No-Match:**
   `compute_no_match_metrics` only counts `status == "no_match"` as $\hat{y}=1$. An execution error (`status == "error"`) is tracked as an operational failure and is not conflated with a semantic `NO_MATCH`.

---

## 5. Recommended Improvements (Without Production Changes)

### Category A: Within Knowledge Recommendation Agent Scope (Evaluation & Agent Refinement)
1. **Dynamic Confidence Tiers:** Rather than a binary $\ge 0.20$ acceptance, introduce confidence tiers:
   - **High Confidence ($\ge 0.50$):** Passages directly address the query (observed in all 14 answerable queries).
   - **Low Confidence ($0.20 - 0.40$):** Passages are topically adjacent but may lack exact supporting evidence. Flag as `tentative` or `low_confidence` in metadata.
2. **Intent Prefix Calibration:** If an intent is broad (e.g. `Delivery / order`), prepending it can artificially inflate similarity for unanswerable queries (e.g., `eval_19`). Only prepend intent when the customer query is short ($< 5$ words) or ambiguous.
3. **Chunk Boundary Cleanup:** Re-chunking PDFs with a minimum chunk size threshold (e.g. discarding chunks $< 100$ characters) would eliminate orphan fragments like `40127cfe9c0a26e5_p1_c1` that produce spurious matches.

### Category B: Team-Level Architectural Options (Requires Team Agreement)
1. **Cross-Encoder / NLI Re-Ranking (Coaching Agent & Knowledge Recommendation Teams):**
   Add a lightweight cross-encoder or NLI model (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2`) to verify that the retrieved passage actually entails the customer's question before returning `SUCCESS`.
2. **Knowledge Base Expansion (Knowledge Base Engineering / Product):**
   Add a standard `company_policies_and_payments.pdf` to cover accepted payment methods, international shipping restrictions, and retail stores, converting unanswerable queries into fully answerable ones.
3. **Coaching Assistant Prompt Grounding (Coaching Agent / LLM Agent):**
   Ensure the LLM agent prompt instructs: *"If the retrieved knowledge passages do not explicitly mention international shipping or cryptocurrency, inform the customer that the policy is currently unavailable or requires escalation."*

---

## 6. Prioritized Action Plan

| Priority | Action | Owner | Impact |
|---|---|---|---|
| **P1** | Provide integration readiness documentation to Orchestrator Team and Streamlit Frontend Team | Knowledge Recommendation Agent | Enables end-to-end integration |
| **P2** | Recommend UI handling for scores between $0.20$ and $0.40$ (displaying "Low relevance" indicator) | Streamlit Frontend & 7 | Transparently communicates uncertainty to the agent coach |
| **P3** | Clean up chunking logic in ingestion pipeline to prevent tiny fragment chunks ($< 100$ chars) | Core Data Models Team & 7 | Prevents spurious single-phrase matches like `eval_20` |
| **P4** | Evaluate Cross-Encoder re-ranking in Milestone 3 | Team | Solves topical vs entailment mismatch |
