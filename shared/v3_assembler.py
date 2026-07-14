"""V3 processor assembler.

Converts a validated V3 config dict into the processor pipeline JSON that the
V3 watermark filter expects.
"""

from __future__ import annotations

from typing import Any


def v3_config_to_processors(config_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a single-node processor list for the V3 watermark pipeline.

    The V3 WatermarkV3Filter expects:
        {"processor_name": "v3_watermark", "v3_config": <full config dict>}

    Margins, rounded corners, etc. that were separate processors in V2 are
    folded into the canvas config inside v3_config, so no extra pipeline
    nodes are needed.
    """
    if not config_dict:
        return []
    return [{"processor_name": "v3_watermark", "v3_config": config_dict}]
