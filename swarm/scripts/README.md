# swarm/scripts

Helper scripts for managing Deforum workflows in SwarmUI.

## manage-workflows.sh

Interactive manager for installing and triggering `deforum_video_sequencer_*` workflows.

### Interactive mode (default)

```bash
bash swarm/scripts/manage-workflows.sh
```

Presents a menu to install workflows, trigger runs via the SwarmUI API, check status, or apply patches.

### Non-interactive mode

**Install a workflow** into a running SwarmUI instance:

```bash
# Install one workflow (auto-detects SwarmUI under ~/SwarmUI)
bash swarm/scripts/manage-workflows.sh --install flux_schnell

# Install all workflows to a specific path
SWARM_ROOT=/opt/swarm/SwarmUI \
  bash swarm/scripts/manage-workflows.sh --install all

# Or specify the destination CustomWorkflows directory directly
bash swarm/scripts/manage-workflows.sh \
  --dest /opt/swarm/SwarmUI/src/BuiltinExtensions/ComfyUIBackend/CustomWorkflows \
  --install all
```

**Trigger a generation** via the SwarmUI API:

```bash
bash swarm/scripts/manage-workflows.sh \
  --run flux_schnell \
  --prompt "bioluminescent forest, flowing water, cinematic" \
  --frames 240 \
  --fps 24 \
  --seed 42

# Remote SwarmUI instance
bash swarm/scripts/manage-workflows.sh \
  --host 192.168.1.50 --port 7801 \
  --run z_image_turbo \
  --prompt "cosmic nebula, time-lapse" \
  --frames 120
```

**Show status:**

```bash
bash swarm/scripts/manage-workflows.sh --status
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `SWARM_ROOT` | auto-detect | Path to the SwarmUI checkout |
| `SWARM_HOST` | `localhost` | SwarmUI API host |
| `SWARM_PORT` | `7801` | SwarmUI API port |
| `SWARM_API_KEY` | *(empty)* | Bearer token if API auth is enabled |
| `WORKFLOW_DEST` | *(derived from SWARM_ROOT)* | Override CustomWorkflows destination |

### Workflow IDs

| ID | File |
|---|---|
| `flux_schnell` | `deforum_video_sequencer_flux_schnell.json` |
| `z_image_turbo` | `deforum_video_sequencer_z_image_turbo.json` |
| `sdxl_turbo` | `deforum_video_sequencer_sdxl_turbo.json` |
| `all` | (installs all three) |
