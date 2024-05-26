# Canfig: Strongly Validated Configuration Language

> **WARNING: This version supports UNIX-based systems only. Windows users should use WSL.**

Canfig is a robust configuration language designed for developers who need precise control and validation of their application settings. The language supports a structured approach to defining, compiling, and deploying configuration settings, making it ideal for both development and production environments.

## Test

**Step 1: Create Canfig Definition File (.cand)**

Start by defining your configuration schema in a `.cand` file. For the syntax and rules, refer to the [Grammar Documentation](./doc/grammar.md). 
Additionally, enhance your development experience with our simple syntax highlighter plugin for VSCode, available here: [canfig-0.0.1.vsix](./extension/canfig-0.0.1.vsix)

#### **Step 2: Compile the Definition**

> Pre-request: Unix-like System, OCaml, Make, Python3   

Compile your `.cand` file into a `.candy` executable configuration using our Python-based compiler:

```shell
python3 compiler.py sample/sample.cand
```

#### **Step 3: Evaluate the Candy**

there is a comprehensive test case inside the evaluator, so, to evaluate/test, just run:

```shell
python3 canfig.py sample/sample.candy
```

