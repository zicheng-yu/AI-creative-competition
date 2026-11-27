"""Render the same workspace data in four downloadable formats."""

import csv
from html import escape
from io import BytesIO, StringIO

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .contracts import Format, Workspace

_LABELS = {"critical": "严重", "warning": "警告", "pass": "通过"}
_METRIC_FIELDS = ("图表", "指标 / 采样点", "策略", "值", "单位")


def metric_rows(workspace: Workspace):
    for chart in workspace.charts:
        for series in chart.series:
            for axis, val in zip(chart.axes, series.values, strict=True):
                yield chart.title, axis.label, series.name, val, chart.unit


def _csv_value(value):
    if isinstance(value, str) and (
        value.startswith(("\n", "\r", "\t"))
        or value.lstrip().startswith(("=", "+", "-", "@"))
    ):
        return "'" + value
    return value


def render_csv(workspace: Workspace) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(_METRIC_FIELDS)
    writer.writerows(tuple(map(_csv_value, row)) for row in metric_rows(workspace))
    return output.getvalue().encode("utf-8-sig")


def render_excel(workspace: Workspace) -> bytes:
    book = Workbook()
    metrics = book.active
    metrics.title = "评测数据"
    findings = book.create_sheet("校验")
    sources = book.create_sheet("来源")

    def append(sheet, row):
        sheet.append(row)
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value, str):
                cell.data_type = "s"

    append(metrics, _METRIC_FIELDS)
    for row in metric_rows(workspace):
        append(metrics, row)
    append(findings, ("等级", "项目", "说明", "建议", "来源"))
    for item in workspace.findings:
        append(
            findings,
            (
                _LABELS[item.severity],
                item.title,
                item.detail,
                item.recommendation,
                item.source_id,
            ),
        )
    append(sources, ("编号", "标题", "版本", "置信度", "片段"))
    for item in workspace.sources:
        append(
            sources,
            (
                item.source_id,
                item.title,
                item.version,
                item.confidence,
                item.raw_snippet,
            ),
        )
    for sheet in book:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        sheet.column_dimensions["A"].width = 24
        sheet.column_dimensions["B"].width = 26
        sheet.column_dimensions["C"].width = 32
        sheet.column_dimensions["D"].width = 28
        sheet.column_dimensions["E"].width = 48
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def report_sections(workspace: Workspace) -> list[tuple[str, list[str]]]:
    findings = [
        f"{_LABELS[item.severity]}｜{item.title}。{item.detail} {item.recommendation}"
        for item in workspace.findings
    ]
    sources = [
        f"{item.title}（{item.source_id} / {item.version}）{item.raw_snippet}"
        for item in workspace.sources
    ]
    metrics = [
        f"{title} · {axis} · {strategy} · {val:g} {unit}"
        for title, axis, strategy, val, unit in metric_rows(workspace)
    ]
    return [("校验", findings), ("来源", sources), ("评测数据", metrics)]


def render_markdown(workspace: Workspace) -> bytes:
    def clean(value: str) -> str:
        return (
            escape(" ".join(value.split())).replace("\\", "\\\\").replace("**", r"\*\*")
        )

    lines = [
        f"# {clean(workspace.title)}",
        "",
        f"版本 {clean(workspace.version)}",
        "",
        clean(workspace.summary),
    ]
    for title, rows in report_sections(workspace):
        lines.extend(("", f"## {title}", ""))
        lines.extend(f"- {clean(line)}" for line in rows)
    return ("\n".join(lines) + "\n").encode("utf-8")


def render_pdf(workspace: Workspace) -> bytes:
    font = "STSong-Light"
    pdfmetrics.registerFont(UnicodeCIDFont(font))
    title = ParagraphStyle(
        "title",
        fontName=font,
        fontSize=23,
        leading=30,
        textColor=colors.HexColor("#172b3c"),
    )
    heading = ParagraphStyle(
        "heading", parent=title, fontSize=13, leading=19, keepWithNext=True
    )
    body = ParagraphStyle(
        "body", fontName=font, fontSize=10.5, leading=16, wordWrap="CJK", spaceAfter=4
    )
    paragraphs = [
        Paragraph(escape(workspace.title), title),
        Paragraph(f"版本 {escape(workspace.version)}", body),
        Paragraph(escape(workspace.summary), body),
    ]
    for label, rows in report_sections(workspace):
        paragraphs.extend((Spacer(1, 12), Paragraph(label, heading)))
        paragraphs.extend(
            Paragraph(escape(value), body) for value in (rows or ["暂无记录"])
        )
    output = BytesIO()
    SimpleDocTemplate(output, title=workspace.title).build(paragraphs)
    return output.getvalue()


_RENDERERS = {
    "md": ("text/markdown", render_markdown),
    "pdf": ("application/pdf", render_pdf),
    "csv": ("text/csv", render_csv),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        render_excel,
    ),
}


def render_report(workspace: Workspace, fmt: Format) -> tuple[str, bytes]:
    media_type, renderer = _RENDERERS[fmt]
    return media_type, renderer(workspace)
