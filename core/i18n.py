"""
ANTIVYRE — Internationalization (i18n) System
Supports EN (default) and ES out of the box.
Community can add more languages by dropping a JSON file in /locales/.

How to add a new language:
  1. Copy locales/en.json to locales/<lang_code>.json  (e.g. locales/fr.json)
  2. Translate every value — keep the keys unchanged
  3. Submit a pull request — that's it!
"""

import json
import os
from pathlib import Path
from typing import Dict

_LOCALES_DIR = Path(__file__).parent.parent / "locales"
_DEFAULT_LANG = "en"
_current: Dict[str, str] = {}
_fallback: Dict[str, str] = {}


def _load(lang: str) -> Dict[str, str]:
    path = _LOCALES_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def set_language(lang: str) -> bool:
    """Switch active language. Falls back to English for missing keys."""
    global _current, _fallback
    _fallback = _load(_DEFAULT_LANG)
    data = _load(lang)
    if not data and lang != _DEFAULT_LANG:
        _current = _fallback
        return False
    _current = data
    return True


def t(key: str, **kwargs) -> str:
    """Translate a key. Supports {variable} interpolation."""
    text = _current.get(key) or _fallback.get(key) or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


def available_languages() -> list[dict]:
    """Return list of available language packs found in /locales/."""
    langs = []
    if not _LOCALES_DIR.exists():
        return langs
    for f in sorted(_LOCALES_DIR.glob("*.json")):
        code = f.stem
        data = _load(code)
        langs.append({
            "code": code,
            "name": data.get("_lang_name", code.upper()),
            "flag": data.get("_lang_flag", "🌐"),
        })
    return langs


# Bootstrap with English on import
set_language(_DEFAULT_LANG)
