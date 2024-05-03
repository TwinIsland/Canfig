# Canfig: Strongly Validated Configuration Language
> **WARNING: This version supports UNIX-based systems only. Windows users should use WSL.**

Canfig is a robust configuration language designed for developers who need precise control and validation of their application settings. The language supports a structured approach to defining, compiling, and deploying configuration settings, making it ideal for both development and production environments.


## 🛠️ For Developers

### 📋 Define Configuration

#### **Step 1: Create Canfig Definition File (.cand)**

Start by defining your configuration schema in a `.cand` file. For the syntax and rules, refer to the [Grammar Documentation](./doc/grammar.md).

#### **Step 2: Compile the Definition**

Compile your `.cand` file into a `.candy` executable configuration using our Python-based compiler:

```shell
python3 compiler.py sample.cand
```

#### **Step 3: Import Candy into Canfig Service**

Load your compiled configuration into the Canfig service:

```shell
canfig create my_config from sample.candy
```

#### **Step 4: Start Canfig Server**

Launch the Canfig server to make your configuration active:

```shell
canfig start
```

### 🥳 Use Configuration

To integrate your Canfig into a Python application, use the Canfig API to fetch configuration data:

```python
from canfig import Canfig

config = Canfig(
    host="localhost",
    use="config_name"
).fetchall()

server_port = config['server']['port']
```

## 🌐 For Users:

Modify and verify your configuration settings by visiting the web interface at `<ip>:<port>/<config_name>/<slice_name>`. This user-friendly interface allows for easy edits and real-time validation of configurations.
