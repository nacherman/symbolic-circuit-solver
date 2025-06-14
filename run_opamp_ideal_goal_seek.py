import sys
import os
import sympy

# Path setup
script_run_dir = os.getcwd()
path_to_solver_package = os.path.join(script_run_dir, "extracted_files/sim12/sim/symbolic-circuit-solver-improve-h-bridge-example/symbolic-circuit-solver-improve-h-bridge-example/")
if path_to_solver_package not in sys.path:
    sys.path.insert(0, path_to_solver_package)

try:
    from symbolic_circuit_solver_master.scs_symbolic_goal_seeker import solve_for_symbolic_unknown
    print("Successfully imported solve_for_symbolic_unknown.")
except ImportError as e:
    print(f"Error importing: {e}")
    print(f"Python path: {sys.path}")
    exit(1)

netlist_file_path = os.path.join(script_run_dir, "goal_seek_opamp_ideal.sp")

unknown_to_solve = 'R2_s'
# Target V(output_node) = -Av_target_s * Vin_s
target_quantity_str = 'V(output_node)'
target_value_expression = '-Av_target_s * Vin_s'

print(f"Attempting to solve for '{unknown_to_solve}' (symbolically for an OpAmp circuit)")
print(f"Such that {target_quantity_str} = {target_value_expression}")
print(f"Using netlist: {netlist_file_path}")

# Parameters that are symbolic in the target expression or netlist,
# and are NOT the unknown_to_solve, should be declared as symbols
# for sympy.solve to treat them correctly.
# solve_for_symbolic_unknown typically handles this by finding free symbols.
# Here, Vin_s, R1_s, Av_target_s are such symbols from our definitions.
# A_param_val, RL_val, Rout_opamp_val are fixed numerics in the .PARAM block.

solutions = solve_for_symbolic_unknown(
    netlist_path=netlist_file_path,
    unknown_param_name_str=unknown_to_solve,
    target_quantity_str=target_quantity_str,
    target_value_expr_str=target_value_expression
)

if solutions:
    print(f"Found solution(s) for {unknown_to_solve}:")

    R1_s_exp, Av_target_s_exp, Vin_s_exp = sympy.symbols('R1_s Av_target_s Vin_s')
    # For an ideal op-amp inverting configuration, Vout/Vin = -R2/R1.
    # So, if Vout = -Av_target_s * Vin_s, then -Av_target_s = -R2_s/R1_s
    # Which means R2_s = Av_target_s * R1_s
    expected_symbolic_solution = Av_target_s_exp * R1_s_exp

    print(f"  Expected symbolic solution form for R2_s (ideal opamp): {expected_symbolic_solution}")

    for sol_idx, sol_expr in enumerate(solutions):
        print(f"  Solution {sol_idx + 1} (Symbolic Expr): {sol_expr}")

        # Verification by simplifying the difference.
        # The solution might be complex due to finite (though large) gain and Rout.
        # We expect it to approximate Av_target_s * R1_s.

        # Let's try to simplify the solution by substituting a very large OpAmp gain (A_param_val -> 0)
        # and very small Rout_opamp_val -> 0, and very large RL_val -> oo (already large).
        # However, the fixed values are already in the netlist.
        # The solution sol_expr will be in terms of R1_s, Av_target_s, Vin_s.

        simplified_expr = sympy.simplify(sol_expr)
        print(f"  Simplified Solution {sol_idx + 1}: {simplified_expr}")

        # Check if the simplified solution is close to the ideal one.
        # This might require more advanced symbolic comparison or numerical tests if not exactly matching.
        # For now, let's try direct simplification of the difference.
        # The expression will contain Vin_s and Av_target_s from the target_value_expression,
        # and R1_s from the circuit.

        # Create the symbols as they appear in sol_expr for proper substitution in expected_symbolic_solution
        # It seems sol_expr already uses the correct symbols based on .PARAM names.

        diff = sympy.simplify(sol_expr - expected_symbolic_solution)

        # Since open-loop gain is finite (1/A_param_val = 1e7), Rout is non-zero,
        # the actual formula will be slightly different from the ideal R2=Av*R1.
        # It will be R2 = R1*Av / (1 - R1*(1+Av)/(Aol*Rout) - (1+Av)/Aol) approx
        # The solution from sympy might be very complex.
        # A full symbolic match might be hard. Let's check if it contains the core part.

        # For now, we'll print the solution and the expected ideal one.
        # A more robust check would involve substituting typical numerical values for symbols
        # in both the derived solution and the ideal formula and comparing results,
        # or analyzing the structure of 'diff'.

        if diff == 0:
            print(f"  SUCCESS: Solution {sol_idx + 1} EXACTLY matches the ideal symbolic form.")
        else:
            print(f"  NOTE: Solution {sol_idx + 1} does not exactly match the ideal form {expected_symbolic_solution}.")
            print(f"         This is expected due to finite (though large) op-amp gain and non-zero Rout.")
            print(f"         Simplified difference to ideal: {diff}")

            # Test with some numeric values
            # Ensure all symbols in sol_expr are covered by test_values or are part of the solution's constants
            # The symbols in sol_expr should be R1_s, Av_target_s, and Vin_s (as per target_value_expression)
            # The fixed parameters (A_param_val, RL_val, Rout_opamp_val) are already numbers in the solver's equations.
            current_expr_symbols = sol_expr.free_symbols
            test_values_dict = {
                R1_s_exp: 1000,
                Av_target_s_exp: 10,
                # Vin_s should ideally cancel out if the circuit behaves linearly for gain.
                # If Vin_s is still in sol_expr, we need to provide a value for it.
                Vin_s_exp: 1 # Arbitrary value if it hasn't cancelled.
            }

            # Filter test_values_dict to only include symbols present in current_expr_symbols
            # This is important if Vin_s correctly cancels from the R2_s expression.
            filtered_test_values = {k: v for k, v in test_values_dict.items() if k in current_expr_symbols}


            numeric_sol = sympy.N(sol_expr.subs(filtered_test_values))
            numeric_expected = sympy.N(expected_symbolic_solution.subs(filtered_test_values)) # Use same filtered set for expected

            print(f"    For R1=1k, Av_target=10 (Vin_s=1 if not cancelled): Solved R2 = {numeric_sol:.4f}, Ideal R2 = {numeric_expected:.4f}")
            if abs(numeric_sol - numeric_expected) / numeric_expected < 0.01: # Check if within 1%
                 print("    Numeric values are close (within 1%), which is good for near-ideal opamp.")
            else:
                 print("    Numeric values differ significantly.")


else:
    print(f"No solution found for {unknown_to_solve} or an error occurred.")
