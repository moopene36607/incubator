# scopescribe

**AI scope-of-loss narrative generator for independent insurance adjusters.**

Turn damage photos + Xactimate line items into a polished, carrier-ready report narrative in under 30 seconds.

---

## The pain

Independent (1099) property adjusters in the US — there are about 120,000 of them — get paid per claim. After every catastrophe deployment (hurricane, hail, wildfire, flood) they have to write a detailed report for the carrier:

- Cause of loss
- Scope of loss
- Methodology
- Per-room / per-elevation findings

Most adjusters spend **3–4 hours per claim** on the narrative sections alone. That's not the inspection or the Xactimate sketch — that's the *writing*. It's the same boilerplate every time, but it has to sound custom and match each carrier's tone.

> "Half of every report is just writing the narrative. It's the same boilerplate every time but it has to sound custom. I lose two claims a week to slow turnaround."

Per-claim income model means **every saved hour is direct income**. A tool that turns 4 hours of writing into 15 minutes of editing pays for itself on claim #1.

## Why no one has built this yet

| Existing tool   | What it does                       | Why it doesn't solve the narrative problem |
|-----------------|------------------------------------|---------------------------------------------|
| Xactimate       | Estimating + line-item pricing     | No narrative writer. Boilerplate templates only. |
| ClaimWizard     | Workflow / claim tracking          | Doesn't generate report text. |
| BuildArray      | Field data capture                 | Photo organization, not writing. |
| Claim Titan     | Carrier-side AI                    | Targets carriers, not field IAs. |

The independent adjuster segment is too small + too geographically scattered for a VC-backed company to chase. Perfect for a focused tool.

## What scopescribe does

```
photos/ + line_items.json + claim metadata
            │
            ▼
   Claude vision + writing
            │
            ▼
   Professional narrative ready for the carrier
```

1. **Vision pass** — Claude looks at each damage photo and produces field observations: damage type, materials affected, severity, position.
2. **Synthesis pass** — Claude combines observations + Xactimate line items + claim context (storm date, address, coverage type) into a coherent narrative with the four standard sections every carrier expects.
3. **Tone match** — The writing matches an adjuster's voice (passive, technical, precise) — not LLM-flavored prose.

Output is plain markdown / text, ready to paste into the adjuster's report template.

## Quick demo (no API key needed)

A pre-generated example is in `examples/sample_output.md` — that's the actual narrative produced from the synthetic input in `samples/sample_input.json`.

## Run it yourself

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python scopescribe.py samples/sample_input.json
```

The input file is a single JSON document — see `samples/sample_input.json` for the shape. Photos can be local file paths *or* text descriptions (the prototype accepts either; descriptions are useful when running the demo without real images).

## What's in the prototype

- `scopescribe.py` — single-file CLI
- `samples/sample_input.json` — synthetic Texas hail claim, 3 photo descriptions, 12 Xactimate line items
- `examples/sample_output.md` — generated narrative (commit-checked so you can read it without running anything)
- `requirements.txt`

Total: ~250 lines of Python.

## What a real product would add (not in prototype)

- Direct Xactimate `.esx` import (parse line items from sketches)
- Carrier-specific tone templates (USAA reads differently than Allstate)
- Photo metadata extraction (EXIF date/GPS for chain-of-custody)
- Re-inspection diff mode (compare two visits)
- Team plan with shared phrase library
- Pay-per-report billing ($15/report) aligned with adjuster income model

## Pricing hypothesis

- $79/month flat (unlimited reports, one user)
- $149/month for teams (up to 5 adjusters)
- $15 per report pay-as-you-go for occasional users

500 paying users at $79 = $40K MRR. Catastrophe season demand alone could fill that.

## Distribution

Independent adjusters cluster in:
- AdjusterTV / AdjusterPro communities
- Catastrophe deployment Facebook groups (active during storm season)
- IA firm rosters (Eberl, Pilot, Worley) — partner channel
- Reddit r/Insurance, r/Adjusters

A 90-second screen recording showing "4 hours of writing → 15 minutes of editing" is the entire marketing motion.

---

Generated 2026-05-10 as the first prototype in this incubator.
