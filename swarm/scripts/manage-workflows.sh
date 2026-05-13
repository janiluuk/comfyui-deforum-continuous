#!/usr/bin/env bash
# manage-workflows.sh — interactive manager for deforum_video_sequencer workflows in SwarmUI
#
# Usage (interactive menu):
#   bash swarm/scripts/manage-workflows.sh
#
# Usage (non-interactive, e.g. CI):
#   bash swarm/scripts/manage-workflows.sh --install flux_schnell
#   bash swarm/scripts/manage-workflows.sh --install all
#   bash swarm/scripts/manage-workflows.sh --run flux_schnell --frames 120 --fps 24 --prompt "cosmic ocean"
#   bash swarm/scripts/manage-workflows.sh --status

set -euo pipefail

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
REPO_ROOT=$(realpath "$SCRIPT_DIR/../..")
WORKFLOWS_SRC="$REPO_ROOT/swarm/CustomWorkflows"

# ---------------------------------------------------------------------------
# Defaults — override via env or CLI flags
# ---------------------------------------------------------------------------
SWARM_ROOT="${SWARM_ROOT:-}"
SWARM_HOST="${SWARM_HOST:-localhost}"
SWARM_PORT="${SWARM_PORT:-7801}"
SWARM_API_KEY="${SWARM_API_KEY:-}"

WORKFLOW_DEST="${WORKFLOW_DEST:-}"   # auto-detected from SWARM_ROOT if unset

WORKFLOWS=(
    "flux_schnell:deforum_video_sequencer_flux_schnell.json:Flux Schnell (12B, 4 steps, needs init image)"
    "z_image_turbo:deforum_video_sequencer_z_image_turbo.json:Z-Image Turbo (6B, 8 steps)"
    "sdxl_turbo:deforum_video_sequencer_sdxl_turbo.json:SDXL Turbo / Juggernaut XL (checkpoint, 4-8 steps)"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { echo "[deforum] $*"; }
info() { echo ""; echo "  $*"; }
err()  { echo "[ERROR] $*" >&2; }

workflow_id()   { echo "$1" | cut -d: -f1; }
workflow_file() { echo "$1" | cut -d: -f2; }
workflow_desc() { echo "$1" | cut -d: -f3-; }

detect_swarm_root() {
    if [[ -n "$SWARM_ROOT" && -d "$SWARM_ROOT" ]]; then
        echo "$SWARM_ROOT"
        return
    fi
    # Common locations — /opt/swarm is the production install on this server
    for candidate in \
        "/opt/swarm" \
        "$HOME/SwarmUI" \
        "/SwarmUI" \
        "$(dirname "$REPO_ROOT")/SwarmUI"; do
        if [[ -d "$candidate/src/BuiltinExtensions/ComfyUIBackend" ]]; then
            echo "$candidate"
            return
        fi
    done
    echo ""
}

detect_workflow_dest() {
    if [[ -n "$WORKFLOW_DEST" ]]; then
        echo "$WORKFLOW_DEST"
        return
    fi
    local root
    root=$(detect_swarm_root)
    if [[ -n "$root" ]]; then
        echo "$root/src/BuiltinExtensions/ComfyUIBackend/CustomWorkflows"
    else
        echo ""
    fi
}

swarm_api() {
    local endpoint="$1"; shift
    local data="${1:-}"
    local url="http://${SWARM_HOST}:${SWARM_PORT}/API/${endpoint}"
    local curl_args=(-s -S -X POST "$url" -H "Content-Type: application/json")
    [[ -n "$SWARM_API_KEY" ]] && curl_args+=(-H "Authorization: Bearer $SWARM_API_KEY")
    [[ -n "$data" ]] && curl_args+=(-d "$data")
    curl "${curl_args[@]}"
}

swarm_is_running() {
    curl -sf "http://${SWARM_HOST}:${SWARM_PORT}/" -o /dev/null --max-time 2 2>/dev/null
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
cmd_setup_models() {
    # Create symlinks so ComfyUI's diffusion_models/ can see models stored under Stable-Diffusion/FLUX1/
    local MODELS_DIR="${1:-/data/models}"

    echo "Setting up model symlinks in $MODELS_DIR/diffusion_models/"
    mkdir -p "$MODELS_DIR/diffusion_models"

    local FLUX1_DIR="$MODELS_DIR/Stable-diffusion/FLUX1"
    local UNET_DIR="$MODELS_DIR/diffusion_models"

    local linked=0 skipped=0
    for f in \
        "flux1-schnell-fp8.safetensors" \
        "flux1-dev-fp8.safetensors" \
        "flux1-dev-bnb-nf4-v2.safetensors"; do
        src="$FLUX1_DIR/$f"
        dst="$UNET_DIR/$f"
        if [[ -f "$src" && ! -e "$dst" ]]; then
            ln -sf "$src" "$dst"
            log "symlinked: $f → diffusion_models/"
            ((linked++)) || true
        elif [[ -e "$dst" ]]; then
            log "already exists: diffusion_models/$f"
            ((skipped++)) || true
        else
            log "source not found, skipping: $src"
        fi
    done

    echo "Done: $linked symlink(s) created, $skipped already present."
}

cmd_status() {
    echo "=== Deforum Workflow Manager — Status ==="
    echo ""
    echo "Repository:  $REPO_ROOT"
    echo "Source dir:  $WORKFLOWS_SRC"

    local dest
    dest=$(detect_workflow_dest)
    echo "Install dir: ${dest:-<not detected — set SWARM_ROOT>}"
    echo ""

    echo "Available source workflows:"
    for w in "${WORKFLOWS[@]}"; do
        local id file desc src_path
        id=$(workflow_id "$w"); file=$(workflow_file "$w"); desc=$(workflow_desc "$w")
        src_path="$WORKFLOWS_SRC/$file"
        if [[ -f "$src_path" ]]; then
            echo "  [✓] $id — $desc"
        else
            echo "  [✗] $id — SOURCE MISSING ($src_path)"
        fi
    done

    if [[ -n "$dest" ]]; then
        echo ""
        echo "Installed workflows:"
        for w in "${WORKFLOWS[@]}"; do
            local id file dest_path
            id=$(workflow_id "$w"); file=$(workflow_file "$w")
            dest_path="$dest/$file"
            if [[ -f "$dest_path" ]]; then
                echo "  [installed] $id"
            else
                echo "  [missing]   $id"
            fi
        done
    fi

    echo ""
    if swarm_is_running; then
        echo "SwarmUI API: RUNNING at http://${SWARM_HOST}:${SWARM_PORT}"
    else
        echo "SwarmUI API: not reachable at http://${SWARM_HOST}:${SWARM_PORT}"
    fi
}

cmd_install() {
    local target="$1"
    local dest
    dest=$(detect_workflow_dest)

    if [[ -z "$dest" ]]; then
        err "Cannot detect SwarmUI install. Set SWARM_ROOT or WORKFLOW_DEST."
        err "Example: SWARM_ROOT=~/SwarmUI bash $0 --install $target"
        exit 1
    fi

    mkdir -p "$dest"

    local installed=0
    for w in "${WORKFLOWS[@]}"; do
        local id file src_path dest_path
        id=$(workflow_id "$w"); file=$(workflow_file "$w")
        src_path="$WORKFLOWS_SRC/$file"
        dest_path="$dest/$file"

        [[ "$target" != "all" && "$target" != "$id" ]] && continue

        if [[ ! -f "$src_path" ]]; then
            err "Source not found: $src_path"
            continue
        fi

        cp "$src_path" "$dest_path"
        log "Installed: $file → $dest_path"
        ((installed++)) || true
    done

    if [[ $installed -eq 0 ]]; then
        err "No matching workflow for '$target'. Valid IDs: flux_schnell, z_image_turbo, sdxl_turbo, all"
        exit 1
    fi

    log "$installed workflow(s) installed. Restart SwarmUI or reload custom workflows to use them."
}

cmd_run() {
    # Trigger a workflow via SwarmUI's GenerateText2Image API
    local workflow_id="$1"
    shift

    # Defaults
    local frames=120 fps=24 prompt="cosmic flowing dreamscape, high detail" \
          negative="" seed=-1 width=1024 height=576

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --frames)   frames="$2";   shift 2 ;;
            --fps)      fps="$2";      shift 2 ;;
            --prompt)   prompt="$2";   shift 2 ;;
            --negative) negative="$2"; shift 2 ;;
            --seed)     seed="$2";     shift 2 ;;
            --width)    width="$2";    shift 2 ;;
            --height)   height="$2";   shift 2 ;;
            *) err "Unknown flag: $1"; exit 1 ;;
        esac
    done

    # Find workflow filename
    local workflow_file=""
    for w in "${WORKFLOWS[@]}"; do
        [[ "$(workflow_id "$w")" == "$workflow_id" ]] && workflow_file=$(workflow_file "$w") && break
    done
    if [[ -z "$workflow_file" ]]; then
        err "Unknown workflow ID: $workflow_id"
        exit 1
    fi
    local workflow_name="${workflow_file%.json}"

    if ! swarm_is_running; then
        err "SwarmUI not reachable at http://${SWARM_HOST}:${SWARM_PORT}. Is it running?"
        exit 1
    fi

    log "Triggering workflow: $workflow_name"
    log "  frames=$frames  fps=$fps  seed=$seed  resolution=${width}x${height}"
    log "  prompt: $prompt"

    local payload
    payload=$(cat <<JSON
{
    "session_id": "deforum-cli",
    "images": 1,
    "prompt": $(printf '%s' "$prompt" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
    "negativeprompt": $(printf '%s' "$negative" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
    "seed": $seed,
    "width": $width,
    "height": $height,
    "customworkflowraw": "$workflow_name",
    "video_frames": $frames,
    "video_fps": $fps
}
JSON
)

    local response
    response=$(swarm_api "GenerateText2Image" "$payload")
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
}

cmd_menu() {
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║     Deforum Video Sequencer — Workflow Manager       ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
    echo "  1) Install workflow(s)"
    echo "  2) Trigger a workflow via SwarmUI API"
    echo "  3) Show status"
    echo "  4) Apply SwarmUI patches"
    echo "  5) Set up model symlinks (Flux Schnell diffusion_models/)"
    echo "  q) Quit"
    echo ""
    printf "Choice: "
    read -r choice

    case "$choice" in
        1) menu_install ;;
        2) menu_run ;;
        3) cmd_status ;;
        4) menu_patches ;;
        5) printf "Models base dir [/data/models]: "; read -r mdir; cmd_setup_models "${mdir:-/data/models}" ;;
        q|Q) exit 0 ;;
        *) echo "Unknown choice."; exit 1 ;;
    esac
}

menu_install() {
    echo ""
    echo "Select workflow to install:"
    local i=1
    for w in "${WORKFLOWS[@]}"; do
        echo "  $i) $(workflow_id "$w") — $(workflow_desc "$w")"
        ((i++)) || true
    done
    echo "  a) All"
    echo ""
    printf "Choice: "
    read -r choice

    if [[ "$choice" == "a" || "$choice" == "A" ]]; then
        cmd_install "all"
        return
    fi

    local idx=$((choice - 1))
    local w="${WORKFLOWS[$idx]:-}"
    if [[ -z "$w" ]]; then
        err "Invalid choice."
        exit 1
    fi

    printf "SwarmUI root [%s]: " "${SWARM_ROOT:-auto-detect}"
    read -r input_root
    [[ -n "$input_root" ]] && SWARM_ROOT="$input_root"

    cmd_install "$(workflow_id "$w")"
}

menu_run() {
    echo ""
    echo "Select workflow to run:"
    local i=1
    for w in "${WORKFLOWS[@]}"; do
        echo "  $i) $(workflow_id "$w") — $(workflow_desc "$w")"
        ((i++)) || true
    done
    printf "Choice: "
    read -r choice

    local idx=$((choice - 1))
    local w="${WORKFLOWS[$idx]:-}"
    if [[ -z "$w" ]]; then
        err "Invalid choice."
        exit 1
    fi
    local wid
    wid=$(workflow_id "$w")

    printf "Prompt [cosmic flowing dreamscape]: "
    read -r prompt
    prompt="${prompt:-cosmic flowing dreamscape}"

    printf "Frames [120]: "
    read -r frames
    frames="${frames:-120}"

    printf "FPS [24]: "
    read -r fps
    fps="${fps:-24}"

    printf "Seed [-1 = random]: "
    read -r seed
    seed="${seed:--1}"

    cmd_run "$wid" --prompt "$prompt" --frames "$frames" --fps "$fps" --seed "$seed"
}

menu_patches() {
    echo ""
    printf "SwarmUI root to patch: "
    read -r swarm_path
    if [[ -z "$swarm_path" ]]; then
        err "No path provided."
        exit 1
    fi
    bash "$REPO_ROOT/patches/apply-patches.sh" "$swarm_path"
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if [[ $# -eq 0 ]]; then
    cmd_menu
    exit 0
fi

COMMAND=""
COMMAND_ARG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install)   COMMAND="install";  COMMAND_ARG="${2:-all}"; [[ $# -ge 2 ]] && shift; shift ;;
        --run)       COMMAND="run";      COMMAND_ARG="${2:-}";    shift 2 ;;
        --status)    COMMAND="status";   shift ;;
        --host)      SWARM_HOST="$2";    shift 2 ;;
        --port)      SWARM_PORT="$2";    shift 2 ;;
        --dest)      WORKFLOW_DEST="$2"; shift 2 ;;
        --setup-models)
            COMMAND="setup_models"
            COMMAND_ARG="${2:-/data/models}"; [[ $# -ge 2 ]] && shift; shift ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --install <id|all>       Install workflow(s) to SwarmUI CustomWorkflows dir"
            echo "  --run <id> [run-opts]    Trigger workflow via SwarmUI API"
            echo "  --setup-models [path]    Create diffusion_models/ symlinks for Flux Schnell (default: /data/models)
  --status                 Show workflow and SwarmUI status"
            echo "  --host <host>            SwarmUI host (default: localhost)"
            echo "  --port <port>            SwarmUI port (default: 7801)"
            echo "  --dest <path>            Override CustomWorkflows destination path"
            echo ""
            echo "Run options (for --run):"
            echo "  --frames <n>             Number of frames (default: 120)"
            echo "  --fps <n>                Frames per second (default: 24)"
            echo "  --prompt <text>          Positive prompt"
            echo "  --negative <text>        Negative prompt"
            echo "  --seed <n>               Seed (-1 for random)"
            echo "  --width <n>              Width (default: 1024)"
            echo "  --height <n>             Height (default: 576)"
            echo ""
            echo "Environment:"
            echo "  SWARM_ROOT               Path to SwarmUI checkout (for --install)"
            echo "  SWARM_HOST / SWARM_PORT  API address (for --run / --status)"
            echo "  SWARM_API_KEY            Bearer token if auth is enabled"
            exit 0
            ;;
        *)
            # Pass remaining args to sub-command
            break
            ;;
    esac
done

case "$COMMAND" in
    install)      cmd_install "$COMMAND_ARG" ;;
    run)          cmd_run "$COMMAND_ARG" "$@" ;;
    status)       cmd_status ;;
    setup_models) cmd_setup_models "$COMMAND_ARG" ;;
    "")           cmd_menu ;;
esac
