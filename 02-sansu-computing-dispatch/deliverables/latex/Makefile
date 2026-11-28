.PHONY: all clean

PLAN_PDF := ../“三苏”创新应用赛道-SuCompute-盼盼法式小面包-计划书.pdf
EVID_PDF := ../“三苏”创新应用赛道-SuCompute-盼盼法式小面包-佐证材料.pdf
OLD_PLAN := ../“三苏”创新应用赛道-苏算绿枢（SuCompute-Opt）-盼盼法式小面包-计划书.pdf
OLD_EVID := ../“三苏”创新应用赛道-苏算绿枢（SuCompute-Opt）-盼盼法式小面包-佐证材料.pdf

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
