# Symbolic Circuit Solver Project

## Introduction

This project provides tools for symbolic circuit analysis, allowing users to understand circuit behavior in terms of symbolic parameters rather than purely numerical results (as in traditional SPICE simulations). This approach is particularly useful for deriving formulas, understanding parameter sensitivities, and solving for circuit component values given specific operational conditions.

The project includes two main functionalities:
1.  An original symbolic circuit solver (`scs.py`) for general symbolic analysis of circuits defined in SPICE-like netlists.
2.  A newer "Symbolic Problem Solver Tool" (`scs_symbolic_solver_tool.py`) designed to determine unknown symbolic parameters in a circuit when certain electrical conditions (voltages, currents, or power values) are specified.

## Original Symbolic Solver (`scs.py`)

The original solver (`scs.py`, along with core modules like `scs_parser.py`, `scs_instance_hier.py`, `scs_circuit.py`, `scs_elements.py`) provides the foundation for symbolic circuit representation and analysis. It parses SPICE-like netlist files and can determine circuit characteristics symbolically.

**Note on Performance and Complexity (from original README):**
The script relies heavily on the `sympy` module. Depending on the size of the network, solving circuits can take a long time. It's advisable to avoid creating circuits with a high node count (e.g., above 10) directly at the top level; instead, try to divide them into subinstances. The number of inner nodes (nets not being port nets) corresponds to the size of the matrix representing the system, and inverting large matrices symbolically is computationally intensive. The number of symbols also impacts the time taken for analysis, primarily due to simplification of the resulting expressions. It's recommended to start with simple models and gradually introduce more parameters, checking the readability of the answers. All models must be linear. For transient analysis, traditional SPICE simulations are more appropriate.

The primary function of this original solver was to determine how different parameters of a network affect the output in an analytical manner.

## New: Symbolic Problem Solver Tool (`scs_symbolic_solver_tool.py`)

This tool (`SymbolicCircuitProblemSolver` class) addresses a different type of problem: **given a circuit with some unknown symbolic parameters, and a set of known electrical conditions (e.g., a specific voltage at a node, current through an element, or power dissipated by an element), find the values of the unknown symbolic parameters.**

### Purpose
Imagine you need to find the value of a resistor (`R_load_sym`) or a source voltage (`U_source_sym`) such that a certain condition (like `V(N_out) = 1.5V` or `P(R_load) = 0.5W`) is met. This tool automates the process by:
1.  Symbolically solving the base circuit.
2.  Formulating new equations based on your specified `known_conditions`.
3.  Solving these equations for the `params_to_solve`.

### Usage

#### 1. Defining Symbolic Parameters in SPICE
For the tool to recognize and solve for a symbolic parameter (e.g., `R_load_sym`), it must be declared in the SPICE netlist. This is typically done in two parts:
   a. Assigning the symbolic parameter to a component's value:
      `.PARAM R_load_val = R_load_sym`
      `R_LOAD N_out 0 {R_load_val}` (Note: the solver has been updated to prefer values without curly braces, e.g., `R_LOAD N_out 0 R_load_val`)
   b. Explicitly declaring the base symbol itself so the parser correctly identifies it as a symbolic entity that can be solved for:
      `.PARAM R_load_sym = R_load_sym`

Other fixed parameters are defined as usual:
      `.PARAM R_fixed = 100`

#### 2. Instantiating the Solver
```python
from symbolic_circuit_solver_master.scs_symbolic_solver_tool import SymbolicCircuitProblemSolver
solver = SymbolicCircuitProblemSolver(netlist_path="path/to/your_netlist.sp")
```

#### 3. Defining Known Conditions
`known_conditions` is a list of dictionaries. Each dictionary specifies a condition:
*   **Voltage:**
    ```python
    {'type': 'voltage', 'node1': 'N1', 'node2': '0', 'value': 5.0}
    # V(N1, 0) = 5.0 Volts
    ```
*   **Current:** (Positive current is assumed to flow from the first listed node to the second in the element's SPICE definition)
    ```python
    {'type': 'current', 'element': 'R1', 'value': 0.1}
    # Current through element R1 is 0.1 Amps
    ```
*   **Power:** (Absorbed power by the element)
    ```python
    {'type': 'power', 'element': 'R1', 'value': 0.5}
    # Power dissipated by element R1 is 0.5 Watts
    ```
The `'value'` field in these conditions can be a numerical value (e.g., `5.0`, `0.1`) or a string representing a symbolic expression (e.g., `'US_sym / 2'`).

#### 4. Defining Parameters to Solve For
`params_to_solve` is a list of strings, where each string is the name of a symbolic parameter (as defined with `.PARAM X_sym = X_sym` in the SPICE file) that you want the solver to find.
```python
params_to_solve = ['R_load_sym', 'U_source_sym']
```

#### 5. Solving and Interpreting Results
```python
solution = solver.solve_for_unknowns(known_conditions, params_to_solve)
if solution:
    for var_symbol, value_expr in solution.items():
        print(f"{var_symbol} = {value_expr}")
        # value_expr can be a numerical value or a sympy expression
```
The `solution` is typically a dictionary where keys are the Sympy symbols of the solved parameters and values are their solutions (either numerical or expressions in terms of other symbols if the system is underdetermined).

If the system of equations derived from `known_conditions` is underdetermined (fewer independent equations than unknowns to solve), `sympy.solve` (used internally) might return a solution where some variables are expressed in terms of others. For example, if solving for `R1_sym`, `R2_sym`, and `US_sym` with only one condition, the solution might be like `{R1_sym: -R2_sym + 100.0*US_sym}`.

## Deriving General Symbolic Formulas

The base components of this project (`scs_parser.py`, `scs_instance_hier.py`) can be used directly to obtain general symbolic formulas for circuit quantities (voltages, currents, power) in terms of the circuit's symbolic parameters, without imposing specific numerical conditions.

This involves:
1.  Parsing the SPICE netlist (e.g., `voltage_divider.sp`) where all relevant component values are defined using symbolic parameters (e.g., `R1_val = R1_sym`, `R2_val = R2_sym`, `US_val = US_sym`).
2.  Creating an instance of the circuit.
3.  Solving this instance symbolically using `top_instance.solve()`.
4.  Calling `top_instance.v(node1, node2)`, `top_instance.i(element_name)`, or `top_instance.p(element_name)` to get the desired symbolic expressions.

These expressions will be purely in terms of the symbolic parameters defined in the netlist.
Refer to `examples/Formula_Derivation/derive_divider_formulas.py` for a practical demonstration.

## Calculating V, I, P for All Components (Post-Problem Solving)

After using `SymbolicCircuitProblemSolver` to determine the values of key unknown parameters, you might want to find the specific voltages, currents, and power values for all components in the circuit.
The `solve_h_bridge_problem.py` example demonstrates this:
1.  First, `solve_for_unknowns()` is called to find, for example, `R3_sym` and `U_sym`.
2.  A comprehensive substitution dictionary is built. This dictionary includes:
    *   All fixed parameter values from the netlist (e.g., `R1_val = 180`).
    *   The now-solved values for the initially unknown parameters (e.g., the numerical value for `R3_sym`).
3.  Iterate through the components of interest:
    *   Retrieve their symbolic voltage, current, or power expressions using `solver.top_instance.v()`, `solver.top_instance.i()`, and `solver.top_instance.p()`.
    *   Substitute the values from the comprehensive dictionary into these expressions using `expr.subs(substitution_dict)`.
    *   Evaluate the result numerically using `.evalf()`.

See the latter part of `examples/H_Bridge/solve_h_bridge_problem.py` for a detailed implementation.

## Examples

The `examples/` directory contains scripts demonstrating various functionalities:

*   **`examples/H_Bridge/`**:
    *   `h_bridge.sp`: An H-Bridge circuit with `R3_sym` and `U_sym` as unknowns.
    *   `solve_h_bridge_problem.py`: Uses `SymbolicCircuitProblemSolver` to find `R3_sym` and `U_sym` given V(N3) and I(R4). Then calculates and prints V, I, P for all resistors.
*   **`examples/Power_Condition_Test/`**:
    *   `power_test.sp`: A simple series resistor circuit with `R2_sym` as an unknown.
    *   `solve_power_test.py`: Solves for `R2_sym` given a power condition on R1. Tests the power condition handling in the solver tool.
*   **`examples/Formula_Derivation/`**:
    *   `voltage_divider.sp`: A voltage divider with all components (`US_sym`, `R1_sym`, `R2_sym`) defined symbolically.
    *   `derive_divider_formulas.py`: Demonstrates deriving general symbolic formulas for V_out, I(R1), I(R2), P(R1), P(R2) using the base solver components.
    *   `solve_underdetermined_divider.py`: Shows how the `SymbolicCircuitProblemSolver` handles an underdetermined system (1 equation, 3 unknowns for the voltage divider), typically returning a parametric solution.

## Running Examples

1.  Ensure all dependencies are installed.
2.  Navigate to the `/app` directory (the parent of `symbolic_circuit_solver_master`).
3.  Run the example scripts using `python3`, e.g.:
    ```bash
    python3 symbolic_circuit_solver_master/examples/H_Bridge/solve_h_bridge_problem.py
    ```
    The scripts contain `sys.path` manipulation to correctly locate the `symbolic_circuit_solver_master` package from the `/app` directory.

## Dependencies

This project relies on the following Python libraries:
*   **Sympy:** For symbolic mathematics (core of the solver).
*   **Numpy:** Used in some analysis functions (e.g., for generating points for sweeps in `scs_analysis.py`).
*   **Matplotlib:** Used for plotting in `scs_analysis.py` (e.g., for DC/AC analysis plots). Not directly used by `SymbolicCircuitProblemSolver` or the formula derivation examples unless they invoke plotting analyses.

Please ensure these are installed in your Python environment (e.g., via `pip install sympy numpy matplotlib`).
