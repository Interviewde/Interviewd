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
    # Auto-confirm in CI (GitHub Actions sets CI=true)
    [[ "${CI:-}" == "true" ]] && return 0
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
        # Installer may exit non-zero to signal "restart your shell" — ignore that,
        # check the binary directly instead.
        curl -LsSf https://astral.sh/uv/install.sh | sh || true
        export PATH="$HOME/.local/bin:$PATH"
        if [[ -x "$HOME/.local/bin/uv" ]] || command -v uv &>/dev/null; then
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
    # Try python3 then python — handles macOS/Linux ('python3') and Windows Git
    # Bash ('python').  The Windows App Execution Alias for python3 exists in
    # PATH but errors at runtime, so we test both existence AND executability.
    local py
    for py in python3 python; do
        if command -v "$py" &>/dev/null \
           && "$py" -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
            return 0
        fi
    done
    return 1
}

_py_cmd() {
    # Return whichever python command actually works on this system
    local py
    for py in python3 python; do
        if command -v "$py" &>/dev/null \
           && "$py" -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
            echo "$py"; return
        fi
    done
    echo python  # fallback
}

if _py_ok; then
    ok "Python $($(_py_cmd) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")"
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
info "uv sync --extra web --extra planner --extra dev"
uv sync --extra web --extra planner --extra dev
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

# Skip interactive key wizard in CI — no real API keys available
if [[ "${CI:-}" == "true" ]]; then
    ok "CI environment — skipping interactive key setup"
    ok "All done. Run 'uv run interviewd setup' to configure API keys."
else
    PYTHONIOENCODING=utf-8 uv run interviewd setup
fi
