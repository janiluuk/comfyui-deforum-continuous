# comfyui-deforum-continuous

ComfyUI workflow presets for Deforum-based generative video, optimised for smooth, low-flicker continuous animation.

## Workflows

### `deforum_z_image_turbo_video.json`

A full Deforum animation workflow built around **Z-Image Turbo** — Alibaba's distilled 6B-parameter diffusion model that generates high-quality frames in ~8 steps.

**Purpose:** produce cinematic, continuously flowing generative video with minimal flickering. Each frame is initialised from the previous one, creating a coherent visual stream rather than a series of disconnected images.

**Key features:**

- **Z-Image Turbo split loaders** — uses ComfyUI's native `UNETLoader`, `CLIPLoader` (type `qwen_image`), and `VAELoader` instead of a single checkpoint, matching the model's three-file layout
- **Anti-flicker defaults** — fixed seed, `euler` + `turbo` scheduler, CFG 1.0, flat 8-step schedule, eased strength/noise ramps, and a very gentle zoom to keep the chain temporally stable
- **Continuation** — a `WAS_Image_Save` node (unmute to enable) saves the last generated frame to `input/z_image_turbo_continue.png`; toggle `use_init = Yes` in the init-image node to resume from exactly where the previous run ended
- **Disabled alternative animation nodes** — `DeforumDepthParamsNode` (3D depth warp), `DeforumCadenceParamsNode` (optical-flow tween frames), and `DeforumColorParamsNode` (colour coherence) are wired into the data chain in bypass mode; right-click any one and enable it to activate that technique
- **ControlNet infrastructure** — `ControlNetLoader` and `DeforumControlNetApply` are present in muted state with a wiring guide; activate them alongside a `DeforumIteratorNode` + `DeforumKSampler` path for per-frame ControlNet guidance

**Required models** (place in the indicated ComfyUI subdirectories):

| File | Folder |
|---|---|
| `z_image_turbo_bf16.safetensors` | `models/diffusion_models/` |
| `qwen_3_4b.safetensors` | `models/text_encoders/` |
| `ae.safetensors` | `models/vae/` |

Download from [Comfy-Org/z\_image\_turbo](https://huggingface.co/Comfy-Org/z_image_turbo).

**Required custom nodes:**

- [deforum-comfy-nodes](https://github.com/XmYx/deforum-comfy-nodes)
- [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) (VHS)
- [was-node-suite-comfyui](https://github.com/WASasquatch/was-node-suite-comfyui) — only needed for the continuation auto-save node

### `deforum_v1_video.json` / `deforum_juggernaut_video.json`

Older SDXL Turbo–based presets using `sd_xl_turbo_1.0_fp16.safetensors` via `CheckpointLoaderSimple`. Same Deforum animation chain, tuned for SDXL's sampler characteristics.
