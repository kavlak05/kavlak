from __future__ import annotations
import datetime
import json
import platform
from safe_evaluator import safe_evaluate, logger


class NexusAgent:
    def __init__(self):
        self.memory = []
        self.tools = {
            "hesapla": self._safe_calc_tool,
            "durum": self._memory_status_tool,
            "not": self._notes_tool,
        }
        self.notes: list[str] = []

    def _safe_calc_tool(self, expression: str) -> str:
        try:
            value = safe_evaluate(expression)
            return f"İşlem sonucu: {value}"
        except ZeroDivisionError:
            return "Hesaplama yapılamadı: sıfıra bölme hatası."
        except Exception as exc:
            logger.error("Araç çalıştırma hatası ('%s'): %s", expression, exc)
            return "Hesaplama yapılamadı: geçersiz veya güvensiz ifade."

    def _memory_status_tool(self, _arg: str = "") -> str:
        total = len(self.memory)
        if total == 0:
            return "Bellek boş; henüz kayıtlı adım yok."
        last_item = self.memory[-1]
        return f"Toplam {total} bellek adımı var; son kayıt ({last_item['role']}): {last_item['content']}"

    def _notes_tool(self, payload: str) -> str:
        text = payload.strip()
        if not text or text.lower() in {"liste", "listele", "göster", "goster"}:
            if not self.notes:
                return "Kayıtlı not bulunmuyor."
            return "Notlar: " + " | ".join(f"{i+1}. {n}" for i, n in enumerate(self.notes))
        self.notes.append(text)
        return f"Not kaydedildi (#{len(self.notes)}): {text}"

    def _file_tool(self, payload: str) -> str:
        rel = payload.strip()
        if not rel:
            return "Kullanım: dosya <dosya_adi> (örnek: dosya data/nexus_state.json)"
        base = Path.cwd().resolve()
        target = (base / rel).resolve()
        if base not in target.parents and target != base:
            return "Güvenlik uyarısı: çalışma dizini dışındaki dosyalara erişilemez."
        if not target.exists() or not target.is_file():
            return f"Dosya bulunamadı: {rel}"
        try:
            raw = target.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return f"Dosya okunamadı: {exc}"
        lines = raw.splitlines()
        preview = " / ".join(lines[:3])[:220]
        return f"Dosya '{rel}' | Satır: {len(lines)}, Karakter: {len(raw)} | Özet: {preview or 'boş'}"

    def _reminder_tool(self, payload: str) -> str:
        text = payload.strip()
        if not text or text.lower() in {"liste", "listele", "göster", "goster"}:
            if not self.reminders:
                return "Bekleyen hatırlatıcı bulunmuyor."
            parts = [f"#{i+1} ({r['due_cycle']}. döngü): {r['message']}" for i, r in enumerate(self.reminders)]
            return "Hatırlatıcılar: " + " | ".join(parts)
        parts = text.split(maxsplit=1)
        if len(parts) == 2 and parts[0].isdigit():
            offset = max(1, int(parts[0]))
            msg = parts[1].strip()
        else:
            offset = 3
            msg = text
        due = max(1, self.cycle_count + offset)
        self.reminders.append({"due_cycle": due, "message": msg})
        return f"Hatırlatıcı eklendi (#{due}. döngü): {msg}"

    def tick_reminders(self, current_cycle: int, recent_cycles: list[dict] = None) -> list[str]:
        self._ensure_state()
        self.cycle_count = max(self.cycle_count, int(current_cycle))
        if isinstance(recent_cycles, list):
            self.recent_cycles = recent_cycles[-20:]
        triggered: list[str] = []
        remaining: list[dict] = []
        for r in self.reminders:
            if int(r.get("due_cycle", 0)) <= self.cycle_count:
                triggered.append(f"Hatırlatıcı: {r.get('message', '')}")
            else:
                remaining.append(r)
        self.reminders = remaining
        return triggered

    def _health_tool(self, _payload: str = "") -> str:
        mem_len = len(getattr(self, "memory", []))
        notes_len = len(getattr(self, "notes", []))
        rem_len = len(self.reminders)
        cyc_len = len(self.recent_cycles)
        return (
            f"Sağlık Özeti: AKTİF | Döngü: {self.cycle_count} | Kayıtlı Döngü: {cyc_len} | "
            f"Bellek Adımı: {mem_len} | Not: {notes_len} | Hatırlatıcı: {rem_len}"
        )

    def _run_single_command(self, cmd: str) -> str:
        cmd = cmd.strip()
        if not cmd:
            return ""
        self.perceive(cmd)
        return self.act()

    def _plan_tool(self, payload: str) -> str:
        steps = [s.strip() for s in payload.split("|") if s.strip()]
        if not steps:
            return "Kullanım: planla <komut1 | komut2 | ...>"
        results: list[str] = []
        for idx, step in enumerate(steps, start=1):
            out = self._run_single_command(step)
            results.append(f"Adım {idx} ({step}): {out}")
        return " | ".join(results)

    def _ensure_state(self) -> None:
        if not hasattr(self, "memory") or not isinstance(self.memory, list):
            self.memory = []
        if not hasattr(self, "notes") or not isinstance(self.notes, list):
            self.notes = []
        if not hasattr(self, "reminders") or not isinstance(self.reminders, list):
            self.reminders = []
        if not hasattr(self, "cycle_count") or not isinstance(self, object):
            self.cycle_count = 0
        if not hasattr(self, "cycle_count"):
            self.cycle_count = 0
        if not hasattr(self, "recent_cycles") or not isinstance(self.recent_cycles, list):
            self.recent_cycles = []
        if not hasattr(self, "tools") or not isinstance(self.tools, dict):
            self.tools = {}

    def perceive(self, input_data: str) -> None:
        logger.info("[Algılandı]: %s", input_data)
        self.memory.append({"role": "user", "content": input_data})

    def plan(self):
        if not self.memory:
            return "respond", "Merhaba, nasıl yardımcı olabilirim?"
        last_input = self.memory[-1]["content"].strip()
        lowered = last_input.lower()
        if lowered == "monitor_holo_core":
            return "respond", f"Holo Core durumu normal; kayıtlı bellek adımı: {len(self.memory)}."
        if lowered.startswith("durum"):
            return "tool_durum", ""
        if lowered.startswith("not"):
            rest = last_input[3:].strip()
            return "tool_not", rest
        if lowered.startswith("hesapla"):
            expr = last_input[len("hesapla"):].strip()
            return "tool_hesapla", expr
        return "respond", "Merhaba, nasıl yardımcı olabilirim?"

    def act(self) -> str:
        action_type, data = self.plan()
        if action_type == "tool_hesapla":
            response = self.tools["hesapla"](data)
        elif action_type == "tool_durum":
            response = self.tools["durum"](data)
        elif action_type == "tool_not":
            response = self.tools["not"](data)
        else:
            response = data
        logger.info("[Eylem]: %s", response)
        self.memory.append({"role": "assistant", "content": response})
        return response
