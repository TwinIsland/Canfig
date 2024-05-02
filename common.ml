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
  | IDENT of string

  | LCBRACE
  | RCBRACE
  | STRUCT
  | SLICE
  | TRIGGER
  | TRICOND
  | PYARG
  | LPAREN
  | RPAREN
  | CONFIG
  | COMMAND of string
  | ARGUMENT of string
  | EOF

type expr =
  | TagExp of token * string
  | StrExp of token * token * token
  | CfgExp of token * token * token
  | TriExp of token * token * token
  | SliExp of token * token * token



