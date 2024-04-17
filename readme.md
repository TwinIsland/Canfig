# Usage

### Step0: import Canfig definition 
```bash
canfig create <config_name> -f sample.cand 
```

### Step1: Satrt Cafig Server 
```bash
canfig serve <config_name> -p <port>
```

### Step2: Edit the config
Canfig provide two ways to edit the config

**Local editor:**

run `canfig edit <config_name> -s <slice_name>` will allow you to edit the slice using vim.


**Web editor:**

After the server running, you can edit the config in `<ip>:<port>/<config_name>/<slice>`



