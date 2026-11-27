"""Use stencil geometry or an explicit tiled YOLO model for visual detection."""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from .labels import CLASSES, Component, TextMark, prefix_of, split_tag, tag_distance

cv2.setNumThreads(2)


def intersection_over_union(a, b):
    l, t = max(a[0], b[0]), max(a[1], b[1])
    r, d = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    inter = max(0, r - l) * max(0, d - t)
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union else 0.0


@lru_cache(maxsize=1)
def _ocr():
    from rapidocr import RapidOCR

    return RapidOCR(
        params={
            "Global.text_score": 0.38,
            "Global.max_side_len": 2800,
            "Det.limit_side_len": 1920,
            "Det.limit_type": "max",
            "EngineConfig.onnxruntime.intra_op_num_threads": 2,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        }
    )


def read_ocr(image) -> list[TextMark]:
    from .vector import polygon_box

    result = _ocr()(
        cv2.cvtColor(image, cv2.COLOR_GRAY2BGR),
        use_det=True,
        use_rec=True,
        use_cls=False,
    )
    if result.boxes is None:
        return []
    return [
        TextMark(text.strip(), polygon_box(box), float(score))
        for text, box, score in zip(
            result.txts, result.boxes, result.scores, strict=True
        )
        if text.strip()
    ]


def read_spec_line(image, rectangle):
    x, y, xx, yy = rectangle
    x, y = max(0, round(float(x))), max(0, round(float(y)))
    xx, yy = (
        min(image.shape[1], round(float(xx))),
        min(image.shape[0], round(float(yy))),
    )
    if xx - x < 5 or yy - y < 4:
        return None
    crop = image[y:yy, x:xx]
    # Trim unused width before line recognition. A wide padded crop can leave
    # the complete label too small after recognizer resizing.
    ink = (crop < 155).sum(axis=0)
    columns = np.flatnonzero(ink)
    if len(columns) < 5:
        return None
    left, right = max(0, int(columns[0]) - 2), min(crop.shape[1], int(columns[-1]) + 3)
    crop = cv2.resize(
        crop[:, left:right], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC
    )
    result = _ocr()(
        cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR),
        use_det=False,
        use_rec=True,
        use_cls=False,
    )
    if not result.txts:
        return None
    text, score = result.txts[0].strip(), float(result.scores[0])
    if not text or score < 0.76:
        return None
    return TextMark(
        text, (float(x + left), float(y), float(right - left), float(yy - y)), score
    )


def _turn(x, y, angle):
    return (-y, x) if angle == 90 else (x, y)


@lru_cache(maxsize=256)
def _stencil(code: str, scale: float, angle: int):
    definition = CLASSES[code]
    left, bottom, right, top = definition["bbox"]
    corners = [_turn(x, y, angle) for x in (left, right) for y in (bottom, top)]
    left, top = min(x for x, _ in corners), max(y for _, y in corners)
    right, bottom = max(x for x, _ in corners), min(y for _, y in corners)
    pad = 3
    w, h = (right - left) * scale, (top - bottom) * scale
    mask = np.zeros((round(h) + 2 * pad + 1, round(w) + 2 * pad + 1), np.uint8)
    thickness = max(1, round(scale * 0.27))

    def position(x, y):
        x, y = _turn(x, y, angle)
        return round((x - left) * scale) + pad, round((top - y) * scale) + pad

    def polyline(points, close=False):
        contour = np.asarray([position(x, y) for x, y in points], dtype=np.int32)
        cv2.polylines(mask, [contour], close, 255, thickness)

    for typ, *args in definition["strokes"]:
        if typ == "L":
            x, y, xx, yy = args
            polyline(((x, y), (xx, yy)))
        elif typ == "R":
            x, y, rw, rh = args
            polyline(((x, y), (x + rw, y), (x + rw, y + rh), (x, y + rh)), close=True)
        elif typ == "C":
            x, y, r = args
            cv2.circle(mask, position(x, y), max(1, round(r * scale)), 255, thickness)
        elif typ == "P":
            polyline(args[0])
        elif typ == "T":
            # Internal characters help separate similar outlines, e.g. A/V/Wh.
            word, x, y, height = args
            if word.isascii() and angle == 0:
                cv2.putText(
                    mask,
                    word,
                    position(x, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    height * scale / 30,
                    150,
                    1,
                    cv2.LINE_8,
                )
    weights = mask.astype(np.float32) / 255
    norm = weights.sum()
    if norm == 0:
        return None
    weights /= norm
    quiet = np.zeros_like(mask)
    quiet[pad + 2 : -pad - 2, pad + 2 : -pad - 2] = 255
    exclusion = cv2.dilate(mask, np.ones((5, 5), np.uint8))
    background = ((quiet > 0) & (exclusion == 0)).astype(np.float32)
    background /= max(1, background.sum())
    relative_ports = {name: position(*xy) for name, xy in definition["ports"].items()}
    return weights, background, (float(pad), float(pad), w, h), relative_ports


def _candidate(code, box, ports, score, mark=None, parsed=None):
    x, y, _, _ = box
    result = Component(
        code,
        box,
        {name: (x + px - 3, y + py - 3) for name, (px, py) in ports.items()},
        float(np.clip(score, 0, 0.98)),
        "visual-stencil",
    )
    if mark is not None:
        result.tag = parsed[1]
        result.spec = parsed[2]
        result.label_anchor = mark
        result.bindings["tag"] = mark
        if result.spec:
            result.bindings["spec"] = mark
    return result


def proposals(image, marks, scale):
    ink = (image < 185).astype(np.uint8)
    distance = cv2.distanceTransform(1 - ink, cv2.DIST_L2, 3)
    field = np.exp(-distance / max(1.15, scale * 0.38)).astype(np.float32)
    known = defaultdict(list)
    for index, mark in enumerate(marks):
        if parsed := split_tag(mark.text):
            known[parsed[0]].append((index, mark, parsed))
    candidates, orphans = defaultdict(list), []
    foreground = ink.astype(np.float32)
    for code, definition in CLASSES.items():
        if not definition["strokes"]:
            continue
        for angle in (0, 90) if code == "FU" else (0,):
            template = _stencil(code, round(scale, 3), angle)
            if template is None:
                continue
            weights, background, (_, _, width, height), ports = template
            th, tw = weights.shape
            if th >= field.shape[0] or tw >= field.shape[1]:
                continue
            shape = cv2.matchTemplate(field, weights, cv2.TM_CCORR)
            shape -= 0.58 * cv2.matchTemplate(foreground, background, cv2.TM_CCORR)

            for index, mark, parsed in known[prefix_of(code)]:
                mx, my, mw, mh = mark.bbox
                radius = scale * 14
                x0 = max(0, int(mx - radius - tw))
                y0 = max(0, int(my - radius - th))
                x1 = min(shape.shape[1], int(mx + mw + radius))
                y1 = min(shape.shape[0], int(my + mh + radius))
                box = shape[y0:y1, x0:x1]
                if not box.size:
                    continue
                _, peaks = cv2.threshold(box, 0.45, 0, cv2.THRESH_TOZERO)
                ys, xs = np.where(
                    (peaks > 0)
                    & (peaks == cv2.dilate(peaks, np.ones((7, 7), np.uint8)))
                )
                scored = []
                for x, y in zip(xs, ys, strict=True):
                    ix, iy = float(x + x0), float(y + y0)
                    dist = tag_distance((ix + 3, iy + 3, width, height), mark) / scale
                    if dist < 10:
                        score = float(box[y, x])
                        scored.append((score - dist * 0.045, score, ix, iy))
                if scored:
                    rank, score, x, y = max(scored)
                    if rank >= 0.40:
                        candidates[index].append(
                            (
                                rank,
                                _candidate(
                                    code,
                                    (x + 3, y + 3, width, height),
                                    ports,
                                    score,
                                    mark,
                                    parsed,
                                ),
                            )
                        )

            # Unlabelled contacts, earth points and other strong glyphs can be
            # recovered geometrically. A high threshold rejects incidental lines.
            peak = cv2.dilate(shape, np.ones((13, 13), np.uint8))
            ys, xs = np.where((shape >= 0.86) & (shape == peak))
            order = sorted(
                zip(xs, ys, strict=True), key=lambda xy: -shape[xy[1], xy[0]]
            )[:32]
            for x, y in order:
                score = float(shape[y, x])
                orphans.append(
                    (
                        score,
                        _candidate(
                            code,
                            (float(x) + 3, float(y) + 3, width, height),
                            ports,
                            score,
                        ),
                    )
                )

    selected = []
    used = set()
    matches = sorted(
        [
            (rank, index, item)
            for index, proposals_for_label in candidates.items()
            for rank, item in proposals_for_label
        ],
        key=lambda pair: (-pair[0], pair[1], pair[2].code),
    )
    for _, index, item in matches:
        if index in used or any(
            intersection_over_union(item.box, old.box) > 0.33 for old in selected
        ):
            continue
        used.add(index)
        selected.append(item)
    for _, item in sorted(orphans, key=lambda pair: -pair[0]):
        if len(selected) >= 300:
            break
        if any(intersection_over_union(item.box, old.box) > 0.30 for old in selected):
            continue
        if (
            item.code in {"PA", "PV", "PJ", "KM_COIL", "KA_COIL", "YC", "YO"}
            and item.confidence < 0.94
        ):
            continue
        selected.append(item)
    return selected


class TiledYolo:
    def __init__(self, weights: Path, confidence: float = 0.30):
        if not weights.is_file():
            raise FileNotFoundError(
                "a local electrical-symbol YOLO checkpoint is required"
            )
        if not 0.0 < confidence <= 1.0:
            raise ValueError("YOLO confidence must be positive and at most 1")
        from sahi import AutoDetectionModel

        self.model = AutoDetectionModel.from_pretrained(
            model_type="ultralytics",
            model_path=str(weights),
            confidence_threshold=confidence,
            device="cpu",
        )

    def __call__(self, image):
        from sahi.predict import get_sliced_prediction

        result = get_sliced_prediction(
            cv2.cvtColor(image, cv2.COLOR_GRAY2RGB),
            self.model,
            slice_height=640,
            slice_width=640,
            overlap_height_ratio=0.2,
            overlap_width_ratio=0.2,
            perform_standard_pred=True,
            postprocess_type="NMS",
            postprocess_match_metric="IOU",
            postprocess_match_threshold=0.45,
            verbose=0,
        )
        components = []
        for prediction in result.object_prediction_list:
            code = prediction.category.name.upper()
            if code not in CLASSES or not CLASSES[code]["bbox"]:
                continue
            left, top, right, bottom = map(float, prediction.bbox.to_xyxy())
            w, h = right - left, bottom - top
            x0, y0, x1, y1 = CLASSES[code]["bbox"]
            ports = {}
            if w <= 0 or h <= 0:
                continue
            for name, (x, y) in CLASSES[code]["ports"].items():
                xf, yf = (x - x0) / (x1 - x0), (y1 - y) / (y1 - y0)
                if code == "FU" and w > h:
                    xf, yf = yf, 1 - xf
                ports[name] = left + xf * w, top + yf * h
            components.append(
                Component(
                    code,
                    (left, top, w, h),
                    ports,
                    float(prediction.score.value),
                    "sahi-yolo",
                )
            )
        return components
