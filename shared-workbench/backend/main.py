"""Serve validated mock or adapter-provided workspaces and report downloads."""

from os import environ
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from pydantic import ValidationError

from .contracts import Format, Identifier, Mode, Workspace, WorkspaceInfo, WorkspaceList
from .reporting import render_report

FIXTURES = Path(__file__).with_name("fixtures")


def create_app(real_dir: Path | None = None) -> FastAPI:
    directory = environ.get("WORKBENCH_REAL_DIR")
    if real_dir is None and directory:
        real_dir = Path(directory)
    app = FastAPI(title="赛道演示工作台接口", version="1.0.0")

    def folder(mode: Mode) -> Path:
        if mode == "mock":
            return FIXTURES
        if real_dir is None or not real_dir.is_dir():
            raise HTTPException(503, "真实数据目录未配置")
        return real_dir

    def read(path: Path) -> Workspace:
        try:
            workspace = Workspace.model_validate_json(path.read_bytes())
        except FileNotFoundError as exc:
            raise HTTPException(404, "工作区不存在") from exc
        except (ValidationError, OSError) as exc:
            raise HTTPException(
                502, f"工作区 {path.stem} 数据无法读取或不符合契约"
            ) from exc
        if workspace.id != path.stem:
            raise HTTPException(502, f"工作区 {path.stem} 的编号与文件名不一致")
        return workspace

    @app.get("/api/v1/workspaces", response_model=WorkspaceList)
    def workspaces(mode: Mode = "mock") -> WorkspaceList:
        items = [
            WorkspaceInfo(id=data.id, title=data.title, subtitle=data.subtitle)
            for path in sorted(folder(mode).glob("*.json"))
            if path.is_file()
            for data in [read(path)]
        ]
        return WorkspaceList(mode=mode, workspaces=items)

    @app.get("/api/v1/workspaces/{workspace_id}", response_model=Workspace)
    def workspace(workspace_id: Identifier, mode: Mode = "mock") -> Workspace:
        return read(folder(mode) / f"{workspace_id}.json")

    @app.post("/api/v1/reports/{fmt}")
    def report(fmt: Format, data: Workspace) -> Response:
        media_type, content = render_report(data, fmt)
        return Response(
            content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{data.id}-report.{fmt}"'
            },
        )

    return app


app = create_app()
