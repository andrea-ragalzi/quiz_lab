#!/usr/bin/env bash
# Run every QuizLab quality gate; exits non-zero on the first failure.
#
#   scripts/check.sh            # all checks (Python + templates + frontend)
#   scripts/check.sh --fix      # apply safe formatters first, then check
#
# Frontend checks need Node.js and `npm ci`; they are development-only and are
# never required to run QuizLab. Set QUIZLAB_SKIP_FRONTEND=1 to skip them
# explicitly (for example on a machine without Node.js).
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -x .venv/bin/python ]]; then
  BIN=.venv/bin/
else
  BIN=""  # assume tools are on PATH (e.g. CI with an activated environment)
fi

step() { printf '\n==> %s\n' "$*"; }

if [[ "${1:-}" == "--fix" ]]; then
  step "Applying formatters"
  "${BIN}ruff" check --fix .
  "${BIN}ruff" format .
  "${BIN}djlint" app/templates --reformat || true  # exits 1 when it changes files
  if [[ "${QUIZLAB_SKIP_FRONTEND:-0}" != "1" ]]; then
    npx --no-install stylelint "app/static/css/**/*.css" --fix
    npx --no-install prettier --write "app/static/**/*.{css,js}"
  fi
fi

step "Ruff lint";            "${BIN}ruff" check .
step "Ruff format";          "${BIN}ruff" format --check .
step "Pyright";              "${BIN}pyright"
step "djLint lint";          "${BIN}djlint" app/templates --lint
step "djLint format";        "${BIN}djlint" app/templates --check

if [[ "${QUIZLAB_SKIP_FRONTEND:-0}" == "1" ]]; then
  step "Frontend checks skipped (QUIZLAB_SKIP_FRONTEND=1)"
else
  if ! command -v npx >/dev/null || [[ ! -d node_modules ]]; then
    echo "Frontend tooling missing: install Node.js and run 'npm ci'," >&2
    echo "or set QUIZLAB_SKIP_FRONTEND=1 to skip these checks." >&2
    exit 1
  fi
  step "Stylelint";          npx --no-install stylelint "app/static/css/**/*.css"
  step "ESLint";             npx --no-install eslint app/static/js
  step "Prettier";           npx --no-install prettier --check "app/static/**/*.{css,js}"
fi

step "Pytest";               "${BIN}pytest" -q

printf '\nAll checks passed.\n'
