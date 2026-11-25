from __future__ import annotations
import asyncio
import logging
import shutil
import subprocess
from aiohttp import web

log = logging.getLogger("nexus.web_avatar")


class WebAvatarServer:
    def __init__(self, *args, state_provider=None, chat_handler=None, cycle_handler=None, host: str = "127.0.0.1", port: int = 8080, http_host: str = None, http_port: int = None, **kwargs):
        if len(args) >= 1 and state_provider is None:
            state_provider = args[0]
        if len(args) >= 2 and chat_handler is None:
            chat_handler = args[1]
        if len(args) >= 3 and cycle_handler is None:
            cycle_handler = args[2]
        self.state_provider = state_provider
        self.chat_handler = chat_handler
        self.cycle_handler = cycle_handler
        self.host = http_host or kwargs.get("host_ip") or host
        raw_port = http_port if http_port is not None else kwargs.get("web_port", port)
        self.port = int(raw_port if raw_port is not None else 8080)
        self.app = web.Application()
        self.app.router.add_get("/", self._handle_index)
        self.app.router.add_get("/api/state", self._handle_state)
        self.app.router.add_post("/api/chat", self._handle_chat)
        self.app.router.add_post("/api/cycle", self._handle_cycle)
        self.app.router.add_post("/api/speak", self._handle_speak)
        self._runner = None
        self._say_proc: subprocess.Popen | None = None
        self._tr_voice: str | None = self._detect_turkish_voice()

    def _detect_turkish_voice(self) -> str | None:
        say_bin = shutil.which("say")
        if not say_bin:
            return None
        try:
            out = subprocess.check_output([say_bin, "-v", "?"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and ("tr_TR" in line or parts[0].lower() in {"yelda", "cem"}):
                    return parts[0]
        except Exception:
            pass
        return None

    def _stop_speaking(self) -> None:
        if self._say_proc and self._say_proc.poll() is None:
            try:
                self._say_proc.terminate()
                self._say_proc.wait(timeout=0.5)
            except Exception:
                try:
                    self._say_proc.kill()
                except Exception:
                    pass
        self._say_proc = None

    async def _handle_index(self, request: web.Request) -> web.Response:
        return web.Response(text=self._render_html(), content_type="text/html", charset="utf-8")

    async def _handle_state(self, request: web.Request) -> web.Response:
        st = self.state_provider() if callable(self.state_provider) else {}
        return web.json_response(st)

    async def _handle_chat(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}
        msg = (data.get("message") or data.get("text") or "").strip()
        if not msg:
            return web.json_response({"ok": False, "reply_text": "Boş mesaj alındı."}, status=400)
        res = await self.chat_handler(msg) if callable(self.chat_handler) else "Hazırım."
        if isinstance(res, dict):
            return web.json_response({
                "ok": True,
                "reply_text": res.get("reply_text") or res.get("reply") or res.get("text") or str(res),
                "visemes": res.get("visemes") or [],
                "emotion": res.get("emotion") or "neutral",
            })
        return web.json_response({"ok": True, "reply_text": str(res), "visemes": [], "emotion": "neutral"})

    async def _handle_cycle(self, request: web.Request) -> web.Response:
        res = await self.cycle_handler() if callable(self.cycle_handler) else {"status": "ok"}
        return web.json_response({"ok": True, **(res if isinstance(res, dict) else {})})

    async def _handle_speak(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}
        if data.get("stop"):
            self._stop_speaking()
            return web.json_response({"ok": True, "stopped": True})
        txt = (data.get("text") or "").strip()
        if txt:
            self._stop_speaking()
            say_bin = shutil.which("say") or "/usr/bin/say"
            cmd = [say_bin]
            if self._tr_voice:
                cmd.extend(["-v", self._tr_voice])
            cmd.extend(["-r", "185", txt])
            try:
                self._say_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                log.info("Ses oynatılıyor (voice=%s): %s", self._tr_voice or "varsayılan", txt[:60])
            except Exception as exc:
                log.warning("say komutu başlatılamadı: %s", exc)
        return web.json_response({"ok": True, "voice": self._tr_voice})

    async def start(self) -> web.AppRunner:
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        await web.TCPSite(self._runner, self.host, self.port).start()
        return self._runner

    async def stop(self) -> None:
        self._stop_speaking()
        if self._runner:
            await self._runner.cleanup()

    def _render_html(self) -> str:
        return """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>NEXUS CORE — Hologram Sesli Avatar</title>
<style>
  :root {
    --bg: #050811;
    --glass: rgba(14, 21, 38, 0.78);
    --line: rgba(148, 163, 184, 0.16);
    --txt: #f8fafc;
    --sub: #94a3b8;
    --c1: #00e5ff;
    --c2: #7c4dff;
    --c3: #00e676;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", sans-serif; }
  body {
    min-height: 100vh;
    background: radial-gradient(ellipse at 18% 12%, rgba(0, 229, 255, 0.16), transparent 45%),
                radial-gradient(ellipse at 82% 85%, rgba(124, 77, 255, 0.18), transparent 48%),
                var(--bg);
    color: var(--txt);
    display: flex; align-items: center; justify-content: center; padding: 20px;
  }
  .shell { width: 100%; max-width: 980px; display: grid; grid-template-columns: 350px 1fr; gap: 20px; }
  @media (max-width: 820px) { .shell { grid-template-columns: 1fr; } }
  .panel {
    background: var(--glass); backdrop-filter: blur(22px);
    border: 1px solid var(--line); border-radius: 26px; padding: 22px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255,255,255,0.06);
  }
  .avatar-col { display: flex; flex-direction: column; align-items: center; justify-content: space-between; gap: 18px; text-align: center; }
  .holo-box { position: relative; width: 210px; height: 210px; display: flex; align-items: center; justify-content: center; }
  .ring-outer {
    position: absolute; inset: 0; border-radius: 50%;
    border: 1.5px solid rgba(0, 229, 255, 0.35);
    box-shadow: 0 0 35px rgba(0, 229, 255, 0.14);
    animation: spinSlow 14s linear infinite;
  }
  .ring-inner {
    position: absolute; inset: 18px; border-radius: 50%;
    background: radial-gradient(circle at 32% 28%, rgba(255,255,255,0.22), transparent 36%),
                radial-gradient(circle at 70% 75%, rgba(124,77,255,0.45), rgba(10,16,32,0.95) 70%);
    border: 1px solid rgba(255,255,255,0.14);
    display: flex; align-items: center; justify-content: center;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }
  .bars { display: flex; align-items: center; gap: 6px; height: 54px; }
  .bar { width: 6px; height: 12px; border-radius: 999px; background: linear-gradient(180deg, var(--c1), var(--c2)); transition: height 0.09s ease; }
  .listening .ring-outer { border-color: rgba(0, 230, 118, 0.75); animation-duration: 5s; }
  .speaking .ring-outer { border-color: rgba(124, 77, 255, 0.85); animation-duration: 3s; }
  .speaking .ring-inner { transform: scale(1.05); }
  @keyframes spinSlow { to { transform: rotate(360deg); } }
  .badge { font-size: 12.5px; color: #e2e8f0; background: rgba(15, 23, 42, 0.78); border: 1px solid var(--line); padding: 7px 14px; border-radius: 999px; }
  .btn-stack { width: 100%; display: flex; flex-direction: column; gap: 10px; }
  button { border: none; border-radius: 14px; padding: 12px 16px; font-size: 14px; font-weight: 600; cursor: pointer; }
  .primary { background: linear-gradient(135deg, var(--c1), var(--c2)); color: #04101f; }
  .danger { background: rgba(255, 82, 82, 0.16); color: #ff9e9e; border: 1px solid rgba(255, 82, 82, 0.42); }
  .ghost { background: rgba(30, 41, 59, 0.72); color: var(--txt); border: 1px solid var(--line); }
  .chat-col { display: flex; flex-direction: column; height: 560px; }
  .top-bar { display: flex; justify-content: space-between; align-items: center; padding-bottom: 14px; border-bottom: 1px solid var(--line); }
  .top-bar h1 { font-size: 17px; }
  .top-bar span { font-size: 12px; color: var(--sub); }
  .feed { flex: 1; overflow-y: auto; padding: 16px 4px; display: flex; flex-direction: column; gap: 12px; }
  .bubble { max-width: 82%; padding: 11px 15px; border-radius: 16px; font-size: 14px; line-height: 1.5; word-wrap: break-word; }
  .bubble.user { align-self: flex-end; background: linear-gradient(135deg, #2563eb, #6d28d9); color: #fff; }
  .bubble.ai { align-self: flex-start; background: rgba(25, 36, 58, 0.88); border: 1px solid var(--line); }
  .input-row { display: flex; gap: 10px; padding-top: 12px; border-top: 1px solid var(--line); }
  .input-row input { flex: 1; background: rgba(10, 15, 29, 0.85); border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px; color: var(--txt); font-size: 14px; outline: none; }
</style>
</head>
<body>
<div class="shell">
  <div class="panel avatar-col" id="avatarPanel">
    <div>
      <div style="font-size:12px;letter-spacing:1.4px;color:var(--sub);text-transform:uppercase;">Hologram Arayüz</div>
      <div style="font-size:19px;font-weight:700;margin-top:4px;">NEXUS CORE</div>
    </div>
    <div class="holo-box">
      <div class="ring-outer"></div>
      <div class="ring-inner">
        <div class="bars" id="waveBars">
          <div class="bar"></div><div class="bar"></div><div class="bar"></div>
          <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        </div>
      </div>
    </div>
    <div class="badge" id="statusBadge">Hazır — Konuşmak için bas</div>
    <div class="btn-stack">
      <button class="primary" id="micBtn" type="button" onclick="toggleConversation()">Konuşmaya Başla</button>
      <button class="danger" id="stopBtn" type="button" onclick="stopConversation()">Durdur</button>
      <button class="ghost" type="button" onclick="triggerCycle()">Otonom Döngü</button>
    </div>
  </div>
  <div class="panel chat-col">
    <div class="top-bar">
      <h1>NEXUS CORE — Canlı Sesli Köprü</h1>
      <span>gemini-3.5-flash-lite</span>
    </div>
    <div class="feed" id="chatFeed">
      <div class="bubble ai">Merhaba. "Konuşmaya Başla" butonuna basıp konuşabilir veya buradan yazabilirsin.</div>
    </div>
    <form class="input-row" onsubmit="handleSubmit(event)">
      <input id="msgInput" type="text" placeholder="Bir şey yaz veya konuş..." autocomplete="off" />
      <button class="primary" type="submit">Gönder</button>
    </form>
  </div>
</div>
<script>
let activeSession = false, recognizer = null, waveTimer = null, waitTimer = null;
const setStatus = t => { const e = document.getElementById("statusBadge"); if (e) e.textContent = t; };
const appendBubble = (role, text) => {
  const f = document.getElementById("chatFeed"); if (!f || !text) return;
  const d = document.createElement("div"); d.className = "bubble " + (role === "user" ? "user" : "ai"); d.textContent = text;
  f.appendChild(d); f.scrollTop = f.scrollHeight;
};
function animateMouth(v, txt) {
  const p = document.getElementById("avatarPanel"), bars = Array.from(document.querySelectorAll("#waveBars .bar"));
  if (waveTimer) clearInterval(waveTimer);
  const dur = Math.min(12000, Math.max(1200, (txt || "").length * 62));
  if (p) p.classList.add("speaking");
  const t0 = Date.now();
  waveTimer = setInterval(() => {
    if (Date.now() - t0 >= dur) { clearInterval(waveTimer); waveTimer = null; bars.forEach(b => b.style.height = "12px"); if (p) p.classList.remove("speaking"); return; }
    bars.forEach(b => b.style.height = (10 + Math.floor(Math.random() * 38)) + "px");
  }, 85);
}
async function speakText(txt) {
  const clean = (txt || "").trim(); if (!clean) return;
  animateMouth([], clean);
  try { await fetch("/api/speak", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({text: clean}) }); } catch (e) {}
  await new Promise(r => { waitTimer = setTimeout(r, Math.min(11000, Math.max(1400, clean.length * 64))); });
}
async function sendPrompt(txt) {
  const clean = (txt || "").trim(); if (!clean) return;
  appendBubble("user", clean); setStatus("Yanıt hazırlanıyor...");
  try {
    const r = await fetch("/api/chat", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({message: clean, text: clean}) });
    const d = await r.json();
    const rep = d.reply_text || d.reply || d.text || "Yanıt alındı.";
    appendBubble("ai", rep); await speakText(rep);
  } catch (e) { setStatus("Bağlantı hatası"); }
  finally { if (activeSession) startListening(); else setStatus("Hazır"); }
}
function handleSubmit(ev) { ev.preventDefault(); const i = document.getElementById("msgInput"); if (!i) return; const v = i.value.trim(); if (!v) return; i.value = ""; sendPrompt(v); }
function startListening() {
  if (!activeSession) return;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { setStatus("Tarayıcı ses tanımayı desteklemiyor"); activeSession = false; updateMicButton(); return; }
  try { if (recognizer) recognizer.abort(); } catch (e) {}
  recognizer = new SR(); recognizer.lang = "tr-TR"; recognizer.interimResults = false; recognizer.maxAlternatives = 1;
  const p = document.getElementById("avatarPanel"); if (p) p.classList.add("listening"); setStatus("Seni dinliyorum...");
  recognizer.onresult = ev => { if (p) p.classList.remove("listening"); const sp = (ev.results[0][0].transcript || "").trim(); if (!sp) { if (activeSession) startListening(); return; } sendPrompt(sp); };
  recognizer.onerror = ev => { if (p) p.classList.remove("listening"); if (!activeSession) return; if (ev.error === "not-allowed" || ev.error === "service-not-allowed") { setStatus("Mikrofon izni gerekli"); activeSession = false; updateMicButton(); return; } setTimeout(() => { if (activeSession) startListening(); }, 500); };
  recognizer.onend = () => { if (p) p.classList.remove("listening"); };
  try { recognizer.start(); } catch (e) {}
}
function updateMicButton() { const b = document.getElementById("micBtn"); if (b) b.textContent = activeSession ? "Konuşmayı Kapat" : "Konuşmaya Başla"; }
async function toggleConversation() { if (activeSession) { await stopConversation(); return; } activeSession = true; updateMicButton(); await speakText("Seni dinliyorum, konuşabilirsin."); if (activeSession) startListening(); }
async function stopConversation() {
  activeSession = false; updateMicButton();
  if (waitTimer) { clearTimeout(waitTimer); waitTimer = null; }
  if (waveTimer) { clearInterval(waveTimer); waveTimer = null; }
  const p = document.getElementById("avatarPanel"), bars = Array.from(document.querySelectorAll("#waveBars .bar"));
  if (p) p.classList.remove("speaking", "listening"); bars.forEach(b => b.style.height = "12px");
  try { if (recognizer) recognizer.abort(); } catch (e) {}
  try { await fetch("/api/speak", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({stop: true}) }); } catch (e) {}
  setStatus("Durduruldu");
}
async function triggerCycle() { setStatus("Otonom döngü çalışıyor..."); try { await fetch("/api/cycle", {method: "POST"}); setStatus("Otonom döngü tamamlandı"); } catch (e) { setStatus("Döngü hatası"); } }
</script>
</body>
</html>"""
