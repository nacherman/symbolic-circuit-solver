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

netlist_file_path = os.path.join(script_run_dir, "goal_seek_vdiv_test.sp")

unknown_to_solve = 'R2_sym'
target_quantity = 'V(N_out)'
target_value_expression = '2.0' # Target V(N_out) = 2.0 Volts

print(f"Attempting to solve for '{unknown_to_solve}'")
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
    expected_r2_val = 2000.0 / 3.0
    print(f"  Expected R2_sym value: {expected_r2_val:.4f} Ohms")
    for sol_idx, sol_expr in enumerate(solutions):
        print(f"  Solution {sol_idx + 1} (Symbolic Expr): {sol_expr}")
        try:
            numeric_solution = float(sol_expr)
            print(f"  Numeric Solution {sol_idx + 1}: {numeric_solution:.4f} Ohms")
            if abs(numeric_solution - expected_r2_val) < 0.01: # Tolerance for float comparison
                print(f"  SUCCESS: Solution {sol_idx + 1} matches the expected numerical value.")
            else:
                print(f"  FAILURE: Solution {sol_idx + 1} ({numeric_solution:.4f}) does NOT match expected ({expected_r2_val:.4f}).")
        except Exception as e:
            print(f"  Could not convert solution {sol_expr} to float: {e}")
else:
    print(f"No solution found for {unknown_to_solve} or an error occurred.")
