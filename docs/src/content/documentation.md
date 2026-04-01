# N5D4 Documentation

## Introduction

**N5D4** (leet-form of **Neurosymbolic Disassembler**, **NSDA**) is a disassembly refinement script on the Ghidra platform. It can help you with: 

- **Non-standard binary disassembly**: PLC binary, customized firmware
- **Distinguishing data in the .text section**: embedded jump tables in ARM32 architecture. 

If you find Ghidra misses a lot of code in its disassembly results, have a try on **N5D4**! You can quickly try **N5D4** on any binary on any platform, provided it can be imported into Ghidra successfully.

## Requirements

### Hardware Requirements
N5D4 supports both CPU and GPU execution. While it can run on a CPU, a **GPU is preferred** to significantly accelerate the training process.

### Software Requirements
The script has been tested and verified on the following versions:

- **Ghidra**: 12.0.4
- **Python**: 3.13.7
- **LTNtorch**: 1.0.2

Install the necessary dependencies within your **PyGhidra** Python environment using:

```bash
$ pip install ltntorch networkx torch
```

## How to Use

Start the Ghidra GUI with **PyGhidra** support:

```bash
$ ${GHIDRA_HOME}/support/pyghidraRun
```

While PyGhidra provides a virtual environment by default, N5D4 requires external libraries. You must prepare a Python virtual environment and install the required dependencies manually before launching.

For example, using pyenv:
```bash
$ pyenv virtualenv 3.13 pyghidra
$ pyenv activate pyghidra
$ pip install ltntorch networkx torch
$ ${GHIDRA_HOME}/support/pyghidraRun
```

This creates a virtual environment using Python 3.13 and installs the necessary libraries. When you execute the pyghidraRun script within an active virtual environment, it will inherit that environment's configuration and packages.

After launching the Ghidra GUI, add the directory containing the script to the script manager paths under **Window -> Script Manager**. Once added, the script will appear in the list.

You can execute it on the currently open program. Upon running, the script will prompt you for the **maximum iterations** and **training epochs**; the default settings are **5** and **500**, respectively.

## Academic Work

N/A

## License

N5D4 uses BSD-3-Clause license. 