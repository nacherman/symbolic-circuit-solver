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
*   **`examples/Formula_Verification/`**: Contains examples related to the Autonomous Formula Verification framework (see dedicated section below).

## Running Examples

1.  Ensure all dependencies are installed.
2.  Navigate to the `/app` directory (the parent of `symbolic_circuit_solver_master`).
3.  Run the example scripts using `python3`, e.g.:
    ```bash
    python3 symbolic_circuit_solver_master/examples/H_Bridge/solve_h_bridge_problem.py
    ```
    The scripts contain `sys.path` manipulation to correctly locate the `symbolic_circuit_solver_master` package from the `/app` directory.

## Autonomous Formula Verification Framework

### Overview

The Autonomous Formula Verification framework is a powerful tool designed to validate symbolic DC formulas (for voltages, currents, and power) derived for linear electronic circuits. It works by comparing the results of these symbolic formulas against a numerical DC Modified Nodal Analysis (MNA) solver across a multitude of automatically generated test points (i.e., different sets of parameter values). This ensures the correctness and consistency of the derived symbolic expressions.

**Capabilities:**
*   Verifies symbolic expressions for DC node voltages, element currents, currents through voltage sources, and power dissipated by elements.
*   Supports circuits composed of linear elements: Resistors (R), independent Voltage Sources (V), independent Current Sources (I), Voltage-Controlled Voltage Sources (VCVS - E), Voltage-Controlled Current Sources (VCCS - G), Current-Controlled Voltage Sources (CCVS - H), and Current-Controlled Current Sources (CCCS - F).
*   Automatically generates diverse test points for circuit parameters using various strategies (cyclic, random linear, random log-scale).
*   Provides detailed reports on matches and mismatches, including the parameters used, symbolic vs. numerical values, and percentage differences.
*   Offers flexibility in defining verification tasks and parameter generation through YAML configuration files.

### Key Modules

The verification framework leverages several key modules from the `symbolic_circuit_solver_master` package:

*   **`scs_numerical_solver.py`**: Provides the core numerical DC solver based on Modified Nodal Analysis (MNA). It calculates node voltages, currents through voltage sources, and subsequently all element currents and power values for a given set of numerical parameters. This serves as the "ground truth" against which symbolic formulas are compared.
*   **`scs_utils.py`**: Contains utility functions essential for the verification process:
    *   `evaluate_symbolic_expr()`: Substitutes numerical values into Sympy expressions and evaluates them.
    *   `compare_numerical_values()`: Compares two numerical values within a given tolerance.
    *   `generate_test_points()`: A sophisticated function for generating lists of parameter value sets (test points). It supports various generation modes (cyclic, random), custom value lists for specific symbols, symbol-specific random ranges, and log-scale random generation for resistance values, ensuring thorough testing across different parameter dimensions.
*   **`scs_verification.py`**: This is the central module for the verification framework.
    *   It contains individual `verify_*_formula` functions (e.g., `verify_node_voltage_formula`) for direct verification tasks.
    *   It defines the `VerificationSuite` class, which allows users to group multiple verification tasks for a single circuit, manage the symbolic solving of the circuit once, and run all tasks efficiently. The `VerificationSuite` is primarily designed to be configured and run using YAML files.

### Using `VerificationSuite` with YAML

The most convenient way to use the verification framework is by defining a `VerificationSuite` using a YAML configuration file. This allows for easy definition of multiple verification tasks without writing extensive Python code.

#### YAML Structure

The YAML file defines the suite's properties and the tasks to be performed:

*   **`suite_name`** (str, optional): A descriptive name for the verification suite. If omitted, a name will be generated based on the netlist file name.
*   **`netlist_path`** (str, required): The path to the SPICE-like netlist file for the circuit under test. This path can be absolute or relative to the location of the YAML file itself.
*   **`tasks`** (list, required): A list of dictionaries, where each dictionary defines a single verification task.

#### Task Definition Fields

Each task in the `tasks` list can have the following fields:

*   **`task_name`** (str, required): A unique, descriptive name for the task (e.g., "V_output_node_check", "I_R1_current_check").
*   **`type`** (str, required): Specifies the type of quantity to verify. Supported values:
    *   `'node_voltage'`: For verifying the voltage at a node (or between two nodes).
    *   `'element_current'`: For verifying the current through a passive element (e.g., Resistor).
    *   `'vsource_current'`: For verifying the current through a voltage source (e.g., V, E, H elements).
    *   `'element_power'`: For verifying the power absorbed by an element.
*   **`target`** (str, required): Identifies the node or element for verification.
    *   For `node_voltage`:
        *   A single node name (e.g., `"N_out"`) implies voltage relative to ground (`V(N_out, 0)`).
        *   Two node names separated by a comma (e.g., `"N1,N2"`) for differential voltage `V(N1, N2)`.
    *   For `element_current`, `vsource_current`, `element_power`: The name of the element as defined in the netlist (e.g., `"R1"`, `"Vin"`, `"E_opamp"`).
*   **`num_sets`** (int, optional): The number of different parameter sets (test points) to generate for this task. Defaults to 5 if not specified.
*   **`stop_on_first_mismatch`** (bool, optional): If `true`, the verification for this specific task will stop after the first mismatch is found. Defaults to `false`.
*   **`user_param_override_values`** (dict, optional): A dictionary where keys are parameter names (strings, as defined in the netlist, e.g., `"R2_val"`) and values are fixed numerical values. These parameters will be held constant at the specified values for all test points generated for this task, overriding any random or cyclic generation for them.
    Example: `R2_val: 10000.0`
*   **`symbol_specific_random_ranges`** (dict, optional): A dictionary where keys are symbolic parameter names (strings, e.g., `"R1_sym"`) and values are `[min, max]` lists defining the range for random value generation for that specific symbol in this task. This overrides the global random ranges defined in `scs_utils.generate_test_points` (like `random_R_range`).
    Example: `R1_sym: [500.0, 1500.0]`

**Note on Test Point Generation Defaults:**
When using `VerificationSuite` (either directly or via YAML), the test points for verification tasks are generated by default using `'random'` `generation_mode` and with `log_scale_random_for_R=True`. These settings are generally recommended for robust verification.

#### Example YAML Configuration

Below is an example YAML configuration for verifying several aspects of an operational amplifier circuit. This example can be found in `symbolic_circuit_solver_master/examples/Formula_Verification/example_opamp_suite.yaml`.

```yaml
suite_name: Op-Amp Example Verification Suite
# Path is relative to this YAML file's location.
netlist_path: ../example_circuits/opamp_circuit.sp
tasks:
  - task_name: V_N_out (OpAmp)
    type: node_voltage
    target: N_out
    num_sets: 3
    symbol_specific_random_ranges:
      R1_sym: [600.0, 1200.0]      # R1_sym uses this range (log-scaled)
      Aol_sym: [15000.0, 45000.0] # Aol_sym uses this range (linear-scaled)
      # V_source_sym (another free symbol in the netlist) will use global default random range.
  - task_name: I_R1 (OpAmp)
    type: element_current
    target: R1
    num_sets: 3
  - task_name: I_Vin (OpAmp)
    type: vsource_current
    target: Vin  # Current through the input voltage source Vin
    num_sets: 3
  - task_name: P_R2 (OpAmp)
    type: element_power
    target: R2   # Power in fixed resistor R2
    num_sets: 3
  - task_name: P_E_opamp (OpAmp)
    type: element_power
    target: E_opamp # Power in the VCVS E_opamp
    num_sets: 3
    user_param_override_values:
        R2_val: 5000 # For this task, R2_val (defined as 10k in netlist) will be fixed to 5k
    stop_on_first_mismatch: false
  - task_name: Malformed Task Example (OpAmp) # This task will be skipped due to missing 'target'
    type: node_voltage
    # target: N_another_node # 'target' field is missing
    num_sets: 1
```
The corresponding netlist `opamp_circuit.sp` (located in `examples/example_circuits/`) would define `R1_sym`, `Aol_sym`, and `V_source_sym` as symbolic parameters (e.g., `.PARAM R1_sym = R1_sym`).

### Running a Verification

The primary way to run a verification suite defined in a YAML file is via the command-line interface of `scs_verification.py`.

1.  **Prepare your YAML file** (e.g., `my_suite.yaml`) defining the `netlist_path` and the verification `tasks`.
2.  **Run the script from the command line**, providing the path to your YAML file as an argument. Assuming your current directory is the root of the project (`/app` in the development environment):
    ```bash
    python -m symbolic_circuit_solver_master.scs_verification path/to/your_suite.yaml
    ```
    For instance, to run the provided example suite:
    ```bash
    python -m symbolic_circuit_solver_master.scs_verification symbolic_circuit_solver_master/examples/Formula_Verification/example_opamp_suite.yaml
    ```

Alternatively, you can run a suite programmatically from another Python script:
```python
from symbolic_circuit_solver_master.scs_verification import VerificationSuite
import os

# Example:
# This assumes your Python script is in a location where it can correctly resolve
# the path to the YAML file.
yaml_filepath = "symbolic_circuit_solver_master/examples/Formula_Verification/example_opamp_suite.yaml"

if not os.path.exists(yaml_filepath):
    print(f"Error: YAML file not found at {yaml_filepath}")
else:
    suite = VerificationSuite.load_from_yaml(yaml_filepath)
    if suite:
        run_summary = suite.run(show_individual_task_summaries=True)

        # Process the run_summary dictionary as needed
        print("\n--- Python Script: Final Suite Run Summary ---")
        print(f"Suite Name: {run_summary.get('suite_name')}")
        print(f"Overall Status: {run_summary.get('status')}")
        print(f"Passed Tasks: {run_summary.get('passed_tasks')}/{run_summary.get('total_tasks')}")
        if run_summary.get('status') == 'FAIL':
            print("Failed Task Details:")
            for task_res in run_summary.get('task_results', []):
                if not task_res.get('verified_all', True): # Check if verified_all is False or missing
                    reason = task_res.get('error', f"Mismatches: {task_res.get('mismatches', 0)}")
                    print(f"  - Task: '{task_res.get('task_name')}' "
                          f"({task_res.get('verification_type')} for "
                          f"'{task_res.get('target_node', task_res.get('target_element', task_res.get('target_identifier')))}') "
                          f"- Status: FAIL ({reason})")
```

### Interpreting Output

The script provides detailed output during its run:

1.  **Suite Loading**: Messages indicating which YAML file is being loaded and any warnings (e.g., for skipped malformed tasks or if the netlist path is adjusted).
2.  **Instance Preparation**: Indicates parsing of the netlist and symbolic solution of the circuit for the entire suite. This happens once.
3.  **Individual Task Execution**: For each task defined in the suite:
    *   Information about the task being run (name, type, target).
    *   The symbolic expression derived by the solver for the target quantity.
    *   For each test point (i.e., set of parameter values) used for verification:
        *   The specific parameter values being used for that test point.
        *   The numerically calculated value from the MNA solver.
        *   The value obtained by evaluating the symbolic formula with these parameters.
        *   A "MATCH" or "MISMATCH" status.
        *   For power calculations involving sources, a note about power convention alignment (numerical solver calculates absorbed power; symbolic formula might represent supplied power, so comparison is made with `-1 * symbolic_value`).
    *   If `show_individual_task_summaries` is `True` (default for CLI execution):
        *   A summary for the individual task ("PASS" or "FAIL").
        *   If the task status is "FAIL" due to mismatches, detailed mismatch information is printed:
            *   The specific parameter map (values of symbolic parameters) that caused the failure.
            *   The differing symbolic and numerical values.
            *   The calculated percentage difference.
            *   Any specific notes or errors encountered during that test point's evaluation.
4.  **Overall Suite Summary**: Printed at the very end:
    *   The name of the verification suite.
    *   The overall result: "Passed X/Y tasks."
    *   If any tasks failed or had errors during setup (like failing to derive a formula):
        *   A list of these tasks, including their name, type, target, and a brief reason for failure (e.g., number of mismatches or an error message like "Failed to derive symbolic expression").

This comprehensive output helps quickly identify whether the symbolic formulas are consistent with numerical simulations and pinpoint discrepancies at the level of specific parameter sets if mismatches occur.


## Dependencies

This project relies on the following Python libraries:
*   **Sympy:** For symbolic mathematics (core of the solver).
*   **Numpy:** Used in some analysis functions (e.g., for generating points for sweeps in `scs_analysis.py` and in the numerical MNA solver).
*   **Matplotlib:** Used for plotting in `scs_analysis.py` (e.g., for DC/AC analysis plots). Not directly used by `SymbolicCircuitProblemSolver` or the formula derivation/verification examples unless they invoke plotting analyses.
*   **PyYAML:** For loading and parsing YAML configuration files (used by `VerificationSuite` in `scs_verification.py`).

Please ensure these are installed in your Python environment (e.g., via `pip install sympy numpy matplotlib pyyaml`).
