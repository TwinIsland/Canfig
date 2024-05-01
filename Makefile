OCAMLC=ocamlc
OCAMLLEX=ocamllex
OCAMLYACC=ocamlyacc

.PHONY: all clean

all: common.cmo ast.ml

common.cmo: common.ml
	$(OCAMLC) -c common.ml -o common.cmo

ast.ml: ast.mll
	$(OCAMLLEX) ast.mll


clean:
	rm -rf common.cmi ast.ml
