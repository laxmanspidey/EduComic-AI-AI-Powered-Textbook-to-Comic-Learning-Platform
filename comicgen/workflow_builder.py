"""
ComfyUI workflow builder.
Builds the workflow JSON for Animagine XL image generation.
"""
import random
from django.conf import settings


def build_animagine_workflow(
    positive_prompt: str,
    negative_prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 25,
    cfg: float = 7.0,
    seed: int = None,
    checkpoint: str = None,
) -> dict:
    """
    Build a complete ComfyUI workflow JSON for Animagine XL.

    Nodes:
      1: CheckpointLoaderSimple
      2: CLIPTextEncode (positive)
      3: CLIPTextEncode (negative)
      4: EmptyLatentImage
      5: KSampler
      6: VAEDecode
      7: SaveImage

    Returns:
        ComfyUI workflow dict to POST to /prompt
    """
    if seed is None:
        seed = random.randint(0, 2**31 - 1)

    if checkpoint is None:
        checkpoint = getattr(settings, 'COMFYUI_CHECKPOINT', 'animagine-xl-4.0-opt.safetensors')

    workflow = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": checkpoint,
            },
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt,
                "clip": ["1", 1],
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["1", 1],
            },
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "karras",
                "denoise": 1.0,
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["5", 0],
                "vae": ["1", 2],
            },
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["6", 0],
                "filename_prefix": "comic_panel",
            },
        },
    }

    return workflow


def get_panel_dimensions(art_style: str = 'comic', panel_type: str = 'standard') -> tuple[int, int]:
    """
    Get optimal panel dimensions for Animagine XL.
    SDXL native resolution is 1024x1024, but landscape panels look better at 1216x832.
    """
    dimensions = {
        'wide': (1216, 832),       # landscape panels
        'tall': (832, 1216),       # portrait panels
        'standard': (1024, 1024),  # square panels
        'banner': (1344, 768),     # wide banner panels
    }
    return dimensions.get(panel_type, (1024, 1024))
