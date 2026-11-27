import base64
import io
import json

import cv2
import ezdxf
import numpy as np
import pymupdf
import pytest

from symbol_parser.engine import parse_drawing
from symbol_parser.labels import (
    Component,
    TextMark,
    bind_labels,
    normalize_spec,
    specs,
    split_tag,
)
from symbol_parser.raster import _stencil
from symbol_parser.refine import VisionRefiner


@pytest.mark.parametrize(
    ("ink", "tag"),
    [("空开３", "QF3"), ("CT 2", "TA2"), ("交流接触F", "KMF"), ("控制变1", "TC1")],
)
def test_nonstandard_tags_and_electrical_ratings(ink, tag):
    assert split_tag(ink)[1] == tag
    assert split_tag("额定100安") is None
    assert normalize_spec("额定63安 三极 50千安") == "In=63A 3P 50kA"
    assert specs("In = 80 A 3P Icu=50kA", "MCCB") == {
        "model": "MCCB",
        "spec": "In=80A 3P Icu=50kA",
        "In_A": 80,
        "poles": 3,
        "Icu_kA": 50,
    }


def test_spatial_binding_is_one_to_one_and_prefix_compatible():
    first = Component("QF", (0, 0, 4, 12), {}, 0.9, "test")
    second = Component("KM_MAIN", (0, 16, 4, 12), {}, 0.9, "test")
    marks = [
        TextMark("QF1", (5, 4, 6, 2)),
        TextMark("额定25安 三极", (5, 7, 8, 2)),
        TextMark("KM1", (5, 20, 6, 2)),
        TextMark("Ie=63A", (5, 23, 8, 2)),
    ]
    bind_labels([first, second], marks, 1.0)
    assert (first.tag, first.spec, second.tag, second.spec) == (
        "QF1",
        "In=25A 3P",
        "KM1",
        "Ie=63A",
    )


def test_dxf_native_blocks_text_curves_and_rotation(tmp_path):
    doc = ezdxf.new("R2010")
    block = doc.blocks.new("QF", base_point=(10, 10))
    block.add_circle((10, 10), 3)
    model = doc.modelspace()
    model.add_blockref("QF", (32, 20), dxfattribs={"rotation": 90})
    model.add_text("空开7", height=2.3).set_placement((42, 22))
    model.add_mtext(
        "额定63安 三极", dxfattribs={"char_height": 2.0, "insert": (42, 20)}
    )
    model.add_arc((80, 20), 8, 0, 180)
    model.add_lwpolyline([(35, 20), (43, 20)])
    path = tmp_path / "drawing.dxf"
    doc.saveas(path)
    payload = parse_drawing(path)
    wire = payload["sheets"][0]
    assert wire["channel"] == "dxf-vector"
    assert {part["type"] for part in wire["primitives"]} == {"ARC", "LWPOLYLINE"}
    (first,) = wire["symbols"]
    assert first["ports"] == {"in": [24.0, 20.0], "out": [40.0, 20.0]}
    assert first["tag"] == "QF7"
    assert first["bbox"][2:] == [16.0, 8.4]
    assert first["specs"]["spec"] == "In=63A 3P"


def _stencil_page():
    weights, _, (_, _, width, height), _ = _stencil("QF", 4.0, 0)
    image = np.full((290, 390), 255, dtype=np.uint8)
    left, top = 41, 33
    end_y, end_x = top + weights.shape[0], left + weights.shape[1]
    image[top:end_y, left:end_x][weights > 0] = 0
    tags = [
        TextMark("QF8", (left + width + 7, top + height / 2, 19, 7)),
        TextMark("In=63A 3P", (left + width + 7, top + height / 2 + 10, 46, 7)),
    ]
    return image, tags


def test_png_and_scanned_pdf_share_bottom_left_format(tmp_path):
    image, tags = _stencil_page()
    image_path = tmp_path / "r.png"
    cv2.imwrite(str(image_path), image)
    png = parse_drawing(image_path, ocr=lambda _: tags, pixels_per_mm=4)
    sheet = png["sheets"][0]
    assert sheet["channel"] == "raster"
    symbol = next(item for item in sheet["symbols"] if item["tag"] == "QF8")
    assert symbol["specs"]["In_A"] == 63
    assert symbol["bbox"][1] == pytest.approx(
        290 - symbol["bbox_top_left"][1] - symbol["bbox"][3]
    )
    json.dumps(png, allow_nan=False)

    with pymupdf.open() as document:
        page = document.new_page(width=390, height=290)
        page.insert_image(page.rect, filename=image_path)
        pdf_path = tmp_path / "s.pdf"
        document.save(pdf_path)
    pdf = parse_drawing(pdf_path, ocr=lambda _: [], pixels_per_mm=8)["sheets"][0]
    assert pdf["channel"] == "pdf-scan"
    assert not pdf["primitives"]


def test_digital_pdf_extracts_vector_and_native_text(tmp_path):
    with pymupdf.open() as document:
        page = document.new_page(width=300, height=230)
        page.draw_line((25, 40), (25, 75))
        page.draw_rect((21, 75, 29, 91))
        page.insert_text((42, 80), "QF1", fontsize=8)
        path = tmp_path / "digital.pdf"
        document.save(path)

    def must_not_use_ocr(_):
        pytest.fail("PDF already contains native device labels")

    sheet = parse_drawing(path, ocr=must_not_use_ocr)["sheets"][0]
    assert sheet["channel"] == "pdf-vector"
    assert {part["type"] for part in sheet["primitives"]} == {"l", "re"}
    assert any(mark["text"] == "QF1" for mark in sheet["source_text"])


def test_vlm_uses_512px_crop_and_never_rewrites_class_or_coordinates(monkeypatch):
    expected = (41.0, 33.0, 32.0, 64.0)
    item = Component("QF", expected, {"in": (57, 33)}, 0.5, "test")
    image, _ = _stencil_page()

    def fake_endpoint(request, *, timeout):
        request_json = json.loads(request.data)
        crop = request_json["messages"][1]["content"][1]["image_url"]["url"]
        prefix, payload = crop.split(",", 1)
        assert prefix == "data:image/png;base64"
        decoded = cv2.imdecode(
            np.frombuffer(base64.b64decode(payload), dtype=np.uint8),
            cv2.IMREAD_GRAYSCALE,
        )
        assert decoded.shape == (512, 512) and decoded.min() == 0
        return io.BytesIO(
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"tag":"空开8","spec":"额定63安 三极"}'
                            }
                        }
                    ]
                }
            ).encode()
        )

    monkeypatch.setattr("symbol_parser.refine.urlopen", fake_endpoint)
    refine = VisionRefiner("http://localhost/v1/chat/completions", "configured-model")
    assert refine(image, item)
    assert (item.code, item.tag, item.spec, item.box) == (
        "QF",
        "QF8",
        "In=63A 3P",
        expected,
    )
    assert item.refined


def test_dxf_vision_preview_projects_native_ports_without_changing_them(tmp_path):
    doc = ezdxf.new("R2010")
    block = doc.blocks.new("QF")
    block.add_circle((0, 0), 3)
    model = doc.modelspace()
    model.add_line((5, 10), (90, 10))
    model.add_line((5, 70), (90, 70))
    model.add_blockref("QF", (32, 45))
    path = tmp_path / "circuit.dxf"
    doc.saveas(path)
    calls = []

    def inspect_crop_context(image, item):
        assert image.ndim == 2 and image.min() < 100
        x, y, width, height = item.box
        assert 0 <= x < x + width <= image.shape[1]
        assert 0 <= y < y + height <= image.shape[0]
        item.tag, item.spec, item.refined = "QF1", "In=63A 3P", True
        calls.append(item.code)

    result = parse_drawing(path, refiner=inspect_crop_context)
    (record,) = result["sheets"][0]["symbols"]
    assert calls == ["QF"]
    assert record["ports"] == {"in": [32.0, 53.0], "out": [32.0, 37.0]}
    assert record["tag"] == "QF1" and record["vlm_refined"]
