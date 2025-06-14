import sys
import os
import sympy # Ensure sympy is imported for sympy.symbols if used directly

# __file__ is .../symbolic_circuit_solver_master/examples/Power_Condition_Test/solve_power_test.py
script_dir = os.path.dirname(os.path.abspath(__file__))
# project_root is .../symbolic_circuit_solver_master
project_root = os.path.dirname(os.path.dirname(script_dir))
# path_to_add is .../ (the directory containing symbolic_circuit_solver_master, i.e. /app)
path_to_add = os.path.dirname(project_root)
if path_to_add not in sys.path: # Ensure we don't add duplicate paths if script is run multiple times in a session
    sys.path.insert(0, path_to_add)

from symbolic_circuit_solver_master.scs_symbolic_solver_tool import SymbolicCircuitProblemSolver
from symbolic_circuit_solver_master.scs_errors import ScsParserError, ScsInstanceError, ScsToolError

def main():
    netlist_file = os.path.join(os.path.dirname(__file__), 'power_test.sp')

    print(f"Attempting to solve Power Condition Test using netlist: {netlist_file}")
    print("This script tests the ability of SymbolicCircuitProblemSolver to solve for an unknown")
    print("parameter (R2_sym) given a power condition on another component (R1).")

    # --- Step 1: Instantiate the SymbolicCircuitProblemSolver ---
    solver = SymbolicCircuitProblemSolver(netlist_path=netlist_file)

    # --- Step 2: Define known electrical conditions ---
    # Condition: Power dissipated by resistor R1 is 1.25 Watts.
    # The element name 'R1' must match its definition in the SPICE file.
    known_conditions = [
        {'type': 'power', 'element': 'R1', 'value': 1.25}
    ]

    # --- Step 3: Define the symbolic parameter(s) to solve for ---
    # 'R2_sym' is expected to be defined in the SPICE netlist (e.g., .PARAM R2_val = R2_sym, .PARAM R2_sym = R2_sym)
    params_to_solve = ['R2_sym']

    try:
        print(f"\nKnown conditions: {known_conditions}")
        print(f"Parameters to solve for: {params_to_solve}")

        # --- Step 4: Call the solver ---
        solution = solver.solve_for_unknowns(known_conditions, params_to_solve)

        print("\n--- Solution for Unknown Parameters ---")
        if not solution: # Handles None or empty list/dict from solver
            print("No solution found or solution is empty.")
            print("This might indicate an issue with the problem formulation or that sympy.solve found no solution.")
        else:
            # sympy.solve might return a list of solutions (dicts) or a single dict.
            # The SymbolicCircuitProblemSolver currently returns solution[0] if it's a list.
            solution_dict = solution if isinstance(solution, dict) else solution[0] if isinstance(solution, list) and solution else {}

            if not solution_dict:
                 print("Solution was empty after processing.")
            else:
                for var, val in solution_dict.items():
                    # var here is expected to be a sympy.Symbol object (e.g., sympy.Symbol('R2_sym'))
                    var_name = str(var)
                    print(f"Solved: {var_name} = {val}")
                    # Try to get a numerical representation
                    if hasattr(val, 'evalf'):
                        numeric_val = val.evalf()
                        print(f"  Numerical value for {var_name}: {numeric_val:.4f}")
                    else:
                        # If it doesn't have evalf, it might be a direct number or a non-sympy object
                        print(f"  Numerical value for {var_name}: {val} (direct value, or type: {type(val).__name__})")

            print("\n--- Expected vs. Actual Solution ---")
            print("The circuit is VS (10V) in series with R1 (5 Ohms) and R2 (R2_sym).")
            print("Power in R1 given as 1.25W.")
            print("Equation: P_R1 = (VS / (R1 + R2_sym))^2 * R1")
            print("1.25 = (10 / (5 + R2_sym))^2 * 5")
            print("This leads to two mathematical solutions for R2_sym: +15 Ohms and -25 Ohms.")
            print("The solver may return either of these. A negative resistance is generally not physical for a passive resistor.")

    except (ScsParserError, ScsInstanceError, ScsToolError, ValueError, FileNotFoundError) as e:
        print(f"An error occurred during the solving process: {e}")
        # For detailed debugging if sympy.solve fails with complex expressions:
        # import traceback
        # print(traceback.format_exc())
    except Exception as e:
        print(f"An unexpected error occurred: {type(e).__name__}: {e}")
        # import traceback
        # print(traceback.format_exc())

if __name__ == '__main__':
    main()
