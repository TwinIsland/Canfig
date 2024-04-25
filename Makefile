OCAMLC=ocamlc
OCAMLLEX=ocamllex

.PHONY: all clean

all: common.cmo tokens.ml

common.cmo: common.ml
	$(OCAMLC) -c common.ml -o common.cmo

tokens.ml: token.mll
	$(OCAMLLEX) token.mll

clean:
	rm -rf common.cmi tokens.ml
