# utils.py
import sympy as sp

def format_symbolic_expression(expr):
    """
    Formats a sympy expression using sympy.pretty for consistent output.
    More complex formatting or simplification could be added here later.
    """
    if expr is None:
        return "None"
    return sp.pretty(expr)

def print_solutions(solution_list, title="Solution"):
    """
    Prints the solutions in a structured way.
    Handles cases where solutions might be empty or contain multiple solution sets.
    """
    print(f"\n--- {title} ---")
    if not solution_list:
        print("  No solution found or an error occurred in the solver.")
        return

    if isinstance(solution_list, list) and not solution_list[0]: # Empty list of dicts
        print("  No unique solution found. The system might be under or over-determined, or inconsistent.")
        print("  Consider checking your knowns, unknowns, and constraints.")
        return

    if not isinstance(solution_list, list): # Should be a list of dicts
        print(f"  Unexpected solution format: {solution_list}")
        return

    for i, sol_dict in enumerate(solution_list):
        if not sol_dict: # Handles cases like [{}, {}]
            print(f"  Solution set {i+1} is empty (no specific values found for unknowns).")
            continue
        print(f"  Solution Set {i+1}:")
        for sym, val in sol_dict.items():
            try:
                num_val = float(val.evalf(chop=True)) # chop=True helps with small numerical errors
                # Check if it's effectively an integer
                if abs(num_val - round(num_val)) < 1e-9: # Tolerance for float comparison
                    print(f"    {sym} = {int(round(num_val))}")
                else:
                    print(f"    {sym} = {num_val:.6g}") # Use general format for floats
            except (AttributeError, TypeError, ValueError):
                print(f"    {sym} = {format_symbolic_expression(val)}")
    if not solution_list: # Redundant check, but covers if list was initially empty
         print("  No solutions were processed.")


if __name__ == '__main__':
    # Example usage for print_solutions
    s_x, s_y = sp.symbols('s_x s_y')
    example_sol_1 = [{s_x: 10, s_y: sp.Rational(1,2)}]
    example_sol_2 = [{s_x: 10, s_y: 20}, {s_x: -10, s_y: -20}]
    example_sol_3 = [{}] # Empty solution dict
    example_sol_4 = []   # Empty list

    print_solutions(example_sol_1, title="Example Solution 1 (Numeric)")
    # Expected: s_x = 10, s_y = 0.5

    R, I = sp.symbols('R I')
    example_sol_symbolic = [{s_x: R*I, s_y: I**2}]
    print_solutions(example_sol_symbolic, title="Example Solution 2 (Symbolic)")
    # Expected: s_x = R*I, s_y = I**2

    print_solutions(example_sol_3, title="Example Solution 3 (Empty dict)")
    print_solutions(example_sol_4, title="Example Solution 4 (Empty list)")

    example_sol_float = [{s_x: 3.1415926535, s_y: 2.0000000001}]
    print_solutions(example_sol_float, title="Example Solution 5 (Floats)")

    example_sol_mixed = [{s_x: 1.23456789, s_y: R}]
    print_solutions(example_sol_mixed, title="Example Solution 6 (Mixed)")
