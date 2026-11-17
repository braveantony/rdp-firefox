#!/usr/bin/env bash
# Build the image: bash test/build.sh [tag]   (default localhost/rdp-firefox:dev)
# SESSION_SHARE=1 in the environment builds the -share variant.
set -eu
cd "$(dirname "$0")/.."
tag=${1:-localhost/rdp-firefox:dev}
podman build --build-arg "SESSION_SHARE=${SESSION_SHARE:-0}" -t "$tag" images/rdp-firefox
