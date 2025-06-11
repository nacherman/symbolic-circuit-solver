"""
Framework for Verifying Symbolic Circuit Formulas against Numerical Simulations.

This module provides tools to compare symbolic expressions (e.g., for node voltages,
element currents, or power) derived from a circuit's symbolic solution against
numerical results obtained from DC MNA simulations. It allows for systematic
testing across various parameter values.

Key features include:
- A `VerificationSuite` class to manage and run a collection of verification tasks
  defined for a single netlist, loadable from a YAML configuration.
- Individual `verify_*_formula` functions for direct, standalone verification of
  specific symbolic expressions.
- Generation of test points (parameter value sets) using strategies like random
  linear or log-scale distributions, with options for custom value lists and
  symbol-specific ranges.
- Comparison of symbolic evaluation results with numerical simulation results,
  reporting matches and mismatches with detailed information.

The primary goal is to ensure the correctness and consistency of symbolic
formulas by checking them against a trusted numerical solver over a range of
input parameters.
"""
import sympy
import os
import sys
import yaml

# Adjust sys.path for direct script execution
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
path_to_add = os.path.dirname(project_root)
if path_to_add not in sys.path:
    sys.path.insert(0, path_to_add)

from symbolic_circuit_solver_master import scs_utils
from symbolic_circuit_solver_master import scs_numerical_solver
from symbolic_circuit_solver_master import scs_errors

# import yaml # Already imported at the top level of the module
import argparse # Added for CLI argument parsing

# Imports needed for the __main__ test block (and VerificationSuite)
from symbolic_circuit_solver_master import scs_circuit
from symbolic_circuit_solver_master import scs_parser as scs_parser_module
from symbolic_circuit_solver_master import scs_instance_hier

def _verify_generic_expression(
    symbolic_expr,
    target_identifier: str,
    netlist_path: str,
    num_test_sets: int,
    user_param_override_values: dict,
    get_numerical_value_callback,
    expression_type_str: str,
    stop_on_first_mismatch: bool = False,
    symbol_specific_random_ranges: dict = None # New parameter
) -> dict:
    """
    Generic private function to verify a symbolic expression against numerical simulations.
    """
    if not hasattr(symbolic_expr, 'free_symbols'):
        print(f"Warning: symbolic_expr for {expression_type_str} '{target_identifier}' does not have free_symbols. Type: {type(symbolic_expr)}")
        free_symbols = set()
    else:
        free_symbols = symbolic_expr.free_symbols

    if user_param_override_values:
        for s_name in user_param_override_values.keys():
            found = any(s.name == s_name for s in free_symbols)
            if not found and free_symbols:
                print(f"Info: Override key '{s_name}' not in formula's free symbols: {[s.name for s in free_symbols]}. It will be passed to numerical solver if it's a netlist .PARAM.")

    list_of_test_param_maps = scs_utils.generate_test_points(
        symbols_set=free_symbols,
        num_sets=num_test_sets,
        # custom_symbol_value_lists can be passed here if needed in future
        # Default generation mode is 'cycle', to use random, it must be specified.
        # For verification, random might be more robust.
        generation_mode='random', # Using random for verification test points
        log_scale_random_for_R=True, # Using log scale for R for verification
        symbol_specific_random_ranges=symbol_specific_random_ranges # Pass through
    )

    mismatches_details = []
    matches_count = 0
    actual_tests_run = 0

    result_key_name = 'target_node' if expression_type_str == "Node Voltage" else 'target_element'
    # Handle cases where num_test_sets might be 0 or formula is constant
    if num_test_sets == 0:
        return {
            'verified_all': True, 'total_tests_planned': 0, 'total_tests_run': 0, 'matches': 0, 'mismatches': 0,
            'mismatches_details': [], result_key_name: target_identifier, 'symbolic_formula': str(symbolic_expr)
        }

    if not list_of_test_param_maps and free_symbols: # Should only happen if num_test_sets was >0 but generation failed
        print(f"Warning: No test points generated for {expression_type_str} formula for '{target_identifier}'.")
        return {
            'verified_all': False, 'total_tests_planned': num_test_sets, 'total_tests_run': 0, 'matches': 0, 'mismatches': 0,
            'mismatches_details': [{'error': f'No test points generated for {expression_type_str} formula.'}],
            result_key_name: target_identifier, 'symbolic_formula': str(symbolic_expr)
        }
    elif not free_symbols and symbolic_expr is not None: # Constant formula
        print(f"Info: {expression_type_str} formula for '{target_identifier}' is a constant: {symbolic_expr}")
        actual_tests_run = 1 # Only one test for a constant formula

        numerical_solver_params_for_constant = {}
        # For constant expressions, overrides are typically for other circuit params not in this specific formula
        if user_param_override_values:
            print(f"Info: Applying user overrides for constant formula check (passed to numerical solver): {user_param_override_values}")
            for k_str, v_val in user_param_override_values.items():
                 numerical_solver_params_for_constant[sympy.symbols(k_str)] = v_val

        symbolic_eval_value = scs_utils.evaluate_symbolic_expr(symbolic_expr, {})

        comparison_symbolic_eval_value = symbolic_eval_value
        is_source_power_test = False
        if expression_type_str == "Element Power" and \
           target_identifier.lower()[0] in ('v', 'e', 'h', 'i', 'g', 'f') and \
           symbolic_eval_value is not None:
            is_source_power_test = True
            comparison_symbolic_eval_value = -symbolic_eval_value
            print(f"  Note: For source '{target_identifier}', comparing numerical absorbed power with -1 * symbolic power (original symbolic: {symbolic_eval_value}). Using {comparison_symbolic_eval_value} for comparison.")

        numerical_results = scs_numerical_solver.solve_dc_numerically(netlist_path, numerical_solver_params_for_constant)
        numerical_value = None
        if numerical_results and isinstance(numerical_results, dict):
            numerical_value = get_numerical_value_callback(numerical_results, target_identifier)

        if numerical_value is not None and comparison_symbolic_eval_value is not None:
            if scs_utils.compare_numerical_values(numerical_value, comparison_symbolic_eval_value):
                matches_count = 1
            else:
                mismatches_details.append({
                    'params_map_sympy_keys': {}, # No varying params for constant formula
                    'params_str': 'Constant Formula (with overrides if any)',
                    'numerical_value': numerical_value,
                    'symbolic_eval_value_original': symbolic_eval_value,
                    'compared_symbolic_value_as_absorbed': comparison_symbolic_eval_value if is_source_power_test else symbolic_eval_value,
                    'note': f'Constant {expression_type_str} formula verification error'
                })
        else:
            mismatches_details.append({
                'params_map_sympy_keys': {},
                'params_str': 'Constant Formula (with overrides if any)',
                'numerical_value': numerical_value,
                'symbolic_eval_value_original': symbolic_eval_value,
                'compared_symbolic_value_as_absorbed': comparison_symbolic_eval_value if is_source_power_test and symbolic_eval_value is not None else symbolic_eval_value,
                'note': f'Failed to get both values for constant {expression_type_str} formula verification'
            })
        # If stop_on_first_mismatch is True and there's a mismatch, this path will effectively stop (as actual_tests_run = 1)
    else: # Symbolic formula with free variables
        for i, base_param_map_sympy_keys in enumerate(list_of_test_param_maps):
            actual_tests_run = i + 1
            print(f"\n--- Verifying {expression_type_str} Test Point Set {i+1}/{num_test_sets} for '{target_identifier}' ---")

            current_symbolic_eval_params = base_param_map_sympy_keys.copy()
            current_numerical_solver_params = base_param_map_sympy_keys.copy()

            if user_param_override_values:
                print(f"  Applying overrides: {user_param_override_values}")
                # user_param_override_values now comes with Sympy keys from VerificationSuite.load_from_yaml
                for sym_key, fixed_value in user_param_override_values.items():
                    if sym_key in current_symbolic_eval_params: # Check if the override is for a free_symbol of the expression
                        current_symbolic_eval_params[sym_key] = fixed_value
                        current_numerical_solver_params[sym_key] = fixed_value
                    else:
                        # If not a free_symbol, it might be another netlist .PARAM to set for numerical solver
                        print(f"    Note: Override for '{sym_key.name}' not in formula's free symbols. Applying to numerical solver only.")
                        current_numerical_solver_params[sym_key] = fixed_value # Assumes sym_key is already a Symbol object

            current_param_values_str = {str(k): v for k, v in current_symbolic_eval_params.items()}
            print(f"  Testing with parameters (for symbolic eval): {current_param_values_str}")
            if current_numerical_solver_params != current_symbolic_eval_params:
                current_num_solver_params_str = {str(k): v for k,v in current_numerical_solver_params.items()}
                print(f"  Parameters for numerical solver: {current_num_solver_params_str}")

            numerical_value = None
            symbolic_eval_value = None
            mismatch_this_point = False

            try:
                numerical_results = scs_numerical_solver.solve_dc_numerically(netlist_path, current_numerical_solver_params)
                if numerical_results and isinstance(numerical_results, dict):
                    numerical_value = get_numerical_value_callback(numerical_results, target_identifier)
                else:
                    print(f"  Warning: Numerical solve failed or did not return expected structure.")
                    print(f"  Numerical results: {numerical_results}")

                symbolic_eval_value = scs_utils.evaluate_symbolic_expr(symbolic_expr, current_symbolic_eval_params)

                comparison_symbolic_eval_value = symbolic_eval_value
                is_source_power_test = False
                if expression_type_str == "Element Power" and \
                   target_identifier.lower()[0] in ('v', 'e', 'h', 'i', 'g', 'f') and \
                   symbolic_eval_value is not None:
                    is_source_power_test = True
                    comparison_symbolic_eval_value = -symbolic_eval_value
                    print(f"  Note: For source '{target_identifier}', comparing numerical absorbed power with -1 * symbolic power (original symbolic (supplied?): {symbolic_eval_value}). Using {comparison_symbolic_eval_value} for comparison.")

                print(f"  Numerical {expression_type_str} for '{target_identifier}': {numerical_value}")
                print(f"  Symbolic Eval {expression_type_str} for '{target_identifier}' (original): {symbolic_eval_value}")
                if is_source_power_test:
                     print(f"  Symbolic Eval {expression_type_str} for '{target_identifier}' (for comparison, as absorbed): {comparison_symbolic_eval_value}")

                if numerical_value is not None and comparison_symbolic_eval_value is not None:
                    if scs_utils.compare_numerical_values(numerical_value, comparison_symbolic_eval_value):
                        matches_count += 1
                        print("  Status: MATCH")
                    else:
                        mismatch_this_point = True
                        mismatches_details.append({
                            'param_map': current_symbolic_eval_params,
                            'params_str': current_param_values_str,
                            'numerical_value': numerical_value,
                            'symbolic_eval_value_original': symbolic_eval_value,
                            'compared_symbolic_value_as_absorbed': comparison_symbolic_eval_value if is_source_power_test else "N/A"
                        })
                        print("  Status: MISMATCH")
                else:
                    mismatch_this_point = True
                    mismatches_details.append({
                        'param_map': current_symbolic_eval_params,
                        'params_str': current_param_values_str,
                        'numerical_value': numerical_value,
                        'symbolic_eval_value_original': symbolic_eval_value,
                        'compared_symbolic_value_as_absorbed': comparison_symbolic_eval_value if is_source_power_test else "N/A",
                        'note': f'One or both evaluation methods failed to produce a {expression_type_str.lower()} value.'
                    })
                    print(f"  Status: ERROR (one or both {expression_type_str.lower()} evaluations failed)")
            except Exception as e_loop:
                mismatch_this_point = True
                print(f"  ERROR during {expression_type_str.lower()} test point processing: {type(e_loop).__name__}: {e_loop}")
                import traceback
                traceback.print_exc()
                mismatches_details.append({
                    'param_map': current_symbolic_eval_params,
                    'params_str': current_param_values_str,
                    'error': str(e_loop)})

            if mismatch_this_point and stop_on_first_mismatch:
                print(f"  STOPPING further tests for '{target_identifier}' due to mismatch and stop_on_first_mismatch=True.")
                break

    if actual_tests_run == 0 and num_test_sets > 0 and not (not free_symbols and symbolic_expr is not None):
        final_verified_all = False
    elif stop_on_first_mismatch and len(mismatches_details) > 0 and actual_tests_run < num_test_sets :
        final_verified_all = False
    else:
        final_verified_all = (len(mismatches_details) == 0) and \
                             (matches_count == actual_tests_run) and \
                             (actual_tests_run > 0 or (actual_tests_run == 0 and num_test_sets == 0))

    return {
        'verified_all': final_verified_all,
        'total_tests_planned': num_test_sets,
        'total_tests_run': actual_tests_run,
        'matches': matches_count, 'mismatches': len(mismatches_details),
        'mismatches_details': mismatches_details, result_key_name: target_identifier,
        'symbolic_formula': str(symbolic_expr)
    }

def verify_node_voltage_formula(
    symbolic_expr, target_node_name: str, netlist_path: str,
    num_test_sets: int = 5, user_param_override_values: dict = None,
    stop_on_first_mismatch: bool = False, symbol_specific_random_ranges: dict = None) -> dict:
    """
    Verifies a symbolic node voltage formula against numerical simulations.

    This function is a specific wrapper around `_verify_generic_expression` tailored
    for node voltage verifications. It can be used standalone or by `VerificationSuite`.

    Args:
        symbolic_expr: The Sympy expression representing the node voltage formula.
        target_node_name (str): The name of the node whose voltage is being verified
                                (e.g., "N_out"). Assumed to be voltage relative to ground.
        netlist_path (str): Path to the netlist file for numerical simulation.
        num_test_sets (int, optional): Number of random parameter sets to test. Defaults to 5.
        user_param_override_values (dict, optional): Dictionary to override specific
                                                     parameter values for all test sets.
                                                     Keys are Sympy symbols or string names.
        stop_on_first_mismatch (bool, optional): If True, stops after the first mismatch.
                                                 Defaults to False.
        symbol_specific_random_ranges (dict, optional): Maps Sympy symbols or string names
                                                        to (min, max) tuples for random generation,
                                                        overriding global defaults.

    Returns:
        dict: A summary dictionary of the verification results, including pass/fail status,
              number of matches/mismatches, and details of any mismatches.
    """
    def get_node_voltage_from_results(results_dict, node_name):
        if results_dict and 'node_voltages' in results_dict:
            return results_dict['node_voltages'].get(node_name)
        return None
    return _verify_generic_expression(symbolic_expr, target_node_name, netlist_path, num_test_sets,
                                      user_param_override_values, get_node_voltage_from_results, "Node Voltage",
                                      stop_on_first_mismatch, symbol_specific_random_ranges)

def verify_element_current_formula(
    symbolic_expr_for_current, target_element_name: str, netlist_path: str,
    num_test_sets: int = 5, user_param_override_values: dict = None,
    stop_on_first_mismatch: bool = False, symbol_specific_random_ranges: dict = None) -> dict:
    """
    Verifies a symbolic element current formula against numerical simulations.

    Wrapper around `_verify_generic_expression` for element current.
    Can be used standalone or by `VerificationSuite`.

    Args:
        symbolic_expr_for_current: Sympy expression for the element's current.
        target_element_name (str): Name of the element (e.g., "R1").
        netlist_path (str): Path to the netlist file.
        Other args are identical to `verify_node_voltage_formula`.

    Returns:
        dict: A summary dictionary of verification results.
    """
    def get_element_current_from_results(results_dict, element_name):
        if results_dict and 'element_currents' in results_dict:
            return results_dict['element_currents'].get(element_name)
        return None
    return _verify_generic_expression(symbolic_expr_for_current, target_element_name, netlist_path,
                                      num_test_sets, user_param_override_values, get_element_current_from_results, "Element Current",
                                      stop_on_first_mismatch, symbol_specific_random_ranges)

def verify_vsource_current_formula(
    symbolic_expr, vsource_name: str, netlist_path: str,
    num_test_sets: int = 5, user_param_override_values: dict = None,
    stop_on_first_mismatch: bool = False, symbol_specific_random_ranges: dict = None) -> dict:
    """
    Verifies a symbolic voltage source current formula against numerical simulations.

    Wrapper around `_verify_generic_expression` for current through a voltage source.
    Can be used standalone or by `VerificationSuite`.

    Args:
        symbolic_expr: Sympy expression for the voltage source's current.
        vsource_name (str): Name of the voltage source element (e.g., "Vin", "E_opamp").
        netlist_path (str): Path to the netlist file.
        Other args are identical to `verify_node_voltage_formula`.

    Returns:
        dict: A summary dictionary of verification results.
    """
    def get_vsource_current_from_results(results_dict, name):
        if results_dict and 'vsource_currents' in results_dict:
            return results_dict['vsource_currents'].get(name)
        return None
    return _verify_generic_expression(symbolic_expr, vsource_name, netlist_path, num_test_sets,
                                      user_param_override_values, get_vsource_current_from_results, "VSource Current",
                                      stop_on_first_mismatch, symbol_specific_random_ranges)

def verify_element_power_formula(
    symbolic_expr_for_power, target_element_name: str, netlist_path: str,
    num_test_sets: int = 5, user_param_override_values: dict = None,
    stop_on_first_mismatch: bool = False, symbol_specific_random_ranges: dict = None) -> dict:
    """
    Verifies a symbolic element power formula against numerical simulations.

    Wrapper around `_verify_generic_expression` for element power.
    Can be used standalone or by `VerificationSuite`.

    Args:
        symbolic_expr_for_power: Sympy expression for the element's power.
        target_element_name (str): Name of the element (e.g., "R1", "Vin").
        netlist_path (str): Path to the netlist file.
        Other args are identical to `verify_node_voltage_formula`.

    Returns:
        dict: A summary dictionary of verification results.
    """
    def get_element_power_from_results(results_dict, element_name):
        if results_dict and 'element_power' in results_dict:
            return results_dict['element_power'].get(element_name)
        return None
    return _verify_generic_expression(symbolic_expr_for_power, target_element_name, netlist_path,
                                      num_test_sets, user_param_override_values, get_element_power_from_results, "Element Power",
                                      stop_on_first_mismatch, symbol_specific_random_ranges)

# Helper for printing mismatch details (used by VerificationSuite and standalone tests)
def print_mismatch_details_helper(details):
    """
    Prints detailed information about mismatches found during verification.

    Args:
        details (list[dict]): A list of mismatch detail dictionaries, typically
                              from the 'mismatches_details' field of a verification
                              summary. Each dictionary contains information about
                              a specific failing test point.
    """
    for detail in details:
        param_map_for_print = detail.get('param_map', detail.get('params_map_sympy_keys'))
        if isinstance(param_map_for_print, dict):
            param_map_str = {str(k): v for k, v in param_map_for_print.items()} # Ensure keys are strings for print
            print(f"    Failing Parameter Map: {param_map_str}")
        else:
            # Fallback for older format or constant expression cases
            print(f"    Params: {detail.get('params_str', 'N/A')}")

        s_val = detail.get('symbolic_eval_value_original', detail.get('symbolic_eval_value'))
        n_val = detail.get('numerical_value')
        print(f"    Symbolic Value: {s_val}")
        print(f"    Numerical Value: {n_val}")

        if detail.get('compared_symbolic_value_as_absorbed') not in ["N/A", None]:
            print(f"    Compared Symbolic (Power Absorbed Convention): {detail.get('compared_symbolic_value_as_absorbed')}")

        if n_val is not None and s_val is not None:
            try:
                n_val_f = float(n_val)
                s_val_f = float(s_val)
                if n_val_f != 0:
                    perc_diff = abs(s_val_f - n_val_f) / abs(n_val_f) * 100
                    print(f"    Percentage Difference (vs Numerical): {perc_diff:.4f}%")
                elif s_val_f != 0:
                    print(f"    Percentage Difference: Inf (Numerical is zero, Symbolic is non-zero)")
                else:
                    print(f"    Percentage Difference: 0.0000% (Both zero)")
            except (ValueError, TypeError) as e_conv:
                print(f"    Percentage Difference: N/A (Could not convert symbolic '{s_val}' or numerical '{n_val}' to float for diff: {e_conv})")

        if 'note' in detail: print(f"    Note: {detail['note']}")
        if 'error' in detail: print(f"    Error: {detail['error']}")
        print("    ----")

class VerificationSuite:
    """
    Manages and runs a suite of verification tasks for a single circuit netlist.

    This class allows users to define multiple verification tasks (e.g., checking
    different node voltages, element currents, or powers) for a circuit specified
    by a netlist file. It handles parsing the netlist and solving for symbolic
    expressions once, then uses these for all tasks in the suite.
    The suite can be configured programmatically by adding tasks or loaded from
    a YAML file.

    Typical Usage:
    1. Instantiate `VerificationSuite` with the `netlist_path`.
    2. Add verification tasks using `add_task()` or load a suite using
       `VerificationSuite.load_from_yaml()`.
    3. Call the `run()` method to execute all tasks.
    4. The `run()` method returns a summary dictionary containing overall results
       and detailed results for each task.

    The results dictionary from `run()` includes:
    - 'suite_name': Name of the suite.
    - 'status': 'PASS' or 'FAIL' for the entire suite.
    - 'passed_tasks': Number of tasks that passed.
    - 'total_tasks': Total number of tasks executed.
    - 'task_results': A list of individual task summary dictionaries.
    """
    def __init__(self, netlist_path: str, suite_name: str = None):
        """
        Initializes a VerificationSuite.

        Args:
            netlist_path (str): The file path to the SPICE-like netlist.
            suite_name (str, optional): A descriptive name for this verification suite.
                                        If None, a name is generated from the netlist filename.
        """
        self.netlist_path = netlist_path
        self.suite_name = suite_name if suite_name else f"Verification Suite for {os.path.basename(netlist_path)}"
        self.tasks = []
        self.top_instance = None
        self.verification_functions_map = {
            'node_voltage': verify_node_voltage_formula,
            'element_current': verify_element_current_formula,
            'vsource_current': verify_vsource_current_formula,
            'element_power': verify_element_power_formula,
        }

    def add_task(self, task_name: str, verification_type: str, target_identifier: str,
                 num_test_sets: int = 5, symbol_specific_random_ranges: dict = None,
                 user_param_override_values: dict = None, stop_on_first_mismatch: bool = False):
        """
        Adds a verification task to the suite.

        Args:
            task_name (str): A descriptive name for this specific verification task.
            verification_type (str): The type of quantity to verify. Supported types are:
                                     'node_voltage', 'element_current',
                                     'vsource_current', 'element_power'.
            target_identifier (str): The name of the node or element to target.
                                     For 'node_voltage', if a single node name (e.g., "N1")
                                     is given, it's assumed relative to ground ("N1,0").
                                     For differential voltage, use "N1,N2".
                                     For elements/vsources, use their netlist name (e.g., "R1", "Vin").
            num_test_sets (int, optional): Number of random parameter sets for verification.
                                           Defaults to 5.
            symbol_specific_random_ranges (dict, optional): Maps Sympy symbols or string names
                                                            to (min, max) tuples for random
                                                            value generation for specific symbols.
                                                            Defaults to None.
                                                            Note: If loaded from YAML, string keys
                                                            are converted to Sympy symbols by loader.
            user_param_override_values (dict, optional): Dictionary to override specific
                                                         parameter values (Sympy symbol or string name
                                                         keys) for all test sets within this task.
                                                         Defaults to None.
                                                         Note: If loaded from YAML, string keys
                                                         are converted to Sympy symbols by loader.
            stop_on_first_mismatch (bool, optional): If True, this task stops testing
                                                     after the first mismatch.
                                                     Defaults to False.
        """
        if verification_type not in self.verification_functions_map:
            print(f"Error: Unknown verification_type '{verification_type}' for task '{task_name}'. Skipping.")
            return

        self.tasks.append({
            'task_name': task_name,
            'verification_type': verification_type,
            'target_identifier': target_identifier,
            'num_test_sets': num_test_sets,
            'symbol_specific_random_ranges': symbol_specific_random_ranges,
            'user_param_override_values': user_param_override_values,
            'stop_on_first_mismatch': stop_on_first_mismatch,
        })
        print(f"Task '{task_name}' ({verification_type} for {target_identifier}) added to suite '{self.suite_name}'.")

    def _prepare_instance(self) -> bool:
        print(f"\n--- Preparing Circuit Instance for Suite: {self.suite_name} ---")
        print(f"Parsing netlist: {self.netlist_path}")
        try:
            top_circuit = scs_circuit.TopCircuit()
            parsed_circuit = scs_parser_module.parse_file(self.netlist_path, top_circuit)
            if not parsed_circuit:
                print("Error: Netlist parsing failed.")
                return False

            print("Creating top instance...")
            self.top_instance = scs_instance_hier.make_top_instance(parsed_circuit)
            if not self.top_instance:
                print("Error: Instance creation failed.")
                return False

            print("Solving circuit symbolically for the suite...")
            self.top_instance.solve() # Solve once for all tasks in the suite
            print("Symbolic solution complete for the suite.")
            return True
        except Exception as e:
            print(f"Error during instance preparation or solving: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _derive_symbolic_expr(self, verification_type: str, target_identifier: str):
        if not self.top_instance:
            print("Error: Top instance not prepared. Cannot derive symbolic expression.")
            return None

        print(f"Deriving symbolic expression for {verification_type} of '{target_identifier}'...")
        expr = None
        try:
            if verification_type == 'node_voltage':
                # Assuming target_identifier like 'N1' means V(N1,0) or 'N1,N2' means V(N1,N2)
                nodes = target_identifier.split(',')
                if len(nodes) == 1:
                    expr = self.top_instance.v(nodes[0], '0')
                elif len(nodes) == 2:
                    expr = self.top_instance.v(nodes[0], nodes[1])
                else:
                    print(f"Error: Invalid target_identifier '{target_identifier}' for node_voltage.")
                    return None
            elif verification_type == 'element_current' or verification_type == 'vsource_current':
                # Assuming .i() method works for both general elements and voltage sources names
                expr = self.top_instance.i(target_identifier)
            elif verification_type == 'element_power':
                expr = self.top_instance.p(target_identifier)
            else:
                print(f"Error: Unknown verification_type '{verification_type}' for expression derivation.")
                return None
            print(f"  Derived: {expr}")
            return expr
        except Exception as e:
            print(f"Error deriving symbolic expression for {target_identifier} ({verification_type}): {type(e).__name__} - {e}")
            return None

    def run(self, show_individual_task_summaries: bool = True):
        print(f"\n--- Running Verification Suite: {self.suite_name} ---")
        if not self._prepare_instance():
            return {
                'suite_name': self.suite_name,
                'status': 'ERROR_PREPARATION',
                'message': 'Failed to prepare circuit instance.',
                'passed_tasks': 0,
                'total_tasks': len(self.tasks),
                'task_results': []
            }

        suite_results = []
        overall_passed_count = 0

        for task_idx, task_params in enumerate(self.tasks):
            task_name = task_params['task_name']
            verification_type = task_params['verification_type']
            target_identifier = task_params['target_identifier']

            print(f"\n--- Running Task {task_idx+1}/{len(self.tasks)}: {task_name} ({verification_type} for {target_identifier}) ---")

            symbolic_expr = self._derive_symbolic_expr(verification_type, target_identifier)

            task_summary = None
            if symbolic_expr is None:
                task_summary = {
                    'task_name': task_name, 'verified_all': False, 'error': 'Failed to derive symbolic expression',
                    'target_identifier': target_identifier, 'verification_type': verification_type
                }
            else:
                verify_function = self.verification_functions_map.get(verification_type)
                if verify_function:
                    task_summary = verify_function(
                        symbolic_expr,
                        target_identifier,
                        self.netlist_path,
                        num_test_sets=task_params['num_test_sets'],
                        symbol_specific_random_ranges=task_params['symbol_specific_random_ranges'],
                        user_param_override_values=task_params['user_param_override_values'],
                        stop_on_first_mismatch=task_params['stop_on_first_mismatch']
                    )
                    task_summary['task_name'] = task_name # Ensure task_name is in summary
                else: # Should have been caught by add_task, but as a safeguard
                    task_summary = {
                        'task_name': task_name, 'verified_all': False, 'error': f'Unknown verification type {verification_type}',
                        'target_identifier': target_identifier, 'verification_type': verification_type
                    }

            suite_results.append(task_summary)
            if task_summary.get('verified_all', False):
                overall_passed_count += 1

            if show_individual_task_summaries:
                print(f"  Summary for Task '{task_name}': {'PASS' if task_summary.get('verified_all') else 'FAIL'}")
                if not task_summary.get('verified_all') and 'error' in task_summary:
                     print(f"    Error: {task_summary['error']}")
                if task_summary.get('mismatches_details'):
                    print("    Mismatch Details:")
                    print_mismatch_details_helper(task_summary['mismatches_details'])

        print(f"\n\n--- Overall Suite Summary for: {self.suite_name} ---")
        print(f"Passed {overall_passed_count}/{len(self.tasks)} tasks.")
        final_status = 'PASS' if overall_passed_count == len(self.tasks) else 'FAIL'

        if final_status == 'FAIL':
            print("\nDetails of failed tasks:")
            for result in suite_results:
                if not result.get('verified_all', False):
                    task_name = result.get('task_name', 'Unknown Task')
                    target_id = result.get('target_node', result.get('target_element', result.get('target_identifier', 'Unknown Target')))
                    v_type = result.get('verification_type', 'Unknown Type')
                    error_msg = result.get('error', '')
                    mismatches = result.get('mismatches', 0)

                    fail_reason = f"Mismatches: {mismatches}" if mismatches > 0 else f"Error: {error_msg}" if error_msg else "Reason not specified"
                    print(f"  - Task: '{task_name}' ({v_type} for '{target_id}') - Status: FAIL ({fail_reason})")

        return {
            'suite_name': self.suite_name,
            'status': final_status,
            'passed_tasks': overall_passed_count,
            'total_tasks': len(self.tasks),
            'task_results': suite_results
        }

    @classmethod
    def load_from_yaml(cls, yaml_filepath: str):
        """
        Loads a verification suite configuration from a YAML file.

        The YAML file should define `suite_name`, `netlist_path`, and a list of `tasks`.
        Each task specifies its `task_name`, `type`, `target`, and optional parameters
        like `num_sets`, `symbol_specific_random_ranges` (with string keys for symbols),
        `user_param_override_values` (with string keys for parameters), and
        `stop_on_first_mismatch`.

        String keys for symbols/parameters in `symbol_specific_random_ranges` and
        `user_param_override_values` from the YAML are converted to Sympy `Symbol`
        objects before being added to tasks.

        If `netlist_path` in YAML is relative, it's resolved relative to the
        YAML file's directory.

        Args:
            yaml_filepath (str): The path to the YAML configuration file.

        Returns:
            VerificationSuite or None: An instance of `VerificationSuite` configured
                                      according to the YAML file, or `None` if
                                      loading or parsing fails or essential data
                                      is missing.
        """
        print(f"\n--- Loading Verification Suite from YAML: {yaml_filepath} ---")
        try:
            with open(yaml_filepath, 'r') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            print(f"Error reading or parsing YAML file '{yaml_filepath}': {type(e).__name__} - {e}")
            return None

        suite_name = config.get('suite_name', f"Suite from {os.path.basename(yaml_filepath)}")
        netlist_path = config.get('netlist_path')

        if not netlist_path:
            print(f"Error: 'netlist_path' not found in YAML configuration '{yaml_filepath}'.")
            return None

        # Make netlist_path absolute if it's relative to the YAML file's directory
        if not os.path.isabs(netlist_path):
            yaml_dir = os.path.dirname(os.path.abspath(yaml_filepath))
            netlist_path = os.path.join(yaml_dir, netlist_path)
            print(f"  Adjusted relative netlist_path to: {netlist_path}")


        suite = cls(netlist_path=netlist_path, suite_name=suite_name)

        yaml_tasks = config.get('tasks', [])
        if not yaml_tasks:
            print(f"Warning: No tasks found in YAML configuration for suite '{suite_name}'.")

        for task_data in yaml_tasks:
            task_name = task_data.get('task_name')
            verification_type = task_data.get('type')
            target_identifier = task_data.get('target')

            # Check for essential keys
            missing_keys = []
            if task_name is None: missing_keys.append('task_name')
            if verification_type is None: missing_keys.append('type')
            if target_identifier is None: missing_keys.append('target')

            if missing_keys:
                effective_task_name = task_name if task_name else "Unnamed Task"
                print(f"Warning: Skipping task '{effective_task_name}' due to missing essential key(s): {', '.join(missing_keys)}.")
                continue

            # Get optional parameters, relying on add_task defaults if not present
            num_sets = task_data.get('num_sets', 5) # Default from add_task signature

            # Process symbol_specific_random_ranges: convert string keys to Symbol objects
            symbol_specific_ranges_sympykeyed = None
            symbol_specific_ranges_yaml = task_data.get('symbol_specific_random_ranges')
            if isinstance(symbol_specific_ranges_yaml, dict):
                symbol_specific_ranges_sympykeyed = {
                    sympy.symbols(str_key): value
                    for str_key, value in symbol_specific_ranges_yaml.items()
                }

            # Process user_param_override_values: convert string keys to Symbol objects
            user_param_overrides_sympykeyed = None
            user_param_overrides_yaml = task_data.get('user_param_override_values')
            if isinstance(user_param_overrides_yaml, dict):
                user_param_overrides_sympykeyed = {
                    sympy.symbols(str_key): value
                    for str_key, value in user_param_overrides_yaml.items()
                }

            stop_on_first_mismatch_yaml = task_data.get('stop_on_first_mismatch', False)

            suite.add_task(
                task_name=task_name,
                verification_type=verification_type,
                target_identifier=target_identifier,
                num_test_sets=num_sets,
                symbol_specific_random_ranges=symbol_specific_ranges_sympykeyed,
                user_param_override_values=user_param_overrides_sympykeyed,
                stop_on_first_mismatch=stop_on_first_mismatch_yaml
            )
        return suite


import argparse # Added for CLI argument parsing

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run a verification suite from a YAML configuration file.")
    parser.add_argument('yaml_filepath', help='Path to the YAML file defining the verification suite.')

    args = parser.parse_args()

    print(f"--- Verification Utility: Loading suite from {args.yaml_filepath} ---")

    suite = VerificationSuite.load_from_yaml(args.yaml_filepath)

    if suite:
        run_summary = suite.run(show_individual_task_summaries=True)

        print("\n--- Final Overall Suite Run Summary (from CLI execution) ---")
        print(f"Suite Name: {run_summary.get('suite_name')}")
        print(f"Overall Status: {run_summary.get('status')}")
        print(f"Passed Tasks: {run_summary.get('passed_tasks')}/{run_summary.get('total_tasks')}")

        if run_summary.get('status') == 'FAIL' or run_summary.get('status') == 'ERROR_PREPARATION':
            if run_summary.get('status') == 'ERROR_PREPARATION':
                print(f"Reason: {run_summary.get('message')}")
            else: # FAIL
                print("Details of failed/error tasks (from final summary object):")
                for task_res in run_summary.get('task_results', []):
                    if not task_res.get('verified_all', True): # Assume fail if 'verified_all' is missing
                        t_name = task_res.get('task_name', 'Unknown Task')
                        t_id_node = task_res.get('target_node')
                        t_id_elem = task_res.get('target_element')
                        t_id_fallback = task_res.get('target_identifier', 'Unknown Target')
                        target_id_str = t_id_node if t_id_node else t_id_elem if t_id_elem else t_id_fallback

                        t_vtype = task_res.get('verification_type', 'Unknown Type')
                        t_error = task_res.get('error', '')
                        t_mismatches = task_res.get('mismatches', 0)

                        reason = f"Mismatches: {t_mismatches}" if t_mismatches > 0 else f"Error: {t_error}" if t_error else "Not specified"
                        print(f"  - Task: '{t_name}' ({t_vtype} for '{target_id_str}') - Status: FAIL ({reason})")
    else:
        print(f"Failed to load verification suite from {args.yaml_filepath}.")
        sys.exit(1) # Exit with error code if suite loading fails

    print("\nCommand-line verification run finished.")
