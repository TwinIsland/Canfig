(* lex_process.ml *)

let lex_file filename =
  let in_channel = open_in filename in
  try
    let lexbuf = Lexing.from_channel in_channel in
    let tokens = ref [] in
    try
      while true do
        let token = get_token lexbuf in  (* Replace Lexer with the actual module name if necessary *)
        tokens := token :: !tokens
      done;
      !tokens  (* This line is not reachable due to the loop *)
    with
    | End_of_file ->
      close_in in_channel;
      List.rev !tokens  (* Return the accumulated tokens, reversed to correct order *)
  with e ->
    close_in_noerr in_channel;
    raise e

let () =
  let tokens = lex_file "sample.cand" in
  List.iter (fun tok -> Printf.printf "%s\n" (string_of_token tok)) tokens
