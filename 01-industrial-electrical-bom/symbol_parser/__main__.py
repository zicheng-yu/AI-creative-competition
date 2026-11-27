"""Parse DXF, PDF or scanned electrical drawings into a common JSON format."""

import json
import os
from argparse import ArgumentParser
from pathlib import Path
from urllib.parse import urlparse

from .engine import parse_drawing
from .raster import TiledYolo, read_ocr
from .refine import VisionRefiner


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--no-ocr", action="store_true", help="Skip optional Paddle OCR inference"
    )
    parser.add_argument(
        "--yolo-weights",
        type=Path,
        help="Use local electrical-symbol YOLO weights through SAHI",
    )
    parser.add_argument(
        "--pixels-per-mm",
        type=float,
        help="Explicit image scale for the geometry stencil",
    )
    parser.add_argument(
        "--vlm-url", help="Optional full OpenAI-compatible vision chat completions URL"
    )
    parser.add_argument(
        "--vlm-model", help="Vision model served by the configured endpoint"
    )
    parser.add_argument("--refine-limit", type=int, default=2)
    parser.add_argument("--yolo-confidence", type=float, default=0.30)
    args = parser.parse_args()
    if args.pixels_per_mm is not None and not 0.5 <= args.pixels_per_mm <= 20:
        parser.error("--pixels-per-mm must be between 0.5 and 20")
    if not 0 <= args.refine_limit <= 8:
        parser.error("--refine-limit must be between 0 and 8")
    refiner = None
    if args.vlm_url or args.vlm_model:
        if (
            not args.vlm_url
            or not args.vlm_model
            or urlparse(args.vlm_url).scheme not in {"https", "http"}
        ):
            parser.error("Vision refinement needs an explicit HTTP(S) URL and model")
        refiner = VisionRefiner(
            args.vlm_url, args.vlm_model, os.environ.get("SYMBOL_PARSER_VLM_TOKEN", "")
        )
    detector = (
        TiledYolo(args.yolo_weights, args.yolo_confidence)
        if args.yolo_weights
        else None
    )
    data = parse_drawing(
        args.drawing,
        ocr=None if args.no_ocr else read_ocr,
        detector=detector,
        refiner=refiner,
        refine_limit=args.refine_limit,
        pixels_per_mm=args.pixels_per_mm,
    )
    args.out.parent.mkdir(exist_ok=True, parents=True)
    args.out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
