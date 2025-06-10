# Astrape Core

_A line in the sand. A spark in the storm._

**Astrape Core** is a modular, locally hosted AI orchestration layer designed for flexibility, control, and extensibility. It is the foundation for larger systems — those meant to serve, not surveil.

This release is the first public artifact: a minimal, functional loop for voice-based interaction.

---
This repository contains the essential skeleton required to build natural language interfaces with:

- Modular orchestration logic
- Speech-to-text / Text-to-speech integration
- Event recognition and system state management
- Simple tool invocation interface
- Stateless loop with memory-ready scaffolding

### ❗ Status
Pre-alpha. Active development. Public loop is functional, but future modules (memory, tools, auth) are pending.

### 🔍 Philosophy
We believe in software that answers to its user. Astrape Core is built to run on your machines, with your data, under your control.

No cloud. No gatekeepers.

## 🔁 What It Does

- Wake/sleep word detection
- Async voice pipeline: **STT → LLM → TTS**
- Modular architecture (drop-in replacements supported)
- TTS failover fallback (Edge, Google, or Coqui)

---

## 📦 What’s Included

| Module           | Description                              |
|------------------|------------------------------------------|
| `core/`          | Orchestration, event logic, main loop    |
| `speech/`        | Whisper STT, TTS wrappers, config-driven |
| `listen/`        | Mic input and event listener             |
| `setup/`         | YAML config loader + default management  |
| `utils/`         | Logger, system tools                     |
| `start.py`       | Entry point for running Astrape Core     |

---

## 🧪 Quick Start

> Requires Python 3.11+ and [LM Studio](https://lmstudio.ai/) for LLM backend

[LM Studio](https://lmstudio.ai)  
[Edge TTS](https://pypi.org/project/edge-tts/)  
[Coqui TTS](https://github.com/coqui-ai/TTS)

1. Set TTS provider (edge (cloud), coqui(local), etc)
2. Set STT provider (google (cloud), whisper(local), etc)
3. Add Local LM Studio Endpoint

4. Clone repo and create virtual environment:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
+```

### 🗣️ Example Usage

> 🧍 "Hey Eliza, can you tell me a story?"  
> 💬 *(LLM responds)* 
> 🔊 *(TTS speaks back using Edge or Coqui)*
> 🧍 "Eliza Sleep"  
> 💻 *(sleep detected)*
> 🧍 "Shut Down" (Can be said from either waking or sleep to trigger)
> 💻 *(system shutdown)*


### 📜 License
This repository is released under the **GNU Affero General Public License v3.0**.

Commercial and extended systems may build from this base, but are licensed separately.

---

### 🌱 Origin
Built not for dominance — but for defense.

This is not the whole tree, only the root system. The rest will grow in time.

---