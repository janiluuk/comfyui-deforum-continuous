"""
add_animatediff.py — inject a switchable AnimateDiff path into each deforum_video_sequencer workflow.

AnimateDiff path layout (muted by default, below existing graph):
  ┌─────────────────────────────────────────────────────────────────────────┐
  │ ANIMATEDIFF PATH  ·  muted by default  ·  requires AnimateDiff-Evolved  │
  │                                                                         │
  │  [Context Opts]──▶[ADE Loader]──────────────────────┐                  │
  │  [Checkpoint*]──▶ (*Flux/Z-Turbo only: own SDXL CKP) ├──▶[KSampler]   │
  │  [CLIP+Encode]──▶ positive cond ────────────────────┤     │            │
  │  [CLIP-Encode]──▶ negative cond ────────────────────┤     │            │
  │  [EmptyLatent] ──▶ latent ──────────────────────────┘     │            │
  │                                                            ▼            │
  │                                               [VAEDecode]──▶[VHS out]  │
  └─────────────────────────────────────────────────────────────────────────┘

SWITCH Deforum → AnimateDiff:
  1. Right-click DeforumSingleSampleNode [id=9] → Mute
  2. Unmute all AD nodes in the group below
SWITCH BACK: reverse.
"""

import json, shutil, copy

# ── helpers ──────────────────────────────────────────────────────────────────

M_ACTIVE = 0
M_MUTED  = 2

def lnk(lid, src, src_slot, dst, dst_slot, ltype):
    return [lid, src, src_slot, dst, dst_slot, ltype]

def inp(name, ltype, link=None):
    return {"name": name, "type": ltype, "link": link}

def out(name, ltype, links=None, slot=0):
    return {"name": name, "type": ltype, "links": links or [], "slot_index": slot, "shape": 3}

def make_node(id, ntype, pos, size, order, mode, title, wv, ins, outs, color=None, properties=None):
    n = {
        "id": id,
        "type": ntype,
        "pos": pos,
        "size": size,
        "flags": {},
        "order": order,
        "mode": mode,
        "inputs": ins,
        "outputs": outs,
        "properties": properties or {"Node name for S&R": ntype},
        "widgets_values": wv,
    }
    if title:
        n["title"] = title
    if color:
        n["color"] = color
    return n

def note(id, pos, size, order, text, title="Note", color="#445"):
    return {
        "id": id, "type": "Note",
        "pos": pos, "size": size,
        "flags": {}, "order": order, "mode": M_ACTIVE,
        "inputs": [], "outputs": [],
        "title": title,
        "properties": {"text": text},
        "widgets_values": [text],
        "color": color,
    }

def vhs_combine_wv(prefix):
    return {
        "frame_rate": 24, "loop_count": 0,
        "filename_prefix": prefix,
        "format": "video/h264-mp4", "pix_fmt": "yuv422p", "crf": 7,
        "save_metadata": True, "trim_to_audio": False,
        "pingpong": False, "save_output": True,
        "videopreview": {"hidden": False, "paused": False},
    }

def vhs_combine_inputs(img_link, fps_link):
    return [
        inp("images",     "IMAGE",           img_link),
        inp("audio",      "AUDIO",           None),
        inp("meta_batch", "VHS_BatchManager", None),
        inp("frame_rate", "FLOAT",           fps_link),
    ]


# ── per-workflow additions ────────────────────────────────────────────────────

def add_animatediff_sdxl(data):
    """SDXL Turbo: uses existing CheckpointLoaderSimple (id=1) + CLIPSetLastLayer (id=23)."""

    # IDs
    N_NOTE   = 24
    N_CTX    = 25   # ADE_AnimateDiffUniformContextOptions
    N_ADE    = 26   # ADE_AnimateDiffLoaderWithContext
    N_POS    = 27   # CLIPTextEncode positive
    N_NEG    = 28   # CLIPTextEncode negative
    N_LAT    = 29   # EmptyLatentImage
    N_KSAMP  = 30   # KSampler
    N_VAED   = 31   # VAEDecode
    N_VHS    = 32   # VHS_VideoCombine (AD output)

    # Link IDs (SDXL last_link_id=23 → start at 24)
    L_CKP_ADE  = 24   # Checkpoint.MODEL → ADE loader
    L_CTX_ADE  = 25   # Context opts → ADE loader
    L_ADE_KS   = 26   # ADE loader.MODEL → KSampler
    L_CLIP_POS = 27   # CLIPSetLastLayer → pos encode
    L_CLIP_NEG = 28   # CLIPSetLastLayer → neg encode
    L_POS_KS   = 29   # pos COND → KSampler.positive
    L_NEG_KS   = 30   # neg COND → KSampler.negative
    L_LAT_KS   = 31   # EmptyLatent → KSampler.latent
    L_KS_VAE   = 32   # KSampler → VAEDecode.samples
    L_CKP_VAE  = 33   # Checkpoint.VAE → VAEDecode.vae
    L_VAE_VHS  = 34   # VAEDecode.IMAGE → VHS.images
    L_FPS_VHS  = 35   # PrimitiveNode FPS → VHS.frame_rate

    Y = 1370  # top of AD block

    SWITCH_TEXT = (
        "ANIMATEDIFF PATH  ·  All nodes below are MUTED by default\n"
        "\n"
        "Required custom node: ComfyUI-AnimateDiff-Evolved\n"
        "Motion module goes in: models/animatediff_models/\n"
        "\n"
        "Controls: edit KSampler (steps / CFG / sampler / scheduler / denoise)\n"
        "          edit EmptyLatentImage batch_size for frame count\n"
        "          edit CLIPTextEncode nodes for prompts\n"
        "\n"
        "TO SWITCH  Deforum → AnimateDiff:\n"
        "  1. Right-click DeforumSingleSampleNode [id=9]  → Mute Node\n"
        "  2. Right-click each node in this group → Remove Mute\n"
        "     (ADE Context, ADE Loader, pos/neg CLIP encode, EmptyLatent, KSampler, VAEDecode, VHS)\n"
        "\n"
        "TO SWITCH BACK: mute all AD nodes; unmute id=9."
    )

    new_nodes = [
        note(N_NOTE, [50, Y], [1200, 210], 23, SWITCH_TEXT,
             "ANIMATEDIFF PATH  ·  muted by default"),

        # Context window options ─── no link inputs, all widgets
        make_node(N_CTX, "ADE_AnimateDiffUniformContextOptions",
                  [50, Y+250], [340, 160], 24, M_MUTED,
                  "Context window · length=16 overlap=4",
                  [16, 1, 4, False],
                  [],
                  [out("CONTEXT_OPTIONS", "CONTEXT_OPTIONS", [L_CTX_ADE])]),

        # ADE loader ─── model from Checkpoint, context_options from above
        make_node(N_ADE, "ADE_AnimateDiffLoaderWithContext",
                  [430, Y+250], [420, 180], 25, M_MUTED,
                  "AnimateDiff loader (SDXL)  ·  set motion module filename",
                  ["animatediff_sdxl_v10.ckpt", "linear (AnimateDiff)"],
                  [inp("model",           "MODEL",           L_CKP_ADE),
                   inp("context_options", "CONTEXT_OPTIONS", L_CTX_ADE)],
                  [out("MODEL", "MODEL", [L_ADE_KS])]),

        # Positive prompt
        make_node(N_POS, "CLIPTextEncode",
                  [50, Y+470], [420, 130], 26, M_MUTED,
                  "Positive prompt (AnimateDiff)",
                  ["cinematic futuristic neon city, smooth flowing camera motion, "
                   "atmospheric haze, volumetric lighting, high detail, photorealistic"],
                  [inp("clip", "CLIP", L_CLIP_POS)],
                  [out("CONDITIONING", "CONDITIONING", [L_POS_KS])]),

        # Negative prompt
        make_node(N_NEG, "CLIPTextEncode",
                  [510, Y+470], [420, 130], 27, M_MUTED,
                  "Negative prompt (AnimateDiff)",
                  ["blurry, low quality, watermark, text, distorted, overexposed, static"],
                  [inp("clip", "CLIP", L_CLIP_NEG)],
                  [out("CONDITIONING", "CONDITIONING", [L_NEG_KS])]),

        # Empty latent — batch_size = frame count
        make_node(N_LAT, "EmptyLatentImage",
                  [980, Y+470], [270, 165], 28, M_MUTED,
                  "Latent frames  ·  batch_size = frame count",
                  [960, 540, 24],
                  [],
                  [out("LATENT", "LATENT", [L_LAT_KS])]),

        # KSampler — all essential controls live here
        make_node(N_KSAMP, "KSampler",
                  [50, Y+640], [315, 270], 29, M_MUTED,
                  "AnimateDiff KSampler  ·  euler · karras · 20 steps · CFG 7",
                  [12345, "fixed", 20, 7.0, "euler", "karras", 1.0],
                  [inp("model",        "MODEL",        L_ADE_KS),
                   inp("positive",     "CONDITIONING", L_POS_KS),
                   inp("negative",     "CONDITIONING", L_NEG_KS),
                   inp("latent_image", "LATENT",       L_LAT_KS)],
                  [out("LATENT", "LATENT", [L_KS_VAE])]),

        # VAEDecode
        make_node(N_VAED, "VAEDecode",
                  [420, Y+640], [210, 130], 30, M_MUTED,
                  "",
                  [],
                  [inp("samples", "LATENT", L_KS_VAE),
                   inp("vae",     "VAE",    L_CKP_VAE)],
                  [out("IMAGE", "IMAGE", [L_VAE_VHS])]),

        # VHS output for AnimateDiff
        make_node(N_VHS, "VHS_VideoCombine",
                  [680, Y+640], [350, 340], 31, M_MUTED,
                  "AnimateDiff output",
                  vhs_combine_wv("animatediff_sdxl"),
                  vhs_combine_inputs(L_VAE_VHS, L_FPS_VHS),
                  [out("Filenames", "VHS_FILENAMES", [])]),
    ]

    new_links = [
        lnk(L_CKP_ADE,  1,     0,  N_ADE,  0, "MODEL"),
        lnk(L_CTX_ADE,  N_CTX, 0,  N_ADE,  1, "CONTEXT_OPTIONS"),
        lnk(L_ADE_KS,   N_ADE, 0,  N_KSAMP, 0, "MODEL"),
        lnk(L_CLIP_POS, 23,    0,  N_POS,  0, "CLIP"),
        lnk(L_CLIP_NEG, 23,    0,  N_NEG,  0, "CLIP"),
        lnk(L_POS_KS,   N_POS, 0,  N_KSAMP, 1, "CONDITIONING"),
        lnk(L_NEG_KS,   N_NEG, 0,  N_KSAMP, 2, "CONDITIONING"),
        lnk(L_LAT_KS,   N_LAT, 0,  N_KSAMP, 3, "LATENT"),
        lnk(L_KS_VAE,   N_KSAMP, 0, N_VAED, 0, "LATENT"),
        lnk(L_CKP_VAE,  1,     2,  N_VAED, 1, "VAE"),
        lnk(L_VAE_VHS,  N_VAED, 0, N_VHS,  0, "IMAGE"),
        lnk(L_FPS_VHS,  11,    0,  N_VHS,  3, "FLOAT"),
    ]

    # Update existing node output link lists
    node_by_id = {n["id"]: n for n in data["nodes"]}

    # Checkpoint MODEL output → add L_CKP_ADE
    node_by_id[1]["outputs"][0]["links"].append(L_CKP_ADE)
    # Checkpoint VAE output → add L_CKP_VAE
    node_by_id[1]["outputs"][2]["links"].append(L_CKP_VAE)
    # CLIPSetLastLayer CLIP output → add L_CLIP_POS, L_CLIP_NEG
    node_by_id[23]["outputs"][0]["links"] += [L_CLIP_POS, L_CLIP_NEG]
    # PrimitiveNode FPS → add L_FPS_VHS
    node_by_id[11]["outputs"][0]["links"].append(L_FPS_VHS)

    data["nodes"].extend(new_nodes)
    data["links"].extend(new_links)
    data["last_node_id"] = max(n["id"] for n in data["nodes"])
    data["last_link_id"] = max(l[0] for l in data["links"])

    data.setdefault("groups", []).append({
        "title": "ANIMATEDIFF PATH  ·  unmute to switch from Deforum  "
                 "·  requires AnimateDiff-Evolved + motion module",
        "bounding": [30, Y-20, 1420, 960],
        "color": "#445",
    })

    return data


def add_animatediff_flux_zturbo(data, ad_prefix, ckp_hint):
    """Flux Schnell / Z-Image Turbo: adds its own CheckpointLoaderSimple for AnimateDiff
    (Flux/Z-Turbo architectures have no native AnimateDiff motion modules).
    """

    # IDs — existing workflows end at node 34, link 33
    N_NOTE   = 35
    N_CKP    = 36   # CheckpointLoaderSimple (SDXL/SD1.5 for AnimateDiff)
    N_CTX    = 37   # ADE_AnimateDiffUniformContextOptions
    N_ADE    = 38   # ADE_AnimateDiffLoaderWithContext
    N_POS    = 39   # CLIPTextEncode positive
    N_NEG    = 40   # CLIPTextEncode negative
    N_LAT    = 41   # EmptyLatentImage
    N_KSAMP  = 42   # KSampler
    N_VAED   = 43   # VAEDecode
    N_VHS    = 44   # VHS_VideoCombine (AD output)

    # Link IDs — start at 34 (last used = 33)
    L_CKP_ADE  = 34
    L_CTX_ADE  = 35
    L_ADE_KS   = 36
    L_CLIP_POS = 37
    L_CLIP_NEG = 38
    L_POS_KS   = 39
    L_NEG_KS   = 40
    L_LAT_KS   = 41
    L_KS_VAE   = 42
    L_CKP_VAE  = 43
    L_VAE_VHS  = 44
    L_FPS_VHS  = 45

    Y = 1500

    SWITCH_TEXT = (
        "ANIMATEDIFF PATH  ·  All nodes below are MUTED by default\n"
        "\n"
        "⚠  Flux / Z-Image Turbo have no native AnimateDiff motion module.\n"
        "   This path uses a SEPARATE SD1.5 or SDXL checkpoint [id=" + str(N_CKP) + "].\n"
        "   Set that checkpoint's filename — the main Flux/Z-Turbo model is NOT used here.\n"
        "   Recommended: any SDXL base model (e.g. SDXL/sd_xl_base_1.0.safetensors)\n"
        "\n"
        "Required custom node: ComfyUI-AnimateDiff-Evolved\n"
        "Motion module goes in: models/animatediff_models/  (e.g. animatediff_sdxl_v10.ckpt)\n"
        "\n"
        "Controls: edit KSampler (steps / CFG / sampler / scheduler)\n"
        "          edit EmptyLatentImage batch_size for frame count\n"
        "\n"
        "TO SWITCH  Deforum → AnimateDiff:\n"
        "  1. Right-click DeforumSingleSampleNode [id=9]  → Mute Node\n"
        "  2. Right-click each node in this group → Remove Mute\n"
        "     (Checkpoint, ADE Context, ADE Loader, pos/neg CLIP, EmptyLatent, "
        "KSampler, VAEDecode, VHS)\n"
        "\n"
        "TO SWITCH BACK: mute all AD nodes; unmute id=9."
    )

    new_nodes = [
        note(N_NOTE, [50, Y], [1400, 250], 30, SWITCH_TEXT,
             "ANIMATEDIFF PATH  ·  muted by default  ·  needs separate SD/SDXL checkpoint"),

        # SDXL/SD1.5 checkpoint for AnimateDiff only
        make_node(N_CKP, "CheckpointLoaderSimple",
                  [50, Y+290], [360, 130], 31, M_MUTED,
                  "AnimateDiff checkpoint  ·  set to any SD1.5 or SDXL base model",
                  ["SDXL/sd_xl_turbo_1.0_fp16.safetensors"],
                  [],
                  [out("MODEL", "MODEL", [L_CKP_ADE], 0),
                   out("CLIP",  "CLIP",  [L_CLIP_POS, L_CLIP_NEG], 1),
                   out("VAE",   "VAE",   [L_CKP_VAE], 2)]),

        # Context window options
        make_node(N_CTX, "ADE_AnimateDiffUniformContextOptions",
                  [460, Y+290], [340, 160], 32, M_MUTED,
                  "Context window · length=16 overlap=4",
                  [16, 1, 4, False],
                  [],
                  [out("CONTEXT_OPTIONS", "CONTEXT_OPTIONS", [L_CTX_ADE])]),

        # ADE loader
        make_node(N_ADE, "ADE_AnimateDiffLoaderWithContext",
                  [850, Y+290], [440, 180], 33, M_MUTED,
                  "AnimateDiff loader  ·  set motion module filename",
                  ["animatediff_sdxl_v10.ckpt", "linear (AnimateDiff)"],
                  [inp("model",           "MODEL",           L_CKP_ADE),
                   inp("context_options", "CONTEXT_OPTIONS", L_CTX_ADE)],
                  [out("MODEL", "MODEL", [L_ADE_KS])]),

        # Positive prompt
        make_node(N_POS, "CLIPTextEncode",
                  [50, Y+510], [440, 130], 34, M_MUTED,
                  "Positive prompt (AnimateDiff)",
                  ["cinematic dreamscape, smooth flowing motion, volumetric light, "
                   "atmospheric depth, photorealistic, high detail"],
                  [inp("clip", "CLIP", L_CLIP_POS)],
                  [out("CONDITIONING", "CONDITIONING", [L_POS_KS])]),

        # Negative prompt
        make_node(N_NEG, "CLIPTextEncode",
                  [540, Y+510], [440, 130], 35, M_MUTED,
                  "Negative prompt (AnimateDiff)",
                  ["blurry, low quality, watermark, text, distorted, overexposed, static, flickering"],
                  [inp("clip", "CLIP", L_CLIP_NEG)],
                  [out("CONDITIONING", "CONDITIONING", [L_NEG_KS])]),

        # Empty latent
        make_node(N_LAT, "EmptyLatentImage",
                  [1030, Y+510], [270, 165], 36, M_MUTED,
                  "Latent frames  ·  batch_size = frame count",
                  [1024, 576, 24],
                  [],
                  [out("LATENT", "LATENT", [L_LAT_KS])]),

        # KSampler
        make_node(N_KSAMP, "KSampler",
                  [50, Y+690], [315, 270], 37, M_MUTED,
                  "AnimateDiff KSampler  ·  euler · karras · 20 steps · CFG 7",
                  [12345, "fixed", 20, 7.0, "euler", "karras", 1.0],
                  [inp("model",        "MODEL",        L_ADE_KS),
                   inp("positive",     "CONDITIONING", L_POS_KS),
                   inp("negative",     "CONDITIONING", L_NEG_KS),
                   inp("latent_image", "LATENT",       L_LAT_KS)],
                  [out("LATENT", "LATENT", [L_KS_VAE])]),

        # VAEDecode
        make_node(N_VAED, "VAEDecode",
                  [420, Y+690], [210, 130], 38, M_MUTED,
                  "",
                  [],
                  [inp("samples", "LATENT", L_KS_VAE),
                   inp("vae",     "VAE",    L_CKP_VAE)],
                  [out("IMAGE", "IMAGE", [L_VAE_VHS])]),

        # VHS output
        make_node(N_VHS, "VHS_VideoCombine",
                  [680, Y+690], [350, 340], 39, M_MUTED,
                  "AnimateDiff output",
                  vhs_combine_wv(ad_prefix),
                  vhs_combine_inputs(L_VAE_VHS, L_FPS_VHS),
                  [out("Filenames", "VHS_FILENAMES", [])]),
    ]

    new_links = [
        lnk(L_CKP_ADE,  N_CKP,   0, N_ADE,   0, "MODEL"),
        lnk(L_CTX_ADE,  N_CTX,   0, N_ADE,   1, "CONTEXT_OPTIONS"),
        lnk(L_ADE_KS,   N_ADE,   0, N_KSAMP, 0, "MODEL"),
        lnk(L_CLIP_POS, N_CKP,   1, N_POS,   0, "CLIP"),
        lnk(L_CLIP_NEG, N_CKP,   1, N_NEG,   0, "CLIP"),
        lnk(L_POS_KS,   N_POS,   0, N_KSAMP, 1, "CONDITIONING"),
        lnk(L_NEG_KS,   N_NEG,   0, N_KSAMP, 2, "CONDITIONING"),
        lnk(L_LAT_KS,   N_LAT,   0, N_KSAMP, 3, "LATENT"),
        lnk(L_KS_VAE,   N_KSAMP, 0, N_VAED,  0, "LATENT"),
        lnk(L_CKP_VAE,  N_CKP,   2, N_VAED,  1, "VAE"),
        lnk(L_VAE_VHS,  N_VAED,  0, N_VHS,   0, "IMAGE"),
        lnk(L_FPS_VHS,  11,      0, N_VHS,   3, "FLOAT"),
    ]

    node_by_id = {n["id"]: n for n in data["nodes"]}
    # PrimitiveNode FPS (id=11): add L_FPS_VHS to its output links
    node_by_id[11]["outputs"][0]["links"].append(L_FPS_VHS)

    data["nodes"].extend(new_nodes)
    data["links"].extend(new_links)
    data["last_node_id"] = max(n["id"] for n in data["nodes"])
    data["last_link_id"] = max(l[0] for l in data["links"])

    data.setdefault("groups", []).append({
        "title": "ANIMATEDIFF PATH  ·  requires separate SD/SDXL checkpoint + AnimateDiff-Evolved  "
                 "·  unmute to switch from Deforum",
        "bounding": [30, Y-20, 1500, 1060],
        "color": "#445",
    })

    return data


# ── process each workflow ─────────────────────────────────────────────────────

WORKFLOWS = [
    (
        "swarm/CustomWorkflows/deforum_video_sequencer_sdxl_turbo.json",
        "sdxl",
        None, None,
    ),
    (
        "swarm/CustomWorkflows/deforum_video_sequencer_flux_schnell.json",
        "flux",
        "animatediff_flux_ckpt",
        "SDXL/sd_xl_base_1.0.safetensors",
    ),
    (
        "swarm/CustomWorkflows/deforum_video_sequencer_z_image_turbo.json",
        "z_image_turbo",
        "animatediff_z_turbo_ckpt",
        "SDXL/sd_xl_base_1.0.safetensors",
    ),
]

for fpath, wtype, ad_prefix, ckp_hint in WORKFLOWS:
    with open(fpath) as f:
        data = json.load(f)

    if wtype == "sdxl":
        data = add_animatediff_sdxl(data)
    else:
        data = add_animatediff_flux_zturbo(data, ad_prefix, ckp_hint)

    with open(fpath, "w") as f:
        json.dump(data, f, indent=2)

    # sync root copy
    root_copy = fpath.replace("swarm/CustomWorkflows/", "")
    shutil.copy(fpath, root_copy)

    node_count = len(data["nodes"])
    link_count = len(data["links"])
    print(f"  {fpath.split('/')[-1]:55s}  nodes={node_count}  links={link_count}  "
          f"last_node_id={data['last_node_id']}  last_link_id={data['last_link_id']}")

print("\nDone — AnimateDiff path added to all three workflows.")
