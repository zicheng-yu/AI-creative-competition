.PHONY: all clean

PLAN_PDF := ../01-项目计划书/人工智能+工业制造赛道-ElectronicBOM-盼盼法式小面包-计划书.pdf
EVID_PDF := ../04-数据集与评测佐证/人工智能+工业制造赛道-ElectronicBOM-盼盼法式小面包-佐证材料.pdf
OLD_PLAN := ../01-项目计划书/人工智能+工业制造赛道-图枢电析（ElectroGraph BOM）-盼盼法式小面包.pdf
OLD_EVID := ../04-数据集与评测佐证/人工智能+工业制造赛道-图枢电析（ElectroGraph BOM）-盼盼法式小面包.pdf

all: plan.pdf evidence.pdf
	cp -f plan.pdf "$(PLAN_PDF)"
	cp -f evidence.pdf "$(EVID_PDF)"
	rm -f "$(OLD_PLAN)" "$(OLD_EVID)"

plan.pdf: plan.tex common.tex
	xelatex -interaction=nonstopmode -halt-on-error plan.tex
	xelatex -interaction=nonstopmode -halt-on-error plan.tex

evidence.pdf: evidence.tex common.tex
	xelatex -interaction=nonstopmode -halt-on-error evidence.tex
	xelatex -interaction=nonstopmode -halt-on-error evidence.tex

clean:
	rm -f *.aux *.log *.out *.toc *.xdv plan.pdf evidence.pdf
