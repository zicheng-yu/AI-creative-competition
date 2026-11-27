"""Atomic in-memory expert review with optimistic concurrency and signed exports."""
import csv
import io
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from .audit import BOUNDARY


class ReviewConflict(ValueError):
    pass


def markdown_text(text):
    text = text.replace("\r", " ").replace("\n", " ")
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_{}\[\]()#!|])", r"\\\1", text)


def csv_cell(text):
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


class ReviewStore:
    def __init__(self):
        self._lock = Lock()
        self._reports = {}

    def draft(self, *, snapshot_id, statements, **metadata):
        report = {
            "report_id": uuid4().hex,
            "snapshot_id": snapshot_id,
            "state": "AI_DRAFT_PENDING_REVIEW",
            "version": 1,
            "statements": statements,
            "review": {},
            "timeline": [],
            "scientific_boundary": BOUNDARY,
            **metadata,
        }
        with self._lock:
            self._reports[report["report_id"]] = deepcopy(report)
        return report

    def review(self, report_id, version, reviewer, actions, *, signoff=False):
        with self._lock:
            current = self._reports[report_id]
            if current["version"] != version or current["state"] == "EXPERT_SIGNED":
                raise ReviewConflict("stale version or signed report")
            report = deepcopy(current)
            valid = {s["statement_id"] for s in report["statements"]}
            revision = version + 1
            timestamp = datetime.now(UTC).isoformat()
            for action in actions:
                statement_id = action["statement_id"]
                if statement_id not in valid:
                    raise ValueError("unknown statement")
                if action["action"] == "comment" and not action.get("note", "").strip():
                    raise ValueError("empty comment")
                if action["action"] != "comment":
                    report["review"][statement_id] = action["action"]
                report["timeline"].append({**action, "reviewer": reviewer,
                                           "timestamp": timestamp, "version": revision})
            report["version"] = revision
            result = {"report": report}
            if signoff:
                if not valid or valid - report["review"].keys():
                    raise ReviewConflict("every statement needs a disposition")
                report["state"] = "EXPERT_SIGNED"
                report["timeline"].append({"action": "signoff", "reviewer": reviewer,
                                           "timestamp": timestamp, "version": revision})
                result["exports"] = self._export(report)
            self._reports[report_id] = report
            return deepcopy(result)

    @staticmethod
    def _export(report):
        accepted = [s for s in report["statements"]
                    if report["review"][s["statement_id"]] == "accept"]
        markdown = [f"# 专家复核报告 v{report['version']}", "", BOUNDARY, "",
                    f"快照 `{report['snapshot_id']}`", ""]
        if report.get("dossier_matrix"):
            markdown.extend(["## 档案处置概览", ""])
            for row in report["dossier_matrix"]:
                fields = row["field_completeness"]
                label = markdown_text(row["label"])
                markdown.append(f"- {label}，完整字段 {fields['present']}/{fields['total']}，"
                                f"未决事项 {len(row['review_status']['open_items'])} 项。")
            markdown.extend(["", "## 已采纳引文", ""])
        if not accepted:
            markdown.append("本报告没有已采纳的引文。")
        csv_buffer = io.StringIO(newline="")
        fields = ["statement_id", "evidence_id", "dataset_version",
                  "primary_ref", "evidence_tier", "ingested_at", "source_url", "nature",
                  "source_review_status", "text"]
        writer = csv.writer(csv_buffer)
        writer.writerow(fields)
        for statement in accepted:
            citation = " · ".join(markdown_text(statement[field]) for field in
                                  ("evidence_id", "dataset_version", "primary_ref", "evidence_tier"))
            markdown.append(f"- {markdown_text(statement['text'])} — {citation}")
            writer.writerow([csv_cell(statement.get(field) or "") for field in fields])
        return {
            "markdown": "\n".join(markdown) + "\n",
            "json": json.dumps(report, ensure_ascii=False, indent=2),
            "evidence_csv": csv_buffer.getvalue(),
        }
