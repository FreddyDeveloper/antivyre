<div align="center">

| [🇺🇸 English](README.md) | [🇪🇸 Español](readme/README.es.md) |

<br/>

# ⚡ ANTIVYRE

### Free, AI-Powered Antivirus — Forever

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://python.org)
[![Powered by Magika](https://img.shields.io/badge/AI-Google%20Magika-orange.svg)](https://github.com/google/magika)
[![Donate](https://img.shields.io/badge/Donate-PayPal-yellow.svg)](https://paypal.me/freddydeveloper)

*The free antivirus that Avast and AVG used to be.*

</div>

---

## Why ANTIVYRE?

The free antivirus market is broken. Avast, AVG, and others have quietly turned "free" into "free to annoy you until you pay." Millions of users worldwide are underprotected.

ANTIVYRE started in 2019, had a working beta by 2021, and is now rebuilt from the ground up with **Google Magika** — an AI-powered file identification engine with 99% accuracy across 200+ file types.

- **100% free.** No ads, no upsells, no hidden tiers. Donations are voluntary.
- **AI-powered.** Google Magika identifies real file types regardless of extension — catches disguised malware the old tools miss.
- **Open source.** GPL v3. Inspect every line of code.
- **Community-driven.** Translations, signatures, and features contributed by users worldwide.
- **Privacy-first.** Nothing leaves your machine. No telemetry, ever.

---

## Features

| Feature | Description |
|---|---|
| 🤖 **AI File Detection** | Google Magika identifies 200+ file types by content, not extension |
| 🎭 **Spoofing Detection** | Catches `.jpg` files that are actually `.exe` |
| ⚡ **Quick Scan** | Scans critical folders + running processes in minutes |
| 🔬 **Full Scan** | All drives, processes, startup registry, resource anomalies |
| 📁 **Folder / File Scan** | Scan any specific path |
| 🔒 **Quarantine** | Safely isolate threats without permanent deletion |
| 📋 **Scan History** | Full log of all past scans and detections |
| 🌍 **Multilingual** | English + Spanish built-in. Community can add any language. |
| 🛡️ **Hash Database** | Known malware MD5 hashes checked locally |

---

## Installation

### Requirements
- Windows 10/11 (macOS/Linux support coming)
- Python 3.10+

### Quick start

```bash
git clone https://github.com/FreddyDeveloper/antivyre.git
cd antivyre
pip install -r requirements.txt
python main.py
```

### Install Magika (required)

```bash
pip install magika
```

---

## How It Works

```
File received
     │
     ▼
[1] Hash check ──────────────────→ Known malicious hash? → THREAT
     │
     ▼
[2] Google Magika AI ────────────→ Real file type identified (99% accuracy)
     │
     ▼
[3] Extension spoofing check ────→ .jpg that's actually a PE binary? → THREAT
     │
     ├── Executable (PE/ELF) ────→ Suspicious import analysis
     ├── Script (PS1/VBA/JS) ────→ Obfuscation + injection pattern scan
     ├── Office document ────────→ Macro signature detection
     └── Text/other ─────────────→ Ransomware note patterns
```

---

## Adding a Language

Drop a translated `locales/<lang>.json` file — no coding required. See [CONTRIBUTING.md](CONTRIBUTING.md).

Current languages: 🇺🇸 English · 🇪🇸 Español

---

## Support the Project

ANTIVYRE is and will always be **100% free**. If it has helped protect your system, consider a voluntary donation:

**[💛 Donate via PayPal](https://paypal.me/freddydeveloper)**

---

## License

[GNU GPL v3](LICENSE) — Free forever.

Built by [FreddyDeveloper](https://www.freddydeveloper.com) · Powered by [Google Magika](https://github.com/google/magika)
