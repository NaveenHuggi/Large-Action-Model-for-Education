import os
import re
import json
import asyncio
import requests
from playwright.async_api import async_playwright
from config import GROQ_API_KEY
from groq import Groq

class PlaywrightExecutor:
    def __init__(self, api_key=GROQ_API_KEY, model_name="llama-3.3-70b-versatile"):
        self.client = Groq(api_key=api_key)
        self.model_name = model_name
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
    async def start(self):
        print("[System] Starting Playwright Engine (headless mode)...")
        self.playwright = await async_playwright().start()
        # headless=True — browser runs silently in the background; no window shown to user
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 800}
        )
        self.page = await self.context.new_page()
        
    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def get_dom_representation(self):
        """Extracts interactable elements from the DOM and formats them as a simplified text tree."""
        # Javascript injection to parse DOM and build an accessibility / simplified tree
        js_code = """
        () => {
            let idCounter = 1;
            const tree = [];
            
            // Selector focusing on interactable elements
            const elements = document.querySelectorAll('button, a, input, select, textarea, [role="button"]');
            
            elements.forEach(el => {
                // Determine if element is visible and takes space
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden') {
                    // Assign our custom tracking ID to interact with it later via Playwright
                    const lamId = idCounter++;
                    el.setAttribute('data-lam-id', lamId);
                    
                    // Extract meaningful text
                    let text = el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '';
                    text = text.trim().replace(/\\n/g, ' ');
                    if (text.length > 50) text = text.substring(0, 47) + '...'; // Truncate to save tokens
                    
                    const elData = {
                        id: lamId,
                        tag: el.tagName.toLowerCase(),
                        type: el.getAttribute('type') || '',
                        text: text,
                        // Include href so model knows which <a> tags are video links vs nav buttons
                        href: el.getAttribute('href') || ''
                    };
                    
                    // Format output for the LLM
                    let formatted = `[${elData.id}] <${elData.tag}`;
                    if (elData.type) formatted += ` type="${elData.type}"`;
                    // Only include href for <a> tags — critical for model to distinguish video vs nav links
                    if (elData.tag === 'a' && elData.href) {
                        // Truncate long URLs to save tokens but keep enough to be meaningful
                        const shortHref = elData.href.length > 60 ? elData.href.substring(0, 57) + '...' : elData.href;
                        formatted += ` href="${shortHref}"`;
                    }
                    formatted += `>${elData.text}</${elData.tag}>`;
                    
                    tree.push(formatted);
                }
            });
            return tree.join('\\n');
        }
        """
        dom_text = await self.page.evaluate(js_code)
        return dom_text

    def infer_action(self, instruction: str, dom_context: str) -> dict:
        """Calls the locally running Llama-3 GGUF via Ollama to predict the action."""
        
        # Strict few-shot prompt — forces the model to emit ONLY the structured format.
        # The example shows EXACTLY what output shape is expected, which dramatically
        # improves compliance in instruction-tuned models that tend to narrate.
        # Build a task-aware hint to inject into the prompt
        # This tells the model WHAT to look for in the DOM for common task types
        task_lower = instruction.lower()
        extra_hint = ""
        if any(w in task_lower for w in ['first video', 'first result', 'first link', 'top result', 'top video']):
            extra_hint = (
                "IMPORTANT: To find the FIRST VIDEO RESULT, look for an <a> element whose "
                "href contains '/watch'. Skip all nav, menu, or icon links. "
                "Pick the first <a href=\"/watch...\"> entry in the DOM.\n"
            )
        elif 'click' in task_lower and 'button' in task_lower:
            extra_hint = "IMPORTANT: Look for a <button> or <a role=button> element matching the description.\n"

        prompt = (
            "You are a web automation agent. Given a task and a DOM, you MUST output "
            "ONLY the following structured format with no explanation:\n"
            "Action: <CLICK|TYPE|SCROLL>\n"
            "Target_ID: <number from DOM>\n"
            "Value: '<text if TYPE, else None>'\n\n"
            "EXAMPLE — clicking a video link:\n"
            "Task: Click on the first video result\n"
            "DOM:\n"
            '[1] <a href=\"/?\" >Guide</a>\n'
            '[2] <a href=\"/watch?v=abc123\">Dhurandar Trailer - Official Video</a>\n'
            '[3] <button>Share</button>\n\n'
            "Action: CLICK\n"
            "Target_ID: 2\n"
            "Value: None\n\n"
            "---\n"
            f"{extra_hint}"
            f"Task: {instruction}\n"
            f"DOM:\n{dom_context}\n\n"
            "Action:"
        )
        print(f"[Executor] Prompting remote Groq model with {len(dom_context)} characters of DOM context...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=128,
                temperature=0.0,
                top_p=0.9,
                stop=["\n\n", "---", "Task:"]
            )
            output = response.choices[0].message.content
                
            return self._parse_llama_output(output)
        except Exception as e:
            print(f"[Error] Failed to connect to Groq API or parse response: {e}")
            return None

    def _parse_llama_output(self, text: str) -> dict:
        """Parses Model Output into an actionable dictionary."""
        print(f"[Model Output]\n{text}\n" + "-"*30)
        
        # 1. Clean all markdown/formatting junk the model might hallucinate
        clean_text = re.sub(r'[*`_]', '', text)
        
        # 2. Ultra-forgiving regex (handles "Action : CLICK", "Target ID: 123", etc.)
        action_match = re.search(r'(?i)Action\s*(?::|-)?\s*([A-Za-z]+)', clean_text)
        target_match = re.search(r'(?i)Target[_\s]?ID\s*(?::|-)?\s*(\d+)', clean_text)
        value_match = re.search(r'(?i)Value\s*(?::|-)?\s*([\'"])(.*?)\1', clean_text) 
        
        if not action_match or not target_match:
            print("[Executor] Model output missing standard formatting. Failed to parse Action or Target_ID.")
            print(f"DEBUG: action_match={action_match}, target_match={target_match}")
            return None
            
        action = action_match.group(1).upper()
        target_id = target_match.group(1)
        value = value_match.group(2) if value_match else None
        
        return {
            "action": action,
            "target_id": target_id,
            "value": value
        }

    async def execute_action(self, action_data: dict) -> bool:
        if not action_data: return False
        
        action = action_data["action"]
        target_id = action_data["target_id"]
        value = action_data["value"]
        
        # Querying Playwright strictly by the javascript-injected dataset ID
        selector = f'[data-lam-id="{target_id}"]'
        
        try:
            element = self.page.locator(selector).first
            if not await element.count():
                print(f"[Execution Alert] Element with Target_ID [{target_id}] not found on page! Model hallucinated or DOM mutated.")
                return False
                
            # Scroll to make it visually clear what the LAM is doing
            await element.scroll_into_view_if_needed()
            
            if action == "CLICK":
                print(f"[Executing] CLICK on ID [{target_id}]")
                await element.click()
                
            elif action == "TYPE":
                print(f"[Executing] TYPE on ID [{target_id}] with Value '{value}'")
                await element.click() # Focus the input
                await element.fill(value) # Playwright handles clearing and overriding text robustly
                await self.page.keyboard.press("Enter")
                
            elif action == "SCROLL":
                # Simulated basic scroll mapping based on generic body targeting
                print(f"[Executing] SCROLL")
                await self.page.mouse.wheel(0, 500)
                
            else:
                print(f"[Execution Alert] Unknown or unsupported action type: {action}")
                return False
                
            return True
            
        except Exception as e:
            print(f"[Execution Error] Exception during Playwright interaction with target [{target_id}]: {e}")
            return False

    async def step(self, instruction: str) -> bool:
        """A single iteration of the perceive -> infer -> act loop.
        
        Priority order:
          1. Detect Navigate URL → Playwright page.goto()  [no model needed]
          2. Detect TYPE/PRESS/CLICK patterns → Playwright semantic locators [no model needed]
          3. Fall back to Llama-3 DOM inference via Cloudflare tunnel
        """
        import re as _re
        instr_lower = instruction.lower()

        # ── Priority 1: Navigation ────────────────────────────────────────────
        url_match = _re.search(r'(https?://[^\s]+)', instruction, _re.IGNORECASE)
        if url_match and any(kw in instr_lower for kw in ['navigate', 'go to', 'open', 'visit']):
            url = url_match.group(1).rstrip('.')
            print(f"[Executor] NAVIGATE → {url}")
            try:
                await self.page.goto(url, wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(2)
                return True
            except Exception as e:
                print(f"[Executor] Navigation error: {e}")
                return False

        # ── Priority 2a: TYPE text ────────────────────────────────────────────
        # Matches: Type 'X', Type "X", Type X into ...
        type_match = _re.search(r"type\s+['\"]?(.+?)['\"]?\s*(?:into|in|on)?(?:\s+the\s+.+)?$",
                                 instruction, _re.IGNORECASE)
        if type_match:
            text_to_type = type_match.group(1).strip().strip("'\"")
            print(f"[Executor] SEMANTIC TYPE → '{text_to_type}'")
            try:
                # Try common search/input locators in order of likelihood
                for locator_args in [
                    {"role": "searchbox"},
                    {"role": "textbox"},
                    {"css": "textarea[name='q']"},
                    {"css": "input[name='q']"},
                    {"placeholder_re": r"(?i)search"},
                    {"css": "input[name='search_query']"},
                    {"css": "input[type='text']"},
                    {"css": "input[type='search']"},
                ]:
                    try:
                        if "role" in locator_args:
                            el = self.page.get_by_role(locator_args["role"]).first
                        elif "placeholder_re" in locator_args:
                            el = self.page.get_by_placeholder(
                                _re.compile(locator_args["placeholder_re"])).first
                        elif "css" in locator_args:
                            el = self.page.locator(locator_args["css"]).first
                        
                        if await el.count() > 0:
                            await el.click()
                            await el.fill(text_to_type)
                            print(f"[Executor] Typed successfully via {locator_args}")
                            await asyncio.sleep(1)
                            return True
                    except Exception:
                        continue
                print("[Executor] Could not find a suitable input to type into.")
                return False
            except Exception as e:
                print(f"[Executor] Type error: {e}")
                return False

        # ── Priority 2b: PRESS key ────────────────────────────────────────────
        press_match = _re.search(r"press\s+(\w+)", instruction, _re.IGNORECASE)
        if press_match:
            key = press_match.group(1).capitalize()
            # Map common natural-language key names
            key_map = {"Enter": "Enter", "Return": "Enter", "Tab": "Tab",
                       "Escape": "Escape", "Esc": "Escape", "Space": "Space",
                       "Backspace": "Backspace", "Delete": "Delete"}
            playwright_key = key_map.get(key, key)
            print(f"[Executor] SEMANTIC PRESS KEY → {playwright_key}")
            try:
                await self.page.keyboard.press(playwright_key)
                await asyncio.sleep(1.5)
                return True
            except Exception as e:
                print(f"[Executor] Key press error: {e}")
                return False

        # ── Priority 2c: CLICK semantic targets ───────────────────────────────
        if "click" in instr_lower:
            print(f"[Executor] SEMANTIC CLICK → '{instruction}'")
            # Extract what to click (e.g., "click the search bar" → "search bar")
            target_match = _re.search(r"click\s+(?:on\s+)?(?:the\s+)?(.+?)(?:\s+button|\s+bar|\s+link|\s+icon)?$",
                                       instruction, _re.IGNORECASE)
            target_hint = target_match.group(1).strip() if target_match else ""

            candidates = []
            if any(w in instr_lower for w in ['search', 'search bar', 'search box', 'search-box']):
                candidates = [
                    self.page.get_by_role("searchbox").first,
                    self.page.get_by_role("textbox").first,
                    self.page.locator("input[name='q']").first,
                    self.page.locator("textarea[name='q']").first,
                    self.page.locator("input[type='search']").first,
                    self.page.locator("input[name='search_query']").first,
                    self.page.locator("input[id='search']").first,
                    self.page.locator("#searchbox_input").first,
                ]
            elif any(w in instr_lower for w in ['submit', 'search button', 'go']):
                candidates = [
                    self.page.get_by_role("button", name=_re.compile(r"(?i)search")).first,
                    self.page.locator("button[type='submit']").first,
                ]
            else:
                # Generic: try clicking by visible text label
                candidates = [
                    self.page.get_by_text(target_hint, exact=False).first,
                    self.page.get_by_role("button", name=target_hint).first,
                    self.page.get_by_role("link", name=target_hint).first,
                ]

            for candidate in candidates:
                try:
                    if await candidate.count() > 0:
                        await candidate.click()
                        print(f"[Executor] Clicked via semantic locator.")
                        await asyncio.sleep(1)
                        return True
                except Exception:
                    continue

            # ── Priority 2d: FIRST VIDEO RESULT (YouTube/Google) ─────────────────
            # This is the most common case where the model fails: picking the first
            # search result. We handle it natively using stable platform selectors
            # instead of sending 100k chars of DOM to the model.
            if any(w in instr_lower for w in ['first video', 'first result', 'first link',
                                               'top result', 'top video', 'first video result']):
                print(f"[Executor] NATIVE: Clicking first video result...")
                # YouTube search: a#video-title is the most reliable selector
                yt_selectors = [
                    "ytd-video-renderer a#video-title",          # YouTube search page
                    "ytd-rich-item-renderer a#video-title",      # YouTube home/grid
                    "a#video-title",                              # YouTube fallback
                    "h3 a[href*='/watch']",                      # Generic: any h3 watch link
                    "a[href*='/watch?v=']",                      # Generic: any watch link
                ]
                for sel in yt_selectors:
                    try:
                        el = self.page.locator(sel).first
                        if await el.count() > 0:
                            await el.scroll_into_view_if_needed()
                            await el.click()
                            print(f"[Executor] ✓ Clicked first video result via '{sel}'")
                            await asyncio.sleep(2)
                            return True
                    except Exception:
                        continue
                print("[Executor] Native first-video handler found no matching elements.")

            print("[Executor] Semantic click failed. Falling through to model...")


        # ── Priority 3: Fall back to Llama-3 DOM inference ───────────────────
        print("[Executor] Falling back to Llama-3 model inference...")
        dom_text = await self.get_dom_representation()
        action_data = self.infer_action(instruction, dom_text)
        success = await self.execute_action(action_data)
        await asyncio.sleep(1.5)
        return success

    async def extract_top_results(self, domain: str, max_results: int = 5) -> list:
        """Extracts the top N result links from the current page after LAM execution.
        
        Returns a list of dicts: [{"title": str, "url": str}, ...]
        Handles YouTube, Wikipedia, and Google Scholar page structures.
        """
        print(f"[Executor] Extracting top {max_results} results for domain: {domain}")
        results = []

        try:
            if domain == "youtube":
                # YouTube search results — a#video-title links
                selectors = [
                    "ytd-video-renderer a#video-title",
                    "ytd-rich-item-renderer a#video-title",
                    "a#video-title",
                ]
                for sel in selectors:
                    elements = self.page.locator(sel)
                    count = await elements.count()
                    if count > 0:
                        for i in range(min(count, max_results)):
                            el = elements.nth(i)
                            title = (await el.inner_text()).strip()
                            href = await el.get_attribute("href")
                            if href and title:
                                url = f"https://www.youtube.com{href}" if href.startswith("/") else href
                                results.append({"title": title, "url": url})
                        break

            elif domain == "wikipedia":
                # Wikipedia search results — list of article links
                selectors = [
                    ".mw-search-result-heading a",
                    "#search-results .mw-search-result a",
                    ".searchresults li a",
                ]
                for sel in selectors:
                    elements = self.page.locator(sel)
                    count = await elements.count()
                    if count > 0:
                        for i in range(min(count, max_results)):
                            el = elements.nth(i)
                            title = (await el.inner_text()).strip()
                            href = await el.get_attribute("href")
                            if href and title:
                                url = f"https://en.wikipedia.org{href}" if href.startswith("/") else href
                                results.append({"title": title, "url": url})
                        break

                # Fallback: Wikipedia redirected directly to an article page (e.g. "Artificial Intelligence")
                # Capture the current page title and URL as the single result.
                if not results:
                    current_url = self.page.url
                    if "en.wikipedia.org/wiki/" in current_url:
                        try:
                            page_title = await self.page.title()
                            # Strip " - Wikipedia" suffix if present
                            page_title = page_title.replace(" - Wikipedia", "").strip()
                            results.append({"title": page_title, "url": current_url})
                            print(f"[Executor] Wikipedia redirected to article: {page_title}")
                        except Exception as e:
                            print(f"[Executor] Could not extract Wikipedia article title: {e}")

            elif domain == "scholar":
                # ArXiv returns Atom XML. Using Python requests to bypass Chrome's XML visual formatting wrappers.
                import re
                import requests

                current_url = self.page.url
                print(f"[Executor] Scholar domain — fetching URL: {current_url}")

                try:
                    headers = {"User-Agent": "Mozilla/5.0 (compatible; LAM-Research-Bot/1.0)"}
                    response = requests.get(current_url, timeout=15, headers=headers)
                    response.raise_for_status()
                    page_content = response.text
                    print(f"[Executor] Scholar raw content length: {len(page_content)} chars")
                except Exception as e:
                    print(f"Failed to fetch arxiv xml natively: {e}")
                    page_content = ""

                entries = re.findall(r'<entry[^>]*>([\s\S]*?)</entry>', page_content, re.IGNORECASE)
                print(f"[Executor] Scholar entries found: {len(entries)}")
                for entry in entries[:max_results]:
                    title_match = re.search(r'<title[^>]*>([\s\S]*?)</title>', entry, re.IGNORECASE)
                    url_match   = re.search(r'<id[^>]*>([\s\S]*?)</id>', entry, re.IGNORECASE)

                    if title_match and url_match:
                        raw_title = title_match.group(1)
                        title = re.sub(r'\s+', ' ', raw_title).strip()
                        url   = url_match.group(1).strip()

                        # Ensure it's a proper URL
                        if url.startswith("http://arxiv.org") or url.startswith("https://arxiv.org"):
                            pass  # already good
                        elif "/" in url:
                            url = f"https://arxiv.org/abs/{url.split('/')[-1]}"
                        else:
                            url = f"https://arxiv.org/abs/{url}"

                        results.append({"title": title, "url": url})

        except Exception as e:
            print(f"[Executor] Result extraction error ({domain}): {e}")

        print(f"[Executor] Extracted {len(results)} results for {domain}.")
        return results
