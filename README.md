# comfyui-deforum-continuous

ComfyUI workflow presets for Deforum-based generative video, optimised for smooth, low-flicker continuous animation.

---

## Workflows

All workflows follow the naming convention **`deforum_video_sequencer_<type>.json`**.  
Canonical copies live in `swarm/CustomWorkflows/` (auto-loaded by SwarmUI via the volume mount in `swarm/docker-compose.host.yml`).  
Root-level copies are identical and exist for convenient drag-and-drop into a bare ComfyUI install.

| File | Model family | Steps | Scheduler |
|---|---|---|---|
| `deforum_video_sequencer_z_image_turbo.json` | Z-Image Turbo (6B, Alibaba) | 8 | `euler` + `turbo` |
| `deforum_video_sequencer_flux_schnell.json` | Flux Schnell (12B, BFL) | 4 | `euler` + `simple` |
| `deforum_video_sequencer_sdxl_turbo.json` | SDXL Turbo (Juggernaut) | 4 | `euler` + `sgm_uniform` |

---

### `deforum_video_sequencer_z_image_turbo.json`

A full Deforum animation workflow built around **Z-Image Turbo** — Alibaba's distilled 6B-parameter diffusion model that generates high-quality frames in ~8 steps.

**Key features:**
- **Z-Image Turbo split loaders** — `UNETLoader`, `CLIPLoader` (type `qwen_image`), `VAELoader`
- **Continuation** — `WAS_Image_Save` (unmute) saves the last frame to `input/z_image_turbo_continue.png`; set `use_init = Yes` in the init-image node to resume seamlessly
- **Optional animation nodes** — `DeforumDepthParamsNode`, `DeforumCadenceParamsNode`, `DeforumColorParamsNode` are bypassed; right-click → enable to activate
- **ControlNet infrastructure** — `ControlNetLoader` + `DeforumControlNetApply` are muted; see [ControlNet usage](#controlnet-usage) below

**Required models** (place in the indicated ComfyUI subdirectories):

| File | Folder |
|---|---|
| `z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors` | `models/diffusion_models/` |
| `qwen_3_4b.safetensors` | `models/text_encoders/` |
| `ae.safetensors` | `models/vae/` |

Download from [Comfy-Org/z\_image\_turbo](https://huggingface.co/Comfy-Org/z_image_turbo).

#### Recommended defaults — Z-Image Turbo

| Parameter | Recommended value | Notes |
|---|---|---|
| **Steps** | `8` | Model sweet-spot; going above 12 rarely helps |
| **CFG** | `1.0` | Distilled — CFG > 1 produces artefacts |
| **Sampler** | `euler` | |
| **Scheduler** | `turbo` | Required for correct noise scaling |
| **Strength schedule** | `0:(0.65), 12:(0.70), 24:(0.62)` | Lower = more temporal coherence |
| **Noise schedule** | `0:(0.030), 12:(0.040)` | Keep small to suppress flicker |
| **Seed** | Fixed (any value) | Random seed causes visible jumps between frames |
| **Resolution** | `1024×576` (16:9) or `768×768` | Stick to multiples of 64 |
| **Zoom schedule** | `0:(1.002)` | Very gentle zoom keeps the chain stable |
| **Frames** | `72–240` | ~3–10 s at 24 fps |
| **FPS (VHS combine)** | `24` | |

---

### `deforum_video_sequencer_flux_schnell.json`

A Deforum animation workflow built around **Flux Schnell** — Black Forest Labs' distilled 12B rectified-flow transformer.

**Key features:**
- **Split loaders** — `UNETLoader`, `DualCLIPLoader` (type `flux`), `VAELoader`
- **Init image required** — place a 1024×576 PNG at `ComfyUI/input/flux_schnell_continue.png` before the first run; `WAS_Image_Save` overwrites it each run for seamless continuation
- **Same optional nodes** — bypassed depth/cadence/colour-coherence; muted ControlNet infrastructure

**Required models** (place in the indicated ComfyUI subdirectories):

| File | Folder |
|---|---|
| `flux1-schnell-fp8.safetensors` | `models/diffusion_models/` (symlink from `Stable-Diffusion/FLUX1/` — see setup script) |
| `clip_l.safetensors` | `models/text_encoders/` |
| `t5xxl_fp8_e4m3fn.safetensors` | `models/text_encoders/` |
| `ae.safetensors` | `models/vae/` |

Download from [Comfy-Org/flux\_schnell](https://huggingface.co/Comfy-Org/flux_schnell). `ae.safetensors` is shared with Z-Image Turbo.

**Required custom nodes:** same as Z-Image Turbo (see below).

#### Recommended defaults — Flux Schnell

| Parameter | Recommended value | Notes |
|---|---|---|
| **Steps** | `4` | Model minimum; 4 is optimal for Schnell |
| **CFG** | `1.0` | Distilled — negative prompts have no effect |
| **Sampler** | `euler` | |
| **Scheduler** | `simple` | Flux-native; do not use `karras` |
| **Strength schedule** | `0:(0.65), 8:(0.72), 24:(0.68)` | Flux handles higher strength well |
| **Noise schedule** | `0:(0.020)` | Flux is very prompt-faithful; keep noise minimal |
| **Seed** | Fixed | Same reason as Z-Image Turbo |
| **Resolution** | `1024×576` or `896×512` | Must use VAE-encode path (init image required) |
| **Zoom schedule** | `0:(1.002)` | |
| **Frames** | `72–240` | |
| **FPS (VHS combine)** | `24` | |

> **First-run checklist:** copy any suitable 1024×576 image to `ComfyUI/input/flux_schnell_continue.png` before the first run. Without it the VAE-encode path fails.

---

### `deforum_video_sequencer_sdxl_turbo.json`

Older SDXL Turbo–based preset using `sd_xl_turbo_1.0_fp16.safetensors` (Juggernaut XL variant) via `CheckpointLoaderSimple`. Same core Deforum chain, tuned for SDXL sampler characteristics.

**Required models:**

| File | Folder |
|---|---|
| `sd_xl_turbo_1.0_fp16.safetensors` (or Juggernaut XL) | `models/checkpoints/` |

#### Recommended defaults — SDXL Turbo

| Parameter | Recommended value | Notes |
|---|---|---|
| **Steps** | `4` | Distilled for 1–4 steps; higher adds little |
| **CFG** | `1.0` | Distilled — CFG > 1 adds artefacts |
| **Sampler** | `euler` | SDXL Turbo canonical sampler |
| **Scheduler** | `sgm_uniform` | Required for correct turbo noise scaling; not karras |
| **Strength schedule** | `0:(0.55), 12:(0.60)` | SDXL is heavier per frame; moderate strength avoids drift |
| **Noise schedule** | `0:(0.040)` | |
| **Seed** | Fixed | |
| **Resolution** | `960×540` | 16:9; SDXL Turbo works well at sub-1024 |
| **Frames** | `48–120` | SDXL is slower per frame |

---

## ControlNet Usage

All workflows include a **muted** ControlNet block that can be activated to guide each frame with a structural signal (depth, Canny edges, pose, etc.).

### Supported workflows

ControlNet works with Z-Image Turbo and Flux Schnell (both include `ControlNetLoader` + `DeforumControlNetApply` nodes). The SDXL Turbo preset does not include this block by default.

### Step-by-step activation

1. **Download a compatible ControlNet model** and place it in `ComfyUI/models/controlnet/`:
   - Z-Image Turbo / Flux: use a native Flux ControlNet (e.g. `flux-canny-controlnet-v3.safetensors`) or a compatible SD3/unified model
   - SDXL: use any SDXL ControlNet (e.g. `controlnet-canny-sdxl-1.0.safetensors`)

2. **Unmute the ControlNetLoader node** — right-click it → **"Remove Mute"** (the node turns from grey to its normal colour).

3. **Set the model filename** — double-click the `ControlNetLoader` widget and select your `.safetensors` file from the dropdown.

4. **Unmute `DeforumControlNetApply`** — same right-click procedure.

5. **Connect the control image source** — the `DeforumControlNetApply` node expects:
   - `image` input: a control image or the output of a preprocessor node (e.g. `CannyEdgePreprocessor`, `MiDaS-DepthMapPreprocessor`)
   - `control_net` input: wired from `ControlNetLoader`
   - `conditioning` input: wired from the positive conditioning output

   For video-to-video guidance, wire the previous frame (from `DeforumIteratorNode` output) into a preprocessor, then into `DeforumControlNetApply`.

6. **Tune the ControlNet strength** in the `DeforumControlNetApply` node:

   | Use case | `strength` | `start_percent` | `end_percent` |
   |---|---|---|---|
   | Loose structural guidance | `0.4–0.6` | `0.0` | `0.7` |
   | Strong edge adherence | `0.7–0.9` | `0.0` | `1.0` |
   | Late-pass refinement only | `0.5–0.8` | `0.3` | `0.9` |

7. **Verify the wiring** — the control signal must feed into the sampler's conditioning path (`DeforumKSampler`), not the bypass path used by `DeforumSingleSampleNode`. Confirm by tracing the orange conditioning wires.

### Common preprocessors

| Effect | Node |
|---|---|
| Canny edges | `CannyEdgePreprocessor` |
| Depth map | `MiDaS-DepthMapPreprocessor` or `ZoeDepthMapPreprocessor` |
| Human pose | `DWPreprocessor` |
| Soft edges | `TEEDPreprocessor` |
| Line art | `LineArtPreprocessor` |

Preprocessor nodes are provided by [comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux).

---

---

## AnimateDiff path

Every workflow ships a **muted AnimateDiff path** directly below the main Deforum graph. It provides an alternative generation method — all frames rendered simultaneously via temporal attention rather than iterative img2img chaining — with the same output VHS node.

### Architecture compatibility

| Workflow | AnimateDiff | Notes |
|---|---|---|
| `sdxl_turbo` | ✓ native | Uses existing CheckpointLoaderSimple + CLIPSetLastLayer |
| `flux_schnell` | via separate checkpoint | Flux has no motion module; path uses its own `CheckpointLoaderSimple` [id=36] |
| `z_image_turbo` | via separate checkpoint | Same — add any SDXL/SD1.5 checkpoint to the AD `CheckpointLoaderSimple` [id=36] |

### Switching from Deforum to AnimateDiff

1. **Mute the Deforum sampler** — right-click `DeforumSingleSampleNode` [id=9] → **Mute Node**
2. **Unmute all AnimateDiff nodes** — right-click each node in the purple group → **Remove Mute**:
   - `CheckpointLoaderSimple` [id=36] *(Flux/Z-Image only)*
   - `ADE_AnimateDiffUniformContextOptions`
   - `ADE_AnimateDiffLoaderWithContext` — set `model_name` to your installed `.ckpt`
   - Both `CLIPTextEncode` nodes — edit the positive/negative prompt text
   - `EmptyLatentImage` — set `batch_size` = desired frame count
   - `KSampler` — adjust steps, CFG, sampler, scheduler, denoise
   - `VAEDecode`
   - `VHS_VideoCombine` (AnimateDiff output)

**To switch back to Deforum:** unmute `DeforumSingleSampleNode` [id=9]; mute the AD nodes above.

### AnimateDiff controls reference

| Node | Key settings |
|---|---|
| `ADE_AnimateDiffLoaderWithContext` | `model_name` — filename of your motion module (place in `models/animatediff_models/`) |
| `ADE_AnimateDiffUniformContextOptions` | `context_length` (default 16) — frames per context window; `context_overlap` (default 4) |
| `EmptyLatentImage` | `batch_size` — total frame count (e.g. 24 = 1 s at 24 fps) |
| `KSampler` | `steps` 20, `cfg` 7.0, `sampler` euler, `scheduler` karras, `denoise` 1.0 (recommended defaults) |
| `VHS_VideoCombine` (AD) | `filename_prefix` — output filename; frame rate shared with Deforum PrimitiveNode |

### Recommended motion modules

| Architecture | Motion module |
|---|---|
| SDXL | `animatediff_sdxl_v10.ckpt` (AnimateDiff-Evolved SDXL) |
| SD 1.5 | `mm_sd_v15_v2.ckpt` or `animatediff_v3_adapter_sd.ckpt` |

Download from [guoyww/animatediff](https://huggingface.co/guoyww/animatediff) and place in `ComfyUI/models/animatediff_models/`.

### Required additional custom node

- [ComfyUI-AnimateDiff-Evolved](https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved)

---

## Required custom nodes (all workflows)

- [deforum-comfy-nodes](https://github.com/XmYx/deforum-comfy-nodes)
- [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) (VHS)
- [was-node-suite-comfyui](https://github.com/WASasquatch/was-node-suite-comfyui) — only for the continuation auto-save node
- [comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux) — only when using ControlNet preprocessors

---

## SwarmUI setup

### Quick start

```bash
cd swarm/launchtools
bash install-linux.sh
```

Copy your desired workflow(s) into SwarmUI's custom-workflows directory or use the Docker volume mount in `swarm/docker-compose.host.yml` which binds `./CustomWorkflows` automatically.

See `swarm/scripts/README.md` for the interactive workflow manager and API-based runner.

### Applying patches

The `patches/` directory contains SwarmUI source patches that improve video generation UX:

| Patch | What it does |
|---|---|
| `swarm-ui-eta-video-preview.patch` | Sets default video preview to `iterate` mode; fixes ETA counter for multi-image batches |
| `swarm-launchtools.patch` | Docker compose: `restart: always`, bind-mount backend, extra ports, multi-GPU; install script path fixes |

Apply both with one command:

```bash
bash patches/apply-patches.sh /path/to/SwarmUI
```

See `patches/apply-patches.sh --help` for options.
