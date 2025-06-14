import os
import sys
import sympy

# Adjust sys.path to allow relative imports of package components
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
path_to_add = os.path.dirname(project_root)
if path_to_add not in sys.path:
    sys.path.insert(0, path_to_add)

# Now import project modules
from symbolic_circuit_solver_master import scs_circuit
from symbolic_circuit_solver_master import scs_parser as scs_parser_module
from symbolic_circuit_solver_master import scs_instance_hier
from symbolic_circuit_solver_master import scs_numerical_solver
from symbolic_circuit_solver_master import scs_utils
from symbolic_circuit_solver_master import scs_errors

def main():
    print("--- Voltage Divider Formula Verification with Auto Test Points ---")

    # 1. Define SPICE netlist with symbolic parameters
    netlist_content = """
* Voltage Divider Test
.PARAM V_in_sym = V_in_sym
.PARAM R1_sym = R1_sym
.PARAM R2_sym = R2_sym

V1 N_in 0 V_in_sym
R1 N_in N_out R1_sym
R2 N_out 0 R2_sym
.end
"""
    temp_netlist_filename = "temp_divider_auto.sp"

    with open(temp_netlist_filename, 'w') as f:
        f.write(netlist_content)

    V_out_symbolic_expr = None
    symbols_in_formula = set()

    try:
        # --- 2. Symbolic Analysis (as before) ---
        print("\n--- Performing Symbolic Analysis ---")
        top_circuit = scs_circuit.TopCircuit()
        parsed_circuit = scs_parser_module.parse_file(temp_netlist_filename, top_circuit)
        if not parsed_circuit:
            raise Exception("Parsing failed.")

        top_instance = scs_instance_hier.make_top_instance(parsed_circuit)
        if not top_instance:
            raise Exception("Instance creation failed.")

        top_instance.solve()
        V_out_symbolic_expr = top_instance.v('N_out', '0')
        print(f"Symbolic expression for V(N_out): {V_out_symbolic_expr}")

        # --- 3. Extract Free Symbols ---
        if hasattr(V_out_symbolic_expr, 'free_symbols'):
            symbols_in_formula = V_out_symbolic_expr.free_symbols
        else: # Handle case where expression might be a constant
            symbols_in_formula = set()
        print(f"Free symbols in the formula: {symbols_in_formula}")

        # --- 4. Generate Test Points ---
        num_test_sets = 5
        print(f"\n--- Generating {num_test_sets} Test Point Sets ---")
        # Ensure symbols_in_formula contains Sympy symbols, not strings, if generate_test_points expects that.
        # V_out_symbolic_expr.free_symbols already returns Sympy symbols.
        test_point_value_list = scs_utils.generate_test_points(symbols_in_formula, num_sets=num_test_sets)

        if not test_point_value_list and symbols_in_formula: # Handle if no test points generated for non-empty symbols
             print("Warning: No test points generated, but formula has symbols. Check generate_test_points.")
             return
        elif not symbols_in_formula and V_out_symbolic_expr is not None: # Formula is a constant
            print(f"Formula is a constant: {V_out_symbolic_expr}")
            # Evaluate it once if possible (it should be a number)
            constant_val = scs_utils.evaluate_symbolic_expr(V_out_symbolic_expr, {})
            print(f"Evaluated constant value: {constant_val}")
            # Numerical simulation with dummy params (as they won't be used for a constant-defined circuit value)
            dummy_params_for_numerical = {s.name: 1.0 for s in symbols_in_formula} if symbols_in_formula else {}
            numerical_results = scs_numerical_solver.solve_dc_numerically(temp_netlist_filename, dummy_params_for_numerical)
            if numerical_results and f"V(N_out)" in numerical_results:
                numerical_result_V_out = numerical_results[f"V(N_out)"]
                print(f"Numerical result for V(N_out) (with dummy params): {numerical_result_V_out}")
                if constant_val is not None and numerical_result_V_out is not None:
                    results_match = scs_utils.compare_numerical_values(constant_val, numerical_result_V_out)
                    print(f"Comparison for constant formula: {'MATCH' if results_match else 'MISMATCH'}")
            else:
                print("Numerical solution failed or V(N_out) not found for constant formula check.")
            return # End here if formula is constant

        for i, param_map_sympy_keys in enumerate(test_point_value_list):
            print(f"\n--- Test Point Set {i+1}/{num_test_sets} ---")
            current_param_values_str = {str(k): v for k, v in param_map_sympy_keys.items()}
            print(f"Parameters: {current_param_values_str}")

            # --- 5a. Numerical Analysis for current test set ---
            # solve_dc_numerically expects param_values keys to be strings matching .PARAM names
            # if those .PARAMs are themselves symbols.
            # The element's get_numerical_dc_value will receive this dict.
            # Inside get_numerical_dc_value, self.values[0] is a Sympy symbol (e.g. R1_sym).
            # So, expr.subs(param_values) needs param_values to have Sympy symbol keys.
            # This means param_map_sympy_keys is the correct one for solve_dc_numerically's
            # internal call to get_numerical_dc_value.

            numerical_results = scs_numerical_solver.solve_dc_numerically(temp_netlist_filename, param_map_sympy_keys)
            numerical_result_V_out = None
            if numerical_results and f"V(N_out)" in numerical_results:
                numerical_result_V_out = numerical_results[f"V(N_out)"]
                print(f"  Numerical V(N_out): {numerical_result_V_out}")
            else:
                print("  Numerical solution failed or V(N_out) not found for this set.")
                continue # Skip to next test set

            # --- 5b. Symbolic Evaluation for current test set ---
            evaluated_symbolic_V_out = scs_utils.evaluate_symbolic_expr(V_out_symbolic_expr, param_map_sympy_keys)
            print(f"  Symbolic Eval V(N_out): {evaluated_symbolic_V_out}")

            # --- 5c. Comparison ---
            if evaluated_symbolic_V_out is not None and numerical_result_V_out is not None:
                results_match = scs_utils.compare_numerical_values(evaluated_symbolic_V_out, numerical_result_V_out)
                print(f"  Comparison: {'MATCH' if results_match else 'MISMATCH'}")
            else:
                print("  Cannot compare due to missing results for this set.")

    except scs_errors.ScsParserError as e:
        print(f"A parser error occurred: {e}")
    except scs_errors.ScsInstanceError as e:
        print(f"An instance error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if os.path.exists(temp_netlist_filename):
            os.remove(temp_netlist_filename)
        print(f"\nCleaned up {temp_netlist_filename}.")

if __name__ == '__main__':
    main()
