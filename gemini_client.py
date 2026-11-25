from __future__ import annotations
import os
import aiohttp


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = (api_key or os.getenv("GEMINI_API_KEY") or "").strip()
        raw_model = (model or os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()
        self.model = "gemini-3.5-flash-lite" if "3.8" in raw_model else raw_model

    async def generate(self, prompt: str, system_instruction: str = "") -> str:
        if not self.api_key:
            return "GEMINI_API_KEY tanımlı değil."
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.65, "maxOutputTokens": 300},
        }
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                    data = await resp.json(content_type=None)
                    if resp.status != 200:
                        err_msg = ""
                        if isinstance(data, dict):
                            err_msg = (data.get("error") or {}).get("message") or str(data)
                        return f"Gemini HTTP {resp.status} ({self.model}): {err_msg[:220]}"
                    candidates = data.get("candidates") or []
                    if not candidates:
                        return "Boş yanıt döndü."
                    parts = ((candidates[0].get("content") or {}).get("parts")) or []
                    texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
                    return "\n".join(texts).strip() or "Yanıt metni boş geldi."
        except Exception as exc:
            return f"Bağlantı hatası: {exc}"

from retry_helper import run_with_503_retry


def run_gemini_with_retry(fn, *args, max_retries: int = 3, base_delay: float = 1.0, **kwargs):
    """Mevcut Gemini istek fonksiyonunu 503 yeniden deneme ile sarar."""
    return run_with_503_retry(fn, *args, max_retries=max_retries, base_delay=base_delay, **kwargs)

    def _offline_fallback(self, prompt: str, reason: str = "çevrimdışı") -> str:
        text = (prompt or "").strip()
        lowered = text.lower()
        if not text:
            return f"[{reason.upper()} MOD] Bağlantı şu an yok; yerel araçlarla (hesapla, durum, not, sistem) devam edebilirim."
        if any(k in lowered for k in ("merhaba", "selam", "naber", "nasılsın", "nasılsın?")):
            return f"[{reason.upper()} MOD] Selam, buradayım. İnternet bağlantısı olmasa da yerel görev ve araçlarla çalışmayı sürdürüyorum."
        if any(k in lowered for k in ("durum", "sistem", "saat", "tarih")):
            return f"[{reason.upper()} MOD] Yerel mod aktif. 'durum' veya 'sistem' komutlarıyla anlık bellek ve saat bilgisini alabilirsin."
        if lowered.startswith("not"):
            return f"[{reason.upper()} MOD] Not komutunu 'not <metin>' biçiminde kullanarak yerel belleğe kaydedebilirsin."
        return (
            f"[{reason.upper()} MOD] Gemini API'ye şu an ulaşılamıyor ({reason}). "
            f"Yerel modda '{text[:80]}' isteğini aldım; hesapla, durum, not ve sistem komutları çevrimdışı çalışmaya devam ediyor."
        )
