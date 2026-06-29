#!/usr/bin/env bash
# VISHMUX one-line installer
# Usage: curl -sSL https://raw.githubusercontent.com/IAMBOYYY/vishmux/main/install.sh | bash

set -e

echo ""
echo "██╗   ██╗██╗███████╗██╗  ██╗███╗   ███╗██╗   ██╗██╗  ██╗"
echo "Installing VISHMUX..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found. Install it first:"
    echo "  Termux: pkg install python"
    echo "  Ubuntu/Debian: sudo apt install python3"
    exit 1
fi

# Check Git
if ! command -v git &> /dev/null; then
    echo "Error: Git not found. Install it first:"
    echo "  Termux: pkg install git"
    echo "  Ubuntu/Debian: sudo apt install git"
    exit 1
fi

# Clone repo
INSTALL_DIR="$HOME/vishmux"
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing install..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    echo "Cloning VISHMUX..."
    git clone https://github.com/IAMBOYYY/vishmux "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Install Python dependencies
echo "Installing dependencies..."
python3 -m pip install -r cli/requirements.txt --quiet

# Create vishmux command alias
SHELL_RC=""
if [ -f "$HOME/.bashrc" ]; then SHELL_RC="$HOME/.bashrc"; fi
if [ -f "$HOME/.zshrc" ]; then SHELL_RC="$HOME/.zshrc"; fi
if [ -f "$HOME/.bash_profile" ]; then SHELL_RC="$HOME/.bash_profile"; fi

ALIAS_LINE="alias vishmux='python3 $INSTALL_DIR/cli/main.py'"

if [ -n "$SHELL_RC" ]; then
    if ! grep -q "alias vishmux=" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# VISHMUX AI Agent" >> "$SHELL_RC"
        echo "$ALIAS_LINE" >> "$SHELL_RC"
        echo "Added 'vishmux' command to $SHELL_RC"
    fi
fi

echo ""
echo "✅ VISHMUX installed successfully!"
echo ""
echo "Next steps:"
echo "  1. Run setup:  python3 $INSTALL_DIR/cli/setup_wizard.py"
echo "  2. Start:      vishmux   (after restarting terminal)"
echo "  Or directly:   python3 $INSTALL_DIR/cli/main.py"
echo ""