"""Bounded local upload, Track 01 inference, and semantic repair preview."""

from __future__ import annotations

import base64
import json
import os
import sys
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

MAX_BYTES = 10 * 1024 * 1024
EXTENSIONS = {".dxf", ".pdf", ".png"}
DEFAULT_PIPELINE = Path(__file__).resolve().parents[2] / "01-industrial-electrical-bom"
app = FastAPI(title="图枢电析审图接口", version="1.0.0")


@lru_cache(maxsize=1)
def pipeline():
    root = Path(
        os.environ.get("ELECTRICAL_PIPELINE_DIR", str(DEFAULT_PIPELINE))
    ).resolve()
    if not (root / "benchmark_e2e" / "adapter.py").is_file():
        raise HTTPException(
            503, "请设置 ELECTRICAL_PIPELINE_DIR 指向 YOU-267 集成版的工业赛道目录。"
        )
    sys.path.insert(0, str(root))
    from benchmark_e2e.adapter import predict
    from compliance.engine import evaluate
    from compliance.repairs import apply_fix, bom_rows
    from compliance.topology import Drawing

    return predict, evaluate, apply_fix, bom_rows, Drawing


async def body_limited(request: Request) -> bytes:
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "单个图纸或工作副本须小于 10 MB。")
        payload.extend(chunk)
    if not payload:
        raise HTTPException(400, "未收到文件内容。")
    return bytes(payload)


async def json_limited(request: Request) -> dict:
    try:
        data = json.loads(await body_limited(request))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, "工作副本 JSON 无效。") from exc
    if not isinstance(data, dict):
        raise HTTPException(422, "工作副本结构无效。")
    doc = data.get("annotation")
    if not isinstance(doc, dict) or not isinstance(doc.get("instances"), list):
        raise HTTPException(422, "工作副本缺少器件列表。")
    if len(doc["instances"]) > 3000:
        raise HTTPException(422, "工作副本器件数量超过 3000。")
    return data


def clause_data():
    root = Path(
        os.environ.get("ELECTRICAL_PIPELINE_DIR", str(DEFAULT_PIPELINE))
    ).resolve()
    entries = json.loads(
        (root / "compliance" / "kb_data" / "clauses.json").read_text(encoding="utf-8")
    )
    if isinstance(entries, dict) and "clauses" in entries:
        entries = entries["clauses"]
    if isinstance(entries, list):
        return {clause["clause_id"]: clause for clause in entries}
    return entries


def _preview(path: Path, prediction: dict):
    import ezdxf
    import pymupdf
    from PIL import Image
    from symbol_parser.engine import _read_image
    from symbol_parser.vector import dxf_preview

    if path.suffix == ".dxf":
        output = dxf_preview(ezdxf.readfile(path))
        if output is None:
            raise ValueError("DXF 没有可渲染的图元")
        raster, project = output
        for item in prediction["annotation"]["instances"]:
            box = item.get("bbox_mm")
            if box:
                x, y, width, height = box
                item["bbox_px"] = list(project((x, -y - height, width, height)))
        image = Image.fromarray(raster)
    elif path.suffix == ".pdf":
        zoom = prediction["coordinate_space"]["raster_pixels_per_pdf_point"]
        with pymupdf.open(path) as document:
            preview = document[0].get_pixmap(
                matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY
            )
            image = Image.frombytes(
                "L", (preview.width, preview.height), preview.samples
            )
    else:
        raster, _ = _read_image(path)
        image = Image.fromarray(raster)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return (
        "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii"),
        image.width,
        image.height,
    )


def _infer(payload: bytes, filename: str):
    import pymupdf
    from ezdxf import DXFError
    from PIL import Image

    predict, evaluate, _apply_fix, bom_rows, Drawing = pipeline()
    suffix = Path(filename).suffix.lower()
    with TemporaryDirectory(prefix="review-drawing-") as staging:
        path = Path(staging) / ("drawing" + suffix)
        path.write_bytes(payload)
        if suffix == ".pdf":
            with pymupdf.open(path) as document:
                if len(document) != 1:
                    raise ValueError("当前工作台每次解析一页 PDF")
        if suffix == ".png":
            with Image.open(path) as image:
                if image.width * image.height > 16_000_000:
                    raise ValueError("PNG 像素超过当前工作台上限")
        try:
            prediction = predict(path)
            preview, width, height = _preview(path, prediction)
        except DXFError as exc:
            raise ValueError("无法读取 DXF 图元。") from exc
    annotation = prediction["annotation"]
    annotation.update(id="upload-" + sha256(payload).hexdigest()[:12], title=filename)
    annotation["sheet"].update(image_width=width, image_height=height)
    annotation["bom"], annotation["bom_summary"] = bom_rows(Drawing(annotation))
    return {
        "id": annotation["id"],
        "title": filename,
        "kind": "upload",
        "preview": preview,
        "width": width,
        "height": height,
        "annotation": annotation,
        "checks": evaluate(annotation),
        "clauses": clause_data(),
        "confidence": {
            item["id"]: item.get("confidence") for item in prediction["symbols"]
        },
        "elapsed_s": prediction["timing"]["total_s"],
        "channel": prediction["channel"],
    }


def _checks(data: dict, repair: bool):
    _predict, evaluate, apply_fix, bom_rows, Drawing = pipeline()
    annotation = data["annotation"]
    annotation["bom"], annotation["bom_summary"] = bom_rows(Drawing(annotation))
    checks = evaluate(annotation)
    if repair:
        requested = data.get("finding") or {}
        key = (requested.get("rule_id"), sorted(requested.get("instance_ids") or []))
        finding = next(
            (
                item
                for item in checks["findings"]
                if item["severity"] != "pass"
                and (item["rule_id"], sorted(item["instance_ids"])) == key
            ),
            None,
        )
        if not finding or not finding["fix_suggestion"]["operations"]:
            raise ValueError("当前版本没有可自动预览的修订。请重新体检。")
        annotation = apply_fix(annotation, finding["fix_suggestion"])
        checks = evaluate(annotation)
    return {"annotation": annotation, "checks": checks}


@app.get("/api/v1/electrical/health")
def health():
    pipeline()
    return {"status": "ok", "engine": "ElectroBench-JS"}


@app.post("/api/v1/electrical/parse")
async def parse(request: Request, filename: Annotated[str, Query(max_length=180)]):
    if Path(filename).suffix.lower() not in EXTENSIONS:
        raise HTTPException(415, "支持 DXF、单页 PDF 和 PNG。")
    payload = await body_limited(request)
    try:
        return await run_in_threadpool(_infer, payload, Path(filename).name)
    except (ValueError, OSError, RuntimeError) as exc:
        raise HTTPException(422, f"解析失败。{exc}") from exc


@app.post("/api/v1/electrical/check")
@app.post("/api/v1/electrical/repair")
async def check(request: Request):
    data = await json_limited(request)
    try:
        return await run_in_threadpool(
            _checks, data, request.url.path.endswith("/repair")
        )
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(422, f"无法更新工作副本。{exc}") from exc
