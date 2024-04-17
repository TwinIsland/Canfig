# Usage

### Step1: write config 
write the cofig in `proto.can` to meet your demand

### Step2: compile your config  
even though most of the bug can be detected by CanfigLSP, it is still recommended to run
to check your config twice via running
```bash
canfig -c proto.can 
```
if no bug report, you are ready to go!

### Step3: start CanfigAPI service
Canfig use TCP to do IPC, and provide API for user to modified their config, to start the service, simply run:
```bash
# host all '.can' config on specific port 
canfig -s "./" <PORT>
```
A human-readable document will also be generated on `/document`
