import os
import sys
import sympy

# Adjust sys.path to allow relative imports of package components
script_dir = os.path.dirname(os.path.abspath(__file__))
# project_root is .../symbolic_circuit_solver-master
project_root = os.path.dirname(os.path.dirname(script_dir))
# path_to_add needs to be the parent of symbolic_circuit_solver_master, i.e. /app
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
    print("--- Voltage Divider Formula Verification ---")

    # 1. Define SPICE netlist with symbolic parameters
    # Using symbolic names that will become Sympy symbols via .PARAM
    # V_in_sym, R1_sym, R2_sym will be the symbols in the symbolic expressions.
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
    temp_netlist_filename = "temp_divider.sp"

    with open(temp_netlist_filename, 'w') as f:
        f.write(netlist_content)

    # Define numerical values for the symbols
    # These need to be Sympy symbols for the symbolic evaluation part
    # and for the numerical solver's substitution if parameters are passed as symbols.
    V_in_sym = sympy.symbols('V_in_sym')
    R1_sym = sympy.symbols('R1_sym')
    R2_sym = sympy.symbols('R2_sym')

    # For evaluate_symbolic_expr (maps Sympy symbols to numbers)
    symbol_map_for_eval = {
        V_in_sym: 10.0,
        R1_sym: 1000.0,
        R2_sym: 1000.0
    }
    # For solve_dc_numerically, the keys in param_values should match what
    # get_numerical_dc_value expects after initial parsing.
    # If .PARAM lines define symbols, those symbols are in element.values[0].
    # So, param_values should map these symbols to numbers.
    param_values_for_numerical = symbol_map_for_eval.copy()


    V_out_symbolic_expr = None
    numerical_result_V_out = None
    evaluated_symbolic_V_out = None
    results_match = False

    try:
        # --- 2. Symbolic Analysis ---
        print("\n--- Performing Symbolic Analysis ---")
        top_circuit = scs_circuit.TopCircuit()
        parsed_circuit = scs_parser_module.parse_file(temp_netlist_filename, top_circuit)
        if not parsed_circuit:
            raise Exception("Parsing failed.")

        # For make_top_instance, param_valsd are default fallbacks if not in circuit's .PARAMs
        # Here, our .PARAMs are symbolic, so they are already in parsed_circuit.parametersd
        # make_top_instance internally uses the circuit's parametersd.
        top_instance = scs_instance_hier.make_top_instance(parsed_circuit)
        if not top_instance:
            raise Exception("Instance creation failed.")

        top_instance.solve() # Perform symbolic solution
        V_out_symbolic_expr = top_instance.v('N_out', '0')
        print(f"Symbolic expression for V(N_out): {V_out_symbolic_expr}")

        # --- 3. Numerical Analysis ---
        print("\n--- Performing Numerical Analysis ---")
        # param_values_for_numerical should map the symbols used in .PARAM to values
        numerical_results = scs_numerical_solver.solve_dc_numerically(temp_netlist_filename, param_values_for_numerical)
        if numerical_results and f"V(N_out)" in numerical_results:
            numerical_result_V_out = numerical_results[f"V(N_out)"]
            print(f"Numerical result for V(N_out): {numerical_result_V_out}")
        else:
            print("Numerical solution did not yield V(N_out). Results:", numerical_results)
            raise Exception("Numerical solution failed or V(N_out) not found.")

        # --- 4. Evaluation & Comparison ---
        print("\n--- Evaluation and Comparison ---")
        print(f"Chosen parameter values for evaluation: { {str(k):v for k,v in symbol_map_for_eval.items()} }")

        evaluated_symbolic_V_out = scs_utils.evaluate_symbolic_expr(V_out_symbolic_expr, symbol_map_for_eval)
        print(f"Symbolic formula evaluated with chosen values: {evaluated_symbolic_V_out}")

        if evaluated_symbolic_V_out is not None and numerical_result_V_out is not None:
            results_match = scs_utils.compare_numerical_values(evaluated_symbolic_V_out, numerical_result_V_out)
            print(f"Comparison (tolerance 1e-6): {'MATCH' if results_match else 'MISMATCH'}")
        else:
            print("Cannot compare due to missing results.")

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
