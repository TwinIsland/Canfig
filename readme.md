# Canfig

New generation configuration language

### For Developers

#### Step 0: Start Canfig Service
```bash
./canfig -p <port>
```

#### Step 1: Create Canfig Definition
The Canfig language uses three main keywords to define and manage configurations:

- `STRUCT`: This tag is used to define a new data type or structure. For example, creating a time structure to ensure time-related configurations are consistently handled.
  
  ```
  STRUCT TIME(max_minute: int = 1000) {
      minute INT,
      second INT,
      CONSTRAINT CHK_Time CHECK (second >= 18 AND minute < max_minute)
  };
  ```

- `CONFIG`: This keyword defines a configuration entry. Each `CONFIG` is an instance of a `STRUCT` or built-in type that specifies how a particular setting or feature should be configured.

> nested config structure will be implemented in the future

```
CONFIG Server: {
    run             BOOLEAN DEFAULT 1,
    name            NAME,
    port            INT,
    description     TEXT    DEFAULT 'default description',
    commands        LIST(COMMAND), 
    alive_time      TIME
};
```

- `SLICE`: Similar to a view (`VIEW`) in SQL, this keyword allows the definition of slices using set operators. Slices are dynamic selections of data from one or more configurations that behave as virtual configurations. They are particularly useful for creating customized views or subsets of configurations based on specific criteria.

```
SLICE Default       = {};
SLICE UserConfig    = (Runner - {Runner.commands}) + {Server.name, Server.port, Server.description};
```

- `TRIGGER`: similar to trigger for database, but use Python code to define trigger

```
TRIGGER ServerChangeAction WHEN CHANGE Server {
    # python interpreter integration
    if err_msg := ASSERT_UNQIUE(list=Server.commands, 
                                getter=lambda obj: obj['name']):
        return CANFIG_ERR(msg=err_msg)
};
```
> Complete sample can be find in: [sample.cand](./sample.cand)

By following these steps and utilizing the Canfig language keywords, developers can efficiently define, manage, and utilize complex configurations within their applications.


#### Step2: Import Defination to Canfig Service
```bash
canfig create <config_name> -f sample_defination.cand 
```

#### Step3: Fetch data
For Python integration, the data can be fetch via CanfigAPI

```python
from canfig import Canfig

config = Canfig(
    host="localhost",
    use="config_name"
).fetchall()

server_port = config['server']['port']
```


### For User:

Edit config in `<ip>:<port>/<config_name>/<slice_name>`