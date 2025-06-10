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
        # 1. Instantiate the solver
        solver = SymbolicCircuitProblemSolver(netlist_path=netlist_path)

        # 2. Define known conditions
        # Given: V(N3) = 0.1V (N3 relative to ground)
        # Given: Current through R4 (from N2 to N3) is 559uA
        # Netlist defines: R4 N2 N3 {R4_val} -> Positive current for R4 is N2->N3
        known_conditions = [
            {'type': 'voltage', 'node1': 'N3', 'node2': '0', 'value': 0.1},
            {'type': 'current', 'element': 'R4', 'value': 559e-6}
        ]

        # 3. Define parameters to solve for (as strings, matching .PARAM names)
        params_to_solve = ['R3_sym', 'U_sym']

        print(f"Known conditions: {known_conditions}")
        print(f"Parameters to solve for: {params_to_solve}")

        # 4. Solve for the unknowns
        solution = solver.solve_for_unknowns(known_conditions, params_to_solve)

        print("\n--- Solution ---")
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

        # 5. Calculate and print the power of R3
        # The solver already has the solution stored, so get_element_power will use it.
        r3_power_expr = solver.get_element_power('R3')

        print("\n--- Power Calculation ---")
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
