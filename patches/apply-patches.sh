#!/usr/bin/env bash
# apply-patches.sh — apply comfyui-deforum SwarmUI patches to a local SwarmUI checkout
#
# Usage:
#   bash patches/apply-patches.sh <swarmui-root>
#   bash patches/apply-patches.sh --check <swarmui-root>   # dry-run only
#
# Example:
#   bash patches/apply-patches.sh ~/SwarmUI

set -euo pipefail

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

usage() {
    echo "Usage: $0 [--check] <path-to-SwarmUI>"
    echo ""
    echo "  --check    Dry-run: verify patches apply cleanly without modifying files."
    echo ""
    echo "Patches applied:"
    echo "  swarm-ui-eta-video-preview.patch  — video preview default + ETA counter fix"
    echo "  swarm-launchtools.patch           — docker-compose restart/ports/GPU + install script fixes"
    exit 1
}

DRY_RUN=false
SWARM_ROOT=""

for arg in "$@"; do
    case "$arg" in
        --check) DRY_RUN=true ;;
        --help|-h) usage ;;
        *) SWARM_ROOT="$arg" ;;
    esac
done

if [[ -z "$SWARM_ROOT" ]]; then
    usage
fi

if [[ ! -d "$SWARM_ROOT" ]]; then
    echo "ERROR: SwarmUI root not found: $SWARM_ROOT" >&2
    exit 1
fi

SWARM_ROOT=$(realpath "$SWARM_ROOT")
echo "SwarmUI root: $SWARM_ROOT"

PATCHES=(
    "swarm-ui-eta-video-preview.patch"
    "swarm-launchtools.patch"
)

GIT_APPLY_FLAGS="--whitespace=fix"
if $DRY_RUN; then
    GIT_APPLY_FLAGS="$GIT_APPLY_FLAGS --check"
    echo "DRY-RUN mode — no files will be modified."
fi

PASS=0
FAIL=0

for patch in "${PATCHES[@]}"; do
    patch_path="$SCRIPT_DIR/$patch"
    if [[ ! -f "$patch_path" ]]; then
        echo "  [SKIP] $patch — file not found"
        continue
    fi

    echo ""
    echo "Applying: $patch"
    if git -C "$SWARM_ROOT" apply $GIT_APPLY_FLAGS "$patch_path" 2>&1; then
        echo "  [OK]"
        ((PASS++)) || true
    else
        echo "  [FAIL] — patch did not apply cleanly."
        echo "  Try: git -C \"$SWARM_ROOT\" apply --reject \"$patch_path\""
        ((FAIL++)) || true
    fi
done

echo ""
echo "Done. $PASS patch(es) applied, $FAIL failed."
[[ $FAIL -eq 0 ]] || exit 1
