#!/usr/bin/env bash
set -euo pipefail

repo_root="${CODESPACE_VSCODE_FOLDER:-$PWD}"
cd "$repo_root"

mkdir -p "$HOME/.npm-global/bin" "$HOME/.local/bin"
npm config set prefix "$HOME/.npm-global"

profile_line='export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"'
if ! grep -Fq "$profile_line" "$HOME/.bashrc" 2>/dev/null; then
  printf '\n%s\n' "$profile_line" >> "$HOME/.bashrc"
fi

export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"

python_bin="$(command -v python3 || command -v python)"
"$python_bin" -m pip install --user --upgrade pip
if [ -f requirements.txt ]; then
  "$python_bin" -m pip install --user -r requirements.txt
fi

npm install -g @anthropic-ai/claude-code

node --version
npm --version
"$python_bin" --version
git --version
claude --version
