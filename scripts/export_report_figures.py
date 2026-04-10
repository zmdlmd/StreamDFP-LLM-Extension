#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import cairosvg


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HTML = ROOT / "docs" / "reports" / "report_figures_frontend_20260409.html"
DEFAULT_OUTPUT = ROOT / "docs" / "reports" / "frontend_exports"
MANIFEST = "manifest.json"


def run_svg_export(html_path: Path, output_dir: Path) -> list[dict[str, str]]:
    subprocess.run(
        ["node", str(ROOT / "scripts" / "export_report_svgs.js"), str(html_path), str(output_dir)],
        check=True,
    )
    manifest_path = output_dir / MANIFEST
    return json.loads(manifest_path.read_text())


def convert_svgs_to_png(manifest: list[dict[str, str]], scale: float) -> list[Path]:
    png_paths: list[Path] = []
    for item in manifest:
        svg_path = Path(item["svg"])
        png_path = svg_path.with_suffix(".png")
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(png_path),
            scale=scale,
            background_color="white",
        )
        png_paths.append(png_path)
    return png_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export report figures from frontend HTML to SVG and PNG.")
    parser.add_argument(
        "--html",
        type=Path,
        default=DEFAULT_HTML,
        help="Path to the frontend report-figure HTML page.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory where exported SVG/PNG files should be written.",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=2.0,
        help="PNG scale factor passed to cairosvg.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    html_path = args.html.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = run_svg_export(html_path, output_dir)
    png_paths = convert_svgs_to_png(manifest, scale=args.scale)

    print("\nPNG exports:")
    for png_path in png_paths:
      print(png_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
