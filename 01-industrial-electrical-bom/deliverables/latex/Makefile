.PHONY: all clean

all: plan.pdf evidence.pdf
	cp -f plan.pdf "../01-项目计划书/人工智能+工业制造赛道-图枢电析（ElectroGraph BOM）-盼盼法式小面包.pdf"
	cp -f evidence.pdf "../04-数据集与评测佐证/人工智能+工业制造赛道-图枢电析（ElectroGraph BOM）-盼盼法式小面包.pdf"

plan.pdf: plan.tex common.tex
	xelatex -interaction=nonstopmode -halt-on-error plan.tex
	xelatex -interaction=nonstopmode -halt-on-error plan.tex

evidence.pdf: evidence.tex common.tex
	xelatex -interaction=nonstopmode -halt-on-error evidence.tex
	xelatex -interaction=nonstopmode -halt-on-error evidence.tex

clean:
	rm -f *.aux *.log *.out *.toc *.xdv plan.pdf evidence.pdf
