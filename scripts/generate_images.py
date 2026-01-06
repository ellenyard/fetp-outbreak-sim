#!/usr/bin/env python3
import argparse
import base64
import os
import re
import sys
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, Iterable, List, Optional, Tuple

from openai import OpenAI
from PIL import Image


MANIFEST_PATH = os.path.join("docs", "image_manifest.md")


@dataclass
class ManifestRow:
    path: str
    prompt: str
    negative: str
    size_text: str


@dataclass
class GenerationResult:
    path: str
    status: str
    message: str


SIZE_PATTERN = re.compile(r"(\d+)\s*x\s*(\d+)")
SVG_SIZE_PATTERN = re.compile(
    r"width=\"(?P<width>\d+)\"\s+height=\"(?P<height>\d+)\""
)
VIEWBOX_PATTERN = re.compile(r"viewBox=\"[\d.]+\s+[\d.]+\s+(\d+)\s+(\d+)\"")


def parse_manifest(path: str) -> List[ManifestRow]:
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()

    header_index = None
    for idx, line in enumerate(lines):
        if line.strip().startswith("| Path/Filename "):
            header_index = idx
            break

    if header_index is None:
        raise ValueError(f"Could not find table header in {path}")

    headers = [h.strip() for h in lines[header_index].strip().strip("|").split("|")]
    rows: List[ManifestRow] = []

    for line in lines[header_index + 2 :]:
        if not line.strip().startswith("|"):
            break
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < len(headers):
            parts.extend([""] * (len(headers) - len(parts)))
        row = dict(zip(headers, parts))
        path_value = row.get("Path/Filename", "")
        if not path_value:
            continue
        rows.append(
            ManifestRow(
                path=path_value,
                prompt=row.get("Generation Prompt", ""),
                negative=row.get("Negative/Avoid", ""),
                size_text=row.get("Size (WxH)", ""),
            )
        )

    return rows


def parse_size(size_text: str) -> Optional[Tuple[int, int]]:
    if not size_text:
        return None
    match = SIZE_PATTERN.search(size_text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def parse_svg_placeholder_size(path: str) -> Optional[Tuple[int, int]]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read(4096)
    except FileNotFoundError:
        return None

    match = SVG_SIZE_PATTERN.search(content)
    if match:
        return int(match.group("width")), int(match.group("height"))

    viewbox = VIEWBOX_PATTERN.search(content)
    if viewbox:
        return int(viewbox.group(1)), int(viewbox.group(2))

    return None


def is_svg_placeholder(path: str) -> bool:
    try:
        with open(path, "rb") as handle:
            snippet = handle.read(256)
    except FileNotFoundError:
        return True

    text = snippet.decode("utf-8", errors="ignore").lstrip()
    return text.startswith("<svg") or text.startswith("<?xml")


def resolve_target_size(row: ManifestRow) -> Tuple[int, int]:
    parsed = parse_size(row.size_text)
    if parsed:
        return parsed

    fallback = parse_svg_placeholder_size(row.path)
    if fallback:
        return fallback

    raise ValueError(f"No size specified and placeholder size missing for {row.path}")


def load_image_bytes(prompt: str, negative: str, size: Tuple[int, int]) -> bytes:
    client = OpenAI()
    request: Dict[str, object] = {
        "model": "gpt-image-1",
        "prompt": prompt,
        "size": f"{size[0]}x{size[1]}",
        "n": 1,
        "response_format": "b64_json",
    }
    if negative:
        request["negative_prompt"] = negative
    response = client.images.generate(**request)
    image_b64 = response.data[0].b64_json
    if not image_b64:
        raise RuntimeError("No image data returned from API")
    return base64.b64decode(image_b64)


def verify_dimensions(image_bytes: bytes, expected: Tuple[int, int]) -> None:
    with Image.open(BytesIO(image_bytes)) as image:
        if image.size != expected:
            raise ValueError(
                f"Generated image size {image.size} does not match expected {expected}"
            )


def write_image(path: str, image_bytes: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(image_bytes)


def format_plan(rows: Iterable[ManifestRow]) -> None:
    for row in rows:
        size = parse_size(row.size_text)
        size_text = f"{size[0]}x{size[1]}" if size else "(from placeholder)"
        print(f"- {row.path}: {size_text}")


def guard_against_replaced(rows: Iterable[ManifestRow], force: bool) -> None:
    replaced = [row.path for row in rows if os.path.exists(row.path) and not is_svg_placeholder(row.path)]
    if replaced and not force:
        sample = "\n".join(f"  - {path}" for path in replaced[:5])
        raise RuntimeError(
            "Refusing to run because placeholder images appear to be replaced. "
            "Re-run with --force to overwrite.\n"
            f"Detected non-placeholder files:\n{sample}"
        )


def generate_images(rows: Iterable[ManifestRow], dry_run: bool) -> List[GenerationResult]:
    results: List[GenerationResult] = []
    for row in rows:
        try:
            target_size = resolve_target_size(row)
        except ValueError as exc:
            results.append(GenerationResult(row.path, "failed", str(exc)))
            continue

        if dry_run:
            results.append(
                GenerationResult(
                    row.path,
                    "skipped",
                    f"Dry-run would generate {target_size[0]}x{target_size[1]}",
                )
            )
            continue

        try:
            image_bytes = load_image_bytes(row.prompt, row.negative, target_size)
            verify_dimensions(image_bytes, target_size)
            write_image(row.path, image_bytes)
            results.append(GenerationResult(row.path, "generated", "ok"))
        except Exception as exc:
            results.append(GenerationResult(row.path, "failed", str(exc)))
    return results


def filter_rows(rows: List[ManifestRow], only: Optional[str]) -> List[ManifestRow]:
    if not only:
        return rows
    matches = [
        row
        for row in rows
        if row.path == only or os.path.basename(row.path) == only
    ]
    if not matches:
        raise ValueError(f"No manifest rows match '{only}'")
    return matches


def summarize(results: List[GenerationResult]) -> None:
    totals = {"generated": 0, "skipped": 0, "failed": 0}
    for result in results:
        totals[result.status] = totals.get(result.status, 0) + 1
    print("\nSummary:")
    for status in ("generated", "skipped", "failed"):
        print(f"- {status}: {totals.get(status, 0)}")
    failures = [result for result in results if result.status == "failed"]
    if failures:
        print("\nFailures:")
        for result in failures:
            print(f"- {result.path}: {result.message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate images from image_manifest.md")
    parser.add_argument(
        "--manifest",
        default=MANIFEST_PATH,
        help="Path to docs/image_manifest.md",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without generating images",
    )
    parser.add_argument(
        "--only",
        help="Generate a single image by filename or manifest path",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite already-generated images",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = parse_manifest(args.manifest)
    rows = filter_rows(rows, args.only)

    guard_against_replaced(rows, args.force)

    if args.dry_run:
        print("Dry-run plan:")
        format_plan(rows)

    results = generate_images(rows, dry_run=args.dry_run)
    summarize(results)

    if any(result.status == "failed" for result in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
