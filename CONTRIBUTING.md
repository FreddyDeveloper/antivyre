# Contributing to ANTIVYRE

Thank you for helping make ANTIVYRE better for everyone! 🎉

## Ways to Contribute

### 🌍 Add a New Language (Translation)

This is the easiest and most impactful contribution.

1. Fork the repository
2. Copy `locales/en.json` → `locales/<your_lang_code>.json`
   - Use standard language codes: `de`, `ja`, `zh`, `ar`, `ru`, etc.
3. Edit the new file:
   - Translate **every value** (the text after the `:`)
   - **Never** change the keys (the text before the `:`)
   - Update these metadata fields at the top:
     ```json
     "_lang_name": "Français",
     "_lang_flag": "🇫🇷",
     "_lang_version": "1.0",
     "_lang_author": "YourGitHubUsername"
     ```
4. Test it: run ANTIVYRE → Settings → select your language
5. Submit a Pull Request with the title: `i18n: Add [Language Name] translation`

**No coding required.** JSON editing is all you need.

Current languages: 🇺🇸 English, 🇪🇸 Spanish, 🇫🇷 French, 🇵🇹 Portuguese — yours could be next!

### 🦠 Add Malware Signatures

Help improve detection by contributing known malware hashes:

1. Add MD5 hashes (one per line) to `db/malicious_hashes.txt`
2. Format: `<md5_hash>  # VirusTotal link or source`
3. Only submit hashes from verified public sources (VirusTotal, MalwareBazaar, etc.)

### 🐛 Report Bugs

Use [GitHub Issues](https://github.com/FreddyDeveloper/antivyre/issues) with:
- ANTIVYRE version
- Operating system
- Steps to reproduce
- Expected vs actual behavior

For **security vulnerabilities**, use the private channel in [SECURITY.md](SECURITY.md).

### 💻 Code Contributions

1. Fork → branch → implement → test → Pull Request
2. Follow the existing code style
3. Add/update tests for new features
4. Update the relevant locale files if you add new UI text

## Code of Conduct

Be kind. Be respectful. We're building something for everyone.

## Support the Project

ANTIVYRE is 100% free and open source. If it has helped you,
consider a voluntary donation: [paypal.me/freddydeveloper](https://paypal.me/freddydeveloper)

Thank you ❤️
