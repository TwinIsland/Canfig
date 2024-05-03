# Canfig

New generation configuration language

## For Developers

#### Step 0: Start Canfig Service
```bash
./canfig -p <port>
```

#### Step 1: Create Canfig Definition
see [grammar.md](./doc/grammar.md)

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


## For User:

Edit config in `<ip>:<port>/<config_name>/<slice_name>`