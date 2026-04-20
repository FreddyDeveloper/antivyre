# ANTIVYRE — Security Policy

## Quick Answers

- Vulnerability reports: use GitHub private security reporting or email below.
- Response time: acknowledgement within 2 business days.
- Default behavior: ANTIVYRE runs entirely locally. No data leaves your machine.
- All scan results are stored in `~/.antivyre/data.db` (local SQLite only).
- No telemetry. No analytics. No ads. Ever.

## Reporting a Vulnerability

**Primary channel:** [GitHub Security Advisories](https://github.com/FreddyDeveloper/antivyre/security/advisories/new)

**Fallback:** Direct contact via [www.freddydeveloper.com](https://www.freddydeveloper.com)

Please include:
- ANTIVYRE version (`Help > About`)
- Operating system and version
- Steps to reproduce
- Impact assessment

## Data & Privacy

ANTIVYRE is designed with privacy as a first principle:

| Operation | Data sent off-device | When |
|---|---|---|
| Scanning files | **Never** | — |
| Checking malware hashes | **Never** (local DB only) | — |
| Update check | Version number only | If auto-update enabled |
| Voluntary donation | Handled entirely by PayPal | Only if user clicks Donate |

### What is stored locally

| Data | Location | Why |
|---|---|---|
| Scan history | `~/.antivyre/data.db` | User review and history |
| Quarantined files | `~/.antivyre/quarantine/` | Safe isolation |
| Settings | `~/.antivyre/data.db` | User preferences |
| Known malicious hashes | `db/malicious_hashes.txt` | Detection engine |

The user has full control over all local data. Everything can be cleared from Settings.

## Security Scanning (CI/CD)

Every commit to this repository is scanned by:

- **gitleaks** — secret/credential leak detection
- **OSV Scanner** — dependency vulnerability scanning
- **Semgrep** — static analysis security scan
- **govulncheck** — Go vulnerability check (for tooling)

## Magika (Google)

File type detection is powered by [Google Magika](https://github.com/google/magika),
released under the Apache 2.0 license. Magika runs 100% locally — no data is sent to Google.

## Responsible Disclosure

We follow coordinated disclosure:

1. Reporter submits via private channel.
2. We acknowledge within 2 business days.
3. We begin remediation within 7 calendar days for confirmed findings.
4. We coordinate disclosure timing with the reporter.
5. We credit reporters in release notes (unless they prefer anonymity).
