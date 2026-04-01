# N5D4 — Neurosymbolic Disassembly Framework

N5D4 is a Ghidra script that uses a **Logic Tensor Network (LTN)**-guided neural model to improve disassembly quality in binary programs. It iteratively predicts whether memory blocks contain code or data, and redisassembles blocks classified as code until no further refinements are possible.

## How It Works

1. **Block extraction** — The program's memory is segmented into `Code`, `Data`, and `Unknown` blocks based on existing Ghidra analysis.
2. **Pseudo-disassembly** — Each block is pseudo-disassembled to extract instruction-level features without committing changes to the listing.
3. **Feature extraction** — Per-block feature vectors are computed from metrics such as zero-byte rate, def-use count, printable character rate, arithmetic instruction ratio, and more.
4. **LTN training** — An MLP classifier is trained under LTN constraints (e.g., *blocks reachable via fallthrough from code are likely code*) using ground-truth labels derived from existing Ghidra annotations.
5. **Redisassembly** — Blocks predicted as code are cleared and re-disassembled in Ghidra's listing. A `PRE` comment marks each redisassembled block.
6. **Iteration** — Steps 1–5 repeat until no new blocks are redisassembled or the iteration limit is reached.

## Requirements

- [Ghidra](https://ghidra-sre.org/) with [PyGhidra](https://github.com/NationalSecurityAgency/ghidra/tree/master/Ghidra/Features/PyGhidra) enabled
- Python dependencies installed in PyGhidra's Python environment:
  ```
  pip install ltntorch networkx torch
  ```

## Usage

1. Open your target binary in Ghidra and run initial auto-analysis.
2. Place `ghidra_scripts/N5D4Disassembly.py` under a directory listed in Ghidra's script paths.
3. Run the script from the **Script Manager** (`Window → Script Manager`).

The script calls `main()` automatically when launched from Ghidra, which:
- Runs the iterative disassembly refinement loop.
- Calls `analyzeAll` on the program once finished.

Two constants at the top of the script control the stopping criteria:

| Constant | Default | Description |
|---|---|---|
| `iterationLimit` | `5` | Maximum number of refinement passes |
| `epochLimit` | `500` | Maximum training epochs per pass |

## Project Structure

```
N5D4/
├── ghidra_scripts/
│   └── N5D4Disassembly.py   # Main GhidraScript
└── README.md
```

## Academic Work
