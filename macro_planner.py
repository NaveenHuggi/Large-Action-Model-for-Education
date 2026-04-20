import os
from groq import Groq
from typing import List
from config import GROQ_API_KEY

class MacroPlanner:
    def __init__(self, api_key: str = None):
        """
        Initializes the MacroPlanner using the Groq API.
        Recommended model: llama3-70b-8192 for complex reasoning.
        """
        self.api_key = api_key or GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set. Please add it to config.py")
        
        self.client = Groq(api_key=self.api_key)
        self.model = "llama-3.3-70b-versatile"  # Updated: llama3-70b-8192 was decommissioned
        self.system_prompt = (
            "You are an expert web automation Macro-Planner. A Chromium browser is already open and running. "
            "Your job is to break down a user's high-level web task into a sequence of simple, granular browser actions. "
            "IMPORTANT RULES:\n"
            "- DO NOT output steps like 'Open a browser', 'Launch Chrome', or 'Start a browser' — the browser is already open.\n"
            "- Every step must be a direct browser action: Navigate to URL, Click, Type, Scroll, or Press Key.\n"
            "- For navigation, use 'Navigate to <URL>' as the step text.\n"
            "- CRITICAL: Your plan MUST STOP as soon as the search results page is visible. "
            "  DO NOT generate any step that clicks on a search result, video, article, or paper link. "
            "  The goal is ONLY to reach the results listing page — never to open any individual result.\n"
            "- Be concise. Return ONLY a numbered list. No extra commentary.\n"
            "Example for 'Search YouTube for cats — stop at results':\n"
            "1. Navigate to https://www.youtube.com\n"
            "2. Click on the search bar\n"
            "3. Type 'cats'\n"
            "4. Press Enter\n"
            "(STOP HERE — do not add any step to click a video)"
        )

    def generate_plan(self, user_task: str) -> List[str]:
        """
        Decomposes the user task into a list of steps.
        """
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Task: {user_task}"}
                ],
                model=self.model,
                temperature=0.2, # Low temperature for more deterministic planning
                max_tokens=1024,
            )
            
            response_text = chat_completion.choices[0].message.content
            # Parse the numbered list into a Python list
            steps = []
            for line in response_text.strip().split('\n'):
                line = line.strip()
                if line and line[0].isdigit() and '. ' in line:
                    step_text = line.split('. ', 1)[1]
                    steps.append(step_text)
            
            # Fallback if parsing fails
            if not steps:
                steps = [response_text.strip()]
                
            return steps
            
        except Exception as e:
            print(f"Error communicating with Groq API: {e}")
            return []

    def replan(self, user_task: str, failed_step: str, memory_context: str) -> str:
        """
        Replans the current step if execution failed, taking into account the feedback from the Critic.
        """
        replan_prompt = (
            f"You previously planned steps for the task: '{user_task}'.\n"
            f"However, the execution engine failed on this step: '{failed_step}'.\n"
            f"Feedback from execution: '{memory_context}'.\n"
            "Please provide ONE revised, immediately actionable next step to recover and proceed. "
            "Output only the revised step text."
        )
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": replan_prompt}
                ],
                model=self.model,
                temperature=0.3,
                max_tokens=256,
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error during replanning: {e}")
            return failed_step

# Example usage (for testing):
if __name__ == "__main__":
    # Ensure GROQ_API_KEY is set in environment variables
    # os.environ["GROQ_API_KEY"] = "your_key_here"
    try:
        planner = MacroPlanner()
        task = "Open Google Chrome, search for 'latest AI news', and click on the first search result."
        print(f"Planning for Task: {task}")
        plan = planner.generate_plan(task)
        for i, step in enumerate(plan, 1):
            print(f"{i}. {step}")
            
        print("\nSimulating failure on step 2...")
        revised_step = planner.replan(task, plan[1], "Search bar was not found on the screen. Maybe the browser hasn't fully loaded.")
        print(f"Revised Step: {revised_step}")
    except ValueError as e:
        print(f"Initialization skipped: {e}")
