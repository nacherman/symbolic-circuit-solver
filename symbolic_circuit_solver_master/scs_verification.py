import sympy
import os
import sys

# Adjust sys.path for direct script execution
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
path_to_add = os.path.dirname(project_root)
if path_to_add not in sys.path:
    sys.path.insert(0, path_to_add)

from symbolic_circuit_solver_master import scs_utils
from symbolic_circuit_solver_master import scs_numerical_solver
from symbolic_circuit_solver_master import scs_errors

# Imports needed for the __main__ test block
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
                for str_key, fixed_value in user_param_override_values.items():
                    symbol_to_override = next((s for s in current_symbolic_eval_params if s.name == str_key), None)
                    if symbol_to_override:
                        current_symbolic_eval_params[symbol_to_override] = fixed_value
                        current_numerical_solver_params[symbol_to_override] = fixed_value
                    else:
                        print(f"    Note: Override '{str_key}' not in formula's free symbols. Adding/overriding for numerical solver.")
                        current_numerical_solver_params[sympy.symbols(str_key)] = fixed_value

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
                            'param_map': current_symbolic_eval_params, # Changed from params_map_sympy_keys
                            'params_str': current_param_values_str,
                            'numerical_value': numerical_value,
                            'symbolic_eval_value_original': symbolic_eval_value,
                            'compared_symbolic_value_as_absorbed': comparison_symbolic_eval_value if is_source_power_test else "N/A"
                        })
                        print("  Status: MISMATCH")
                else:
                    mismatch_this_point = True
                    mismatches_details.append({
                        'param_map': current_symbolic_eval_params, # Changed from params_map_sympy_keys
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
                    'param_map': current_symbolic_eval_params, # Changed from params_map_sympy_keys
                    'params_str': current_param_values_str,
                    'error': str(e_loop)})

            if mismatch_this_point and stop_on_first_mismatch:
                # Ensure verified_all will be False if we break due to mismatch
                # final_verified_all computation below will handle this correctly
                # as mismatches_details will not be empty.
                print(f"  STOPPING further tests for '{target_identifier}' due to mismatch and stop_on_first_mismatch=True.")
                break

    # Determine final verification status
    if actual_tests_run == 0 and num_test_sets > 0 and not (not free_symbols and symbolic_expr is not None):
        # This case means no tests were actually performed for a variable expression, which is a failure.
        final_verified_all = False
    elif stop_on_first_mismatch and len(mismatches_details) > 0 and actual_tests_run < num_test_sets :
        # If stopped early due to a mismatch, it's not fully verified.
        final_verified_all = False
    else:
        # Normal case: all planned tests run (or constant expression tested once)
        # Verified if no mismatches AND (all tests run OR it was a constant formula OR num_test_sets was 0)
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
    def get_element_power_from_results(results_dict, element_name):
        if results_dict and 'element_power' in results_dict:
            return results_dict['element_power'].get(element_name)
        return None
    return _verify_generic_expression(symbolic_expr_for_power, target_element_name, netlist_path,
                                      num_test_sets, user_param_override_values, get_element_power_from_results, "Element Power",
                                      stop_on_first_mismatch, symbol_specific_random_ranges)

if __name__ == '__main__':
    print("--- Verification Utility Self-Test ---")

    netlist_content_simple_divider = """
* Voltage Divider Test for Verification Utility
.PARAM V_in_sym = V_in_sym
.PARAM R1_sym = R1_sym
.PARAM R2_sym = R2_sym
V1 N_in 0 V_in_sym
R1 N_in N_out R1_sym
R2 N_out 0 R2_sym
.end
"""
    temp_file_simple_divider = "temp_verifier_simple_divider.sp"
    with open(temp_file_simple_divider, 'w') as f:
        f.write(netlist_content_simple_divider)

    print("\n--- Processing Simple Divider for V and I Formulas ---")
    top_circuit_sd = scs_circuit.TopCircuit()
    parsed_circuit_sd = scs_parser_module.parse_file(temp_file_simple_divider, top_circuit_sd)
    if not parsed_circuit_sd: print("SIMPLE DIVIDER PARSING FAILED"); sys.exit(1)
    top_instance_sd = scs_instance_hier.make_top_instance(parsed_circuit_sd)
    if not top_instance_sd: print("SIMPLE DIVIDER INSTANCE CREATION FAILED"); sys.exit(1)
    top_instance_sd.solve()
    v_n_out_sd_expr = top_instance_sd.v('N_out', '0')
    i_r1_sd_expr = top_instance_sd.i('R1')
    print(f"  Derived V(N_out) for simple divider: {v_n_out_sd_expr}")
    print(f"  Derived I(R1) for simple divider: {i_r1_sd_expr}")

    # Helper for printing mismatch details
    def print_mismatch_details(details):
        for detail in details:
            param_map_for_print = detail.get('param_map', detail.get('params_map_sympy_keys')) # Use new 'param_map' key
            if isinstance(param_map_for_print, dict):
                 # Convert sympy symbols in keys to strings for cleaner printing
                param_map_str = {str(k): v for k, v in param_map_for_print.items()}
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
                    # Use the 'original' symbolic value if available, else the direct one.
                    # For power, if 'compared_symbolic_value_as_absorbed' was used for comparison,
                    # the % diff should still be based on the 'symbolic_eval_value_original'
                    # to reflect the formula as written by user, or be clear about convention.
                    # For now, using s_val (which is symbolic_eval_value_original from detail)
                    s_val_f = float(s_val)

                    if n_val_f != 0:
                        perc_diff = abs(s_val_f - n_val_f) / abs(n_val_f) * 100
                        print(f"    Percentage Difference (vs Numerical): {perc_diff:.4f}%")
                    elif s_val_f != 0: # n_val is 0, s_val is not
                        print(f"    Percentage Difference: Inf (Numerical is zero, Symbolic is non-zero)")
                    else: # Both zero
                        print(f"    Percentage Difference: 0.0000% (Both zero)")

                except (ValueError, TypeError) as e_conv:
                    print(f"    Percentage Difference: N/A (Could not convert symbolic '{s_val}' or numerical '{n_val}' to float for diff: {e_conv})")

            if 'note' in detail: print(f"    Note: {detail['note']}")
            if 'error' in detail: print(f"    Error: {detail['error']}")
            print("    ----") # Separator for multiple mismatches

    results_v_sd = verify_node_voltage_formula(v_n_out_sd_expr, 'N_out', temp_file_simple_divider, num_test_sets=2)
    print("\n--- Voltage Verification (Simple Divider, No Override) ---")
    print(f"  Result summary: { {k:v for k,v in results_v_sd.items() if k != 'mismatches_details'} }")
    if results_v_sd['mismatches_details']: print_mismatch_details(results_v_sd['mismatches_details'])

    results_i_sd = verify_element_current_formula(i_r1_sd_expr, 'R1', temp_file_simple_divider, num_test_sets=2)
    print("\n--- Current Verification (Simple Divider, R1) ---")
    print(f"  Result summary: { {k:v for k,v in results_i_sd.items() if k != 'mismatches_details'} }")
    if results_i_sd['mismatches_details']: print_mismatch_details(results_i_sd['mismatches_details'])

    # Test stop_on_first_mismatch=True
    print("\n--- Testing stop_on_first_mismatch=True (forcing a mismatch for V(N_out)) ---")
    v_in_sym_for_test, r1_sym_for_test, r2_sym_for_test = sympy.symbols('V_in_sym R1_sym R2_sym')
    correct_expr_for_symbols = (r2_sym_for_test * v_in_sym_for_test) / (r1_sym_for_test + r2_sym_for_test)
    faulty_expr = correct_expr_for_symbols * 0.99 # Introduce 1% error to ensure mismatch
    # Using sympy.symbols('ErrorForce') could also work if added to the expression,
    # e.g. faulty_expr = correct_expr_for_symbols + sympy.symbols('R1_sym') * 0.0001
    # to use an existing symbol if 'ErrorForce' is not defined in the netlist params.
    # The current faulty_expr approach is simpler.

    print(f"  Intentionally using faulty expression: {faulty_expr} for V(N_out)")
    results_stop_test = verify_node_voltage_formula(
        faulty_expr,
        'N_out',
        temp_file_simple_divider,
        num_test_sets=5, # Use more than 1 to demonstrate it stops early
        stop_on_first_mismatch=True
    )
    print("\n--- Verification Summary (Stop on First Mismatch Test for V(N_out)) ---")
    summary_dict_stop_test = {k:v for k,v in results_stop_test.items() if k != 'mismatches_details'}
    print(f"  Result summary: {summary_dict_stop_test}")
    if results_stop_test['mismatches_details']:
        print(f"  Mismatch Details (expecting only 1 due to stop_on_first_mismatch=True):")
        print_mismatch_details(results_stop_test['mismatches_details'])

    if summary_dict_stop_test.get('total_tests_run') == 1 and summary_dict_stop_test.get('mismatches') == 1:
        print("  VERIFIED: stop_on_first_mismatch correctly stopped after 1 test point on the first mismatch.")
    elif summary_dict_stop_test.get('total_tests_planned') > 1 : # only print error if it was supposed to run multiple tests
        print("  WARNING: stop_on_first_mismatch test did not behave as expected. Check 'total_tests_run'.")


    if os.path.exists(temp_file_simple_divider): os.remove(temp_file_simple_divider)
    print(f"\nCleaned up {temp_file_simple_divider}.")

    # --- Test with a more complex circuit ---
    netlist_content_complex = """
* Complex Test Circuit: Inverting Op-Amp with Symbolic Params
.PARAM V_source_sym = V_source_sym
.PARAM R1_sym = R1_sym
.PARAM R2_val = 10k          ; Fixed R2
.PARAM Aol_sym = Aol_sym

Vin N_in 0 V_source_sym
R1 N_in N_minus R1_sym
R2 N_minus N_out R2_val
E_opamp N_out 0 0 N_minus Aol_sym
.end
"""
    temp_file_complex = "temp_complex_circuit.sp"
    with open(temp_file_complex, 'w') as f:
        f.write(netlist_content_complex)

    print("\n--- Processing Complex Circuit (Inverting Op-Amp) ---")
    top_circuit_complex = scs_circuit.TopCircuit()
    parsed_circuit_complex = scs_parser_module.parse_file(temp_file_complex, top_circuit_complex)
    if not parsed_circuit_complex: print("COMPLEX CIRCUIT PARSING FAILED"); sys.exit(1)
    top_instance_complex = scs_instance_hier.make_top_instance(parsed_circuit_complex)
    if not top_instance_complex: print("COMPLEX CIRCUIT INSTANCE CREATION FAILED"); sys.exit(1)

    print("Solving complex circuit symbolically...")
    top_instance_complex.solve()
    print("Symbolic solution complete for complex circuit.")

    v_n_out_expr_sym = top_instance_complex.v('N_out', '0')
    i_r1_expr_sym = top_instance_complex.i('R1')
    i_vin_expr_sym = top_instance_complex.i('Vin')
    i_e_opamp_expr_sym = top_instance_complex.i('E_opamp')
    p_r2_expr_sym = top_instance_complex.p('R2')
    p_e_opamp_expr_sym = top_instance_complex.p('E_opamp')

    print(f"  Derived V(N_out) complex (symbolic): {v_n_out_expr_sym}")
    print(f"  Derived I(R1) complex (symbolic): {i_r1_expr_sym}")
    print(f"  Derived I(Vin) complex (symbolic): {i_vin_expr_sym}")
    print(f"  Derived I(E_opamp) complex (symbolic): {i_e_opamp_expr_sym}")
    print(f"  Derived P(R2) complex (symbolic): {p_r2_expr_sym}")
    print(f"  Derived P(E_opamp) complex (symbolic): {p_e_opamp_expr_sym}")

    num_complex_tests = 3
    # Define symbols used in the complex circuit for specific ranges
    V_source_sym_cplx = sympy.symbols('V_source_sym')
    R1_sym_cplx = sympy.symbols('R1_sym')
    Aol_sym_cplx = sympy.symbols('Aol_sym')

    complex_circuit_verification_summaries = []

    # Example of using symbol_specific_random_ranges
    specific_ranges_for_complex_test = {
        R1_sym_cplx: (500.0, 1500.0),       # R1_sym will be log-scaled within 500-1500
        Aol_sym_cplx: (10000.0, 50000.0)  # Aol_sym will be linear-scaled within 10k-50k
                                          # V_source_sym_cplx will use global V-range
    }
    print(f"\n--- Verifying V(N_out) from Complex Circuit (Symbolic Params) with Specific Ranges ---")
    print(f"  Using specific random ranges: { {str(k):v for k,v in specific_ranges_for_complex_test.items()} }")
    results_vnout = verify_node_voltage_formula(
        v_n_out_expr_sym, 'N_out', temp_file_complex,
        num_test_sets=num_complex_tests,
        symbol_specific_random_ranges=specific_ranges_for_complex_test
    )
    complex_circuit_verification_summaries.append(results_vnout)
    print(f"  Result summary: { {k:v for k,v in results_vnout.items() if k != 'mismatches_details'} }")
    if results_vnout['mismatches_details']: print_mismatch_details(results_vnout['mismatches_details'])

    print(f"\n--- Verifying I(R1) from Complex Circuit (Symbolic Params) ---")
    results_ir1 = verify_element_current_formula(i_r1_expr_sym, 'R1', temp_file_complex, num_test_sets=num_complex_tests)
    complex_circuit_verification_summaries.append(results_ir1)
    print(f"  Result summary: { {k:v for k,v in results_ir1.items() if k != 'mismatches_details'} }")
    if results_ir1['mismatches_details']: print_mismatch_details(results_ir1['mismatches_details'])

    print(f"\n--- Verifying I(Vin) from Complex Circuit (Symbolic Params) ---")
    results_ivin = verify_vsource_current_formula(i_vin_expr_sym, 'Vin', temp_file_complex, num_test_sets=num_complex_tests)
    complex_circuit_verification_summaries.append(results_ivin)
    print(f"  Result summary: { {k:v for k,v in results_ivin.items() if k != 'mismatches_details'} }")
    if results_ivin['mismatches_details']: print_mismatch_details(results_ivin['mismatches_details'])

    print(f"\n--- Verifying I(E_opamp) from Complex Circuit (Symbolic Params) ---")
    results_ieopamp = verify_vsource_current_formula(i_e_opamp_expr_sym, 'E_opamp', temp_file_complex, num_test_sets=num_complex_tests)
    complex_circuit_verification_summaries.append(results_ieopamp)
    print(f"  Result summary: { {k:v for k,v in results_ieopamp.items() if k != 'mismatches_details'} }")
    if results_ieopamp['mismatches_details']: print_mismatch_details(results_ieopamp['mismatches_details'])

    print(f"\n--- Verifying P(R2) from Complex Circuit (Symbolic Params) ---")
    results_pr2 = verify_element_power_formula(p_r2_expr_sym, 'R2', temp_file_complex, num_test_sets=num_complex_tests)
    complex_circuit_verification_summaries.append(results_pr2)
    print(f"  Result summary: { {k:v for k,v in results_pr2.items() if k != 'mismatches_details'} }")
    if results_pr2['mismatches_details']: print_mismatch_details(results_pr2['mismatches_details'])

    print(f"\n--- Verifying P(E_opamp) from Complex Circuit (Symbolic Params) ---")
    results_peopamp = verify_element_power_formula(p_e_opamp_expr_sym, 'E_opamp', temp_file_complex, num_test_sets=num_complex_tests)
    complex_circuit_verification_summaries.append(results_peopamp)
    print(f"  Result summary: { {k:v for k,v in results_peopamp.items() if k != 'mismatches_details'} }")
    if results_peopamp['mismatches_details']: print_mismatch_details(results_peopamp['mismatches_details'])

    # --- Overall Summary for Complex Circuit ---
    total_complex_checks = len(complex_circuit_verification_summaries)
    passed_complex_checks = 0
    for summary in complex_circuit_verification_summaries:
        if summary.get('verified_all', False):
            passed_complex_checks += 1

    print(f"\n\n--- Complex Circuit Overall Verification Summary ---")
    print(f"Passed {passed_complex_checks}/{total_complex_checks} checks.")

    if passed_complex_checks < total_complex_checks:
        print("\nDetails of failed checks for Complex Circuit:")
        for summary in complex_circuit_verification_summaries:
            if not summary.get('verified_all', False):
                target_id = summary.get('target_node', summary.get('target_element', 'Unknown Target'))
                formula = summary.get('symbolic_formula', 'Unknown Formula')
                # Attempt to infer expression type from target key
                expr_type = "Node Voltage" if 'target_node' in summary else \
                            "Element Current" if target_id.startswith(('R','L','C')) else \
                            "VSource Current" if target_id.startswith(('V','E','H')) else \
                            "Element Power" # Fallback, could be more specific
                # This inference of expr_type is heuristic; actual type passed to _verify_generic_expression would be better.
                # However, the summary dictionary doesn't store 'expression_type_str' directly.
                # For now, target_id and formula should be enough for identification.
                print(f"  - Failed: Verification for '{target_id}'. Formula: {formula}")
                # Detailed mismatches were already printed when the check was run.
                # If more detail is needed here, one could re-print summary['mismatches_details']
    else:
        print("All complex circuit verification checks passed successfully!")


    if os.path.exists(temp_file_complex):
        os.remove(temp_file_complex)
    print(f"\nCleaned up {temp_file_complex}.")

    print("\nAll tests finished.")
