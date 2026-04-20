# ============================================================
# LAM Central Configuration File
# ============================================================
# Set your API keys here once. All other modules import from here.

import os

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── Local LLM Endpoint ────────────────────────────────────────────────────────
# You are running a Docker container with Llama_8B (via llama.cpp server)
# The default completion endpoint is at port 8080.
OLLAMA_URL = "http://localhost:8080/completion"

# Model name (Optional for llama.cpp server as it auto-loads from the container)
OLLAMA_MODEL_NAME = "llama-3-8b-instruct"

# ── Domain Configuration ──────────────────────────────────────────────────────
# Starting URLs and search query templates for each supported domain.
DOMAIN_CONFIG = {
    "youtube": {
        "label":     "YouTube",
        "start_url": "https://www.youtube.com",
        "task_template": "Search YouTube for '{query}'. Navigate to the search results page and STOP. Do NOT click on any video result.",
    },
    "wikipedia": {
        "label":     "Wikipedia",
        "start_url": "https://www.wikipedia.org",
        "task_template": "Search Wikipedia for '{query}'. Navigate to the search results page and STOP. Do NOT click on any article result.",
    },
    "scholar": {
        "label":     "Research Papers",
        "start_url": "http://export.arxiv.org/api/query?search_query=all:{query}&max_results=5",
        "task_template": "The browser is already displaying the arXiv XML results for '{query}'. Simply verify the page has loaded and STOP. Do NOT click anywhere.",
    },
}
