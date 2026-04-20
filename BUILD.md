# ANTIVYRE — Build Guide
## How to compile `AntivyreSetup.exe` from source

---

## Requirements

Install these tools **once**:

| Tool | Download | Purpose |
|---|---|---|
| Python 3.11 (64-bit) | [python.org](https://python.org) | Runtime |
| PyInstaller | `pip install pyinstaller` | Bundles Python → .exe |
| UPX (optional) | [upx.github.io](https://upx.github.io) | Compresses the .exe (~30% smaller) |
| Inno Setup 6 | [jrsoftware.org/isinfo.php](https://jrsoftware.org/isinfo.php) | Generates Setup.exe wizard |

---

## Step 1 — Install all Python dependencies

Open a terminal in the project root folder:

```bash
pip install -r requirements.txt
pip install pyinstaller pillow
```

---

## Step 2 — (Optional) Install UPX for smaller output

Download UPX, extract it, and add it to your PATH.  
PyInstaller will detect it automatically.

---

## Step 3 — Build the app bundle with PyInstaller

```bash
pyinstaller build.spec
```

This creates:
```
dist/
└── Antivyre/
    ├── Antivyre.exe    ← main executable
    ├── assets/              ← icons bundled
    ├── locales/             ← language files bundled
    ├── db/                  ← malware hashes bundled
    └── _internal/           ← Python runtime + all libraries
```

The entire `dist/Antivyre/` folder is self-contained.  
No Python installation needed on the target machine.

---

## Step 4 — Compile the installer with Inno Setup

1. Open **Inno Setup Compiler**
2. File → Open → select `installer/antivyre.iss`
3. Build → **Compile** (or press F9)

Output:
```
installer/Output/AntivyreSetup.exe   ← ready to distribute!
```

---

## What the installer does

When a user runs `AntivyreSetup.exe`:

1. Shows a professional wizard (English/Spanish/French/Portuguese)
2. Lets user choose install folder (default: `C:\Program Files\ANTIVYRE`)
3. Optional: creates Desktop shortcut
4. Optional: adds to Windows startup
5. Registers in **Add/Remove Programs** with icon and version info
6. Offers to launch ANTIVYRE immediately after install

When uninstalling:
1. Kills the process if running
2. Removes all files
3. Removes registry entries
4. Removes Start Menu shortcuts
5. Clean removal — no leftovers

---

## Folder structure after building

```
antivyre/
├── main.py
├── build.spec              ← PyInstaller config
├── version_info.txt        ← Windows version resource
├── requirements.txt
├── installer/
│   ├── antivyre.iss  ← Inno Setup script
│   └── Output/
│       └── AntivyreSetup.exe  ← FINAL PRODUCT
├── dist/
│   └── Antivyre/      ← PyInstaller output (used by Inno Setup)
├── assets/
├── core/
├── db/
├── locales/
└── ui/
```

---

## Distribution checklist

- [ ] `pyinstaller build.spec` completes without errors
- [ ] `dist/Antivyre/Antivyre.exe` launches correctly
- [ ] All 4 languages work in the built .exe
- [ ] System tray appears when minimizing
- [ ] Inno Setup compiles `AntivyreSetup.exe`
- [ ] Test install on a clean Windows machine (no Python)
- [ ] Test uninstall — no files left behind

---

## Troubleshooting

**"ModuleNotFoundError" when running the .exe**  
→ Add the missing module to `hiddenimports` in `build.spec` and rebuild.

**Magika model not found**  
→ Check that `magika/models` and `magika/config` paths in `build.spec` datas are correct.  
→ Run `python -c "import magika; print(magika.__file__)"` to find the install path.

**Icon not showing**  
→ Verify `assets/icon.ico` exists and contains 256×256 resolution.

**Antivirus flags the .exe (false positive)**  
→ This is common with PyInstaller builds. Submit to VirusTotal and request a whitelist from the AV vendor.  
→ Code signing with a certificate eliminates this entirely.
