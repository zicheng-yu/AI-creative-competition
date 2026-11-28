.PHONY: all clean

DEST_PLAN := ../人工智能+医疗健康赛道-流盾智研（FluVax-Evidence Agent）-盼盼法式小面包-计划书.pdf
DEST_EVID := ../人工智能+医疗健康赛道-流盾智研（FluVax-Evidence Agent）-盼盼法式小面包-佐证材料.pdf

all: plan.pdf evidence.pdf
	cp -f plan.pdf "$(DEST_PLAN)"
	cp -f evidence.pdf "$(DEST_EVID)"

plan.pdf: plan.tex common.tex
	xelatex -interaction=nonstopmode -halt-on-error plan.tex
	xelatex -interaction=nonstopmode -halt-on-error plan.tex

evidence.pdf: evidence.tex common.tex
	xelatex -interaction=nonstopmode -halt-on-error evidence.tex
	xelatex -interaction=nonstopmode -halt-on-error evidence.tex

clean:
	rm -f *.aux *.log *.out *.toc *.xdv plan.pdf evidence.pdf
