#!/usr/bin/env bash
set -uo pipefail

root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$root"
log_dir="$(mktemp -d)"
trap 'rm -rf "$log_dir"' EXIT
passed=0
failed=0

run() {
  local name="$1"
  shift
  if "$@" >"$log_dir/$name" 2>&1; then
    printf '%-14s PASS\n' "$name"
    ((passed += 1))
  else
    printf '%-14s FAIL\n' "$name"
    cat "$log_dir/$name"
    ((failed += 1))
  fi
}

run black .venv/bin/black --check moonlight-voice/moonlight_voice tests moonlight-voice/tests
run ruff .venv/bin/ruff check moonlight-voice/moonlight_voice tests moonlight-voice/tests
run pylint env PYTHONPATH=moonlight-voice .venv/bin/pylint moonlight-voice/moonlight_voice tests
run mypy env PYTHONPATH=moonlight-voice .venv/bin/mypy moonlight-voice/moonlight_voice tests moonlight-voice/tests
run pyright env PYTHONPATH=moonlight-voice .venv/bin/pyright
run python-tests .venv/bin/python -m unittest discover -s tests
run addon-tests env PYTHONPATH=moonlight-voice .venv/bin/python -m pytest moonlight-voice/tests -q
run eslint npm run --silent lint
run prettier npm run --silent format:check
run typecheck npm run --silent typecheck

printf 'checks: %d passed, %d failed\n' "$passed" "$failed"
test "$failed" -eq 0
