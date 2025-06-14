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

netlist_file_path = os.path.join(script_run_dir, "goal_seek_vdiv_sym_target.sp")

unknown_to_solve = 'R2_sym'
target_quantity = 'V(N_out)'
# Target V(N_out) = Vin_s / K_div_s (a symbolic expression)
target_value_expression = 'Vin_s / K_div_s'

print(f"Attempting to solve for '{unknown_to_solve}' (symbolically)")
print(f"Such that {target_quantity} = {target_value_expression}")
print(f"Using netlist: {netlist_file_path}")

solutions = solve_for_symbolic_unknown(
    netlist_path=netlist_file_path,
    unknown_param_name_str=unknown_to_solve,
    target_quantity_str=target_quantity,
    target_value_expr_str=target_value_expression
)

if solutions:
    print(f"Found solution(s) for {unknown_to_solve}:")

    # Define the symbols used in the expected solution for comparison
    R1_s_exp, Vin_s_exp, K_div_s_exp = sympy.symbols('R1_s Vin_s K_div_s')
    # Expected solution: R2_sym = R1_s / (K_div_s - 1)
    # Or, if Vin_s / (Vin_s / K_div_s - 1) ? No, that's not it.
    # V_N_out = Vin_s * R2_sym / (R1_s + R2_sym)
    # Target: V_N_out = Vin_s / K_div_s
    # So: Vin_s / K_div_s = Vin_s * R2_sym / (R1_s + R2_sym)
    # Assuming Vin_s is not zero, we can divide by Vin_s:
    # 1 / K_div_s = R2_sym / (R1_s + R2_sym)
    # R1_s + R2_sym = K_div_s * R2_sym
    # R1_s = K_div_s * R2_sym - R2_sym
    # R1_s = R2_sym * (K_div_s - 1)
    # R2_sym = R1_s / (K_div_s - 1)
    expected_symbolic_solution = R1_s_exp / (K_div_s_exp - 1)

    print(f"  Expected symbolic solution form for R2_sym: {expected_symbolic_solution}")

    for sol_idx, sol_expr in enumerate(solutions):
        print(f"  Solution {sol_idx + 1} (Symbolic Expr): {sol_expr}")

        # Verification by simplifying the difference
        simplified_diff = sympy.simplify(sol_expr - expected_symbolic_solution)
        if simplified_diff == 0:
            print(f"  SUCCESS: Solution {sol_idx + 1} matches the expected symbolic form.")
        else:
            print(f"  FAILURE: Solution {sol_idx + 1} does NOT match expected symbolic form.")
            print(f"           Simplified difference: {simplified_diff}")
            # Try expanding both to see if they are equivalent non-simplified forms
            # This can happen if sympy's default simplification isn't exactly what we wrote.
            if sympy.simplify(sympy.expand(sol_expr) - sympy.expand(expected_symbolic_solution)) == 0:
                 print(f"           However, they ARE equivalent after sympy.expand().")
            else:
                 print(f"           Also NOT equivalent after sympy.expand().")


else:
    print(f"No solution found for {unknown_to_solve} or an error occurred.")
