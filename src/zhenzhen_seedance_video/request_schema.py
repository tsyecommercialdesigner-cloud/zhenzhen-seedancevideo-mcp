"""Discoverable union of supported inputs; model-specific checks remain server-side."""

from typing import Annotated

from pydantic import Field

MEDIA = {
    "description": "HTTP(S) URL or managed local input with an absolute local_path.",
    "anyOf": [
        {"type": "string"},
        {
            "type": "object",
            "properties": {"local_path": {"type": "string"}},
            "required": ["local_path"],
            "additionalProperties": False,
        },
    ],
}
CONTENT = {
    "type": "array",
    "description": "Ordered image_url, video_url or audio_url items, each with nested url.",
    "items": {
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "type": {"const": name},
                    name: {
                        "type": "object",
                        "properties": {"url": MEDIA},
                        "required": ["url"],
                        "additionalProperties": False,
                    },
                },
                "required": ["type", name],
                "additionalProperties": False,
            }
            for name in ("image_url", "video_url", "audio_url")
        ]
    },
}
METADATA = {
    "type": "object",
    "properties": {
        "resolution": {"type": "string", "description": "Allowed values depend on model."},
        "ratio": {"type": "string", "description": "Allowed values depend on model."},
        "generate_audio": {
            "type": "boolean",
            "description": "Normal generation defaults to true; not applicable to final/upscale.",
        },
        "duration": {"type": "number", "description": "-1 selects automatic duration."},
        "seed": {"type": "number"},
        "return_last_frame": {"type": "boolean"},
        "draft": {"type": "boolean"},
        "draft_task_id": {"type": "string"},
        "output_format": {"type": "string", "enum": ["mp4", "mov"]},
        "omni_reference_task_type": {
            "type": "string",
            "enum": ["edit", "reference", "extend", "auto"],
        },
        "content": CONTENT,
    },
    "additionalProperties": False,
}
REQUEST_SCHEMA = {
    "description": (
        "Model-specific fields differ; call get_capabilities with api_id and model_id. "
        "Regular generation requires prompt; draft-to-video requires metadata.draft_task_id. "
        "Upscaling requires one video in metadata.content and no prompt."
    ),
    "properties": {
        "model": {"type": "string", "description": "Supplier model ID; not model_id."},
        "prompt": {"type": "string", "description": "Required for normal generation."},
        "seconds": {"type": "string", "description": "Integer string; e.g. '4'."},
        "images": {"type": "array", "items": MEDIA},
        "metadata": METADATA,
        "enhance_prompt": {
            "type": "boolean",
            "description": "Initial default false; omitted value can follow shared authorization.",
        },
    },
    "required": ["model"],
    "additionalProperties": False,
}
VideoRequest = Annotated[dict, Field(json_schema_extra=REQUEST_SCHEMA)]
