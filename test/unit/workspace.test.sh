#!/usr/bin/env bash
# Logic of the workspace desktop (no X server needed), run inside the image:
#   bash test/unit/workspace.test.sh [image]
# shellcheck disable=SC1091
set -u
cd "$(dirname "$0")/../.." || exit 1
. test/lib.sh
IMG=${1:-localhost/rdp-firefox:dev}
say core
if out=$(podman run --rm --entrypoint python3 -v "$PWD/test/unit:/t:ro,Z" "$IMG" /t/core_test.py 2>&1); then
  pass "core_test.py: $(tail -1 <<<"$out")"
else
  bad "core_test.py"; printf '%s\n' "$out" | tail -40
fi
finish
