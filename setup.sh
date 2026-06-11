#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Agentic AI (Python) — one-shot setup for macOS (Homebrew).
#
# Installs/verifies: Python 3.12+, MongoDB, Ollama. Creates .venv and installs
# the project (editable, with dev extras). Pulls the embedding + a chat model.
# Prepares config.json from the example, injecting any API keys found in the env.
# Writes run.sh to launch all three services.
#
# Idempotent — safe to re-run. Degrades gracefully when something is missing.
# API keys (Tavily / Pinecone / Anthropic) cannot be auto-provisioned; this
# script reads them from the environment if set, else writes placeholders and
# prints exactly which keys to fill in.
# ─────────────────────────────────────────────────────────────────────────────
set -u

# ── pretty output ────────────────────────────────────────────────────────────
BLUE=$'\033[0;34m'; YELLOW=$'\033[0;33m'; GREEN=$'\033[0;32m'; RED=$'\033[0;31m'; DIM=$'\033[2m'; RST=$'\033[0m'
say()  { printf "%s==>%s %s\n" "$BLUE" "$RST" "$1"; }
ok()   { printf "%s  ok%s %s\n" "$GREEN" "$RST" "$1"; }
warn() { printf "%s warn%s %s\n" "$YELLOW" "$RST" "$1"; }
err()  { printf "%s  !!%s %s\n" "$RED" "$RST" "$1"; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT" || exit 1

CHAT_MODEL="${CHAT_MODEL:-gemma2:2b}"
EMBED_MODEL="${EMBED_MODEL:-nomic-embed-text}"

say "Agentic AI (Python) setup — repo at $ROOT"

# ── 0. platform check ────────────────────────────────────────────────────────
if [[ "$(uname)" != "Darwin" ]]; then
  warn "This script targets macOS/Homebrew. On other platforms, install Python 3.12+, MongoDB and Ollama manually, then re-run the venv/config steps below."
fi

# ── 1. Homebrew ──────────────────────────────────────────────────────────────
if command -v brew >/dev/null 2>&1; then
  ok "Homebrew present"
else
  warn "Homebrew not found. Install it from https://brew.sh then re-run. Continuing best-effort."
fi
BREW() { command -v brew >/dev/null 2>&1 && brew "$@"; }

# ── 2. Python 3.12+ ──────────────────────────────────────────────────────────
PY=""
pick_python() {
  for c in python3.13 python3.12 python3; do
    if command -v "$c" >/dev/null 2>&1; then
      v="$("$c" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)"
      major="${v%%.*}"; minor="${v##*.}"
      if [[ "$major" == "3" && "$minor" -ge 12 ]]; then PY="$c"; return 0; fi
    fi
  done
  return 1
}
if pick_python; then
  ok "Python $("$PY" -V 2>&1 | awk '{print $2}') ($PY)"
else
  say "Installing Python 3.12 via Homebrew…"
  BREW install python@3.12 && hash -r
  pick_python && ok "Python $("$PY" -V 2>&1 | awk '{print $2}')" \
    || { err "Python 3.12+ unavailable; install it and re-run."; PY=""; }
fi

# ── 3. venv + project install ────────────────────────────────────────────────
if [[ -n "$PY" ]]; then
  if [[ ! -d .venv ]]; then
    say "Creating virtualenv at .venv…"
    "$PY" -m venv .venv && ok "venv created"
  else
    ok ".venv already exists"
  fi
  say "Installing project (editable, with dev extras)…"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip >/dev/null 2>&1
  if python -m pip install -e ".[dev]"; then
    ok "pip install -e \".[dev]\" complete"
  else
    err "pip install failed — check the output above."
  fi
else
  warn "Skipping venv/pip (no suitable Python)."
fi

# ── 4. MongoDB ───────────────────────────────────────────────────────────────
if command -v mongod >/dev/null 2>&1; then
  ok "MongoDB present"
else
  say "Installing MongoDB Community (tap + install)…"
  BREW tap mongodb/brew >/dev/null 2>&1
  BREW install mongodb-community >/dev/null 2>&1 && ok "MongoDB installed" \
    || warn "Could not install MongoDB via brew; install it manually."
fi
if command -v brew >/dev/null 2>&1 && brew services list 2>/dev/null | grep -q '^mongodb-community'; then
  if brew services list 2>/dev/null | grep -E '^mongodb-community' | grep -q started; then
    ok "MongoDB service already running"
  else
    say "Starting MongoDB…"
    brew services start mongodb-community >/dev/null 2>&1 && ok "MongoDB started" \
      || warn "Could not start MongoDB; start it manually (brew services start mongodb-community)."
  fi
else
  warn "MongoDB brew service not detected; ensure mongod is running on :27017."
fi

# ── 5. Ollama + models ───────────────────────────────────────────────────────
if command -v ollama >/dev/null 2>&1; then
  ok "Ollama present"
else
  say "Installing Ollama…"
  BREW install ollama >/dev/null 2>&1 && ok "Ollama installed" \
    || warn "Could not install Ollama via brew; install from https://ollama.com."
fi
if command -v ollama >/dev/null 2>&1; then
  # ensure the daemon is up (brew service preferred, else background it)
  if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1 && brew services list 2>/dev/null | grep -q '^ollama'; then
      brew services start ollama >/dev/null 2>&1
    else
      say "Starting 'ollama serve' in the background…"
      nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
    fi
    # wait briefly for it to come up
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1 && break
      sleep 1
    done
  fi
  if curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
    ok "Ollama daemon reachable"
    say "Pulling embedding model: $EMBED_MODEL"
    ollama pull "$EMBED_MODEL" >/dev/null 2>&1 && ok "$EMBED_MODEL ready" || warn "pull of $EMBED_MODEL failed"
    say "Pulling chat model: $CHAT_MODEL"
    ollama pull "$CHAT_MODEL" >/dev/null 2>&1 && ok "$CHAT_MODEL ready" || warn "pull of $CHAT_MODEL failed"
  else
    warn "Ollama daemon not reachable on :11434; start it (ollama serve) and pull: $EMBED_MODEL, $CHAT_MODEL."
  fi
fi

# ── 6. config.json (inject env keys, else placeholders) ──────────────────────
CFG="$ROOT/config.json"
if [[ -f "$CFG" ]]; then
  ok "config.json already exists (left untouched)"
else
  say "Creating config.json from config.example.json…"
  cp config.example.json "$CFG"
  # Inject any keys present in the environment, in place. Uses python if available
  # (no jq dependency); falls back to leaving the example placeholders.
  if [[ -n "$PY" ]] || command -v python3 >/dev/null 2>&1; then
    PYBIN="${PY:-python3}"
    "$PYBIN" - "$CFG" <<'PYEOF'
import json, os, sys
path = sys.argv[1]
with open(path) as f:
    cfg = json.load(f)
env_map = {
    "TAVILY_API_KEY": "TAVILY_API_KEY",
    "PINECONE_API_KEY": "PINECONE_API_KEY",
    "ANTHROPIC_API_KEY": "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL": "ANTHROPIC_MODEL",
    "OLLAMA_MODEL": "OLLAMA_MODEL",
    "EMBEDDING_MODEL": "EMBEDDING_MODEL",
    "PINECONE_INDEX": "PINECONE_INDEX",
}
for cfg_key, env_key in env_map.items():
    val = os.environ.get(env_key)
    if val:
        cfg[cfg_key] = val
# If an Anthropic key was supplied via env, flip the credit flag so the backend
# rule (key + model + credit) can engage; otherwise stay on Ollama.
if os.environ.get("ANTHROPIC_API_KEY"):
    cfg["ANTHROPIC_CREDIT_BALANCE"] = True
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
PYEOF
    ok "config.json written"
  else
    warn "No python to inject env keys; config.json carries example placeholders."
  fi
fi

# ── 7. run.sh launcher ───────────────────────────────────────────────────────
RUN="$ROOT/run.sh"
say "Writing run.sh launcher…"
cat > "$RUN" <<'RUNEOF'
#!/usr/bin/env bash
# Launch all three Agentic AI (Python) services together.
# Ctrl-C stops them all. Logs go to /tmp/agentic-*.log and the console.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT" || exit 1
[[ -d .venv ]] && source .venv/bin/activate

pids=()
cleanup() { echo; echo "Stopping services…"; for p in "${pids[@]}"; do kill "$p" 2>/dev/null; done; }
trap cleanup INT TERM EXIT

echo "Starting retrieval  → http://localhost:8081"
uvicorn retrieval.app.main:app   --port 8081 & pids+=($!)
echo "Starting agent      → http://localhost:8082"
uvicorn agent.app.main:app       --port 8082 & pids+=($!)
echo "Starting mcp_server → http://localhost:8083 (SSE)"
uvicorn mcp_server.app.server:app --port 8083 & pids+=($!)

echo
echo "All three services starting. Open the chat at http://localhost:8082"
echo "Press Ctrl-C to stop."
wait
RUNEOF
chmod +x "$RUN"
ok "run.sh ready (chmod +x)"

# ── 8. summary + key notice ──────────────────────────────────────────────────
echo
say "Setup complete."
echo "${DIM}  • Launch everything:  ./run.sh${RST}"
echo "${DIM}  • Chat UI:            http://localhost:8082${RST}"
echo "${DIM}  • Ingest UI:          http://localhost:8081${RST}"
echo "${DIM}  • Tests:              source .venv/bin/activate && pytest -q${RST}"

missing=()
if [[ -f "$CFG" ]]; then
  grep -q '"TAVILY_API_KEY": *"tvly-\.\.\."' "$CFG"   && missing+=("TAVILY_API_KEY   (Web search — Tavily)")
  grep -q '"PINECONE_API_KEY": *"pc-\.\.\."' "$CFG"   && missing+=("PINECONE_API_KEY (My Library vectors — Pinecone)")
  grep -q '"ANTHROPIC_API_KEY": *"sk-ant-\.\.\."' "$CFG" && missing+=("ANTHROPIC_API_KEY (optional — Claude backend)")
fi
if (( ${#missing[@]} )); then
  echo
  warn "API keys still needed in ${CFG#$ROOT/}:"
  for m in "${missing[@]}"; do echo "      - $m"; done
  echo "${DIM}      Edit config.json (gitignored) and fill them in, or export them and re-run setup.sh.${RST}"
  echo "${DIM}      Without keys: Web and My Library features are limited; plain Ollama chat still works.${RST}"
else
  ok "All API keys present in config.json."
fi
