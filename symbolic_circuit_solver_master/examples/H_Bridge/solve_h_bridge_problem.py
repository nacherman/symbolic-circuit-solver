import sys
import os
import sympy

# __file__ is .../symbolic_circuit_solver-master/examples/H_Bridge/solve_h_bridge_problem.py
script_dir = os.path.dirname(os.path.abspath(__file__))
# project_root is .../symbolic_circuit_solver-master
project_root = os.path.dirname(os.path.dirname(script_dir))
# path_to_add is .../ (the directory containing symbolic_circuit_solver-master, i.e. /app)
path_to_add = os.path.dirname(project_root)
sys.path.insert(0, path_to_add)

# Now import using full package path from the directory added to sys.path
from symbolic_circuit_solver_master.scs_symbolic_solver_tool import SymbolicCircuitProblemSolver
from symbolic_circuit_solver_master.scs_errors import ScsParserError, ScsInstanceError, ScsToolError

def main():
    netlist_filename = "h_bridge.sp" # Assumed to be in the same directory as this script (script_dir)
    netlist_path = os.path.join(script_dir, netlist_filename)

    print(f"Attempting to solve H-Bridge problem using netlist: {netlist_path}")

    try:
        # --- Step 1: Instantiate the SymbolicCircuitProblemSolver ---
        solver = SymbolicCircuitProblemSolver(netlist_path=netlist_path)

        # --- Step 2: Define known electrical conditions for the circuit problem ---
        # Given: V(N3) = 0.1V (N3 relative to ground)
        # Given: Current through R4 (from N2 to N3) is 559uA
        # Netlist defines: R4 N2 N3 {R4_val} -> Positive current for R4 is N2->N3
        known_conditions = [
            {'type': 'voltage', 'node1': 'N3', 'node2': '0', 'value': 0.1},
            {'type': 'current', 'element': 'R4', 'value': 559e-6}
        ]

        # --- Step 3: Define the symbolic parameters that need to be solved for ---
        # These names must match the symbolic names used in the .PARAM definitions in the SPICE file
        # (e.g., .PARAM R3_val = R3_sym, .PARAM R3_sym = R3_sym)
        params_to_solve = ['R3_sym', 'U_sym']

        print(f"Known conditions: {known_conditions}")
        print(f"Parameters to solve for: {params_to_solve}")

        # --- Step 4: Call the solver to find the values of the specified parameters ---
        solution = solver.solve_for_unknowns(known_conditions, params_to_solve)

        print("\n--- Solution for Unknown Parameters ---")
        if solution:
            for param, value in solution.items():
                # Ensure keys are strings for display if they are sympy symbols
                param_name = str(param)
                # Try to evaluate to a floating point number if possible
                try:
                    numeric_value = float(value.evalf())
                    print(f"{param_name}: {numeric_value:.4f}")
                except (AttributeError, TypeError):
                    print(f"{param_name}: {value}") # Print symbolic expression if evalf fails

            # Store solved values (as sympy symbols as keys) for potential further use
            # This is already done internally by the solver in self.solved_symbolic_vars
            # R3_sym_solved_val = solution.get(sympy.symbols('R3_sym'))
            # U_sym_solved_val = solution.get(sympy.symbols('U_sym'))

        else:
            print("No solution found.")
            return

        # --- Step 5: Calculate and display detailed V, I, P for each resistor ---
        # This section demonstrates how to use the solved parameters and base circuit solution
        # to find operating points for all components.
        print("\n\n--- Detailed V, I, P for each Resistor ---")

        # Create a comprehensive substitution dictionary:
        # 1. Start with all .PARAM definitions from the netlist (e.g., R1_val -> 180).
        #    These are stored in solver.top_instance.paramsd (Symbol objects mapped to expressions or values).
        # 2. Substitute the 'solution' (solved variables like U_sym, R3_sym) into these expressions.
        #    For example, if U_source_val was defined as U_sym, it now becomes the numerical value of U_sym.
        #    If R3_val was R3_sym, it becomes the solved numerical value of R3_sym.
        # 3. Add the solved variables themselves to ensure they take precedence.
        final_subs_dict_for_eval = {}
        # Start with all parameters as defined in the instance (e.g. R1_val -> 180, U_source_val -> U_sym)
        if solver.top_instance and solver.top_instance.paramsd: # Changed solver_tool to solver
            for param_symbol, value_expr in solver.top_instance.paramsd.items(): # Changed solver_tool to solver
                final_subs_dict_for_eval[param_symbol] = value_expr

        # Substitute solved symbols (like U_sym, R3_sym) into the expressions derived from paramsd
        temp_subs_for_paramsd_eval = {}
        for k, v_expr in final_subs_dict_for_eval.items():
            if hasattr(v_expr, 'subs'):
                # Substitute solved variables into the parameter expressions first
                temp_subs_for_paramsd_eval[k] = v_expr.subs(solution)
            else:
                temp_subs_for_paramsd_eval[k] = v_expr # It's already a number e.g. 180
        final_subs_dict_for_eval = temp_subs_for_paramsd_eval

        # Ensure the solved symbols themselves are in the dict with their final numerical values
        for solved_sym, solved_val in solution.items():
            final_subs_dict_for_eval[solved_sym] = solved_val


        resistors_info = {
            'R1': ('N_TOP', 'N1'),
            'R2': ('N1', 'N2'),
            'R3': ('N2', '0'),
            'R4': ('N2', 'N3'),
            'R5': ('N_TOP', 'N3'),
            'R6': ('N3', '0')
        }

        for r_name, (n1, n2) in resistors_info.items():
            print(f"--- {r_name} ---")
            try:
                # These expressions will be in terms of netlist params like R1_val, U_source_val etc.
                v_expr = solver.top_instance.v(n1, n2) # Changed solver_tool to solver
                i_expr = solver.top_instance.i(r_name) # Changed solver_tool to solver
                p_expr = solver.top_instance.p(r_name) # Changed solver_tool to solver

                # Substitute all known fixed and solved parameters to get final numerical expressions
                # The expressions from v, i, p are already in terms of base symbols (U_sym, R1_val etc.)
                # after the initial .solve() in _parse_and_solve_base_circuit.
                # So we only need to substitute the solved values and the fixed values from .PARAM lines.
                # final_subs_dict_for_eval should contain everything needed.

                v_val_substituted = v_expr.subs(final_subs_dict_for_eval)
                i_val_substituted = i_expr.subs(final_subs_dict_for_eval)
                p_val_substituted = p_expr.subs(final_subs_dict_for_eval)

                v_val_numeric = v_val_substituted.evalf() if hasattr(v_val_substituted, 'evalf') else v_val_substituted
                i_val_numeric = i_val_substituted.evalf() if hasattr(i_val_substituted, 'evalf') else i_val_substituted
                p_val_numeric = p_val_substituted.evalf() if hasattr(p_val_substituted, 'evalf') else p_val_substituted

                # Safer way to get resistance value
                target_r_param_name_str = r_name + '_val'
                actual_r_param_symbol_key = None
                # Iterate through the keys of the dictionary that contains the original symbols from parsing
                # These original Symbol objects must be used for lookup.
                if solver.top_instance and solver.top_instance.paramsd:
                    for sym_key in solver.top_instance.paramsd.keys():
                        if str(sym_key) == target_r_param_name_str:
                            actual_r_param_symbol_key = sym_key
                            break

                if actual_r_param_symbol_key:
                    # Now get the (potentially substituted) value from final_subs_dict_for_eval
                    r_actual_expr = final_subs_dict_for_eval.get(actual_r_param_symbol_key)
                else:
                    r_actual_expr = None # Parameter symbol not found in original paramsd

                if r_actual_expr is None:
                    r_actual_numeric = f"N/A (param symbol {target_r_param_name_str} not in instance params)"
                elif hasattr(r_actual_expr, 'evalf'): # If it's an expression, evaluate it
                    r_actual_numeric = r_actual_expr.evalf()
                else: # Otherwise, it should be a number already
                    r_actual_numeric = r_actual_expr

                print(f"  Resistance: {r_actual_numeric} Ω")
                print(f"  Voltage:    {v_val_numeric:.4f} V")
                print(f"  Current:    {i_val_numeric * 1000:.4f} mA")
                print(f"  Power:      {p_val_numeric * 1000:.4f} mW")

            except Exception as e_detail:
                print(f"  Error calculating details for {r_name}: {type(e_detail).__name__} - {e_detail}")
        # Section to add ends here

        # --- Step 6: Original separate power calculation for R3 (for comparison/verification) ---
        # This uses the SymbolicCircuitProblemSolver's get_element_power method, which internally
        # also performs substitutions using the solved_symbolic_vars and the instance's paramsd.
        r3_power_expr = solver.get_element_power('R3')

        print("\n--- Verification: Power Calculation for R3 (using get_element_power) ---")
        print(f"Symbolic power of R3: {r3_power_expr}")

        # Evaluate the power numerically
        # All symbols involved (R3_sym, U_sym, and fixed resistors like R1_val)
        # should have been substituted by get_element_power using solved_symbolic_vars and paramsd.
        try:
            r3_power_numeric = float(r3_power_expr.evalf())
            print(f"Numerical power of R3: {r3_power_numeric:.6e} W")
        except (AttributeError, TypeError) as e:
            print(f"Could not evaluate power of R3 numerically: {e}")
            print("This might happen if the expression still contains unsolved symbols.")

    except (ScsParserError, ScsInstanceError, ScsToolError, ValueError, FileNotFoundError) as e:
        print(f"\nAn error occurred: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
