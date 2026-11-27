"""Generate publication-sized Track 01 charts from scored results."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager, pyplot as plt, rcParams
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import PercentFormatter
import numpy as np

from .metrics import summarize

INK = "#16283f"
TEAL = "#087c7b"
BLUE = "#3972bb"
AMBER = "#b97225"
MUTED = "#53647a"
GRID = "#dfe6ee"
PALETTE = ("#8da2b9","#5b88c8","#bc8545",TEAL)
MAIN_LANES = ("b1","b2","b3","full")
VARIANTS = ("png","no_topology","no_kg")
METRICS = ("composite","symbol","spec_semantic","edge","bom_detail","bom_summary")


def metric(summary, key):
    value = summary[key]
    if isinstance(value, dict):
        return value["recall"] if key.startswith("bom_") else value["f1"]
    return value


def figure_labels():
    installed = {font.name: font.fname for font in font_manager.fontManager.ttflist}
    for name in ("Microsoft YaHei","SimHei","Noto Sans CJK SC","Source Han Sans SC","WenQuanYi Micro Hei"):
        path = installed.get(name)
        if path:
            font_manager.fontManager.addfont(path)
            rcParams["font.family"] = name
            return True
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")):
        if path.is_file():
            font_manager.fontManager.addfont(path)
            rcParams["font.family"] = font_manager.FontProperties(fname=path).get_name()
            return True
    rcParams["font.family"] = "DejaVu Sans"
    return False


def eligible(result, lane):
    row = result["lanes"][lane]["main"]
    return row is not None and row["drawings"] == result["lanes"]["full"]["main"]["drawings"]


def _style(axis, *, grid="y"):
    axis.set_axisbelow(True)
    axis.grid(axis=grid, color=GRID, linewidth=.7)
    axis.spines[["top","right","left","bottom"]].set_visible(False)
    axis.tick_params(length=0, colors=MUTED)


def _save(figure, directory, name):
    figure.savefig(directory / name, dpi=300, facecolor="white", bbox_inches="tight", pad_inches=.25)
    plt.close(figure)


def _comparison(result, directory, zh):
    groups = [lane for lane in MAIN_LANES if eligible(result, lane)]
    labels = ("综合解析","符号 F1","规格语义","无向边 F1","BOM 明细","BOM 型号汇总") if zh else (
        "Composite","Symbol F1","Spec binding","Edge F1","BOM detail","BOM model groups")
    names = {"b1":"B1 OCR","b2":"B2 Raster","b3":"B3 VLM","full":"Full"}
    data = result["lanes"]
    fig, ax = plt.subplots(figsize=(12.2,5.2), layout="constrained")
    x = np.arange(len(labels))
    width = .76/len(groups)
    for i, lane in enumerate(groups):
        values = [metric(data[lane]["main"], key) for key in METRICS]
        pos = x + (i-(len(groups)-1)/2)*width
        bars = ax.bar(pos, [value or 0 for value in values], width*.88,
                      color=PALETTE[MAIN_LANES.index(lane)], label=names[lane], zorder=3)
        for bar, value in zip(bars, values, strict=True):
            if value is not None:
                ax.annotate(f"{value:.0%}", (bar.get_x()+bar.get_width()/2, bar.get_height()),
                            xytext=(0,5), textcoords="offset points", ha="center", va="bottom",
                            color=INK, fontsize=8.1)
    ax.hlines(.93,-.49,.49,color="#ac362e",linestyles="--",linewidth=1.4, label="93%")
    ax.hlines(.95,3.51,5.49,color=AMBER,linestyles="--",linewidth=1.4, label="95%")
    ax.set(ylim=(0,1.14), xticks=x, xticklabels=labels)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_title("主验收集 · 基线与完整系统" if zh else "Main set · Baselines and full system",
                 loc="left", color=INK, fontsize=17, fontweight="bold", pad=20)
    _style(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(.50,-.08), frameon=False, ncol=len(groups)+2)
    if "b3" not in groups:
        note = "B3 无完整预测，未绘制" if zh else "B3 has no complete prediction set"
        ax.text(.99,1.045,note,ha="right",transform=ax.transAxes,color=MUTED,fontsize=9)
    _save(fig,directory,"fig1_baseline_comparison.png")


def _ablation(result, directory, zh):
    fig, axes = plt.subplots(1,3,figsize=(12.2,4.55),layout="constrained",sharey=True)
    titles = ("A1 全光栅","A2 朴素连线","A3 去 KG") if zh else ("A1 Raster only","A2 Nearest wiring","A3 No KG")
    categories = ("综合解析","拓扑 F1","BOM 明细","型号汇总","规格精确") if zh else (
        "Composite","Topology F1","BOM detail","Model groups","Emitted exact")
    keys = ("composite","edge","bom_detail","bom_summary","spec_emitted_exact")
    full = result["lanes"]["full"]["main"]
    differences = [[100*(metric(full,k)-metric(result["lanes"][lane]["main"],k)) for k in keys]
                   for lane in VARIANTS]
    ymin = min(-1, min(min(a) for a in differences)-2)
    ymax = max(3, max(max(a) for a in differences)+6)
    for ax, title, delta in zip(axes,titles,differences,strict=True):
        ax.bar(range(len(keys)),delta,color=[TEAL if v >= 0 else AMBER for v in delta], width=.65)
        for idx,val in enumerate(delta):
            ax.text(idx,val+(.55 if val >= 0 else -.55),f"{val:+.1f}",color=INK,ha="center",
                    va="bottom" if val >= 0 else "top",fontsize=9)
        ax.axhline(0,color=MUTED,linewidth=.7)
        ax.set(xticks=range(len(keys)),xticklabels=categories,ylim=(ymin,ymax))
        ax.tick_params(axis="x",labelrotation=23)
        ax.set_title(title,loc="left",color=INK,fontweight="bold",fontsize=12)
        _style(ax)
    axes[0].set_ylabel("百分点" if zh else "Percentage points",color=MUTED)
    fig.suptitle("完整系统相对各消融组的变化 · 11 张" if zh else "Full minus each ablation · 11 drawings",
                 x=.02,ha="left",color=INK,fontsize=17,fontweight="bold")
    _save(fig,directory,"fig2_ablation_contribution.png")


def _subset(result, directory, zh):
    rows = sorted((r for r in result["per_drawing"] if r["lane"] == "full"),
                  key=lambda r: (("primary","secondary","defect","degraded").index(r["subset"]),r["drawing_id"]))
    metrics = METRICS[:-1]
    data = [[metric(summarize([row]),key) for key in metrics] for row in rows]
    table = np.array([[float("nan") if val is None else val for val in row] for row in data])
    fig,(heat,lat)=plt.subplots(1,2,figsize=(12.2,6.3),layout="constrained",gridspec_kw={"width_ratios":[1.5,1]})
    colors = LinearSegmentedColormap.from_list("ink",["#f9f1df","#92d2ce","#16696d"])
    heat.imshow(table,vmin=0,vmax=1,cmap=colors,aspect="auto")
    labels = ("综合","符号","规格","拓扑","BOM 明细") if zh else ("Composite","Symbols","Specs","Topology","BOM detail")
    heat.set(xticks=range(len(metrics)),xticklabels=labels,yticks=range(len(rows)),
             yticklabels=[r["drawing_id"] for r in rows])
    heat.tick_params(axis="both",length=0,colors=MUTED,labelsize=8)
    heat.spines[:].set_visible(False)
    for y, row in enumerate(table):
        for x,val in enumerate(row):
            heat.text(x,y,f"{val:.0%}" if np.isfinite(val) else "—",ha="center",va="center",
                      color="white" if val>.82 else INK,fontsize=8.5)
    heat.set_title("14 张图的分项结果" if zh else "Per-drawing metrics · 14 drawings",loc="left",color=INK,pad=12)
    lanes = ("full","dxf","png","pdf")
    names = ("Full","DXF","PNG","PDF")
    series = [result["lanes"][k]["main"]["timing"]["total_s"] for k in lanes]
    means,p95 = ([v[key] for v in series] for key in ("mean","p95"))
    ys = np.arange(len(names))
    lat.barh(ys,means,color=TEAL,height=.48,label="均值" if zh else "Mean")
    lat.scatter(p95,ys,color=INK,s=25,label="P95",zorder=4)
    lat.axvline(15,color="#ac362e",linestyle="--",linewidth=1.3,label="15 s")
    ceiling = max(15, *p95)
    for y, value in zip(ys,means,strict=True):
        lat.text(value+.025*ceiling,y+.21,f"{value:.2f}",color=INK,fontsize=9)
    lat.set(yticks=ys,yticklabels=names,xlim=(0,ceiling*1.16),xlabel="秒 / 张" if zh else "Seconds / drawing")
    lat.invert_yaxis()
    _style(lat,grid="x")
    lat.set_title("11 张主集各通道耗时" if zh else "Main-set pipeline time",loc="left",color=INK,pad=12)
    lat.legend(frameon=False,loc="upper center",bbox_to_anchor=(.5,-.13),ncol=3)
    _save(fig,directory,"fig3_subset_heatmap_latency.png")


def _error_charts(result,directory,zh):
    fig,(ax,degraded)=plt.subplots(1,2,figsize=(12.2,4.6),layout="constrained")
    stages = ("symbol","spec","topology")
    title = ("符号","规格","拓扑") if zh else ("Symbols","Specifications","Topology")
    total = result["error_analysis"]["by_stage"]
    counts = [total.get(k,0) for k in stages]
    ax.barh(title,counts,color=(BLUE,AMBER,TEAL),height=.48)
    for i, value in enumerate(counts):
        ax.text(value+.015*max(1,*counts),i,f"{value}  ({value/max(1,sum(counts)):.0%})",
                va="center",color=INK,fontsize=10)
    ax.set_xlim(0,max(1,*counts)*1.36)
    ax.invert_yaxis()
    _style(ax,grid="x")
    ax.set_title("完整系统上游差错计数" if zh else "Observed upstream discrepancies",loc="left",color=INK,pad=12)
    ax.set_xlabel("差错事件（不含下游重复计数）" if zh else "Events (excludes downstream repeats)",color=MUTED)
    data = result["lanes"]
    main = data["png"]["main"]
    decay = data["png"]["degraded"]
    without = data["degraded_no_kg"]["degraded"]
    groups = [main, decay, without]
    selected = ("composite","symbol","spec_semantic","edge","spec_emitted_exact")
    labels = ("综合","符号","规格语义","拓扑","输出规格精确") if zh else (
        "Composite","Symbols","Spec binding","Topology","Emitted exact")
    legends = ("PNG 主集","PNG 退化","PNG 退化去 KG") if zh else ("PNG main","PNG degraded","Degraded no KG")
    x = np.arange(len(labels))
    for i, group in enumerate(groups):
        degraded.bar(x+(i-1)*.23,[metric(group,k) or 0 for k in selected],width=.21,
                     color=(BLUE,TEAL,AMBER)[i],label=legends[i])
    degraded.yaxis.set_major_formatter(PercentFormatter(1))
    degraded.set(xticks=x,xticklabels=labels,ylim=(0,1.05))
    _style(degraded)
    degraded.set_title("分集退化变化 · 同一 PNG 通道" if zh else "Degradation · Same PNG pipeline",
                       loc="left",color=INK,pad=12)
    degraded.legend(frameon=False,loc="lower center",bbox_to_anchor=(.5,-.25),ncol=3,fontsize=8)
    _save(fig,directory,"fig4_error_attribution.png")


def render_charts(result, directory):
    directory.mkdir(parents=True,exist_ok=True)
    zh = figure_labels()
    rcParams["axes.unicode_minus"] = False
    for chart in (_comparison,_ablation,_subset,_error_charts):
        chart(result,directory,zh)
