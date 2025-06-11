# Symbolic Circuit Solver Project

## Introduction

This project provides tools for symbolic circuit analysis, allowing users to understand circuit behavior in terms of symbolic parameters rather than purely numerical results (as in traditional SPICE simulations). This approach is particularly useful for deriving formulas, understanding parameter sensitivities, and solving for circuit component values given specific operational conditions.

The project includes [several key functionalities]:
1.  An original symbolic circuit solver (`scs.py`) for general symbolic analysis of circuits defined in SPICE-like netlists.
2.  A "Symbolic Problem Solver Tool" (`scs_symbolic_solver_tool.py`) designed to determine unknown symbolic parameters in a circuit when certain electrical conditions (voltages, currents, or power values) are specified.
3.  An "Autonomous Formula Verification Framework" (`scs_verification.py`, `scs_numerical_solver.py`, `scs_utils.py`) for validating derived symbolic formulas against numerical simulations.
4.  A "Generalized Symbolic Goal Seeking" feature (`scs_symbolic_goal_seeker.py`) to solve for a circuit parameter that achieves a specific symbolic target for an electrical quantity.

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

## Generalized Symbolic Circuit Analysis and Custom Scenarios

This powerful feature, primarily accessed via the `solve_circuit_for_unknowns` function (found in `scs_symbolic_goal_seeker.py`), allows users to work directly with the fundamental system of circuit equations (MNA - Modified Nodal Analysis). It offers a flexible way to define custom analysis scenarios by specifying which parameters are known and which circuit variables or parameters should be solved for symbolically.

### `solve_circuit_for_unknowns()`

**Function Signature (from `scs_symbolic_goal_seeker.py`):**
```python
solve_circuit_for_unknowns(
    netlist_path: str = None,
    known_values_map_str_keys: typing.Dict[str, typing.Union[str, float, int]] = None,
    unknowns_to_solve_for_str: typing.List[str] = None,
    top_instance_optional: scs_instance_hier.Instance = None
) -> typing.List[typing.Dict[sympy.Symbol, sympy.Expr]]
```

**Parameters:**

*   `netlist_path` (str): Path to the SPICE-like netlist file. Required if `top_instance_optional` is not provided.
*   `known_values_map_str_keys` (dict): A dictionary where:
    *   Keys are **strings** matching the symbolic parameter names used in the SPICE netlist's `.PARAM` directives (e.g., the `R1_sym` in `.PARAM R1_actual_value = R1_sym`).
    *   Values can be numerical constants (e.g., `100`, `1.5`) or other Sympy symbols (allowing results to be expressed in terms of these "scenario symbols").
    *   Example: `{'R_load_sym': 50, 'Gain_param_sym': sympy.symbols('A_scenario_val')}`
*   `unknowns_to_solve_for_str` (list[str]): A list of strings specifying the variables for which symbolic solutions are desired. These strings can name:
    *   Node voltages: e.g., `"V_N1"` for the voltage at node `N1` (relative to ground). The underlying symbol is typically `V_N1`.
    *   Element currents: e.g., `"I_R1"` for the current through element `R1`. The underlying symbol is typically `I_R1`. The direction is as defined by the element's node order in the netlist (N+ to N-).
    *   SPICE parameters: e.g., `"R1_sym"` if this parameter is *not* specified in `known_values_map_str_keys` and you wish to solve for it.
    *   If this list is empty or `None`, the function attempts to solve for all defined node voltages, all element currents, and any SPICE parameters not present in `known_values_map_str_keys`.
*   `top_instance_optional` (scs_instance_hier.Instance, optional): An optional, pre-parsed circuit instance. If provided, `netlist_path` might be bypassed for parsing if the instance is already suitable.

**Returns:**

*   (list[dict]): A list of solution dictionaries. Each dictionary maps Sympy `Symbol` objects (representing the solved unknowns) to their resulting Sympy expressions. An empty list indicates no solution or an error.

**Key Concept:**

The `solve_circuit_for_unknowns` function (via `generate_circuit_equations`) first constructs the circuit's complete MNA system:
1.  Kirchhoff's Current Law (KCL) equations for each non-ground node.
2.  Constitutive V-I relationships for every circuit element.

Users define a specific analysis scenario by providing the `known_values_map_str_keys`. This map tells the solver which symbolic parameters from the netlist (e.g., `R1_s`, `Vin_s`) should be substituted with fixed numerical values or with other user-defined scenario symbols. Any parameters from the netlist not included in this map are typically treated as further unknowns in the system. The `unknowns_to_solve_for_str` list then tells `sympy.solve()` which variables' symbolic expressions are of interest. For complex results (e.g., solving for an input voltage based on an output condition), it's often necessary to include all intermediate circuit variables (other node voltages and element currents) in `unknowns_to_solve_for_str` to allow Sympy to fully resolve the desired primary unknowns in terms of the scenario symbols.

### Example: H-Bridge Symbolic Analysis for Input Voltage

The script `examples/Symbolic_Goal_Seeking/h_bridge_analysis.py` uses this approach to determine the required input voltage (`Vin_s`) for an H-bridge to achieve a specific target voltage across its load, given symbolic values for switch and load resistances.

**(a) Netlist Setup:**
The H-bridge is defined with symbolic parameters for its input voltage source (`Vin_s`) and all resistors: `Rul_s` (upper-left), `Rll_s` (lower-left), `Rur_s` (upper-right), `Rlr_s` (lower-right), and `Rload_s` (the load). Each is declared like `.PARAM Rul_s = Rul_s`.

**(b) Scenario and Goal:**
*   **Knowns**: The switch resistances are mapped to scenario symbols representing their state (e.g., `sR_on` for low resistance, `sR_off` for high resistance). The load resistance `Rload_s` is mapped to a scenario symbol `sRload`.
    ```python
    # sR_on, sR_off, sRload are pre-defined sympy.symbols
    knowns_map = {
        'Rul_s': sR_on,    # Upper-left is ON
        'Rll_s': sR_off,   # Lower-left is OFF
        'Rur_s': sR_off,   # Upper-right is OFF
        'Rlr_s': sR_on,    # Lower-right is ON
        'Rload_s': sRload
    }
    ```
    (Note: `sVload_target` is not in `known_values_map_str_keys` because it's part of an added constraint equation, not a direct substitution for a `.PARAM`).

*   **Constraint**: An additional equation is added to the MNA system: the voltage across the load (`V_Na - V_Nb`) must equal another scenario symbol, `sVload_target`.
    `sympy.Eq(V_Na_symbol - V_Nb_symbol, sVload_target)`
*   **Goal**: Solve for the circuit's main input voltage parameter `Vin_s` (the value of the `Vin` source element) and the current `I_Vin` (current through the `Vin` source element) in terms of `sR_on`, `sR_off`, `sRload`, and `sVload_target`.

**(c) Solving:**
*   `unknowns_list` includes `'Vin_s'`, `'I_Vin'`, and all other node voltage symbols (e.g., `'V_N_supply'`, `'V_Na'`, `'V_Nb'`) and element current symbols (e.g., `'I_Rul'`, `'I_Rload'`) from the circuit.
*   `solve_from_equations` (called by `solve_circuit_for_unknowns`) then finds expressions for `Vin_s` and `I_Vin`.

This example yields complex symbolic formulas for `Vin_s` and `I_Vin` which can then be numerically evaluated for specific resistance and target voltage values.

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

## Generalized Symbolic Goal Seeking (`scs_symbolic_goal_seeker.py`)

### Overview

This feature allows you to solve for a single unknown symbolic parameter within a circuit such that a specific electrical quantity (like a node voltage, element current, or power) achieves a desired target value. The target value can itself be a symbolic expression or a numerical constant. This is useful for design tasks where you need to determine a component value or source setting to meet a particular performance goal.

For example, you can ask: "What value of `R_load_sym` makes `V(N_out)` equal to `Vin_sym / 2`?" or "What `Vin_sym` is needed for `P(R_load)` to be `1.0W`?"

The core of this functionality is provided by the `solve_for_symbolic_unknown` function in the `scs_symbolic_goal_seeker.py` module.

### How to Use `solve_for_symbolic_unknown`

The main function is:
```python
solve_for_symbolic_unknown(
    netlist_path: str,
    unknown_param_name_str: str,
    target_quantity_str: str,
    target_value_expr_str: str
) -> typing.List[sympy.Expr]
```

**Parameters:**

*   `netlist_path` (str):
    Path to the SPICE-like netlist file describing the circuit.
*   `unknown_param_name_str` (str):
    The string name of the symbolic parameter within the netlist that you want to solve for. This parameter must be defined symbolically in your netlist (see Netlist Requirements below). Example: `"R_load_sym"`.
*   `target_quantity_str` (str):
    A string that specifies the electrical quantity you want to control. Supported formats:
    *   `"V(node_name)"`: Voltage at `node_name` relative to ground (e.g., `"V(N_out)"`).
    *   `"V(node1,node2)"`: Voltage between `node1` and `node2` (e.g., `"V(N1,N2)"`).
    *   `"I(element_name)"`: Current through the specified `element_name` (e.g., `"I(R1)"`). The direction is as defined by the element's node order in the netlist.
    *   `"P(element_name)"`: Power absorbed by the specified `element_name` (e.g., `"P(R1)"`).
*   `target_value_expr_str` (str):
    A string representing the desired value for the `target_quantity_str`. This can be:
    *   A numerical constant (e.g., `"1.5"` for 1.5 Volts).
    *   A symbolic expression involving other symbolic parameters defined in the netlist (e.g., `"Vin_val / 2"`, `"my_const * R2_sym"`).

**Netlist Requirements for Symbolic Parameters:**

For the goal seeker to work correctly, any parameter intended to be an unknown (like `unknown_param_name_str`) or any parameter used in `target_value_expr_str` that should be treated as a symbol rather than a fixed numerical value from a `.PARAM` line, must be explicitly declared as a symbolic entity in the SPICE netlist. This is typically done in two ways:

1.  **Parameter Declaration**: Use a `.PARAM` statement to declare the symbol itself. The convention is `.PARAM MySymbol = MySymbol`.
    ```spice
    .PARAM R_unknown = R_unknown  ; Declares R_unknown as a symbol
    .PARAM V_in_val = V_in_val    ; Declares V_in_val as a symbol (if used in target_value_expr_str)
    .PARAM R_fixed = 1k         ; A fixed value, not treated as a variable by sympy by default
    ```
2.  **Component Value Assignment**: Assign the symbolic parameter to the component's value.
    ```spice
    R_load N_out 0 R_unknown  ; R_load's value is the symbolic R_unknown
    V_source N_in 0 V_in_val  ; V_source's value is the symbolic V_in_val
    ```
    (Note: The solver prefers component values without curly braces, e.g., `R_load N_out 0 R_unknown` instead of `{R_unknown}`).

**Return Value:**

The function returns a `typing.List[sympy.Expr]`. This list contains the Sympy expressions that are the solutions for the `unknown_param_name_str`.
*   If one or more solutions are found, they will be in the list.
*   If the equation is contradictory (no solution), the list will be empty.
*   If the unknown parameter does not appear in the formed equation (e.g., the target quantity is independent of the unknown), `sympy.solve` might return `[]` (if the equation holds true for all values of the unknown) or specific conditions. The function aims to return a list of expressions for the unknown.
*   In case of errors during parsing, instance creation, symbolic solution of the circuit, or processing the target quantity, an empty list is returned and error messages are printed to the console.

### Usage Example

Consider a simple voltage divider where we want to find the input voltage `Vin_unknown` such that the output voltage `V(N_out)` is equal to a symbolic target `V_target_level`.

**1. SPICE Netlist (`_temp_goal_seek_vdiv.sp` - example path):**
```spice
* Voltage Divider for Goal Seeking Vin_unknown
.PARAM Vin_unknown = Vin_unknown  ; The unknown we are solving for
.PARAM R1_val = 1k                ; Fixed value for R1
.PARAM R2_val = 1k                ; Fixed value for R2
.PARAM V_target_level = V_target_level ; Symbolic target level

VS Vin_node 0 Vin_unknown
R1 Vin_node N_out R1_val
R2 N_out 0 R2_val
.end
```

**2. Python Script:**
```python
import sympy
import os
import sys

# Adjust sys.path to import from the parent package (assuming specific project structure)
# This setup is typical for running scripts within the 'examples' directory.
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_examples = os.path.dirname(script_dir) # e.g., examples/
project_root_package = os.path.dirname(project_root_examples) # e.g., symbolic_circuit_solver_master/
main_project_root = os.path.dirname(project_root_package) # Parent of symbolic_circuit_solver_master/
if main_project_root not in sys.path:
    sys.path.insert(0, main_project_root)

from symbolic_circuit_solver_master.scs_symbolic_goal_seeker import solve_for_symbolic_unknown

# Create a temporary netlist file for this example script
netlist_content = """
* Voltage Divider for Goal Seeking Vin_unknown
.PARAM Vin_unknown = Vin_unknown
.PARAM R1_val = 1k
.PARAM R2_val = 1k
.PARAM V_target_level = V_target_level
VS Vin_node 0 Vin_unknown
R1 Vin_node N_out R1_val
R2 N_out 0 R2_val
.end
"""
temp_netlist_file = "_temp_goal_seek_vdiv.sp" # Created in the current working directory
with open(temp_netlist_file, 'w') as f:
    f.write(netlist_content)

# Define parameters for goal seeking
unknown_to_solve = 'Vin_unknown'
target_quantity = 'V(N_out)'  # Equivalent to V(N_out,0)
target_value_expression = 'V_target_level' # Target V_out is the symbolic V_target_level

print(f"Attempting to solve for '{unknown_to_solve}' such that {target_quantity} = {target_value_expression}")

solutions = solve_for_symbolic_unknown(
    netlist_path=temp_netlist_file,
    unknown_param_name_str=unknown_to_solve,
    target_quantity_str=target_quantity,
    target_value_expr_str=target_value_expression
)

if solutions:
    print(f"Found solution(s) for {unknown_to_solve}:")
    for sol_idx, sol_expr in enumerate(solutions):
        print(f"  Solution {sol_idx + 1}: {sol_expr}")
        # For this voltage divider, V(N_out) = Vin_unknown * R2_val / (R1_val + R2_val)
        # If R1_val and R2_val are treated as symbols (e.g. .PARAM R1_val=R1_val),
        # then Vin_unknown = V_target_level * (R1_val + R2_val) / R2_val
        # If R1_val=1k, R2_val=1k are fixed numbers, then Vin_unknown = 2 * V_target_level.
        # The current netlist example uses fixed 1k values, so the symbolic solver
        # within scs_instance_hier will substitute these before solve_for_symbolic_unknown gets it.
        # The actual expression derived by top_instance.v() will have these numerical values.

        # Let's verify the expected form if R1_val and R2_val were symbolic.
        # R1_s, R2_s, VT_s = sympy.symbols('R1_val R2_val V_target_level')
        # expected_symbolic_form = VT_s * (R1_s + R2_s) / R2_s
        # print(f"  Expected general symbolic form (if R1, R2 were symbols): {expected_symbolic_form}")
        # If R1=1k, R2=1k, then expected is V_target_level * (1000 + 1000) / 1000 = 2 * V_target_level
        V_target_level_sym = sympy.symbols('V_target_level')
        expected_numerical_form = 2 * V_target_level_sym
        print(f"  Expected form (with R1=1k, R2=1k): {expected_numerical_form}")
        if sympy.simplify(sol_expr - expected_numerical_form) == 0:
             print(f"  Solution {sol_idx+1} matches expected numerical form.")
        else:
             print(f"  Solution {sol_idx+1} does NOT match expected numerical form. Difference: {sympy.simplify(sol_expr - expected_numerical_form)}")


else:
    print(f"No solution found for {unknown_to_solve} or an error occurred.")

# Cleanup
if os.path.exists(temp_netlist_file):
    os.remove(temp_netlist_file)
```

This example demonstrates how to set up the problem and call the function. The actual expression for `V(N_out)` would be derived by the internal symbolic solver, and then `sympy.solve` would be used to find `Vin_unknown`.
Refer to the example script `examples/Symbolic_Goal_Seeking/voltage_divider_goal_seek.py` for a runnable demonstration.


## Dependencies

This project relies on the following Python libraries:
*   **Sympy:** For symbolic mathematics (core of the solver).
*   **Numpy:** Used in some analysis functions (e.g., for generating points for sweeps in `scs_analysis.py` and in the numerical MNA solver).
*   **Matplotlib:** Used for plotting in `scs_analysis.py` (e.g., for DC/AC analysis plots). Not directly used by `SymbolicCircuitProblemSolver` or the formula derivation/verification examples unless they invoke plotting analyses.
*   **PyYAML:** For loading and parsing YAML configuration files (used by `VerificationSuite` in `scs_verification.py`).

Please ensure these are installed in your Python environment (e.g., via `pip install sympy numpy matplotlib pyyaml`).
