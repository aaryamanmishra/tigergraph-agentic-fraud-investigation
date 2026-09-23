# FraudNet: Video Demonstration Script (3–5 Minutes)

*Video Demo Guide for Hacker House Goa 2026 — TigerGraph Agentic Fraud Challenge*

---

## Video Specifications
- **Target Duration:** 3:30 – 4:30 minutes
- **Resolution:** 1080p (1920x1080) or 4K
- **UI Base URL:** `http://127.0.0.1:5000`
- **Presenting Case:** `HHG-014` (primary fraud hero) and `HHG-001` (legitimate hero contrast)

---

## Step-by-Step Script & Visual Walkthrough

### [0:00 – 0:35] Scene 1: The Hook & Overview
- **Visual:** Browser showing the **FraudNet Investigation Control Room** landing on `http://127.0.0.1:5000/case/HHG-014`.
- **Speaker:**
  > "Hello everyone! This is **FraudNet**, an autonomous, graph-native fraud investigation agent built for the Hacker House Goa 2026 TigerGraph Challenge.
  >
  > In traditional banking, fraud pipelines end when an ML model assigns a risk score. But a score isn't a verdict. An alert requires investigating: traversing multi-hop card relationships, checking device infrastructure, assessing uncertainty, applying regulatory policy, and filing statutory reports.
  >
  > FraudNet replaces manual analyst triage with an agentic workflow powered by TigerGraph, TigerGraph MCP, GraphRAG, and deterministic policy enforcement."

---

### [0:35 – 1:15] Scene 2: Case HHG-014 — Trigger & The TigerGraph Evidence Graph
- **Visual:** Zoom in on the top header of HHG-014 (`Analyst request`, flagged transaction `3478561`, card `C13487-K1`, exposure `$74.96`), then scroll down to the **Interactive TigerGraph Evidence Graph** panel. Click and drag a few nodes. Click on the device node (`SM-G935F`).
- **Speaker:**
  > "Let's look at our first hero case: **HHG-014**.
  >
  > The trigger arrived not from an automated score, but as an analyst alert on transaction 3478561 for $74.96 on card C13487-K1. The analyst noted an unusual device profile.
  >
  > The agent immediately invoked the official **TigerGraph MCP interface** to traverse the graph. 
  > 
  > Look at this interactive D3 evidence graph rendered here. When the agent queried `get_device_neighbors`, it uncovered that this Android device fingerprint is shared across **34 distinct payment cards**! What looked like an isolated $74 transaction is actually a coordinated multi-card syndicate attack."

---

### [1:15 – 1:55] Scene 3: GraphRAG Case Memory & Grounded Evidence
- **Visual:** Scroll to the **Reconstructed Agent Activity Trace**, then down to the **GraphRAG Case Memory** section showing closed cases `CC-2985`, `CC-3035`, `CC-2649`, and `CC-2971`.
- **Speaker:**
  > "Next, FraudNet's **GraphRAG engine** kicked in.
  >
  > Before prompting our LLM reasoning layer, GraphRAG traversed historical investigations in TigerGraph and retrieved four relevant closed cases — including Case CC-2985 — where this same syndicate infrastructure had operated previously.
  >
  > In the Activity Trace, notice how every finding has strict provenance. Every entity ID — transaction, card, customer, and device — is checked against a 631,000-entity registry to completely eliminate hallucination."

---

### [1:55 – 2:35] Scene 4: Uncertainty, The Evidence Loop, and PolicyEngine Gate
- **Visual:** Scroll to the **Uncertainty & Decision Confidence** panel, then to the **Evidence Request / Reassessment** block, and then highlight the **PolicyEngine Gate** (LLM Recommendation vs. Enforced Policy).
- **Speaker:**
  > "Notice our uncertainty handling. Initially, with single-transaction visibility, the agent placed the transaction in an evidence loop, recommending `VERIFY_WITH_CUSTOMER`. 
  >
  > But once the device graph traversal returned the 34-card syndicate cluster, the fraud probability surged to **95.0%**, reducing uncertainty to **LOW**.
  >
  > Now look at the **PolicyEngine Gate**. We do NOT allow the LLM to make autonomous regulatory actions. The LLM recommended creating a case, but our deterministic PolicyEngine evaluated the statutory bank rules:
  > - **Rule R6** for shared-device coordinated attacks.
  > - **Rule R9** for undocumented syndicate abuse.
  > 
  > The PolicyEngine upgraded the action set to mandate `CREATE_CASE`, `FILE_REPORT`, `ESCALATE_TO_ANALYST`, and `MONITOR_CONNECTED_CARDS`. 
  > 
  > Furthermore, because coordinated syndicate abuse was proven, the system generated a FinCEN-compliant **Suspicious Activity Report (SAR)** with full narrative justification."

---

### [2:35 – 3:15] Scene 5: Case Persistence & The 20-Case Benchmark Dashboard
- **Visual:** Point to the badge `Written to TigerGraph: Yes` (Graph Case ID `HHG-014`). Then click the **Benchmark Dashboard** link in the top nav to open `http://127.0.0.1:5000/benchmark`. Scroll through the **20-Case Investigation Matrix**.
- **Speaker:**
  > "Before finishing, the agent called TigerGraph's `write_case` tool to persist this closed case back to the graph, becoming instant memory for future investigations.
  >
  > Now let's visit the **Benchmark Dashboard**. 
  >
  > FraudNet evaluated all 20 Hacker House Goa exam cases against live TigerGraph Cloud and Groq's LLM endpoint. 
  > 
  > All 20 cases passed 100% schema validation and entity integrity checks. Across the benchmark, the agent identified 18 confirmed frauds, 2 legitimate transactions, executed 16 controlled evidence loops, filed 10 statutory SARs, and protected $3,515 in exposure at an average execution latency of 30 seconds."

---

### [3:15 – 3:55] Scene 6: The Contrast — Case HHG-001 (Legitimate Travel)
- **Visual:** Click on `HHG-001` in the 20-case matrix (or navigate to `/case/HHG-001`). Show the green **LEGITIMATE** badge, 5.0% fraud probability, and final action `CLOSE_NO_FRAUD`.
- **Speaker:**
  > "To see how FraudNet avoids false-positive disruption, look at **Case HHG-001**.
  >
  > Here, the automated model scored transaction 3514030 at 0.61 — a high risk score for an unfamiliar billing region.
  >
  > A naive system would have blocked the card. FraudNet saw that the transaction was in-person, checked customer history, initiated an evidence request to the cardholder, and received confirmation that the customer was traveling.
  >
  > The PolicyEngine applied **Rule R3**, calibrated fraud probability down to 5.0%, and executed `CLOSE_NO_FRAUD` with zero customer friction."

---

### [3:55 – 4:20] Scene 7: Conclusion
- **Visual:** Return to the top of `/benchmark` or GitHub repository page.
- **Speaker:**
  > "FraudNet demonstrates that graph technology and agentic reasoning belong together. TigerGraph provides the ground-truth relationship structure that prevents hallucination, while agentic LLMs provide adaptive synthesis and auditability.
  >
  > All 20 validated answer files, the full 126-test suite, and complete documentation are live in our repository. Thank you!"

---

## Presentation Checklist
- [ ] Local Flask server running: `cd ui && ../.venv/bin/python app.py`
- [ ] Browser zoomed to ~110% for crisp readability.
- [ ] Test client navigates smoothly between `/case/HHG-014`, `/benchmark`, and `/case/HHG-001`.
- [ ] Recording audio is clear with zero background noise.
