.PHONY: all clean

all: plan.pdf evidence.pdf
	cp -f plan.pdf "../“三苏”创新应用赛道-苏算绿枢（SuCompute-Opt）-盼盼法式小面包-计划书.pdf"
	cp -f evidence.pdf "../“三苏”创新应用赛道-苏算绿枢（SuCompute-Opt）-盼盼法式小面包-佐证材料.pdf"

plan.pdf: plan.tex common.tex
	xelatex -interaction=nonstopmode -halt-on-error plan.tex
	xelatex -interaction=nonstopmode -halt-on-error plan.tex

evidence.pdf: evidence.tex common.tex
	xelatex -interaction=nonstopmode -halt-on-error evidence.tex
	xelatex -interaction=nonstopmode -halt-on-error evidence.tex

clean:
	rm -f *.aux *.log *.out *.toc *.xdv plan.pdf evidence.pdf
