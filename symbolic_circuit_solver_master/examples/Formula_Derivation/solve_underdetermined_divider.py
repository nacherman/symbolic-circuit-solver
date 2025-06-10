import sys
import os
import sympy

# __file__ is .../symbolic_circuit_solver_master/examples/Formula_Derivation/solve_underdetermined_divider.py
script_dir = os.path.dirname(os.path.abspath(__file__))
# project_root_package_dir is .../symbolic_circuit_solver_master
project_root_package_dir = os.path.dirname(os.path.dirname(script_dir))
# path_to_add_for_package_import is .../ (the directory containing symbolic_circuit_solver_master, i.e. /app)
path_to_add_for_package_import = os.path.dirname(project_root_package_dir)
if path_to_add_for_package_import not in sys.path:
    sys.path.insert(0, path_to_add_for_package_import)

from symbolic_circuit_solver_master.scs_symbolic_solver_tool import SymbolicCircuitProblemSolver
from symbolic_circuit_solver_master.scs_errors import ScsParserError, ScsInstanceError, ScsToolError

def main():
    netlist_file = os.path.join(os.path.dirname(__file__), 'voltage_divider.sp') # Uses the existing .sp file

    print(f"Attempting to solve underdetermined Voltage Divider from netlist: {netlist_file}")
    print("This script demonstrates how SymbolicCircuitProblemSolver handles an underdetermined system,")
    print("where there are more unknowns to solve for than independent equations from known conditions.")

    # --- Step 1: Instantiate the SymbolicCircuitProblemSolver ---
    # It uses voltage_divider.sp, where US_sym, R1_sym, R2_sym are symbolic.
    solver_tool = SymbolicCircuitProblemSolver(netlist_path=netlist_file)

    # --- Step 2: Define a single known electrical condition ---
    # Current through R1 = 0.01 A.
    # This provides one equation: I(R1) = US_sym / (R1_sym + R2_sym) = 0.01.
    known_conditions = [
        {'type': 'current', 'element': 'R1', 'value': 0.01}
    ]

    # --- Step 3: Define parameters to solve for ---
    # We are trying to solve for all three symbolic parameters.
    params_to_solve = ['US_sym', 'R1_sym', 'R2_sym']

    try:
        print(f"\nKnown conditions: {known_conditions}")
        print(f"Parameters to solve for: {params_to_solve}")

        # --- Step 4: Call the solver ---
        solution = solver_tool.solve_for_unknowns(known_conditions, params_to_solve)

        print("\n--- Solution for Underdetermined System ---")
        if not solution: # This covers empty list and None
            print("No solution found or solution is empty.")
            print("This can happen with underdetermined systems if sympy.solve cannot easily express a parametric solution,")
            print("or if the system has no solution (e.g. contradictory equations).")
        else:
            print("Raw solution from sympy.solve:")
            # sympy.solve for underdetermined systems might return a list of solution dicts,
            # often with expressions for some variables in terms of others.
            # For this 1-equation, 3-unknowns system, it's likely to solve for one variable
            # in terms of the other two.
            print(solution) # solution is expected to be a list of dicts, or a single dict

            # If solution is a list, iterate through it (usually one dict for parametric solutions)
            solution_list = solution if isinstance(solution, list) else [solution]
            for sol_dict in solution_list:
                for var, expr in sol_dict.items():
                    print(f"  {var} = {expr}")

            print("\nExplanation of the result:")
            print("The system has 1 known condition (I(R1) = 0.01A) and 3 unknowns (US_sym, R1_sym, R2_sym).")
            print("This is an underdetermined system, so unique numerical values for all unknowns are not expected.")
            print("The solution above likely expresses one variable in terms of the others.")
            print("For example, I(R1) = US_sym / (R1_sym + R2_sym) = 0.01.")
            print("Sympy might solve this for US_sym: US_sym = 0.01 * (R1_sym + R2_sym),")
            print("or for R1_sym: R1_sym = (US_sym / 0.01) - R2_sym, etc.")
            print("The specific form depends on how sympy.solve processes the equations.")
            print("If the solution list is empty, it means no specific parameterization was found by sympy.solve.")


    except (ScsParserError, ScsInstanceError, ScsToolError, ValueError, FileNotFoundError) as e:
        print(f"An error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {type(e).__name__}: {e}")
        # import traceback
        # print(traceback.format_exc())

if __name__ == '__main__':
    main()
