# Symbolic Circuit Solver and Analyzer

This project provides tools for symbolic analysis of electronic circuits described by SPICE-like netlists. It can generate and solve Modified Nodal Analysis (MNA) equations symbolically, allowing for goal-seeking and parametric analysis.

## Features (Overview)

*   Parsing of SPICE-like netlists.
*   Symbolic solution of DC operating points (node voltages, element currents, power).
*   **Generalized Symbolic Circuit Analysis**: Solve the fundamental circuit equations (KCL, KVL, V-I relations) for user-defined knowns and unknowns.
*   **Symbolic Goal Seeking**: Determine the value of one circuit parameter required to achieve a specific target for a voltage, current, or power.
*   (Placeholder for other features like Verification Framework, etc.)

## Generalized Symbolic Circuit Analysis

This powerful feature allows users to solve the fundamental system of circuit equations under various scenarios. The primary function for this is `solve_circuit_for_unknowns`.

### `solve_circuit_for_unknowns()`

This function provides a direct way to work with the circuit's MNA (Modified Nodal Analysis) equation system.

**Function Signature (Conceptual):**
`solve_circuit_for_unknowns(netlist_path, known_values_map_str_keys, unknowns_to_solve_for_str, top_instance_optional=None)`

**Parameters:**

*   `netlist_path` (str): Path to the SPICE netlist file.
*   `known_values_map_str_keys` (dict): A dictionary where:
    *   Keys are **strings** representing the symbolic parameter names as defined in the SPICE netlist (e.g., the `X_sym` in `.PARAM R1_val = X_sym`).
    *   Values can be:
        *   Numerical values (e.g., `100`, `1.5`).
        *   Sympy symbols, allowing results to be expressed in terms of these "scenario" symbols.
    *   Example: `{'R_load_sym': 50, 'Gain_param': sympy.symbols('A_val')}`
*   `unknowns_to_solve_for_str` (list[str]): A list of strings specifying the variables for which symbolic solutions are desired. These strings can be:
    *   Node voltages: e.g., `"V_N1"` for the voltage at node `N1`.
    *   Element currents: e.g., `"I_R1"` for the current through element `R1`. The direction is typically defined as flowing from the element's first listed node to its second.
    *   SPICE parameters: e.g., `"R1_sym"` if you want to solve for a parameter itself (it should not also be in `known_values_map_str_keys`).
    *   If this list is empty or `None`, the function will attempt to solve for all defined node voltages, element currents, and any SPICE parameters not specified in `known_values_map_str_keys`.
*   `top_instance_optional` (scs_instance_hier.Instance, optional): An optional, pre-parsed circuit instance. If provided, `netlist_path` might be ignored.

**Returns:**

*   (list[dict]): A list of solution dictionaries. Each dictionary maps Sympy `Symbol` objects (for the solved unknowns) to their resulting Sympy expressions. If the system has one unique solution, the list will contain one dictionary. Multiple dictionaries imply multiple solution sets. An empty list means no solution was found.

**Key Concept:**

The `solve_circuit_for_unknowns` function (via the helper `generate_circuit_equations`) first constructs the complete set of fundamental circuit equations:
*   Kirchhoff's Current Law (KCL) for each node.
*   Voltage-Current (V-I) relationships for each element (e.g., Ohm's Law for resistors, constitutive equations for controlled sources).
*   Equations from explicit voltage definitions (e.g., `V_N_supply = Vin_s` for a voltage source `Vin N_supply 0 Vin_s`).

The user then defines a scenario by specifying which symbolic parameters from the netlist (e.g., `R1_s`, `Vin_s`) are considered "known" for this analysis by providing their values (numeric or other scenario symbols) in `known_values_map_str_keys`. Any parameters not in this map are treated as additional unknowns if not explicitly listed in `unknowns_to_solve_for_str`.
The function then uses `sympy.solve()` to find expressions for the `unknowns_to_solve_for_str` in terms of the "known" scenario values/symbols. To obtain solutions for primary variables (like an input voltage) fully in terms of scenario parameters, it's often necessary to include all intermediate circuit variables (other node voltages and element currents) in the `unknowns_to_solve_for_str` list, so they can be algebraically eliminated by Sympy.

### Example: H-Bridge Symbolic Analysis

An example (`examples/Symbolic_Goal_Seeking/h_bridge_analysis.py`) demonstrates this for an H-bridge circuit.

**(a) Netlist:** The H-bridge is defined with symbolic parameters for the input voltage source (`Vin_s`) and all resistors: upper-left (`Rul_s`), lower-left (`Rll_s`), upper-right (`Rur_s`), lower-right (`Rlr_s`), and the load (`Rload_s`). Each has a `.PARAM X_s = X_s` definition.

**(b) Scenario & Constraint:**
The analysis aims to find the required input voltage (`Vin_s`) under certain conditions.
*   The switch resistances are assigned symbolic scenario values representing their state (e.g., `sR_on` for "on" switches, `sR_off` for "off" switches).
*   The load resistance `Rload_s` is also represented by a scenario symbol, say `sRload`.
*   A **constraint** is added as an extra equation: the voltage across the load (`V_Na - V_Nb`) must equal a target symbolic value, `sVload_target`.

**(c) Goal:**
Solve for the circuit's main input voltage parameter `Vin_s` (the value of the `Vin` source) and the current through it (`I_Vin`) in terms of `sR_on`, `sR_off`, `sRload`, and `sVload_target`.

**(d) Setup for `solve_circuit_for_unknowns` (Conceptual):**

*   `known_values_map_str_keys`:
    ```python
    # Scenario symbols defined using sympy.symbols('R_on R_off ...')
    # sR_on, sR_off, sRload, sVload_target are Sympy symbols.
    knowns = {
        'Rul_s': sR_on,    # Upper-left is ON
        'Rll_s': sR_off,   # Lower-left is OFF
        'Rur_s': sR_off,   # Upper-right is OFF
        'Rlr_s': sR_on,    # Lower-right is ON
        'Rload_s': sRload
    }
    ```
    (Note: `sVload_target` is not in `known_values_map_str_keys` because it's part of an added constraint equation, not a direct substitution for a `.PARAM`).

*   `unknowns_to_solve_for_str`:
    To ensure `Vin_s` and `I_Vin` are expressed in terms of the scenario symbols, all other circuit variables are included:
    ```python
    unknowns = [
        'Vin_s', 'I_Vin',        # Primary targets
        'V_N_supply', 'V_Na', 'V_Nb', # All node voltages
        'I_Rul', 'I_Rll', 'I_Rur', 'I_Rlr', 'I_Rload' # All element currents (except I_Vin)
    ]
    ```
The function then provides symbolic expressions for `Vin_s` and `I_Vin` which can be further evaluated numerically for specific values of `sR_on`, `sR_off`, `sRload`, and `sVload_target`.

## Simplified Goal Seeking: `solve_for_symbolic_unknown()`

For simpler scenarios where the goal is to find the value of a *single circuit parameter* (e.g., `Rfeedback_sym`) such that a *single circuit quantity* (e.g., `V(N_out)`) achieves a desired symbolic or numerical value, the function `solve_for_symbolic_unknown()` can be used. It leverages the circuit instance's `.v()`, `.i()`, and `.p()` methods to define the target expression and works by adding one goal equation to the system.

## Installation

(Placeholder for installation instructions)

## Usage

(Placeholder for general usage instructions)

## Examples

*   `examples/Symbolic_Goal_Seeking/h_bridge_analysis.py`: Demonstrates using `solve_circuit_for_unknowns` for H-bridge analysis.
*   (Placeholder for other examples)

## Contributing

(Placeholder for contribution guidelines)
