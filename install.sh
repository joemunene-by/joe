#!/usr/bin/env bash
# install.sh: symlink every binary in bin/ into ~/.local/bin/.
#
# Re-run anytime you pull updates; existing symlinks are replaced.
# Add ~/.local/bin to your PATH if it isn't already.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_SRC="$REPO_ROOT/bin"
BIN_DST="$HOME/.local/bin"

mkdir -p "$BIN_DST"

echo "installing joe binaries from $BIN_SRC -> $BIN_DST"
for f in "$BIN_SRC"/*; do
  name="$(basename "$f")"
  ln -sf "$f" "$BIN_DST/$name"
  echo "  $name"
done

cat <<EOF

next steps:
  1. ensure ~/.local/bin is on PATH (try: echo 'export PATH=\$HOME/.local/bin:\$PATH' >> ~/.zshrc)
  2. install python deps:
       python3 -m pip install --user rich prompt_toolkit fastapi uvicorn mcp
  3. pull the default models:
       ollama pull gemma3:4b
       ollama pull qwen2.5-coder:7b
       ollama pull qwen2.5-coder:14b
       ollama pull nomic-embed-text
  4. (optional but recommended) build a personalised orchestrator:
       see docs/REFERENCE.md "self-training" section, or just:
         ollama create joe-gemma -f path/to/your/Modelfile
  5. run \`joe doctor\` to confirm everything is wired
  6. \`joe\` to start
EOF
