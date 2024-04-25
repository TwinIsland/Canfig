(* File: common.ml *)

type token =
  | VERSION
  | MIN_SUP
  | AUTHOR
  | DESCRIPTION
  | LOG
  | DOC
  | HELP
  | SEMI
  | STRING of string
  | IDENTIFIER of string
  | EOF
