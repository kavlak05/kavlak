from __future__ import annotations
import asyncio
import logging
import os
from gemini_client import GeminiClient
from web_avatar_server import WebAvatarServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("nexus")


from agent_module import NexusAgent
from gemini_client import run_gemini_with_retry

from pathlib import Path
import json

class MetaHumanSystem:
    def __init__(self):
        self.gemini = GeminiClient()
        self.agent = NexusAgent()
        self.task_queue = ["monitor_holo_core", "hesapla (12 + 8) * 3 / 2"]
        self.cycle_history: list[dict] = []
        self.max_history = 20
        self.cycle_count = 0
        self.last_action = "idle"
        self.web_server = WebAvatarServer(
            state_provider=self.get_state,
            chat_handler=self.handle_chat,
            cycle_handler=self.run_cycle,
            http_host="127.0.0.1",
            http_port=8080,
        )

    def get_state(self) -> dict:
        return {"cycle_count": self.cycle_count, "last_action": self.last_action, "model": self.gemini.model}

    async def handle_chat(self, message: str) -> dict:
        reply = await self.gemini.generate(
            prompt=message,
            system_instruction="Sen NEXUS CORE adlı otonom yapay zeka asistanısın. Kısa, doğal, net ve Türkçe yanıt ver.",
        )
        return {"reply_text": reply, "emotion": "focused"}

    def _next_task(self) -> str:
        if self.task_queue:
            return self.task_queue.pop(0)
        if self.cycle_count % 2 == 0:
            return f"hesapla ({self.cycle_count} + 4) * 2"
        return "monitor_holo_core"

    async def _generate_cycle_note(self, task: str, agent_output: str) -> str:
        prompt = (
            f"Döngü #{self.cycle_count} için kısa tek cümlelik durum notu üret. "
            f"Görev: {task} | Ajan çıktısı: {agent_output}"
        )
        try:
            def _invoke_gemini():
                if hasattr(self.gemini, "generate"):
                    return run_gemini_with_retry(
                        lambda: asyncio.run(self.gemini.generate(prompt)),
                        max_retries=2,
                        base_delay=0.5,
                    )
                return f"Model hazır ({self.gemini.model}): {agent_output}"

            result = await asyncio.to_thread(_invoke_gemini)
            return str(result).strip()
        except Exception as exc:
            log.warning("Gemini döngü notu atlandı: %s", exc)
            return f"Yerel çıktı: {agent_output}"

    def get_recent_cycles(self, limit: int = 5) -> list[dict]:
        if limit <= 0:
            return []
        return self.cycle_history[-limit:]


    STATE_FILE = Path("data/nexus_state.json")

    def save_state(self) -> None:
        try:
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "cycle_history": list(getattr(self, "cycle_history", []))[-20:],
                "agent": self.agent.export_state() if hasattr(self.agent, "export_state") else {},
            }
            self.STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def load_state(self) -> None:
        try:
            if not self.STATE_FILE.exists():
                return
            payload = json.loads(self.STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                cycles = payload.get("cycle_history")
                if isinstance(cycles, list) and hasattr(self, "cycle_history"):
                    self.cycle_history = cycles[-20:]
                agent_data = payload.get("agent")
                if isinstance(agent_data, dict) and hasattr(self.agent, "load_state"):
                    self.agent.load_state(agent_data)
        except Exception:
            pass

    async def run_cycle(self) -> dict:
        self.cycle_count += 1
        task = self._next_task()
        self.last_action = task
        self.agent.perceive(task)
        agent_output = self.agent.act()
        log.info(
            "Otonom döngü #%s tamamlandı -> aksiyon=%s, çıktı=%s, model=%s",
            self.cycle_count,
            self.last_action,
            agent_output,
            self.gemini.model,
        )
        gemini_note = await self._generate_cycle_note(task, agent_output)
        record = {
            "cycle": self.cycle_count,
            "action": self.last_action,
            "output": agent_output,
            "gemini_note": gemini_note,
        }
        self.cycle_history.append(record)
        if len(self.cycle_history) > self.max_history:
            self.cycle_history = self.cycle_history[-self.max_history :]
        return record

    async def main_loop(self):
        await self.web_server.start()
        log.info("Web Hologram Avatar arayüzü aktif: http://localhost:8080 (model=%s)", self.gemini.model)
        interval = int(os.getenv("AUTONOMY_INTERVAL_SEC", "900"))
        try:
            while True:
                await asyncio.sleep(interval)
                await self.run_cycle()
        finally:
            await self.web_server.stop()


if __name__ == "__main__":
    system = MetaHumanSystem()
    asyncio.run(system.main_loop())
