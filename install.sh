#!/bin/bash
# Hunter StrikeR — One-line Installer
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/FreddyDeveloper/hunter-striker/main/install.sh | bash
#
# What this does:
#   1. Checks for Python 3.10+
#   2. Clones the repo (or pulls latest if already cloned)
#   3. Creates a virtual environment
#   4. Installs all dependencies including Magika
#   5. Creates a launcher script in ~/.local/bin/hunter-striker

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

INSTALL_DIR="$HOME/.hunter-striker"
BIN_DIR="$HOME/.local/bin"
REPO_URL="https://github.com/FreddyDeveloper/hunter-striker.git"

echo ""
echo -e "${CYAN}⚡ Hunter StrikeR Installer${NC}"
echo -e "${CYAN}   Free, AI-Powered Antivirus${NC}"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✗ Python 3 not found. Please install Python 3.10+ first.${NC}"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo -e "${RED}✗ Python $PY_VERSION found but 3.10+ is required.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python $PY_VERSION found${NC}"

# Clone or update
if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "  Updating existing installation…"
    cd "$INSTALL_DIR" && git pull --quiet
else
    echo -e "  Downloading Hunter StrikeR…"
    git clone --quiet "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Virtual environment
if [ ! -d "$INSTALL_DIR/.venv" ]; then
    echo -e "  Creating virtual environment…"
    python3 -m venv "$INSTALL_DIR/.venv"
fi

source "$INSTALL_DIR/.venv/bin/activate"

# Install dependencies
echo -e "  Installing dependencies (this includes Google Magika)…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create launcher
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/hunter-striker" << LAUNCHER
#!/bin/bash
source "$INSTALL_DIR/.venv/bin/activate"
python "$INSTALL_DIR/main.py" "\$@"
LAUNCHER
chmod +x "$BIN_DIR/hunter-striker"

# PATH setup
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$HOME/.bashrc"
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$HOME/.zshrc" 2>/dev/null || true
    export PATH="$BIN_DIR:$PATH"
fi

echo ""
echo -e "${GREEN}✓ Hunter StrikeR installed successfully!${NC}"
echo ""
echo -e "  Run it with: ${CYAN}hunter-striker${NC}"
echo ""
echo -e "  Hunter StrikeR is 100% free."
echo -e "  Voluntary donations: ${CYAN}https://paypal.me/freddydeveloper${NC}"
echo ""
