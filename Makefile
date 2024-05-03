OCAMLC=ocamlc
OCAMLLEX=ocamllex
OCAMLYACC=ocamlyacc

.PHONY: all clean

all: common.cmi ast.ml

exe: all
	$(OCAMLC) ast.ml -o ast

common.cmi: common.ml
	$(OCAMLC) -c common.ml

ast.ml: ast.mll
	$(OCAMLLEX) ast.mll


clean:
	rm -rf common.cmi ast.ml ast.cmi ast
