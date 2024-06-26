{
open Common;;
}

let numeric = ['0' - '9']
let lowercase = ['a' - 'z']
let uppercase = ['A' - 'Z' '_']
let letter =['a' - 'z' 'A' - 'Z' '_']


rule token = parse
   | "@version" { VERSION }
   | "@min_sup" { MIN_SUP }
   | "@author" { AUTHOR }
   | "@description" { DESCRIPTION }
   | "@log" { LOG }
   | "@doc" { DOC }
   | "@help" { HELP }
   | "STRUCT"  { STRUCT }
   | "CONFIG"  { CONFIG }
   | "TRIGGER" { TRIGGER }
   | "SLICE"   { SLICE }
   | "="       { COMMAND (equal_match lexbuf) }
   | "WHEN CHANGE"   { TRICOND }
   | ";"     { SEMI }
   | "("       { ARGUMENT (argument_match lexbuf) }
   | ")"       { raise (Failure "unmatched ()")}
   | "{"       { COMMAND (command_match 1 lexbuf) }
   | "}"       { raise (Failure "unmatched command block") }
   | [' ' '\t' '\n' '\r']+ { token lexbuf }  (* Skip whitespace *)
   | "\"" { STRING ( string_match lexbuf ) }
   | uppercase (lowercase|uppercase)*  as id { IDENT id }
   | eof { EOF }
   | _ { failwith "Unexpected character" }
   
   | "(*" { comment_match 1 lexbuf}
   | "*)" { raise (Failure "unmatched closed comment") }
   | "//" { block_comment_match lexbuf }

and equal_match = parse
  | _ as c  {
        let next_char = Lexing.lexeme_char lexbuf 1 in
        if next_char = ';'
        then
            ""
        else
            Printf.sprintf "%c%s" c (equal_match lexbuf)
    }


and argument_match = parse 
   | ")" { "" }
   | _ as c  { Printf.sprintf "%c%s" c (argument_match lexbuf) }


and command_match level = parse
   | "{"      { "{" ^ (command_match (level + 1) lexbuf) }
   | "}"      { if level = 1 then "" else "}" ^ (command_match (level - 1) lexbuf) }
   | "(*" { cmd_comment_match 1 level lexbuf}
   | "*)" { raise (Failure "unmatched closed comment") }
   | eof      { failwith "unmatched command block" }
   | _ as c   { Printf.sprintf "%c%s" c (command_match level lexbuf) }

and cmd_comment_match l1 l2 = parse
   | "(*" { cmd_comment_match (l1 + 1) l2 lexbuf }
   | "*)" { if l1 = 1 then command_match l2 lexbuf else cmd_comment_match (l1 - 1) l2 lexbuf }
   | eof { failwith "unmatched open comment" }
   | _ { cmd_comment_match l1 l2 lexbuf }

and comment_match level = parse
   | "(*" { comment_match (level + 1) lexbuf }
   | "*)" { if level = 1 then token lexbuf else comment_match (level - 1) lexbuf }
   | eof { failwith "unmatched open comment" }
   | _ { comment_match level lexbuf }

and block_comment_match = parse
   | '\n' { token lexbuf }
   | eof { EOF }
   | _ { block_comment_match lexbuf }


and string_match = parse
   | "\\\\" { "\\" ^ string_match lexbuf }
   | "\\'" { "\'" ^ string_match lexbuf }
   | "\\\"" { "\"" ^ string_match lexbuf }
   | "\\t" { "\t" ^ string_match lexbuf }
   | "\\n" { "\n" ^ string_match lexbuf }
   | "\\r" { "\r" ^ string_match lexbuf }
   | "\\b" { "\b" ^ string_match lexbuf }
   | "\\ " { " " ^ string_match lexbuf }
   | "\\" ['0'-'9']['0'-'9']['0'-'9'] as v {
       (String.make 1 (char_of_int (int_of_string ("0o"^v)))) ^ string_match lexbuf }
   | "\\" ('\n' | '\r') [' ' '\t']* { string_match lexbuf }
   | "\"" { "" }
   | _ as c { (String.make 1 c) ^ string_match lexbuf }


{
let get_all_tokens s =
   let b = Lexing.from_string (s^"\n") in
   let rec g () = 
   match token b with EOF -> []
   | t -> t :: g () in
   g ()

let try_get_all_tokens s =
    try (Some (get_all_tokens s), true)
    with Failure "unmatched open comment" -> (None, true)
       | Failure "unmatched closed comment" -> (None, false)

let string_of_token = function
    | VERSION -> "VERSION"
    | MIN_SUP -> "MIN_SUP"
    | AUTHOR -> "AUTHOR"
    | DESCRIPTION -> "DESCRIPTION"
    | LOG -> "LOG"
    | DOC -> "DOC"
    | HELP -> "HELP"
    | SEMI -> "SEMI"
    | STRING s -> Printf.sprintf "STRING(%s)" s
    | IDENT s -> Printf.sprintf "IDENT(%s)" s
    | LCBRACE -> "LCBRACE"
    | RCBRACE -> "RCBRACE"
    | STRUCT -> "STRUCT"
    | SLICE -> "SLICE"
    | TRIGGER -> "TRIGGER"
    | TRICOND -> "TRICOND"
    | PYARG -> "PYARG"
    | LPAREN -> "LPAREN"
    | RPAREN -> "RPAREN"
    | CONFIG -> "CONFIG"
    | COMMAND s -> Printf.sprintf "COMMAND(%s)" s
    | ARGUMENT s -> Printf.sprintf "ARGUMENT(%s)" s
    | EOF -> "EOF"


(* Main function to process files *)
let () =
    let args = Sys.argv in
    if Array.length args < 4 then
        Printf.eprintf "Usage: %s <input_file> -o <output_file>\n" args.(0)
    else
        let input_file = args.(1) in
        let output_file = args.(3) in
        if args.(2) <> "-o" then
            Printf.eprintf "Invalid option: %s. Use -o for output file specification.\n" args.(2)
        else
            try
                let ic = open_in input_file in
                let input_content = really_input_string ic (in_channel_length ic) in
                close_in ic;
                match try_get_all_tokens input_content with
                | (Some tokens, _) ->
                    let output_content = String.concat "[_!]" (List.map string_of_token tokens) in
                    let oc = open_out (output_file ^ ".cando") in
                    output_string oc output_content;
                    close_out oc
                | (None, _) ->
                    Printf.eprintf "Error processing tokens from input file.\n"
            with
            | Sys_error s -> Printf.eprintf "Error: %s\n" s

}
