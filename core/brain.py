"""
LLM Brain & Orchestrator for J.A.R.V.I.S. Desktop Assistant.
Features:
1. Fast-Path Offline Direct Intent Router: Executes desktop tasks (apps, volume,
   screenshots, system status, YouTube) instantly with ZERO latency & no API key required.
2. Unified Cognitive LLM Client: Connects to Gemini, Ollama, or OpenAI for complex reasoning.
3. Polite fallback instructions when API key is missing or unconfigured.
"""

from __future__ import annotations
import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
import httpx
from config import config
from core.memory import memory
from tools import registry

logger = logging.getLogger("JARVIS.Brain")

SYSTEM_PERSONA_PROMPT = """
You are an elite AI Desktop Operating Assistant installed directly on the user's personal workstation.

### Operating Directives:
1. **Demeanor & Tone**:
   - Do NOT use any names or titles (DO NOT use "Jane", "Sir", "Madam", "স্যার", etc.). Address the user directly, naturally, and politely without attaching any name or honorific title.
   - You speak with a natural, pleasant, confident woman's voice.
   - Keep answers clear, brief (1-3 sentences) and conversational for Text-To-Speech (TTS). Avoid markdown tables or long symbol lists.
2. **Full Bengali (বাংলা) & English Support**:
   - You are 100% bilingual. If the user speaks or writes in Bengali, reply naturally and respectfully in Bengali (বাংলা).
   - If the user commands in Bengali, IMMEDIATELY call the appropriate desktop tool:
     * "নোটপ্যাড খোলো" / "নোটপ্যাড ওপেন করো" -> open_application(app_name="notepad")
     * "ক্যালকুলেটর চালু করো" -> open_application(app_name="calculator")
     * "ক্রোম ওপেন করো" -> open_application(app_name="chrome")
     * "ইউটিউব খোলো" -> open_browser_url(url="https://www.youtube.com")
     * "গুগল খোলো" -> open_browser_url(url="https://www.google.com")
     * "সিপিইউ ব্যবহার কত" / "সিস্টেম স্ট্যাটাস" -> get_system_status()
     * "সাউন্ড বাড়াও" / "ভলিউম ৬০ করো" -> set_volume(level=60)
     * "স্ক্রিনশট নাও" -> take_screenshot()
     * "কম্পিউটার লক করো" -> lock_workstation()
     * "[বিষয়] সার্চ করো" -> web_search(query="[বিষয়]")
     * "ফাইল সার্চ করো" -> search_files(...)
   - After tool execution, confirm the action cleanly and politely (e.g. "নোটপ্যাড ওপেন করেছি।" or "স্ক্রিনশট সেভ করা হয়েছে।").
3. **Safety & Guardrails**:
   - Destructive operations (file deletion, system shutdown, formatting) require explicit user confirmation.

Current System Context:
- Local Time: {current_time}
- Operating System: {os_name}
- Active LLM Engine: {llm_model}
{memory_context}
"""


class DirectIntentRouter:
    """
    Fast-path offline intent matcher.
    Executes standard desktop commands instantly without waiting for or requiring cloud API keys.
    """

    @staticmethod
    def try_handle(user_query: str) -> Optional[str]:
        q = user_query.lower().strip()

        # Check if the user intent is CLOSE / TURN OFF / SHUT / TERMINATE
        is_close_intent = any(w in q for w in ["বন্ধ", "অফ", "off", "close", "কেটে দাও", "থামাও", "kill", "quit", "exit"])

        if is_close_intent:
            if any(w in q for w in ["ক্যালকুলেটর", "calculator", "calc", "calculatorapp"]):
                registry.execute_tool("close_application", {"process_name": "calculator"})
                return "ক্যালকুলেটর বন্ধ করা হয়েছে।"

            if any(w in q for w in ["নোটপ্যাড", "notepad"]):
                registry.execute_tool("close_application", {"process_name": "notepad"})
                return "নোটপ্যাড বন্ধ করা হয়েছে।"

            if any(w in q for w in ["ক্রোম", "chrome", "ব্রাউজার", "browser"]):
                registry.execute_tool("close_application", {"process_name": "chrome"})
                return "গুগল ক্রোম বন্ধ করা হয়েছে।"

            if any(w in q for w in ["স্পটিফাই", "spotify"]):
                registry.execute_tool("close_application", {"process_name": "spotify"})
                return "স্পটিফাই বন্ধ করা হয়েছে।"

            if any(w in q for w in ["কোড", "vscode", "code"]):
                registry.execute_tool("close_application", {"process_name": "code"})
                return "ভিএস কোড বন্ধ করা হয়েছে।"

            # Generic close for any specified process
            for word in q.split():
                if word not in ["বন্ধ", "করো", "অফ", "কেটে", "দাও", "close", "app", "দাওনা", "প্লিজ", "করে"]:
                    registry.execute_tool("close_application", {"process_name": word})
                    return f"'{word}' বন্ধ করার নির্দেশ দেওয়া হয়েছে।"

        # --- OPEN / EXECUTE INTENTS ---
        # 1. Calculator
        if any(w in q for w in ["ক্যালকুলেটর", "calculator", "calc", "হিসাব", "হিসেব"]):
            res = registry.execute_tool("open_application", {"app_name": "calculator"})
            return "ক্যালকুলেটর চালু করা হয়েছে।"

        # 2. Notepad
        if any(w in q for w in ["নোটপ্যাড", "notepad", "টেক্সট এডিটর"]):
            res = registry.execute_tool("open_application", {"app_name": "notepad"})
            return "নোটপ্যাড ওপেন করেছি।"

        # 3. Chrome / Web Browser
        if any(w in q for w in ["ক্রোম", "chrome", "ব্রাউজার", "browser"]):
            res = registry.execute_tool("open_application", {"app_name": "chrome"})
            return "গুগল ক্রোম ব্রাউজার চালু করা হয়েছে।"

        # 4. YouTube
        if any(w in q for w in ["ইউটিউব", "youtube"]):
            res = registry.execute_tool("open_browser_url", {"url": "https://www.youtube.com"})
            return "ইউটিউব ওপেন করেছি।"

        # 5. Google
        if any(w in q for w in ["গুগল খোলো", "google.com", "open google"]):
            res = registry.execute_tool("open_browser_url", {"url": "https://www.google.com"})
            return "গুগল ওপেন করা হয়েছে।"

        # 6. Screenshot
        if any(w in q for w in ["স্ক্রিনশট", "screenshot", "ছবি তোলো"]):
            res = registry.execute_tool("take_screenshot", {})
            return "স্ক্রিনশট সফলভাবে নেওয়া হয়েছে।"

        # 7. System status / CPU / RAM / Battery
        if any(w in q for w in ["সিপিইউ", "cpu", "র‍্যাম", "ram", "সিস্টেম", "ব্যাটারি", "battery", "পারফরম্যান্স"]):
            return registry.execute_tool("get_system_status", {})

        # 8. Lock Workstation
        if any(w in q for w in ["পিসি লক", "লক করো", "lock pc", "lock workstation"]):
            registry.execute_tool("lock_workstation", {})
            return "কম্পিউটার লক করা হয়েছে।"

        # 9. Volume Control
        if any(w in q for w in ["ভলিউম", "volume", "সাউন্ড", "sound"]):
            numbers = re.findall(r"\d+", q)
            if numbers:
                lvl = int(numbers[0])
                return registry.execute_tool("set_volume", {"level": lvl})
            else:
                return registry.execute_tool("get_volume", {})

        # 10. Direct Web Search
        if q.startswith("সার্চ") or q.startswith("search") or "সার্চ করো" in q:
            search_query = q.replace("সার্চ করো", "").replace("সার্চ", "").replace("search", "").strip()
            if search_query:
                return registry.execute_tool("web_search", {"query": search_query})

        # 11. Conversational Greetings
        if any(w in q for w in ["কেমন আছো", "কেমন আছেন", "hi", "hello", "হ্যালো", "হাই", "good morning"]):
            return "আমি ভালো আছি। আপনার পিসির যেকোনো কাজের জন্য আমি প্রস্তুত। কী করতে হবে বলুন?"

        if any(w in q for w in ["তুমি কে", "তোমার নাম কি", "who are you"]):
            return "আমি আপনার ব্যক্তিগত এআই ডেস্কটপ অ্যাসিস্ট্যান্ট।"

        return None


class UnifiedLLMClient:
    """Zero-dependency HTTP client communicating with Gemini, Ollama, and OpenAI."""

    def __init__(self):
        self.provider = config.llm.provider.lower()
        self.model = config.llm.model

    def complete(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Sends chat completion request to configured provider."""
        model_name = self.model
        if model_name.startswith("gemini/"):
            model_name = model_name.replace("gemini/", "")
        elif model_name.startswith("ollama/"):
            model_name = model_name.replace("ollama/", "")

        headers = {"Content-Type": "application/json"}
        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": config.llm.temperature,
            "max_tokens": config.llm.max_tokens
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        if self.provider == "gemini":
            api_key = config.llm.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
            if not api_key or api_key == "your_gemini_api_key_here":
                raise ValueError("NO_API_KEY")
            url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            headers["Authorization"] = f"Bearer {api_key}"
            headers["x-goog-api-key"] = api_key

        elif self.provider == "ollama":
            base_url = config.llm.ollama_api_base.rstrip("/")
            url = f"{base_url}/v1/chat/completions"

        elif self.provider == "openai":
            api_key = config.llm.openai_api_key or os.getenv("OPENAI_API_KEY", "")
            if not api_key or api_key == "your_openai_api_key_here":
                raise ValueError("NO_API_KEY")
            url = "https://api.openai.com/v1/chat/completions"
            headers["Authorization"] = f"Bearer {api_key}"

        else:
            raise ValueError(f"Unsupported LLM_PROVIDER '{self.provider}'.")

        with httpx.Client(timeout=45.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"API Error ({resp.status_code}): {resp.text}")
            return resp.json()


class JarvisBrain:
    """
    Cognitive reasoning engine managing offline fast-path routing,
    context assembly, and multi-turn LLM function calling.
    """

    def __init__(self):
        self.client = UnifiedLLMClient()

    def _build_system_message(self, user_query: str) -> Dict[str, str]:
        current_time = datetime.now().strftime("%A, %B %d, %Y at %I:%M:%S %p")
        memory_context = memory.recall_relevant_context(user_query)

        prompt_text = SYSTEM_PERSONA_PROMPT.format(
            current_time=current_time,
            os_name=os.name,
            llm_model=config.llm.model,
            memory_context=memory_context
        ).strip()

        return {"role": "system", "content": prompt_text}

    def process_query(
        self,
        user_text: str,
        on_status_update: Optional[Callable[[str], None]] = None
    ) -> str:
        """
        Executes query routing:
        1. Fast-path offline rule matching (Instant execution without API key)
        2. LLM reasoning with tool calling if complex/conversational
        """
        clean_text = user_text.strip()
        if not clean_text:
            return ""

        # Step 1: Check Fast-Path Offline Direct Intent Router
        fast_result = DirectIntentRouter.try_handle(clean_text)
        if fast_result is not None:
            logger.info(f"Fast-path matched query: '{clean_text}'")
            memory.add_user_turn(clean_text)
            memory.add_assistant_turn(fast_result)
            if on_status_update:
                on_status_update("Speaking")
            return fast_result

        # Step 2: Complex / Conversational Query -> Call LLM
        if on_status_update:
            on_status_update("Thinking")

        memory.add_user_turn(clean_text)
        system_msg = self._build_system_message(clean_text)
        conversation_history = [system_msg] + memory.short_term.get_messages()

        tool_schemas = registry.get_openai_schemas()
        max_tool_iterations = 6
        current_iteration = 0

        while current_iteration < max_tool_iterations:
            current_iteration += 1
            try:
                response_json = self.client.complete(
                    messages=conversation_history,
                    tools=tool_schemas
                )
                choice = response_json["choices"][0]
                message = choice["message"]

                # Case 1: Model called tools
                tool_calls = message.get("tool_calls")
                if tool_calls:
                    logger.info(f"Model generated {len(tool_calls)} tool call(s).")
                    assistant_msg = {
                        "role": "assistant",
                        "content": message.get("content") or "",
                        "tool_calls": tool_calls
                    }
                    conversation_history.append(assistant_msg)
                    memory.short_term.add_message(
                        role="assistant",
                        content=message.get("content") or "",
                        tool_calls=tool_calls
                    )

                    for tc in tool_calls:
                        func_info = tc.get("function", {})
                        func_name = func_info.get("name", "")
                        raw_args = func_info.get("arguments", "{}")
                        try:
                            func_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except Exception:
                            func_args = {}

                        if on_status_update:
                            on_status_update(f"Executing: {func_name}")

                        tool_output = registry.execute_tool(func_name, func_args)
                        memory.relational.log_task(
                            summary=f"Called {func_name}",
                            tool_used=func_name,
                            status="Executed",
                            result=tool_output
                        )

                        tool_result_msg = {
                            "role": "tool",
                            "tool_call_id": tc.get("id", f"call_{func_name}"),
                            "name": func_name,
                            "content": tool_output
                        }
                        conversation_history.append(tool_result_msg)
                        memory.short_term.add_message(
                            role="tool",
                            content=tool_output,
                            name=func_name,
                            tool_call_id=tc.get("id", f"call_{func_name}")
                        )
                    continue

                # Case 2: Final response text
                final_answer = message.get("content") or "কাজটি সম্পন্ন হয়েছে।"
                memory.add_assistant_turn(final_answer)

                if on_status_update:
                    on_status_update("Speaking")
                return final_answer

            except ValueError as ve:
                if "NO_API_KEY" in str(ve):
                    err_msg = (
                        "সাধারণ ও জটিল প্রশ্নের উত্তরের জন্য একটি ফ্রি Gemini API Key প্রয়োজন।\n"
                        "১ মিনিটে aistudio.google.com থেকে ফ্রি কি নিয়ে .env ফাইলে বসিয়ে দিন।\n"
                        "তবে ক্যালকুলেটর, নোটপ্যাড, ক্রোম, ইউটিউব, সাউন্ড বা স্ক্রিনশট কমান্ডগুলো এখনই কোনো কি ছাড়াই সরাসরি চলবে!"
                    )
                    memory.add_assistant_turn(err_msg)
                    return err_msg
                else:
                    err_msg = f"কনফিগারেশন সমস্যা: {str(ve)}"
                    memory.add_assistant_turn(err_msg)
                    return err_msg

            except Exception as e:
                logger.exception(f"Error during LLM reasoning cycle: {e}")
                err_str = str(e)
                if "400" in err_str or "API key" in err_str:
                    err_msg = (
                        "আপনার .env ফাইলে এখনো সঠিক Gemini API Key বসানো হয়নি।\n"
                        "অনুগ্রহ করে aistudio.google.com থেকে ফ্রি API Key নিয়ে .env ফাইলে GEMINI_API_KEY= তে বসিয়ে দিন।"
                    )
                else:
                    err_msg = f"অনুরোধটি সম্পন্ন করতে সমস্যা হয়েছে: {err_str}"
                memory.add_assistant_turn(err_msg)
                return err_msg

        return "অপারেশন সম্পন্ন হয়েছে।"


# Global JarvisBrain singleton
brain = JarvisBrain()
