### CONFIG Server:

- **run**: BOOLEAN (DEFAULT: 1)
  - Indicates whether the server should be running.
- **name**: NAME
  - Name of the server.
- **port**: INT
  - Port number for the server.
- **description**: TEXT (DEFAULT: 'default description')
  - Description of the server.
- **commands**: LIST(COMMAND)
  - List of commands associated with the server.
- **alive_time**: TIME
  - Time duration indicating the server's uptime.

### CONFIG Runner:

- **flag**: Server.run (Auto-set, not exposed to the user)
  - Flag indicating the server's running status.
- **on_server**: Server.name (Auto-set, not exposed to the user)
  - Name of the server associated with the runner.
- **runner_name**: TEXT(64) OPTIONAL
  - Name of the runner (optional).
- **commands**: LIST(COMMAND)
  - List of commands associated with the runner.
- **nickname**: LIST(TEXT(64))
  - List of nicknames for the runner.
- **alive_time**: TIME(500)
  - Time duration indicating the runner's uptime.
