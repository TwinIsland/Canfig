# Milestone 1

I've recently completed the initial design of the Canfig language, incorporating feedback from my friends. I'd like to share a few key insights and updates since my first report.

## Relational Model Reconsideration
After some thought, I've realized that integrating a relational model into Canfig might not be necessary. Initially, it seemed like a good solution for managing config dependencies, but I believe these issues can be more effectively addressed with a trigger feature. Here’s why:
1. Using relational models adds complexity without significant benefits, especially as configs grow larger—imagine managing Kubernetes-scale configurations.
2. The problems relational models aim to solve can be tackled with triggers, maintaining simplicity and improving manageability.

## Features and Comparison
As the design progresses, I notice similarities with languages like Cue and Pkl. While these languages offer basic validation checks (like ensuring numbers fall within a certain range), Canfig aims to elevate configuration validation to a new level. A standout feature is the integration of Python in our triggers. This allows for complex validations and operations, as demonstrated in the following example where we match `server.name` with a regex and check `server.port` for a specific value:

```python
TRIGGER ServerChangeAction WHEN CHANGE Server {
    # Integration with Python interpreter
    if Server.run == 0:
        Runner.flag = 0

    if err_msg := ASSERT_REGEX(target=Server.name, pattern="server-[a|b|c]"):
        return CANFIG_ERR(msg=err_msg)

    if ASSERT_EQUAL(target=Server.port, dest=8000):
        return CANFIG_WARN(msg="the server port uses port 8000")
};
```

## Target and Philosophy
In the ARC (GitHub Action Runner Operator), many bugs stem from user errors, such as they don't know or misunderstand how to specified configuration. Canfig aims to prevent these issues by transforming developer's documentation into code. This philosophy underpins Canfig’s approach: it’s not just a traditional config language but one with a robust validation system designed to preemptively solve problems before they arise.

By translating documentation into executable validation rules, Canfig ensures configurations are correct from the start, reducing errors and improving user experience.


## Implementation Steps

Here's a clearer and more detailed explanation of how to implement Canfig, along with a guide on how to use it.

### Preprocessing and Parsing
1. **Macro Expansion**: Use `gcc -E` to preprocess any macros in the code, expanding them so that the parser can understand them without needing to interpret macros directly.
2. **Lexing**: Utilize `ocamllex` to break the input into a sequence of tokens, which are the basic meaningful components of our language.
3. **Parse Tree**: Employ `ocaml` to construct a parse tree from the tokens, which represents the syntactic structure of the input based on the defined grammar.

### Interpretation and Management
After parsing, manage each configuration and structure definition by storing them in SQLite. This allows for:
- **Basic Constraint and Type Checking**: SQLite supports enforcing data integrity through constraints, which can be effectively utilized to ensure the configurations meet the specified rules.

### Backend Service Setup
1. **Fetch Config from SQLite**: Retrieve the current configuration data stored in SQLite.
2. **Update Trigger Policy**: Adjust the triggers based on the current configurations and any new changes.
3. **Start Backend with FastAPI**: Use FastAPI, a modern, fast web framework for building APIs with Python, to serve the backend services.
4. **Materialize Slice and Start Router**: Materialize configurations into slices, similar to views in MySQL, and set up routing for each slice for efficient data handling and retrieval.

## How to Use Canfig

### For Developers

#### Step 1: Create Canfig Definition
The Canfig language uses three main keywords to define and manage configurations:

- `STRUCT`: This tag is used to define a new data type or structure. For example, creating a time structure to ensure time-related configurations are consistently handled.
  
  ```python
  STRUCT TIME(max_minute: int = 1000) {
      minute INT,
      second INT,
      CONSTRAINT CHK_Time CHECK (second >= 18 AND minute < max_minute)
  };
  ```

- `CONFIG`: This keyword defines a configuration entry. Each `CONFIG` is an instance of a `STRUCT` or built-in type that specifies how a particular setting or feature should be configured.

```python
CONFIG Server: {
    run             BOOLEAN DEFAULT 1,
    name            NAME,
    port            INT,
    description     TEXT    DEFAULT 'default description',
    commands        LIST(COMMAND), 
    alive_time      TIME,    
    server_spec     {
        (* Anonymous STRUCT *)
        server_owner    TEXT,
        server_size     INT CHECK(server_size > 100)
    } OPTIONAL
};
```

- `SLICE`: Similar to a view (`VIEW`) in SQL, this keyword allows the definition of slices using set operators. Slices are dynamic selections of data from one or more configurations that behave as virtual configurations. They are particularly useful for creating customized views or subsets of configurations based on specific criteria.

```python
SLICE Default       = {};
SLICE UserConfig    = (Runner - {Runner.commands}) + {Server.name, Server.port, Server.description};
```

- `TRIGGER`: similar to trigger for database, but use Python code to define trigger

```python
TRIGGER ServerChangeAction WHEN CHANGE Server.commands {
    # python interpreter integration
    if err_msg := ASSERT_UNQIUE(list=Server.commands, 
                                getter=lambda obj: obj['name']):
        return CANFIG_ERR(msg=err_msg)
};
```
> Complete sample can be find in: https://github.com/TwinIsland/Canfig/blob/main/sample.cand

By following these steps and utilizing the Canfig language keywords, developers can efficiently define, manage, and utilize complex configurations within their applications.


#### Step2: Import Defination to Canfig Service
```bash
canfig create <config_name> -f sample_defination.cand 
```

#### Step3: Fetch data
For Python integration, the data can be fetch via CanfigAPI

```python
import os
from canfig import Canfig

config = Canfig(
    host="localhost",
    use="config_name"
).fetchall()

server_port = config['server']['port']
```


### For User:

edit config in `<ip>:<port>/<config_name>/<slice_name>`