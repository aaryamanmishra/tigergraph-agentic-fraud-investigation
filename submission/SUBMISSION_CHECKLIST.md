# FraudNet — Final Hackathon Submission Checklist

*Hacker House Goa 2026 — TigerGraph Agentic Fraud Investigation Challenge*

---

## 1. Repository & Codebase (Automated Checks Verified)

- [x] **Core Backend Protected:** `src/agent/`, `src/graph/`, `src/policy/`, `src/rag/` intact and untampered.
- [x] **Test Suite Passing:** All 126 automated unit and regression tests pass (`.venv/bin/python -m pytest tests/ -q` → 126 passed).
- [x] **Investigation Control Room UI:** Flask web console verified across all routes (`/`, `/case/HHG-001`, `/case/HHG-014`, `/benchmark`, `/api/*`).
- [x] **D3 Interactive Graph:** Force-directed entity graph renders smoothly with node selection and evidence highlighting.
- [x] **Deterministic PolicyEngine:** Rules R1–R10 enforced with exact approval routes (AUTO/L1/L2).
- [x] **Schema Validation:** All output generation strictly adheres to `docs/answer_schema.md` and Pydantic validation.
- [x] **Entity Integrity:** Zero hallucinations across 631,219 ground-truth dataset entities (`evaluation/check_integrity.py`).
- [x] **Python Compilation:** `python -m py_compile ui/app.py` passes with zero syntax errors.
- [x] **Git Cleanliness:** `git diff --check` passes with zero whitespace or line-ending anomalies.

---

## 2. 20 Benchmark Answer Files

- [x] **Canonical Files Present:** `results/groq_tigergraph/HHG-001.json` through `HHG-020.json` present and validated.
- [x] **Submission Export Populated:** `submission/answers/` contains 20 byte-identical copies of canonical outputs.
- [x] **Submission Documentation:** `submission/README.md` documents schemas, generation methodology, and replay transparency.
- [x] **Full 20-Case Verification:** 20/20 files pass both `validate_case_answer` and `check_case_integrity`.
- [x] **Required Invariants Checked:**
  - Case records with verdicts, probabilities, and patterns.
  - Affected transactions, connected cards, and device profiles where applicable.
  - Initial and final next-best actions with approval routes.
  - Mandatory SAR filings with justifications and narratives where required.
  - TigerGraph writeback status accurately reported.

---

## 3. Submission Documentation & Assets

- [x] **Technical Blog Draft:** Written and verified in `docs/technical_blog.md`.
- [x] **Demo Video Script:** Written and timed (3–5 minutes) in `docs/demo_script.md`.
- [x] **Social Media Drafts:** Prepared for X and LinkedIn in `docs/social_post.md` (tagging `@TigerGraphDB`).
- [x] **Root README:** Up to date with architecture, quick start, real benchmark statistics, and UI documentation.
- [x] **Environment Template:** `.env.example` created with placeholders only (no secrets).

---

## 4. Human / External Actions (To Be Completed Before Submitting)

- [ ] **Rotate Real API Keys:**
  - Rotate TigerGraph Cloud secrets, Groq keys, Gemini keys, or Mistral keys stored in local `.env` before sharing any archives.
- [ ] **Publish Technical Blog Post:**
  - Publish `docs/technical_blog.md` on Medium, Substack, Dev.to, or company engineering blog.
  - Copy published blog URL into submission form and social posts.
- [ ] **Record & Upload Demo Video:**
  - Follow `docs/demo_script.md` using the live Flask UI at `http://127.0.0.1:5000`.
  - Target runtime: 3:30 – 4:30 minutes.
  - Upload to YouTube (Public / Unlisted) or Loom.
  - Copy video link into submission form and social posts.
- [ ] **Publish Social Post:**
  - Post the X thread and/or LinkedIn post from `docs/social_post.md`.
  - Ensure `@TigerGraphDB` is tagged.
  - Copy post link into submission form.
- [ ] **Final Git Commit & Push:**
  ```bash
  git add README.md .env.example submission/ docs/
  git commit -m "docs: final hackathon submission package"
  git push origin main
  ```
- [ ] **Submit Official Form:**
  - Repository URL: `https://github.com/aaryamanmishra/tigergraph-agentic-fraud-investigation`
  - Demo Video URL: `[INSERT URL]`
  - Technical Blog URL: `[INSERT URL]`
  - Social Post URL: `[INSERT URL]`
  - 20 Answer Files: confirm hosted in `submission/answers/` on GitHub `main` branch.
