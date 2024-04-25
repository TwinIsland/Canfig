{
open Common;;

}


rule token = parse
  | "@version" { VERSION }
  | "@min_sup" { MIN_SUP }
  | "@author" { AUTHOR }
  | "@description" { DESCRIPTION }
  | "@log" { LOG }
  | "@doc" { DOC }
  | "@help" { HELP }
  | ";"     { SEMI }
  | [' ' '\t' '\n' '\r']+ { token lexbuf }  (* Skip whitespace *)
  | "\"" { STRING ( string_match lexbuf ) }
  | ['A'-'Z' 'a'-'z' '0'-'9' '_']+ as id { IDENTIFIER(id) }
  | eof { EOF }
  | _ { failwith "Unexpected character" }



and string_match = parse 
   | "\\\\" { "\\" ^  string_match lexbuf }
   | "\\'" { "\'" ^  string_match lexbuf }
   | "\\\"" { "\"" ^  string_match lexbuf }
   | "\\t" { "\t" ^  string_match lexbuf }
   | "\\n" { "\n" ^  string_match lexbuf }
   | "\\r" { "\r" ^  string_match lexbuf }
   | "\\b" { "\b" ^  string_match lexbuf }
   | "\\ " { " " ^  string_match lexbuf }
   | "\"" { "" }
   | "\\" (['0' - '9']['0' - '9']['0' - '9'] as v) { (String.make 1 (char_of_int (int_of_string v))) ^  string_match lexbuf }
   | [' ' '!' '#'-'~'] as s { (String.make 1 s) ^  string_match lexbuf }
   | "\\\n" [' ' '\t']* {  string_match lexbuf }
{
let lextest s = token (Lexing.from_string s)



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
 }

