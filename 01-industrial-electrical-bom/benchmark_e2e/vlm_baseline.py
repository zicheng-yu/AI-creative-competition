"""Optional, separately generated OpenAI-compatible vision predictions."""

from abc import ABC, abstractmethod
import argparse
import base64
import json
import os
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image

from electrobench.catalog import BY_CODE

PENDING = "pending_vlm_api_key"
PROMPT = """Transcribe visible electrical drawing evidence as JSON only. Return an object with
symbols [{id,class_code,tag,bbox_px:[left,top,width,height],specs:{spec,model}}],
edges [{source,target,kind}], bom_items [{class_code,tag,model,spec,qty,unit,instance_ids}],
and findings [{rule_id,severity,instance_ids}]. Use pixel coordinates in the supplied image.
Use the component classes {codes}. Use one unique string id per symbol. Edge kind is power,
control, branch or pe. Include only models and specs identifiable from the drawing.
For compliance report observed red findings with rule identifiers selectivity_inversion,
ampacity_insufficient, motor_protection_missing or interlock_missing. Return empty arrays
where no item was found. Use no sample identifiers and do not guess unprinted values."""


class BaseVLMBaseline(ABC):
    """TODO(zicheng): plug in VLM provider."""

    @abstractmethod
    def predict(self, path: Path) -> dict:
        """Accept a single PNG and return the structured observations."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OpenAICompatibleVision(BaseVLMBaseline):
    def __init__(self, endpoint, model, token, *, timeout=120):
        parsed = urlparse(endpoint)
        if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("invalid VLM endpoint")
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("remote VLM endpoints require HTTPS")
        if not model or not token:
            raise ValueError("missing VLM model or token")
        self.endpoint = endpoint
        self.model = model
        self._token = token
        self.timeout = timeout

    @classmethod
    def from_environment(cls):
        endpoint = os.environ.get("TRACK01_VLM_ENDPOINT")
        model = os.environ.get("TRACK01_VLM_MODEL")
        token = os.environ.get("TRACK01_VLM_TOKEN")
        if not all((endpoint, model, token)):
            return None
        return cls(endpoint, model, token)

    def predict(self, path):
        from .adapter import source_only

        if Path(path).suffix.lower() != ".png":
            raise ValueError("B3 uses the same original PNG as B1/B2")
        with source_only(path) as asset:
            content = base64.b64encode(asset.read_bytes()).decode("ascii")
            with Image.open(asset) as raster:
                width, height = raster.size
        request = Request(
            self.endpoint, method="POST",
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self._token},
            data=json.dumps({
                "model": self.model, "temperature": 0, "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": PROMPT.replace("{codes}", ", ".join(BY_CODE))},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + content}},
                ]}],
            }).encode("utf-8"),
        )
        with build_opener(_NoRedirect()).open(request, timeout=self.timeout) as response:
            reply = json.load(response)
        observations = json.loads(reply["choices"][0]["message"]["content"])
        return observations | {"image_width": width, "image_height": height}


def load_predictions(path):
    if path is None:
        return {"status": PENDING, "predictions": {}}
    from .adapter import SCORING_FILES

    path = Path(path)
    if path.name.lower() in SCORING_FILES or path.resolve().name.lower() in SCORING_FILES:
        raise ValueError("reference files cannot be loaded as VLM predictions")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0.0" or not isinstance(data.get("predictions"), list):
        raise ValueError("expected a 1.0.0 VLM predictions list")
    rows = {}
    for entry in data["predictions"]:
        identifier = entry["drawing_id"]
        if identifier in rows:
            raise ValueError(f"repeated VLM drawing id: {identifier}")
        rows[identifier] = entry
    if not rows:
        raise ValueError("VLM predictions file is empty")
    return {"status": "scored_predictions", "predictions": rows}


def to_prediction(row, source):
    with Image.open(source) as asset:
        width, height = asset.size
    if (row["image_width"], row["image_height"]) != (width, height):
        raise ValueError("VLM boxes must refer to the original PNG dimensions")
    symbols = []
    ids = set()
    for item in row["symbols"]:
        node = item["id"]
        if not isinstance(node, str) or not node or node in ids:
            raise ValueError("invalid or repeated VLM symbol id")
        ids.add(node)
        x, y, w, h = item["bbox_px"]
        if not (0 <= x < width and 0 <= y < height and 0 < w <= width-x and 0 < h <= height-y):
            raise ValueError("VLM symbol bbox must lie inside the original PNG")
        symbols.append({"id": node, "class_code": item["class_code"], "tag": item.get("tag", ""),
                        "specs": item.get("specs", {}), "bbox_top_left": [x,y,w,h]})
    edges = row["edges"]
    if any(e["source"] not in ids or e["target"] not in ids for e in edges):
        raise ValueError("VLM edge references an unknown instance")
    items = []
    for item in row["bom_items"]:
        qty = item["qty"]
        if not isinstance(qty, int) or qty < 1 or any(n not in ids for n in item.get("instance_ids", [])):
            raise ValueError("invalid VLM BOM item")
        items.append({k: item.get(k, "") for k in ("class_code","tag","spec","model","unit")} |
                     {"qty": qty, "anchors": [{"instance_id": i} for i in item.get("instance_ids", [])]})
    findings = row["findings"]
    if any(not set(f["instance_ids"]) <= ids for f in findings):
        raise ValueError("VLM finding references an unknown instance")
    for item in findings:
        item.setdefault("severity", "error")
    elapsed = row.get("seconds")
    if elapsed is not None and not 0 <= elapsed < float("inf"):
        raise ValueError("invalid VLM elapsed duration")
    return {"channel": "vlm-png", "coordinate_space": {"width": width, "height": height},
            "symbols": symbols, "graph": {"edges": edges}, "bom": {"items": items, "summary": items},
            "compliance": {"findings": findings, "counts": {"error": sum(
                f["severity"] == "error" for f in findings)}}, "warnings": [],
            "timing": {"parse_s": elapsed, "topology_s": 0., "compliance_s": 0., "total_s": elapsed}
            if elapsed is not None else None}


def main():
    from .baselines import originals

    cli = argparse.ArgumentParser(description="Explicitly request B3 predictions from the configured endpoint.")
    cli.add_argument("--samples", type=Path, default=Path(__file__).resolve().parents[1] / "samples")
    cli.add_argument("--out", type=Path, required=True)
    options = cli.parse_args()
    provider = OpenAICompatibleVision.from_environment()
    if provider is None:
        cli.exit(1, PENDING + "\n")
    rows = []
    for directory in sorted(options.samples.glob("*/*")):
        asset = originals(directory).get("png")
        if asset:
            started = perf_counter()
            observations = provider.predict(asset)
            rows.append(observations | {"drawing_id": directory.name, "seconds": perf_counter()-started})
    options.out.write_text(json.dumps({"schema_version": "1.0.0", "predictions": rows},
                                      ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
