# Image Generation Pipeline

This guide explains how to generate the Rivergate image set from the manifest in `docs/image_manifest.md`.

## Prerequisites

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Export your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="..."
   ```

## Usage

### Dry run

Preview what would be generated (no API calls):

```bash
python scripts/generate_images.py --dry-run
```

### Generate all images

```bash
python scripts/generate_images.py
```

### Force overwriting existing generated images

The script refuses to run if it detects that placeholder SVGs have already been replaced. Use `--force` to override:

```bash
python scripts/generate_images.py --force
```

### Regenerate a single image

Provide a full manifest path or just the filename:

```bash
python scripts/generate_images.py --only scenarios/lepto_rivergate/assets/ward_northbend_hero.svg
# or
python scripts/generate_images.py --only ward_northbend_hero.svg
```

## Manifest assumptions

- The script reads the Markdown table under **Image Table** in `docs/image_manifest.md`.
- It expects a column named **Path/Filename**, plus **Generation Prompt**, **Negative/Avoid**, and **Size (WxH)**.
- If **Size (WxH)** is blank, the script falls back to the placeholder SVG's `width`/`height` attributes or `viewBox`.
- Images are written to the exact path in the manifest. When the manifest uses `.svg` filenames, the generated raster output is still written to that path, replacing the SVG placeholder.

## Output verification

- Generated images are validated against the requested dimensions.
- A summary is logged with generated, skipped (dry run), and failed counts.
