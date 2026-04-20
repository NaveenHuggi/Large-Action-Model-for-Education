import os
import csv
import json
import time
import asyncio
import logging
from datetime import datetime
from macro_planner import MacroPlanner
from executor import PlaywrightExecutor
from critic import AgenticCritic
from config import DOMAIN_CONFIG

# ── Metrics CSV Writer ────────────────────────────────────────────────────────
CSV_PATH = "eval_metrics.csv"
CSV_HEADERS = [
    "timestamp", "task", "domain", "start_url",
    "steps_planned",      # Total steps in the macro plan
    "steps_executed",     # Steps actually attempted (incl. retries)
    "steps_succeeded",    # Steps that returned success=True on first try
    "steps_skipped",      # Steps skipped after MAX_STEP_RETRIES failures
    "total_retries",      # Cumulative retry count across all steps
    "task_success",       # 1 if all steps completed, 0 otherwise
    "tsr",                # Task Success Rate for this run (1.0 or 0.0)
    "ssr",                # Step Success Rate = succeeded / executed
    "avg_steps_per_task", # steps_executed (useful when aggregated)
    "skip_rate",          # steps_skipped / steps_planned
    "retry_rate",         # total_retries / steps_planned
    "completion_time_sec"
]

def save_metrics(m: dict):
    """Appends one row of metrics to eval_metrics.csv. Creates file + header if needed."""
    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(m)
    logging.info(
        f"[METRICS] Saved → domain={m['domain']} | TSR={m['tsr']} | "
        f"SSR={m['ssr']:.2f} | Skip={m['skip_rate']:.2f} | "
        f"Time={m['completion_time_sec']}s"
    )

# ── Results JSON helpers ──────────────────────────────────────────────────────
RESULTS_PATH = "results.json"

def load_results() -> dict:
    if os.path.exists(RESULTS_PATH):
        try:
            with open(RESULTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_results(data: dict):
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ── Logging setup ─────────────────────────────────────────────────────────────
import sys, io as _io

# Force UTF-8 on the console stream so special chars (→ etc.) don't crash on Windows cp1252
_utf8_stream = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
_console_handler = logging.StreamHandler(_utf8_stream)
_console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("lam_dom_execution.log", encoding="utf-8"),
        _console_handler,
    ]
)

# ── Core agentic loop ─────────────────────────────────────────────────────────
async def run_agentic_loop(
    user_task: str,
    start_url: str = "https://google.com",
    domain: str = "youtube",
    max_iterations: int = 20,
    keep_alive: bool = False,
):
    logging.info("=" * 60)
    logging.info("LAM DOM EXECUTION ENGINE STARTING")
    logging.info(f"Task   : {user_task}")
    logging.info(f"Domain : {domain}")
    logging.info(f"URL    : {start_url}")
    logging.info("=" * 60)

    planner = MacroPlanner()
    critic   = AgenticCritic()
    executor = PlaywrightExecutor()

    await executor.start()

    try:
        logging.info(f"[SYSTEM] Navigating to: {start_url}")
        await executor.page.goto(start_url)
        await executor.page.wait_for_load_state("networkidle", timeout=15000)

        # ── Phase 1: Macro Planning ───────────────────────────────────────────
        logging.info("[PLANNING] Decomposing task into steps...")
        full_plan = planner.generate_plan(user_task)

        if not full_plan:
            logging.error("[PLANNER] Empty plan returned. Check Groq API key. Aborting.")
            return

        logging.info("Generated Plan:")
        for i, step in enumerate(full_plan, 1):
            logging.info(f"  {i}. {step}")

        iteration        = 0
        current_step_idx = 0
        step_retry_count = 0
        MAX_STEP_RETRIES = 3
        os.makedirs("states", exist_ok=True)

        # ── Metrics counters ──────────────────────────────────────────────────
        _t_start         = time.time()
        _steps_succeeded = 0
        _steps_skipped   = 0
        _steps_executed  = 0
        _total_retries   = 0

        # ── Phase 2: Agentic Execution & Reflection Loop ──────────────────────
        while current_step_idx < len(full_plan) and iteration < max_iterations:
            current_step = full_plan[current_step_idx]
            iteration   += 1

            logging.info("\n" + "-" * 40)
            logging.info(f"Iteration {iteration} | Step {current_step_idx + 1}/{len(full_plan)}")
            logging.info(f"Instruction: {current_step}")
            logging.info("-" * 40)

            # [A] Before screenshot
            before_path = f"states/step_{iteration}_before.png"
            await executor.page.screenshot(path=before_path)

            # [B] Execute step
            success = await executor.step(current_step)
            _steps_executed += 1

            if not success:
                step_retry_count += 1
                _total_retries   += 1
                if step_retry_count >= MAX_STEP_RETRIES:
                    logging.warning(
                        f"[EXECUTOR] Step failed {MAX_STEP_RETRIES}× — skipping: '{current_step}'"
                    )
                    _steps_skipped  += 1
                    current_step_idx += 1
                    step_retry_count = 0
                else:
                    logging.error(
                        f"[EXECUTOR] Attempt {step_retry_count}/{MAX_STEP_RETRIES} failed. Retrying..."
                    )
                    await asyncio.sleep(2)
                continue

            _steps_succeeded   += 1
            step_retry_count    = 0   # reset on success

            logging.info("[EXECUTOR] Action executed. Waiting for UI to settle...")
            try:
                await executor.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                await asyncio.sleep(1.5)

            # [C] After screenshot
            after_path = f"states/step_{iteration}_after.png"
            await executor.page.screenshot(path=after_path)

            # [D] Critic evaluation
            logging.info("[CRITIC] Evaluating visual state change...")
            evaluation = critic.evaluate_action(before_path, after_path, current_step)

            if evaluation["success"]:
                logging.info("[REWARD] Critic approved — moving to next step.")
                current_step_idx += 1
            else:
                logging.warning(f"[PENALTY] Critic rejected: {evaluation['feedback']}")
                logging.info("[PLANNER] Replanning failed step...")
                revised = planner.replan(user_task, current_step, evaluation["feedback"])
                logging.info(f"Revised Step: {revised}")
                full_plan[current_step_idx] = revised

        # ── Phase 3: Result Extraction ────────────────────────────────────────
        task_success = current_step_idx >= len(full_plan)

        if task_success:
            logging.info("\n[SUCCESS] Task completed! Extracting top results...")
            max_r = 4 if domain == "youtube" else 5
            top_results = await executor.extract_top_results(domain, max_results=max_r)
            logging.info(f"[RESULTS] Extracted {len(top_results)} results.")
        else:
            logging.warning(f"\n[TIMEOUT] Max iterations ({max_iterations}) reached. Task incomplete.")
            top_results = []

        # Persist results to results.json (merge with any existing data from other domains)
        all_results = load_results()
        all_results[domain] = top_results
        save_results(all_results)
        logging.info(f"[RESULTS] Saved to '{RESULTS_PATH}'.")

        # ── Phase 4: Metrics ──────────────────────────────────────────────────
        _elapsed    = round(time.time() - _t_start, 2)
        _planned    = len(full_plan)
        _ssr        = round(_steps_succeeded / _steps_executed, 4) if _steps_executed > 0 else 0.0
        _skip_rate  = round(_steps_skipped   / _planned,        4) if _planned > 0 else 0.0
        _retry_rate = round(_total_retries   / _planned,        4) if _planned > 0 else 0.0

        save_metrics({
            "timestamp"          : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "task"               : user_task,
            "domain"             : domain,
            "start_url"          : start_url,
            "steps_planned"      : _planned,
            "steps_executed"     : _steps_executed,
            "steps_succeeded"    : _steps_succeeded,
            "steps_skipped"      : _steps_skipped,
            "total_retries"      : _total_retries,
            "task_success"       : int(task_success),
            "tsr"                : 1.0 if task_success else 0.0,
            "ssr"                : _ssr,
            "avg_steps_per_task" : _steps_executed,
            "skip_rate"          : _skip_rate,
            "retry_rate"         : _retry_rate,
            "completion_time_sec": _elapsed,
        })

        if keep_alive:
            logging.info("\n[SYSTEM] Keep-alive mode — waiting for manual stop...")
            while True:
                await asyncio.sleep(1)

    finally:
        await executor.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LAM Execution Engine")
    parser.add_argument("--task",       type=str, required=True, help="Natural language task for the LAM")
    parser.add_argument("--url",        type=str, default="https://google.com", help="Starting URL")
    parser.add_argument("--domain",     type=str, default="youtube",
                        choices=list(DOMAIN_CONFIG.keys()),
                        help="Target domain: youtube | wikipedia | scholar")
    parser.add_argument("--keep-alive", action="store_true", help="Keep browser open after finishing")
    args = parser.parse_args()

    try:
        asyncio.run(run_agentic_loop(
            user_task  = args.task,
            start_url  = args.url,
            domain     = args.domain,
            keep_alive = args.keep_alive,
        ))
    except KeyboardInterrupt:
        logging.info("Session manually terminated.")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
