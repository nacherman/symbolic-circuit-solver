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

netlist_file_path = os.path.join(script_run_dir, "user_bridge_symbolic_r3_target_i.sp")

unknown_to_solve = 'R3_s'
target_quantity = 'I(VdummyI34)'
target_value_expression = 'I_target_s'

print(f"Attempting to solve for symbolic formula of '{unknown_to_solve}'")
print(f"Such that {target_quantity} = {target_value_expression}")
print(f"Using netlist: {netlist_file_path}")

solutions = solve_for_symbolic_unknown(
    netlist_path=netlist_file_path,
    unknown_param_name_str=unknown_to_solve,
    target_quantity_str=target_quantity,
    target_value_expr_str=target_value_expression
)

if solutions:
    print(f"Found symbolic solution(s) for {unknown_to_solve}:")
    r3_formula = solutions[0] # Expecting one formula
    print(f"  R3_s = {r3_formula}")

    print("\n--- Numerical Verification ---")
    # Define symbols as they appear in the formula (based on .PARAM names)
    U1_sym, U2_sym, R1_sym, R2_sym, R4_sym, R5_sym, R6_sym, I_target_sym = sympy.symbols(
        'U1_s U2_s R1_s R2_s R4_s R5_s R6_s I_target_s'
    )

    numerical_values = {
        U1_sym: 1.0,
        U2_sym: 0.1,
        R1_sym: 180.0,
        R2_sym: 100.0,
        R4_sym: 22.0,
        R5_sym: 39.0,
        R6_sym: 39.0,
        I_target_sym: -0.000559 # -0.559 mA
    }

    print(f"Substituting numerical values: {numerical_values}")

    try:
        r3_numerical_value = r3_formula.subs(numerical_values).evalf()
        print(f"  Calculated numerical R3_s = {r3_numerical_value:.4f} Ohms")

        expected_r3 = 56.18
        if abs(r3_numerical_value - expected_r3) < 0.1: # Tolerance
            print(f"  SUCCESS: Numerical R3 ({r3_numerical_value:.4f}) matches expected {expected_r3} Ohms (within tolerance).")
        else:
            print(f"  FAILURE: Numerical R3 ({r3_numerical_value:.4f}) does NOT match expected {expected_r3} Ohms.")
    except Exception as e:
        print(f"  Error during numerical substitution/evaluation: {e}")
        print(f"  Formula was: {r3_formula}")

else:
    print(f"No symbolic solution found for {unknown_to_solve} or an error occurred.")
