import sys
import os
import sympy

# Add project root to Python path - This needs to be adapted to the tool's execution environment
# Assuming the script is run from where 'extracted_files' is visible,
# and the symbolic_circuit_solver_master is inside 'extracted_files/sim12/sim/symbolic-circuit-solver-improve-h-bridge-example/symbolic-circuit-solver-improve-h-bridge-example/'
script_run_dir = os.getcwd() # Where this script itself is placed by the subtask
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

netlist_file_path = os.path.join(script_run_dir, "goal_seek_test.sp")

unknown_to_solve = 'Vin_s'
target_quantity = 'I(R1)' # Current through R1
target_value_expression = 'I_R1_target' # Target current

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
    # Define the expected symbols to compare against
    R1_sym_exp, R2_sym_exp, I_R1_target_sym_exp = sympy.symbols('R1_s R2_s I_R1_target')
    expected_solution = I_R1_target_sym_exp * (R1_sym_exp + R2_sym_exp)
    print(f"  Expected solution form: {expected_solution}")
    for sol_idx, sol_expr in enumerate(solutions):
        print(f"  Solution {sol_idx + 1}: {sol_expr}")
        # Verification
        simplified_diff = sympy.simplify(sol_expr - expected_solution)
        if simplified_diff == 0:
            print(f"  Solution {sol_idx + 1} matches the expected symbolic form.")
        else:
            print(f"  Solution {sol_idx + 1} does NOT match. Simplified difference: {simplified_diff}")
else:
    print(f"No solution found for {unknown_to_solve} or an error occurred.")
