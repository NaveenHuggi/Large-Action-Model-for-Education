"""
summarizer.py — Brief Summary Generator
Uses the Groq API (llama-3.3-70b-versatile) to produce a concise research
summary from the top-N links collected by the LAM across all domains.
"""
import os
from groq import Groq
from config import GROQ_API_KEY


class Summarizer:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set.")
        self.client = Groq(api_key=self.api_key)
        self.model  = "llama-3.3-70b-versatile"

    def generate_summary(self, query: str, results: dict) -> str:
        """
        Generates a brief research summary from collected domain results.

        Args:
            query   : The original user search query.
            results : Dict from results.json e.g.
                      {
                        "youtube":   [{"title": ..., "url": ...}, ...],
                        "wikipedia": [...],
                        "scholar":   [...],
                      }
        Returns:
            A concise multi-paragraph summary string.
        """
        # Build a readable context block from the collected links
        context_lines = []
        domain_labels = {
            "youtube":   "YouTube Videos",
            "wikipedia": "Wikipedia Articles",
            "scholar":   "Research Papers",
        }

        for domain_key, label in domain_labels.items():
            items = results.get(domain_key, [])
            if items:
                context_lines.append(f"\n{label}:")
                for i, item in enumerate(items, 1):
                    context_lines.append(f"  {i}. {item.get('title', 'No title')} — {item.get('url', '')}")

        if not context_lines:
            return "No results collected yet. Please run the agent first."

        context_text = "\n".join(context_lines)

        prompt = (
            f"You are a research assistant. The user searched for: \"{query}\".\n\n"
            f"Resources collected:\n{context_text}\n\n"
            "Write a SHORT summary in exactly 3 bullet points (• ):\n"
            "• What the topic is\n"
            "• Key themes across these results\n"
            "• Why it matters / what someone would learn\n\n"
            "Rules: max 120 words total, no headings, no extra paragraphs, plain text only."
        )

        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.3,
                max_tokens=180,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"[Summary Error] Could not generate summary: {e}"


if __name__ == "__main__":
    # Quick test
    import json
    sample_results = {
        "youtube":   [{"title": "What is AI?", "url": "https://youtube.com/watch?v=abc"}],
        "wikipedia": [{"title": "Artificial intelligence", "url": "https://en.wikipedia.org/wiki/AI"}],
        "scholar":   [{"title": "Deep Learning in Healthcare", "url": "https://google.com/..."}],
    }
    s = Summarizer()
    print(s.generate_summary("Artificial Intelligence", sample_results))
