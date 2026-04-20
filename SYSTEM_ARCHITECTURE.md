# 🤖 LAM (Large Action Model) — System Architecture

> **A DOM-driven, LLM-orchestrated UI Automation Agent that plans, executes, reflects, and self-heals — all in real-time.**

---

## 📐 High-Level System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          STREAMLIT DASHBOARD  (app.py)                          │
│  ┌─────────────────────────────┐   ┌─────────────────────────────────────────┐  │
│  │       Sidebar Controls      │   │          Terminal Output Panel           │  │
│  │  • Task text area           │   │  • Live log streaming (lam_dom_ex.log)  │  │
│  │  • Start / Stop buttons     │   │  • Auto-refresh every 1.5s              │  │
│  │  • Keep Alive toggle        │   │  • Last 40 log lines rendered           │  │
│  └────────────┬────────────────┘   └─────────────────────────────────────────┘  │
└───────────────┼─────────────────────────────────────────────────────────────────┘
                │ subprocess.Popen(agentic_loop.py --task "..." --url "...")
                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AGENTIC LOOP  (agentic_loop.py)                         │
│                                                                                 │
│   ┌───────────────┐    ┌────────────────────┐    ┌──────────────────────────┐  │
│   │ MacroPlanner  │    │  PlaywrightExecutor │    │     AgenticCritic        │  │
│   │  (Groq API)   │    │ (Playwright + Llama)│    │  (Groq Vision API)       │  │
│   │               │    │                     │    │                          │  │
│   │ llama-3.3-70b │    │ [DOM Extraction]    │    │ llama-3.2-11b-vision     │  │
│   │ -versatile    │    │ [Semantic Locators] │    │  • Before screenshot     │  │
│   │               │    │ [Local Llama-3 GGUF]│    │  • After screenshot      │  │
│   └───────────────┘    └────────────────────┘    │  • SUCCESS / FAILURE     │  │
│                                                   └──────────────────────────┘  │
│                                                                                 │
│   📊 Metrics Sink → eval_metrics.csv                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                          Playwright controls
                                        │
                    ┌───────────────────▼────────────────────┐
                    │         Chromium Browser (Headless=False)│
                    │   Real-time visible UI interactions      │
                    └─────────────────────────────────────────┘
                                        │
                           Cloudflare Tunnel (LocalTunnel)
                                        │
                    ┌───────────────────▼────────────────────┐
                    │  Colab-Hosted Ollama (Llama-3 8B GGUF) │
                    │  POST /api/generate                     │
                    │  Model: lam_agent (fine-tuned Llama-3) │
                    └─────────────────────────────────────────┘
```

---

## 📦 Component Breakdown

| File | Role | Model / API Used |
|---|---|---|
| `app.py` | Streamlit UI — user entry point | — |
| `agentic_loop.py` | Master orchestrator — coordinates all agents | — |
| `macro_planner.py` | Task decomposition into browser action steps | Groq → `llama-3.3-70b-versatile` |
| `executor.py` | DOM extraction + action inference + Playwright execution | Local Ollama (`lam_agent` / Llama-3 8B) |
| `critic.py` | Visual state-change evaluator (before/after screenshots) | Groq Vision → `llama-3.2-11b-vision-preview` |
| `config.py` | Central config — API keys, tunnel URL, model names | — |
| `eval_metrics.csv` | Persisted evaluation metrics for every task run | — |

---

## 🔄 Execution Phases

### Phase 0 — User Interaction (Frontend)
```
User → Streamlit UI (app.py)
  • Enters natural language task (e.g., "search YouTube for Dhurandar trailer")
  • Sets starting URL (default: https://google.com)
  • Clicks "🚀 Start Agent"
  • Streamlit spawns agentic_loop.py as a background subprocess
  • Live terminal output streams from lam_dom_execution.log
```

---

### Phase 1 — Macro Planning
```
MacroPlanner (macro_planner.py)
  Input:  Natural language user task
  Model:  Groq API → llama-3.3-70b-versatile  (temp=0.2, max_tokens=1024)
  Output: Ordered list of atomic browser actions

Example Output:
  1. Navigate to https://www.youtube.com
  2. Click on the search bar
  3. Type 'Dhurandar trailer'
  4. Press Enter
  5. Click on the first video result
```

---

### Phase 2 — Browser Initialization
```
PlaywrightExecutor.start()
  • Launches Chromium (headless=False — user can see browser in real-time)
  • Viewport: 1280 × 800
  • Navigates to the starting URL
  • Waits for network idle
```

---

### Phase 3 — Agentic Execution Loop
```
For each step in the macro plan:

  [A] BEFORE screenshot → states/step_N_before.png

  [B] Executor.step(instruction)  — 3-tier priority resolution:

      Priority 1: NAVIGATE
      ├── Regex detects URL in instruction
      └── Playwright page.goto() — no model needed

      Priority 2: SEMANTIC LOCATORS (no model needed)
      ├── 2a. TYPE → tries searchbox / textbox / input[type='search'] locators
      ├── 2b. PRESS KEY → maps "Enter", "Escape", etc. to Playwright keys
      ├── 2c. CLICK (semantic) → gets_by_role / get_by_text / get_by_label
      └── 2d. FIRST VIDEO RESULT → native YouTube CSS selectors (ytd-video-renderer a#video-title)

      Priority 3: LOCAL LLM FALLBACK (DOM-based Inference)
      ├── DOM Extraction via JS injection:
      │     - Queries: button, a, input, select, textarea, [role="button"]
      │     - Assigns data-lam-id to each visible element
      │     - Extracts: tag, type, text, href
      │     - Returns simplified text tree
      │
      ├── Prompt sent to Colab-hosted Llama-3 (via Cloudflare tunnel):
      │     Input:  instruction + DOM text tree
      │     Output: Action: CLICK|TYPE|SCROLL
      │             Target_ID: <number>
      │             Value: '<text if TYPE>'
      │
      └── Playwright executes parsed action via data-lam-id selector

  [C] AFTER screenshot → states/step_N_after.png

  [D] Critic Evaluation:
      └── AgenticCritic.evaluate_action(before, after, step)
            • Sends both screenshots to Groq Vision API
            • Model: llama-3.2-11b-vision-preview
            • Returns: SUCCESS / FAILURE + reason

  [E] Decision Gate:
      ├── SUCCESS → advance to next step (current_step_idx += 1)
      └── FAILURE → trigger Replanning:
            MacroPlanner.replan(task, failed_step, critic_feedback)
            → Generates ONE revised recovery step
            → Replaces failed step in plan and retries

  [F] Step Retry Guard:
      └── If execution fails 3× consecutively → skip step (MAX_STEP_RETRIES=3)
```

---

### Phase 4 — Self-Healing (Replanning)
```
Triggered when: Critic returns FAILURE

MacroPlanner.replan()
  Input:  original task + failed step + critic feedback text
  Model:  Groq API → llama-3.3-70b-versatile  (temp=0.3, max_tokens=256)
  Output: ONE revised action step
  Effect: Replaces failed step in plan in-place → loop continues
```

---

### Phase 5 — Metrics Capture
```
On loop exit (success OR max_iterations hit):

eval_metrics.csv records:
  ┌─────────────────────┬──────────────────────────────────────────┐
  │ Field               │ Description                              │
  ├─────────────────────┼──────────────────────────────────────────┤
  │ timestamp           │ When the task ran                        │
  │ task                │ The original user task string            │
  │ start_url           │ Starting URL                             │
  │ steps_planned       │ Total steps in macro plan                │
  │ steps_executed      │ Total attempts (incl. retries)           │
  │ steps_succeeded     │ First-try successes                      │
  │ steps_skipped       │ Steps abandoned after 3 failures         │
  │ total_retries       │ Cumulative retries across all steps      │
  │ task_success        │ 1 if all steps completed, else 0         │
  │ tsr                 │ Task Success Rate (1.0 or 0.0)           │
  │ ssr                 │ Step Success Rate = succeeded/executed    │
  │ avg_steps_per_task  │ steps_executed (useful when aggregated)  │
  │ skip_rate           │ steps_skipped / steps_planned            │
  │ retry_rate          │ total_retries / steps_planned            │
  │ completion_time_sec │ Wall-clock time for the full task        │
  └─────────────────────┴──────────────────────────────────────────┘

Observed Performance (from eval_metrics.csv):
  • All 5 recorded task runs: TSR = 1.0, SSR = 1.0
  • Average completion time: ~13 seconds per task
  • Zero skips, zero retries on YouTube search tasks
```

---

### Phase 6 — Session Termination / Keep-Alive
```
If --keep-alive flag is set:
  • Browser stays open after task completion
  • Agentic loop sleeps indefinitely
  • User can inspect the browser state
  • Manually stopped via "🛑 Stop Agent" button in Streamlit

Otherwise:
  • executor.stop() closes browser + Playwright gracefully
  • Streamlit detects process exit (poll() returns code)
  • UI reverts to "System ready" idle state
```

---

## 🌐 Infrastructure Diagram

```
 ┌──────────────────────────────┐
 │   LOCAL MACHINE              │
 │   ┌────────────────────┐     │
 │   │  Streamlit (app.py)│     │
 │   └────────┬───────────┘     │
 │            │ subprocess      │
 │   ┌────────▼───────────┐     │
 │   │  agentic_loop.py   │     │
 │   │  + macro_planner   │     │         ┌─────────────────────┐
 │   │  + executor        │─────────────► │   GROQ CLOUD API    │
 │   │  + critic          │     │         │  • llama-3.3-70b    │
 │   └────────┬───────────┘     │         │    (planner)        │
 │            │                 │         │  • llama-3.2-11b-v  │
 │   ┌────────▼───────────┐     │         │    (vision critic)  │
 │   │ Chromium Browser   │     │         └─────────────────────┘
 │   │ (Playwright)       │     │
 │   └────────────────────┘     │         ┌─────────────────────┐
 │            │                 │         │  GOOGLE COLAB       │
 │   Cloudflare Tunnel URL ──────────────►│  Ollama server      │
 │   (loca.lt endpoint)         │         │  Model: lam_agent   │
 └──────────────────────────────┘         │  (Llama-3 8B GGUF)  │
                                          └─────────────────────┘
```

---

## 🔑 Key Design Decisions

### 1. Three-Tier Execution Priority
The executor avoids calling the remote LLM for common, predictable actions (navigation, typing, key presses). Only truly ambiguous DOM-level interactions fall through to the expensive Llama-3 inference call. This reduces latency and cost significantly.

### 2. Cloudflare Tunnel + curl_cffi
The local Llama model runs on a free Google Colab GPU. The Cloudflare tunnel (LocalTunnel `loca.lt`) exposes the Ollama port. `curl_cffi` is used instead of `requests` to spoof Chrome's TLS fingerprint and bypass Cloudflare bot-blocking interstitials.

### 3. data-lam-id Injection
Rather than relying on brittle CSS selectors or XPath, the executor injects a unique `data-lam-id` attribute to every visible interactive element before prompting the model. The model outputs a simple integer ID, and Playwright uses `[data-lam-id="N"]` to interact — making the system robust to dynamic DOM changes.

### 4. Critic-in-the-Loop
The AgenticCritic compares before/after screenshots using a multimodal vision LLM rather than checking return codes or DOM state. This is more robust since it evaluates *visual intent* — e.g., confirming that a page actually navigated, or that a form was submitted.

### 5. Isolateed Metrics (No Side Effects)
The metrics tracking counters (`_steps_succeeded`, `_steps_skipped`, etc.) are purely observational and never influence the execution logic. They are computed post-run to ensure clean separation of concerns.

---

## 📁 File Structure

```
Execution LAM/
├── app.py                  # Streamlit frontend — user entry point
├── agentic_loop.py         # Master orchestrator — execution engine
├── macro_planner.py        # LLM-based task decomposer (Groq)
├── executor.py             # DOM extractor + action executor (Playwright + Ollama)
├── critic.py               # Visual action evaluator (Groq Vision)
├── config.py               # Centralized config (API keys, tunnel URL)
├── eval_metrics.csv        # Persisted run-level evaluation metrics
├── lam_dom_execution.log   # Execution log (live-streamed to Streamlit)
├── lam_execution.log       # Historical/full execution log
└── states/                 # Before/after screenshots per step
    ├── step_1_before.png
    ├── step_1_after.png
    └── ...
```

---

## 📊 Observed Evaluation Results

| Task | Steps | TSR | SSR | Time (s) |
|---|---|---|---|---|
| YouTube search: Dhurandar trailer + click | 5 | 1.0 | 1.0 | 14.46 |
| YouTube search: Jaye sagana song + click | 5 | 1.0 | 1.0 | 13.36 |
| YouTube search: Dhurandar trailer + click | 5 | 1.0 | 1.0 | 11.58 |
| YouTube search: Dhurandar trailer + click | 5 | 1.0 | 1.0 | 13.90 |
| YouTube search: Lut le gaya song + click | 5 | 1.0 | 1.0 | 11.88 |

> **TSR = Task Success Rate | SSR = Step Success Rate**
> All 5 recorded runs achieved perfect TSR=1.0 and SSR=1.0 with zero retries and zero skipped steps.

---

*Generated from full codebase analysis of `Execution LAM/` — April 2026*
