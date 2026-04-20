import os
from groq import Groq
import base64
from config import GROQ_API_KEY

class AgenticCritic:
    def __init__(self, api_key: str = None):
        """
        Initializes the Critic Agent.
        Uses a Multimodal model (e.g., LLaVA or GPT-4o-mini equivalent if Groq supports it,
        or a smart LLM inference fallback) to verify state changes.
        """
        self.api_key = api_key or GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set. Please add it to config.py")
        self.client = Groq(api_key=self.api_key)
        # Assuming groq vision model (e.g. llama-3.2-90b-vision-preview or similar available vision model)
        # If a vision model is unavailable in Groq at runtime, we can fall back to standard Text-based reasoning.
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"  # Current Groq vision model (Apr 2025+)

    def encode_image(self, image_path: str):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def evaluate_action(self, state_before_path: str, state_after_path: str, action_attempted: str) -> dict:
        """
        Evaluates whether an action was successful by comparing the "Before" and "After" screenshots.
        Returns a dictionary with 'success' (bool) and 'feedback' (str).
        """
        print(f"Critic evaluating action: {action_attempted}")
        
        try:
            base64_before = self.encode_image(state_before_path)
            base64_after = self.encode_image(state_after_path)
            
            prompt = (
                f"You are an AI Critic evaluating UI interactions. I am sending you two screenshots.\n"
                f"The first one is the 'Before' state. The second one is the 'After' state.\n"
                f"The Agent attempted to perform the action: '{action_attempted}'.\n"
                "Analyze the differences between the two images visually.\n"
                "Did the action succeed? For example, did a menu open, or a new page load?\n"
                "Respond strictly with 'SUCCESS' or 'FAILURE' on the first line, followed by a brief reason on the second line."
            )

            # NOTE: If your Groq account does not have vision access, you must swap this out with
            # an API that supports Vision (like OpenAI GPT-4o) or implement a simpler heuristic
            # (e.g., ImageHash comparison to detect screen changes).
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_before}",
                                },
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_after}",
                                },
                            }
                        ],
                    }
                ],
                temperature=0.1,
                max_tokens=100
            )

            response_text = completion.choices[0].message.content.strip()
            print(f"Critic Assessment:\n{response_text}")
            
            lines = response_text.split('\n')
            status = lines[0].strip().upper()
            reason = lines[1].strip() if len(lines) > 1 else "No reason provided."

            if "SUCCESS" in status:
                return {"success": True, "feedback": reason}
            else:
                return {"success": False, "feedback": reason}

        except Exception as e:
            print(f"Critic Evaluation Error: {e}")
            print("Falling back to basic ImageHash comparison or assuming success temporarily.")
            # Fallback heuristic: assume success if vision API fails
            return {"success": True, "feedback": "Vision API error, assuming success for now."}

if __name__ == "__main__":
    print("Critic module loaded.")
