#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  Interviewd — one-shot setup script
#  Run this once after cloning: bash setup.sh
#
#  Works on macOS, Linux, and Windows (Git Bash / WSL)
#  Windows (native PowerShell)? Run setup.ps1 instead:
#      Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; .\setup.ps1
#
#  Installs: uv → Python 3.11 → Node.js → Python deps → frontend deps
#  Then hands off to `interviewd setup` for API key configuration.
# ══════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC}  $*"; }
fail() { echo -e "  ${RED}✗${NC}  $*" >&2; }
info() { echo -e "     $*"; }
warn() { echo -e "  ${YELLOW}!${NC}  $*"; }
step() { echo; echo -e "${BOLD}$*${NC}"; printf '%.0s─' {1..52}; echo; }
ask()  {
    local ans
    read -r -p "     $1 [Y/n] " ans
    [[ -z "$ans" || "$ans" =~ ^[Yy] ]]
}

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo
echo "══════════════════════════════════════════════════════"
echo "  Interviewd Setup"
echo "══════════════════════════════════════════════════════"

# ── Step 1: uv ────────────────────────────────────────────────────
step "[1/5] uv  (Python toolchain manager)"

if command -v uv &>/dev/null; then
    ok "uv $(uv --version | awk '{print $2}')"
else
    fail "uv not found"
    info "Official installer: https://docs.astral.sh/uv/"
    if ask "Install uv now?"; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # Load uv into current shell
        export PATH="$HOME/.local/bin:$PATH"
        # shellcheck source=/dev/null
        source "$HOME/.local/bin/env" 2>/dev/null || true
        if command -v uv &>/dev/null; then
            ok "uv installed"
        else
            fail "uv installed but not in PATH yet"
            info "Restart your terminal and re-run: bash setup.sh"
            exit 1
        fi
    else
        fail "uv is required — install from https://docs.astral.sh/uv/ and re-run this script"
        exit 1
    fi
fi

# ── Step 2: Python 3.11+ ──────────────────────────────────────────
step "[2/5] Python 3.11+"

_py_ok() {
    command -v python3 &>/dev/null || return 1
    python3 -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null
}

if _py_ok; then
    ok "Python $(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")"
else
    fail "Python 3.11+ not found"
    info "uv can install and manage Python versions for you"
    if ask "Install Python 3.11 via uv?"; then
        uv python install 3.11
        ok "Python 3.11 installed"
    else
        fail "Python 3.11+ is required — install from https://python.org/downloads and re-run"
        exit 1
    fi
fi

# ── Step 3: Node.js ───────────────────────────────────────────────
step "[3/5] Node.js + npm"

if command -v node &>/dev/null && command -v npm &>/dev/null; then
    ok "node $(node --version)  •  npm $(npm --version)"
else
    fail "node / npm not found"

    # Pick an install method based on OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        INSTALL_CMD="brew install node"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        # Git Bash on Windows
        INSTALL_CMD="winget install --id OpenJS.NodeJS.LTS -e"
    else
        # Linux — install via nvm so no sudo is needed
        INSTALL_CMD="nvm"
    fi

    info "Install Node.js from https://nodejs.org"

    if [[ "$INSTALL_CMD" == "nvm" ]]; then
        info "Will install nvm (Node Version Manager) then Node LTS"
        if ask "Install Node.js via nvm?"; then
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
            export NVM_DIR="$HOME/.nvm"
            # shellcheck source=/dev/null
            [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
            nvm install --lts
        else
            fail "Node.js is required — install from https://nodejs.org and re-run"
            exit 1
        fi
    else
        info "Will run: $INSTALL_CMD"
        if ask "Install Node.js now?"; then
            eval "$INSTALL_CMD"
        else
            fail "Node.js is required — install from https://nodejs.org and re-run"
            exit 1
        fi
    fi

    if command -v node &>/dev/null; then
        ok "node $(node --version)  •  npm $(npm --version)"
    else
        fail "Node.js installed but not in PATH yet"
        info "Restart your terminal and re-run: bash setup.sh"
        exit 1
    fi
fi

# ── Step 4: Python deps ───────────────────────────────────────────
step "[4/5] Python dependencies"
info "uv sync --extra web"
uv sync --extra web
ok "Python deps ready"

# ── Step 5: Frontend deps ─────────────────────────────────────────
step "[5/5] Frontend dependencies"
info "npm install  (frontend/)"
(cd frontend && npm install)
ok "Frontend deps ready"

# ── Hand off to API key wizard ────────────────────────────────────
echo
echo "══════════════════════════════════════════════════════"
ok "System setup complete"
echo "══════════════════════════════════════════════════════"

uv run interviewd setup
