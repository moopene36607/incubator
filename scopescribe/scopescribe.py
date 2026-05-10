"""scopescribe — generate scope-of-loss narratives from claim data + photos.

Usage:
    python scopescribe.py samples/sample_input.json
    python scopescribe.py samples/sample_input.json --out report.md

Reads a single JSON file describing the claim, structure, photos (paths or
descriptions), and Xactimate line items, then produces a carrier-ready
narrative as markdown.

Requires ANTHROPIC_API_KEY in the environment.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096

SYSTEM_PROMPT = """You are a senior independent property insurance adjuster writing a formal Scope of Loss narrative for a residential claim. You write the way experienced field IAs write: passive voice where appropriate, technical, factual, never speculative. You cite damage by photo ID. You match Xactimate line items to physical findings. You never invent damage that is not in the source observations.

Output format — markdown, four required sections in this exact order:

# Scope of Loss Narrative

## 1. Cause of Loss
A factual paragraph identifying the peril, the date, and the meteorological / event evidence supporting causation. Cite the weather summary if provided. Do not editorialize. 4 to 6 sentences.

## 2. Methodology
A short paragraph describing how the inspection was conducted: elevations walked, roof access method (if implied), photo documentation, measurements per ANSI / IICRC norms. Use the elevations provided. 3 to 5 sentences. Skip this section if `include_methodology` is false.

## 3. Scope of Loss
The substantive section. Walk through the structure systematically — roof first (by slope or elevation), then exterior wall components (siding, gutters, fascia, windows, doors), then interior if any. For each affected component:
  - State the damage in technical terms (granule loss, mat fracture, mechanical impact, lateral displacement, etc.)
  - Cite supporting photos by ID (e.g., "Refer to Photo P-01")
  - Bridge to the Xactimate line item that addresses repair (cite by code, e.g., "Repair scope under RFG 240 with associated tear-off DMO RFG and disposal DMO HAUL")
  - State scope (replace vs repair) and reasoning when not obvious
Use bullet sub-points under bolded component headers. Be exhaustive over the photos and line items provided — every photo should be referenced and every nonzero line item should map to a finding.

## 4. Recommendation
One short paragraph stating the recommended disposition (covered loss subject to policy terms, recommended payment per estimate, any items requiring carrier review or additional documentation). 3 to 4 sentences. Skip this section if `include_recommendation` is false.

Voice rules:
- Use third person, past tense for observations ("Impacts were observed", not "I saw").
- No filler phrases ("It is important to note", "Furthermore"). Adjusters do not write that way.
- Measurements stay in the units provided (inches, LF, SQ, etc.).
- If a line item has quantity 0 or unit_price 0, do not invent damage to justify it — note it as "no associated finding" only if relevant, or omit entirely.
- Do not include a closing signature, contact info, or boilerplate.

Carrier tone variants:
- "neutral_technical" — default. Plain professional voice.
- "conservative" — extra hedging, qualifies all opinions, frequent reference to policy.
- "narrative" — slightly more prose, full sentences over bullets, used for carriers that prefer flowing reports.
"""


def encode_image(path: Path) -> dict[str, Any]:
    """Return an Anthropic-API image content block from a local file path."""
    suffix = path.suffix.lower().lstrip(".")
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(suffix)
    if not media_type:
        raise ValueError(f"Unsupported image type: {path}")
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def build_user_message(claim_data: dict[str, Any], input_dir: Path) -> list[dict[str, Any]]:
    """Build the user-message content blocks: claim/structure JSON, then photos, then line items."""
    blocks: list[dict[str, Any]] = []

    intro = {
        "claim": claim_data["claim"],
        "structure": claim_data["structure"],
        "options": claim_data.get("options", {}),
    }
    blocks.append({
        "type": "text",
        "text": "## Claim and structure context\n\n```json\n" + json.dumps(intro, indent=2) + "\n```",
    })

    blocks.append({"type": "text", "text": "## Field photo observations\n"})
    for photo in claim_data.get("photo_observations", []):
        header = f"\n### Photo {photo['id']} — {photo['location']}\n"
        blocks.append({"type": "text", "text": header})
        if "image_path" in photo:
            blocks.append(encode_image(input_dir / photo["image_path"]))
            if photo.get("description"):
                blocks.append({"type": "text", "text": f"Field note: {photo['description']}"})
        else:
            blocks.append({"type": "text", "text": photo.get("description", "(no description provided)")})

    blocks.append({
        "type": "text",
        "text": "## Xactimate line items\n\n```json\n"
                + json.dumps(claim_data.get("xactimate_line_items", []), indent=2)
                + "\n```",
    })

    blocks.append({
        "type": "text",
        "text": "Now produce the Scope of Loss narrative in the format and voice specified. "
                "Map every nonzero line item to a finding and cite every photo at least once.",
    })

    return blocks


def generate_narrative(input_path: Path) -> str:
    import anthropic

    claim_data = json.loads(input_path.read_text())
    user_blocks = build_user_message(claim_data, input_path.parent)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_blocks}],
    )

    return "".join(block.text for block in response.content if block.type == "text")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="Path to claim JSON input file")
    parser.add_argument("--out", type=Path, help="Write narrative to this file (default: stdout)")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("error: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2

    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2

    narrative = generate_narrative(args.input)

    if args.out:
        args.out.write_text(narrative)
        print(f"wrote {len(narrative)} chars to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(narrative)
        if not narrative.endswith("\n"):
            sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
