# Changelog — ANTIVYRE

All notable changes to this project will be documented in this file.

## [1.0.0] — 2025

### This is not a beta anymore.

ANTIVYRE was started in 2019, had a working beta by 2021,
and was rebuilt from the ground up in 2025 with Google Magika as the
AI detection backbone.

### Added
- **Google Magika integration** — AI-powered file type identification (99% F1, 200+ types)
- **Extension spoofing detection** — catches `.jpg` files that are really executables
- **Specialized analyzers** — dedicated engines for PE/ELF, scripts, Office macros
- **Full i18n system** — English + Spanish built-in, any language addable via JSON
- **SQLite scan history** — full audit trail with WAL-mode atomic writes
- **Quarantine system** — atomic file isolation (no corrupt states on crash)
- **Secure auto-updater** — HTTPS-only, host-validated, hash-verified binary updates
- **Malware hash database** — community-maintained MD5 hash blocklist
- **Real-time monitor** (experimental) — watchdog-based high-risk path monitoring
- **Security CI pipeline** — gitleaks, pip-audit, Semgrep on every commit
- **SECURITY.md** — full disclosure policy and data transparency document
- **CONTRIBUTING.md** — step-by-step guide for adding translations and signatures
- **GPL v3 license** — free forever, no restrictions on personal/commercial use
- **Voluntary donation** — PayPal link, never a paywall

### Versus the 2021 beta
| Area | Beta (2021) | v1.0.0 |
|---|---|---|
| File type detection | Extension + regex | Google Magika AI |
| False positive rate | High | Dramatically reduced |
| File types covered | ~10 | 200+ |
| Spoofing detection | None | Yes |
| Languages | 1 (English) | 4 (EN, ES, FR, PT) + community |
| Database | Basic SQLite | WAL-mode, atomic writes |
| CI security | None | gitleaks + pip-audit + Semgrep |
| Auto-update | None | Secure, hash-validated |
| Real-time protection | None | Experimental (watchdog) |

## [0.3.0-beta] — 2021

- Working beta with regex-based detection
- Tkinter GUI with Quick Scan, Full Scan, Folder Scan
- SQLite detections database
- Windows registry scanning
- Known issue: high false positive rate (reason for pause)

## [0.1.0-alpha] — 2019

- Initial proof of concept
- Basic file scanning with pattern matching
