# AI Document Screening System — Team Build Guide
**SIH 2026 | Repo: `Div-yan5h/ai-document-screening`**

This is the one document everyone reads before touching code. It tells you what the system does, what your job is, exactly what to paste into your ChatGPT and Antigravity, and what you're never allowed to touch. If you follow this, five people can build in parallel without breaking each other's work.

---

## 0. Read This First — The One Rule That Matters

We have **one frozen file**: `backend/app/schemas/contracts.py`.

Think of it like a plug socket standard. Every module is an appliance — as long as it has the right plug shape (the contract), it doesn't matter what's happening inside the appliance. You can build your module however you want internally. But the plug — what goes in, what comes out — is fixed. **Nobody edits this file alone.** If you think it needs to change, you stop and bring it to Div (who reviews it with Claude, the project architect) before writing any code around the change.

This single rule is what lets 5 people work at the same time without merge hell.

---

## 1. The Big Picture (everyone must understand this, not just your own piece)

We're building a system that takes a document photo + a live selfie, and tells a border officer: *is this person who they claim to be, and is the document real?*

The pipeline:

```
Upload (doc photo + live photo)
   ↓
M1  Ingestion          → cleans up the images
   ↓
M2  Classifier         → figures out: passport? visa? ID card?
   ↓
M3  OCR                → reads the text off the document
   ↓
   ┌─────────────┬─────────────┬─────────────┐
   M4 MRZ         M5 Rules       M6 Tamper       (these 3 run off M3's output,
   (passport code)  (expired?     (was it         can happen in parallel)
                     valid dates?)  edited?)
   └─────────────┴─────────────┴─────────────┘
   ↓                                              ┌─────────────┐
   M7 Face Verification ──────────────────────────┤  M8 Database │  (also parallel
   (does selfie match doc photo?)                  │  (blacklist  │   with each other)
                                                    │  check)      │
                                                    └─────────────┘
   ↓
M9  Risk Engine         → combines every signal above into one score (0–100) + reasons
   ↓
Frontend / Officer Dashboard → officer sees the score, the "why", and clicks Approve/Deny/Escalate
```

Every arrow above is a **contract** — a fixed JSON shape. As long as your module's output matches its contract exactly, it plugs into the pipeline correctly, guaranteed.

**Why everyone needs to understand the whole thing, not just their box:** if you don't know what M5 actually needs from you, you'll build something technically "correct" that's useless downstream. Read section 1 twice if you have to. It's 5 minutes now vs. hours of integration pain later.

---

## 2. Repo Setup (Div does this once, before anyone starts)

- [x] GitHub repo created: `Div-yan5h/ai-document-screening` (private)
- [x] Folder structure created (`backend/app/modules/m1_ingestion` through `m9_risk_engine`, `orchestrator/`, `frontend/`)
- [x] `contracts.py` written and frozen — all 9 Pydantic models validated
- [x] `TECH_STACK.md` committed
- [x] Walking skeleton built and tested (stub versions of every module wired end-to-end through the orchestrator, all tests passing)
- [ ] Add all 5 developers as collaborators on GitHub
- [ ] Everyone clones the repo and confirms they can run the existing stub pipeline locally before writing any real code

**Branches:** nobody commits directly to `main`. Each person works on their own branch:

| Person | Branch |
|---|---|
| P1 | `feature/p1-ingestion` |
| P2 | `feature/p2-classifier-ocr` |
| P3 | `feature/p3-integrity` |
| P4 | `feature/p4-identity-db` |
| P5 | `feature/p5-risk-frontend` |

Merge into `main` via Pull Request. P1, as platform lead, does the final integration merges.

---

## 3. Who Owns What

| Person | Owns | Module folder(s) |
|---|---|---|
| **P1 — Platform Lead** | M1 Ingestion + the Orchestrator + FastAPI `main.py` | `m1_ingestion/`, `orchestrator/`, `main.py` |
| **P2 — Document Understanding** | M2 Classifier + M3 OCR | `m2_classifier/`, `m3_ocr/` |
| **P3 — Document Integrity** | M4 MRZ + M5 Rule Validation + M6 Tamper Detection | `m4_mrz/`, `m5_rules/`, `m6_tamper/` |
| **P4 — Identity & Records** | M7 Face Verification + M8 DB/Blacklist Check | `m7_face/`, `m8_db/` |
| **P5 — Risk & Frontend** | M9 Risk Engine + entire Next.js frontend | `m9_risk_engine/`, `frontend/` |
| **P6 — UI/UX Designer** | Figma only — no code | (none — hands designs to P5) |

**Hard rule:** you only ever write files inside your own folder(s). If you think you need to touch someone else's folder, stop — that's a sign the contract needs adjusting, which goes through Div → Claude first, not a quick fix on your own.

---

## 4. The Golden Workflow — How Everyone Works, Every Day

This is the loop you repeat for every single task, big or small:

```
1. You read the Build Spec section for YOUR module
        ↓
2. You open a chat with YOUR ChatGPT (using the exact prompt in Section 6 below)
        ↓
3. Your ChatGPT breaks your module into small tasks and gives Antigravity ONE task at a time
        ↓
4. Antigravity implements that one task and reports back what it changed
        ↓
5. Your ChatGPT checks the report against the Build Spec + the frozen contract
   (does NOT just trust Antigravity's word for it — it actually verifies)
        ↓
6. If correct → move to the next task
   If wrong → your ChatGPT tells Antigravity exactly what to fix, and you repeat step 4
        ↓
7. Repeat until your module is fully built
        ↓
8. At meaningful milestones, your ChatGPT writes a short status report → Div sends it to Claude (project architect) for a system-level check
```

**Why this matters:** Antigravity is fast but doesn't know the big picture — it just does what it's told. Your ChatGPT is the one holding the actual spec and contract in its head and checking Antigravity's work against it, task by task. If you skip the "ChatGPT reviews the report" step and just let Antigravity keep going, small mistakes compound and you won't find them until integration day — which is the worst possible time to find them.

---

## 5. What NOT to Touch — Ever

- ❌ `backend/app/schemas/contracts.py` — frozen. Don't add fields, don't rename fields, don't change types, even "just to make my module simpler." If it's genuinely blocking you, that's a real conversation with Div/Claude, not a quiet edit.
- ❌ Anyone else's module folder.
- ❌ `orchestrator/pipeline.py` and `main.py` — P1 only.
- ❌ Committing straight to `main`.
- ❌ Letting Antigravity "helpfully" refactor something outside your assigned folder because it noticed something it didn't like. Antigravity does exactly what your ChatGPT tells it to, one scoped task at a time — nothing more.

If Antigravity's report mentions it touched a file outside your folder, that's an automatic reject — have it revert and redo the task scoped correctly.

---

## 6. Your Module, Your Prompt

Below is everything you personally need. Find your name, read your module's job in plain language, then **copy the "ChatGPT Reviewer Prompt" block exactly as-is** into a new ChatGPT conversation to get started. Attach the Build Spec file to that same conversation first.

---

### P1 — Platform Lead (M1 + Orchestrator + FastAPI)

**In plain language:** You're the plumbing. M1 takes the two uploaded photos and cleans them up (straightens, denoises, sharpens contrast) so every module downstream gets a decent image to work with. The Orchestrator is the traffic controller — it calls every other person's module in the right order and hands outputs to inputs. `main.py` is the actual web server that accepts the officer's upload and returns the final result.

**You receive:** raw uploaded files (document photo, live photo) via `POST /screen`.
**You return (M1):** `IngestionOutput` — session ID, path to the cleaned-up document image, path to the live photo, an optional guess at doc type.
**You also own:** wiring every other module's `run()` function together in the right order (see the pipeline diagram in Section 1), including running M4/M5/M6 in parallel and M7/M8 in parallel where possible.

**Already done:** stub versions of everything are wired and tested end-to-end (the walking skeleton). Your job now is to replace the M1 stub with the real OpenCV preprocessing, and to swap in everyone else's real modules as they land — one at a time, re-testing after each swap.

<details>
<summary><b>ChatGPT Reviewer Prompt — copy this exactly</b></summary>

```
You are the technical lead and reviewer for M1 (Ingestion & Preprocessing) AND the
Orchestrator/FastAPI layer in a 5-person software project.

Read the attached Build Spec completely before doing anything.

Your responsibility is M1 (ingestion), the orchestrator (pipeline.py), and main.py
(FastAPI). You do not directly implement code. Antigravity is the developer that
will modify the repository and write code based on your instructions.

Your job is to:
1. Understand the entire system and how M1/orchestrator sit at the front and the
   integration point of the pipeline.
2. Break your work into small, clear implementation tasks (real OpenCV
   preprocessing for M1: grayscale, deskew, denoise, CLAHE contrast).
3. Give Antigravity precise instructions for ONE task at a time.
4. After Antigravity completes a task, carefully review its report and the
   changed code/files.
5. Check the implementation follows the Build Spec and the frozen I/O contracts
   exactly — M1 must produce exactly IngestionOutput as defined in contracts.py.
6. Never modify contracts.py or another person's module folder.
7. As real M2-M9 modules land from other developers, your job is to swap them
   into the orchestrator ONE AT A TIME, replacing the matching stub, and re-run
   the full end-to-end pipeline test after each swap before moving to the next.
8. If something is wrong, explain the problem and give Antigravity a specific
   correction task. If correct, move to the next task.
9. Keep the orchestrator compatible with asyncio.gather() for the M4/M5/M6
   parallel group and the M7/M8 parallel group, as described in the Build Spec.

Do NOT blindly trust Antigravity's report. Verify its work against the Build Spec.
Do NOT redesign the architecture yourself. If the frozen contract or architecture
needs to change, stop and explain the issue rather than changing it.

You should always know: what M1/orchestrator receive and return, which modules
are real vs. still stubbed, what's already implemented, and what the next
smallest useful task is.

When starting, first give me:
A. Your understanding of M1 and the orchestrator's job
B. Inputs and outputs for M1
C. The implementation stages (M1 real logic first, then module swap-in order)
D. The first Antigravity task

After each Antigravity report, review it and decide: approve and give the next
task, or reject and give a correction task.

Periodically, at a meaningful milestone (M1 real logic done, each module swap
completed, full real pipeline working), prepare a concise status report for
Claude, the overall project architect.
```
</details>

---

### P2 — Document Understanding (M2 Classifier + M3 OCR)

**In plain language:** M2 looks at the document and decides what it is — passport, visa, or ID card. M3 actually reads the text off it — the name, date of birth, document number, etc. Think of M2 as "what kind of form is this" and M3 as "now fill in the blanks by reading it."

**M2 receives:** the cleaned image from M1. **M2 returns:** `ClassifierOutput` — doc type + confidence.
**M3 receives:** the cleaned image + M2's doc type. **M3 returns:** `OCROutput` — a dictionary of fields (name, dob, doc_number, expiry_date, nationality, issue_date), a confidence per field, and the raw OCR text.

**Fallback safety net (important):** if your classifier doesn't train well in time, have a hardcoded rule-based fallback ready (e.g. aspect ratio + MRZ-like text block near the bottom = passport) so the pipeline never hard-fails on a bad classification.

<details>
<summary><b>ChatGPT Reviewer Prompt — copy this exactly</b></summary>

```
You are the technical lead and reviewer for M2 (Document Classifier) AND M3
(OCR) in a 5-person software project.

Read the attached Build Spec completely before doing anything.

Your responsibility is ONLY M2 and M3. You do not directly implement the code.
Antigravity is the developer that will modify the repository and write the
code based on your instructions.

Your job is to:
1. Understand the entire system and how M2 and M3 fit into it (M2 feeds M3 and
   M9; M3 feeds M4, M5, M6, and M9).
2. Break M2 and M3 into small, clear implementation tasks. Build M2 first
   (M3 needs M2's doc_type as an input), then M3.
3. Give Antigravity precise instructions for ONE task at a time.
4. After Antigravity completes a task, carefully review its report and, when
   available, the changed code/files.
5. Check that the implementation follows the Build Spec and the frozen I/O
   contracts. M2 must produce exactly ClassifierOutput; M3 must produce
   exactly OCROutput.
6. Confirm M2 has a safe fallback path if classifier confidence is low
   (return "unknown" rather than forcing a wrong label) and a rule-based
   fallback if the trained model isn't ready in time.
7. Never modify contracts.py or another person's module.
8. If something is wrong, explain the problem and give Antigravity a specific
   correction task. If correct, move to the next task.
9. Keep M2 and M3 compatible with the orchestrator and the other modules.

Do NOT blindly trust Antigravity's report. Verify its work against the Build
Spec. Do NOT redesign the architecture yourself. If you believe the frozen
contract or architecture must change, stop and explain the issue rather than
changing it.

You should always know: what M2 and M3 are supposed to do, what they receive,
what they must return, what modules depend on them, what's already
implemented, and what the next smallest useful task is.

When starting, first give me:
A. Your understanding of M2 and M3
B. Their inputs and outputs
C. The implementation stages (M2 stages, then M3 stages)
D. The first Antigravity task

After each Antigravity report, review it and decide: approve and give the
next task, or reject and give a correction task.

Periodically, at a meaningful milestone (M2 complete, M3 complete, both
integrated and tested together), prepare a concise status report for Claude,
the overall project architect.
```
</details>

---

### P3 — Document Integrity (M4 MRZ + M5 Rules + M6 Tamper)

**In plain language:** All three of your modules answer "is this document internally consistent and untouched?" M4 reads the little machine-readable code strip at the bottom of passports/IDs and cross-checks it against what M3 read visually — they should match. M5 checks the logic (is it expired? do the dates make sense?). M6 checks for signs of digital editing (was a photo swapped, was text pasted in?).

**M4 receives:** cleaned image + M3's OCR output. **M4 returns:** `MRZOutput` — whether an MRZ was found, its fields, checksum validity, and a match/mismatch flag per field against the OCR.
**M5 receives:** OCR fields + MRZ output (prefer MRZ when valid — it's more reliable). **M5 returns:** `RuleValidationOutput` — is it expired, is the format valid, is it logically consistent, plus a list of plain-English flags.
**M6 receives:** cleaned image + OCR output. **M6 returns:** `TamperOutput` — a 0–1 suspicion score, flagged regions, and the three underlying signal scores (ELA, copy-move, font inconsistency).

**Important wording rule:** M6 only ever reports "suspicion," never "confirmed tampering" — it's a heuristic, not proof.

<details>
<summary><b>ChatGPT Reviewer Prompt — copy this exactly</b></summary>

```
You are the technical lead and reviewer for M4 (MRZ Parser + Cross-Check),
M5 (Rule Validation), and M6 (Tamper Detection) in a 5-person software
project.

Read the attached Build Spec completely before doing anything.

Your responsibility is ONLY M4, M5, and M6. You do not directly implement the
code. Antigravity is the developer that will modify the repository and write
the code based on your instructions.

Your job is to:
1. Understand the entire system and how M4/M5/M6 fit into it — all three
   consume M3's OCR output and feed into M9's risk engine, and can be built
   and can run in parallel with each other.
2. Break M4, M5, and M6 into small, clear implementation tasks.
3. Give Antigravity precise instructions for ONE task at a time.
4. After Antigravity completes a task, carefully review its report and, when
   available, the changed code/files.
5. Check that the implementation follows the Build Spec and the frozen I/O
   contracts exactly: M4 must produce MRZOutput, M5 must produce
   RuleValidationOutput, M6 must produce TamperOutput.
6. Confirm M4 handles documents with no MRZ zone gracefully (mrz_present =
   false, skip cross-check, never crash the pipeline).
7. Confirm M5's flags are written as full plain-English sentences (they feed
   the officer's "why" display directly), not error codes.
8. Confirm M6 only ever labels findings as "suspicion," never "confirmed
   tampering," and that its three signals (ELA, copy-move, font
   inconsistency) are documented and combined in a simple, explainable way.
9. Never modify contracts.py or another person's module.
10. If something is wrong, explain the problem and give Antigravity a specific
    correction task. If correct, move to the next task.

Do NOT blindly trust Antigravity's report. Verify its work against the Build
Spec. Do NOT redesign the architecture yourself. If you believe the frozen
contract or architecture must change, stop and explain the issue rather than
changing it.

You should always know: what M4, M5, M6 are supposed to do, what they
receive, what they must return, what depends on them, what's already
implemented, and what the next smallest useful task is.

When starting, first give me:
A. Your understanding of M4, M5, and M6
B. Their inputs and outputs
C. The implementation stages for each
D. The first Antigravity task

After each Antigravity report, review it and decide: approve and give the
next task, or reject and give a correction task.

Periodically, at a meaningful milestone (each module complete, all three
integrated and tested together), prepare a concise status report for Claude,
the overall project architect.
```
</details>

---

### P4 — Identity & Records (M7 Face Verification + M8 DB/Blacklist)

**In plain language:** M7 answers "is the person in the live selfie the same person as the document photo?" M8 answers "does this document number show up in our records as blacklisted, or is it clean?"

**M7 receives:** cleaned document image + live photo from M1. **M7 returns:** `FaceVerificationOutput` — similarity score (0–1), a match band (confident_match / review / likely_mismatch), and a liveness flag (null if not implemented).
**M8 receives:** the document number (prefer MRZ value if valid, else OCR value). **M8 returns:** `DBCheckOutput` — status (clean / blacklisted / watchlist / not_found / db_unavailable) and optional record metadata.

**Two things you must get right:**
- Tune your face-match thresholds against your own test images before the demo — don't ship the first numbers you guess.
- `not_found` must never quietly become `clean` — absence of a record isn't proof of innocence. Same for DB failures: wrap the query in try/except and return `db_unavailable` explicitly, never let a failure silently pass as clean.

<details>
<summary><b>ChatGPT Reviewer Prompt — copy this exactly</b></summary>

```
You are the technical lead and reviewer for M7 (Face Verification) AND M8
(DB/Blacklist Check) in a 5-person software project.

Read the attached Build Spec completely before doing anything.

Your responsibility is ONLY M7 and M8. You do not directly implement the
code. Antigravity is the developer that will modify the repository and write
the code based on your instructions.

Your job is to:
1. Understand the entire system and how M7/M8 fit into it — both feed M9's
   risk engine and can be built/run in parallel with each other and with
   M4/M5/M6.
2. Break M7 and M8 into small, clear implementation tasks.
3. Give Antigravity precise instructions for ONE task at a time.
4. After Antigravity completes a task, carefully review its report and, when
   available, the changed code/files.
5. Check that the implementation follows the Build Spec and the frozen I/O
   contracts exactly: M7 must produce FaceVerificationOutput, M8 must
   produce DBCheckOutput.
6. Confirm M7's similarity-to-band thresholds are tuned against real test
   images, not left as unverified guesses, before being treated as final.
7. Confirm M8 never defaults an unfound record to "clean" (must return
   "not_found") and never lets a DB connection failure silently resolve to
   "clean" (must return "db_unavailable" explicitly, wrapped in try/except).
8. Confirm the MongoDB seed data is clearly synthetic (mix of clean/expired/
   blacklisted fake records) — never real personal data.
9. Never modify contracts.py or another person's module.
10. If something is wrong, explain the problem and give Antigravity a
    specific correction task. If correct, move to the next task.

Do NOT blindly trust Antigravity's report. Verify its work against the Build
Spec. Do NOT redesign the architecture yourself. If you believe the frozen
contract or architecture must change, stop and explain the issue rather than
changing it.

You should always know: what M7 and M8 are supposed to do, what they
receive, what they must return, what depends on them, what's already
implemented, and what the next smallest useful task is.

When starting, first give me:
A. Your understanding of M7 and M8
B. Their inputs and outputs
C. The implementation stages for each
D. The first Antigravity task

After each Antigravity report, review it and decide: approve and give the
next task, or reject and give a correction task.

Periodically, at a meaningful milestone (each module complete, both
integrated and tested together), prepare a concise status report for Claude,
the overall project architect.
```
</details>

---

### P5 — Risk & Frontend (M9 Risk Engine + Next.js Frontend)

**In plain language:** M9 is the module that adds everything up — it takes every other module's output and turns it into one final number (0–100) plus a plain-English explanation of why. The frontend is what the officer actually sees and clicks: upload screen, results screen with the score and the "why," and Approve/Deny/Escalate buttons.

**You are the busiest role on the team** — you own the module that depends on everyone else's real output, *and* the entire UI. Don't wait around for other modules or for P6's Figma handoff to finish. Build M9's wiring and a rough frontend shell against fake/mocked outputs that match the contracts, starting immediately. Swap in real data and the real Figma design later.

**M9 receives:** the outputs of M5 (rules), M6 (tamper), M7 (face), M8 (DB) — plus M2/M3/M4 for context. **M9 returns:** `RiskEngineOutput` — a risk_score (0-100), a risk_band (low/medium/high), a reasons list, and a contributions breakdown per signal (this feeds the officer's "why" panel directly, so keep the math traceable).

**Starting weights** (tune and justify, don't leave unexplained): blacklist_hit 0.30, expired 0.20, ocr_mrz_mismatch 0.20, face_mismatch 0.20, tamper_suspicion 0.10.

<details>
<summary><b>ChatGPT Reviewer Prompt — copy this exactly</b></summary>

```
You are the technical lead and reviewer for M9 (Risk Engine) AND the Next.js
frontend (upload UI + officer dashboard) in a 5-person software project.

Read the attached Build Spec completely before doing anything.

Your responsibility is ONLY M9 and the frontend. You do not directly
implement the code. Antigravity is the developer that will modify the
repository and write the code based on your instructions.

Your job is to:
1. Understand the entire system and how M9 sits at the end of the backend
   pipeline (consuming every other module's real output) and how the
   frontend sits at the very end (consuming M9's output).
2. Because M9 depends on everyone else's real modules, which aren't all
   ready immediately: instruct Antigravity to build M9's logic AND the
   frontend shell against fake/mocked outputs that exactly match the frozen
   contracts, starting immediately — do not wait for real modules.
3. Break M9 and the frontend into small, clear implementation tasks.
4. Give Antigravity precise instructions for ONE task at a time.
5. After Antigravity completes a task, carefully review its report and, when
   available, the changed code/files.
6. Check that the implementation follows the Build Spec and the frozen I/O
   contracts exactly. M9 must produce exactly RiskEngineOutput.
7. Verify the risk-score weighting is documented, justified, and tunable —
   not a black box — and that the "reasons" list is built from plain-English
   sentences sorted by contribution size.
8. Verify the frontend's results screen lets an officer see the score, the
   top reasons, AND a drill-down into each raw module output (OCR fields,
   face similarity number, DB status) — not just the final number.
9. Track P6's Figma handoff separately: once Figma designs land, give
   Antigravity a scoped task to reskin the already-working frontend shell
   to match — do not rebuild the shell from scratch.
10. Never modify contracts.py or another person's module.
11. If something is wrong, explain the problem and give Antigravity a
    specific correction task. If correct, move to the next task.

Do NOT blindly trust Antigravity's report. Verify its work against the Build
Spec. Do NOT redesign the architecture yourself. If you believe the frozen
contract or architecture must change, stop and explain the issue rather than
changing it.

You should always know: what M9 and the frontend are supposed to do, what
they receive, what they must return/display, what's already implemented
(mocked vs real), and what the next smallest useful task is.

When starting, first give me:
A. Your understanding of M9 and the frontend
B. M9's inputs and outputs
C. The implementation stages (M9 against mocks, frontend shell against
   mocks, then real-data swap-in, then Figma reskin)
D. The first Antigravity task

After each Antigravity report, review it and decide: approve and give the
next task, or reject and give a correction task.

Periodically, at a meaningful milestone (M9 logic complete, frontend shell
working end-to-end on mocks, real-data swap complete, Figma reskin
complete), prepare a concise status report for Claude, the overall project
architect.
```
</details>

---

### P6 — UI/UX Designer (Figma only, no code)

**In plain language:** you design what the officer actually looks at — the upload screen, the results/dashboard screen showing the risk score and reasons, and the officer's action buttons (Approve/Deny/Escalate). You never touch the repo or write code. When your Figma file is ready, it's handed straight to P5, who implements it in Next.js.

**What to design (all in Figma):**
1. Upload screen — document photo input + live photo capture, clear instructions, upload progress state.
2. Results screen — a prominent risk score + color-coded band (low/medium/high), a short "top reasons" list, and a drill-down panel showing each module's raw output (OCR fields, face similarity, DB status) for officers who want to dig deeper.
3. Risk visualization — a clear, quick-to-read visual for the score/band (think a gauge, a colored bar, or a badge — not a wall of numbers).
4. Officer action buttons — Approve / Deny / Escalate, with a confirmation state, since this is logged as the audit trail.
5. Overall visual system — consistent colors, type, spacing across all screens so P5 isn't guessing at implementation details.

Deliver your Figma file with named frames per screen and, ideally, exported specs (spacing, colors, font sizes) so P5's Antigravity prompts can reference exact values instead of eyeballing your design.

---

## 7. Sending a Milestone Update to Claude

Whenever your ChatGPT flags a meaningful milestone (your module complete, integration point reached, a contract question comes up), send Div a short status update in this shape — he'll forward it to Claude for the system-level check:

```
[Your Module] — Status Update

Completed:
- (bullet list of what's actually done and tested)

Validation:
- (what tests you ran, what passed)

Still stubbed / not yet real:
- (be honest — half-done counts as half-done)

Any contract questions or architecture concerns:
- (if none, say "none — contract followed exactly as frozen")

Next step:
- (what you're doing next)
```

Claude will not review every tiny Antigravity task — only real milestones. Don't over-send; don't under-send. If you genuinely finished a module or hit an integration point, that's a milestone.

---

## 8. Getting to a Finished Project — Final Checklist

- [ ] All 5 members have repo access and their own branch
- [ ] Everyone has read Section 1 (the whole pipeline), not just their own module
- [ ] Each person's module replaces its stub, one at a time, re-tested against the walking-skeleton test after every swap (P1's job to coordinate this)
- [ ] `requirements.txt` is pinned with exact versions the moment anyone installs a new dependency (PaddleOCR/InsightFace/YOLO are picky about version drift across machines)
- [ ] Test data is prepared early: 3–5 genuine specimen documents, 1–2 manually tampered versions (your tamper-detection ground truth), a synthetic MongoDB seed (10–15 fake records, mixed statuses), and matching live-photo pairs for face verification
- [ ] P6's Figma lands with named frames + exported specs; P5 reskins the already-working frontend shell rather than rebuilding it
- [ ] Full pipeline runs end-to-end on real modules, not mocks, before the demo
- [ ] Three demo cases prepared and rehearsed: one clean pass, one tampered document, one blacklisted document
- [ ] Buffer time is actually left before the deadline — something will break during final integration, budget for it
- [ ] `contracts.py` — check one last time — untouched from the frozen version, or any changes were reviewed and approved by Claude first

If every box is checked, you're demo-ready.
