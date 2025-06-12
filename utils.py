# utils.py
import sympy as sp
# Ensure simplify is available, though it's usually part of the main sympy import
from sympy import simplify

def format_symbolic_expression(expr):
    """
    Formats a sympy expression using sympy.pretty for consistent output.
    Now also simplifies the expression.
    """
    if expr is None:
        return "None"
    try:
        # Simplify the expression before pretty printing
        simplified_expr = simplify(expr)
        return sp.pretty(simplified_expr)
    except Exception:
        # If simplification fails for some reason, pretty print original
        return sp.pretty(expr)


def print_solutions(solution_list, title="Solution"):
    """
    Prints the solutions in a structured way.
    Handles cases where solutions might be empty or contain multiple solution sets.
    Applies simplification to symbolic expressions.
    """
    print(f"\n--- {title} ---")
    if not solution_list: # Handles None or empty list from solver directly
        print("  No solution found or an error occurred in the solver.")
        return

    # Check if the list contains any non-empty dictionaries
    # any(solution_list) would be False if solution_list is [{}]
    # any(s for s in solution_list if s) handles lists like [{}, {}] or [{}, {'x':1}]
    if not any(s for s in solution_list if s):
        print("  No specific solution values found (system might be trivial, under-determined with no unique solution for requested vars, or solution was empty).")
        return

    if not isinstance(solution_list, list):
        print(f"  Unexpected solution format: {solution_list}")
        return

    for i, sol_dict in enumerate(solution_list):
        if not sol_dict:
            print(f"  Solution Set {i+1} is empty.")
            continue
        print(f"  Solution Set {i+1}:")
        # Sort items by symbol name for consistent output
        try:
            # Attempt to sort, hoping symbols have a consistent string representation
            sorted_items = sorted(sol_dict.items(), key=lambda item: str(item[0]))
        except Exception:
            # Fallback if sorting fails (e.g., mixed types that can't be compared via str)
            sorted_items = sol_dict.items()


        for sym, val in sorted_items:
            try:
                # Attempt to evaluate to a float with precision, and chop small errors
                num_val = float(val.evalf(chop=True))
                if abs(num_val - round(num_val)) < 1e-9:
                    print(f"    {str(sym):<15} = {int(round(num_val))}")
                else:
                    print(f"    {str(sym):<15} = {num_val:.6g}")
            except (AttributeError, TypeError, ValueError, sp.SympifyError): # Added SympifyError
                pretty_expr = format_symbolic_expression(val)
                lines = pretty_expr.split('\n')
                print(f"    {str(sym):<15} = {lines[0]}")
                for line in lines[1:]:
                    print(f"    {'':<15}   {line}")

    # This final check might be redundant given the initial checks, but kept for safety.
    # if not any(s for s in solution_list if s): # Re-check if any solution was actually processed
    #      print("  No solutions were processed or displayed (list might have contained only empty dicts).")


if __name__ == '__main__':
    s_x, s_y, s_z = sp.symbols('s_x s_y s_z')

    print("Testing print_solutions with various cases:")

    # Test case for simplification
    expr_unsimplified = (s_x**2 - 1) / (s_x - 1) + s_y * (s_z + 1) - s_y*s_z
    # Simplified: s_x + 1 + s_y

    example_sol_complex_sym = [{
        s_x: expr_unsimplified,
        s_y: s_x + s_y + s_z + s_x - s_z # Should simplify to 2*s_x + s_y
    }]
    print_solutions(example_sol_complex_sym, title="Example Solution with Simplification")

    example_sol_1 = [{s_x: 10, s_y: sp.Rational(1,2)}]
    print_solutions(example_sol_1, title="Example Solution 1 (Numeric)")

    R, I = sp.symbols('R I')
    example_sol_symbolic = [{s_x: R*I, s_y: I**2}]
    print_solutions(example_sol_symbolic, title="Example Solution 2 (Simple Symbolic)")

    example_sol_empty_dict_list = [{}] # A list containing one empty solution
    print_solutions(example_sol_empty_dict_list, title="Example Solution 3 (List with one empty dict)")

    example_sol_empty_list = [] # An actual empty list
    print_solutions(example_sol_empty_list, title="Example Solution 4 (Empty list from solver)")

    example_sol_none = None # Solver might return None
    print_solutions(example_sol_none, title="Example Solution 4b (None from solver)")

    example_sol_float = [{s_x: 3.141592653589793, s_y: 2.00000000012345}]
    print_solutions(example_sol_float, title="Example Solution 5 (Floats with chop and .6g)")

    example_sol_multiple_empty = [{}, {}]
    print_solutions(example_sol_multiple_empty, title="Test improved empty message (List of multiple empty dicts)")

    # Example with a slightly more complex structure that should simplify
    a = sp.Symbol('a')
    complex_expr = a + a + (a**2 - 1)/(a-1) - (a+1) + 5
    # simplifies to 2*a + 5
    print_solutions([{sp.Symbol('complex_val'): complex_expr}], title="Test complex simplification")

    # Example with multi-line pretty print
    f = sp.Function('f')
    multiline_expr = sp.Eq(f(s_x), sp.sin(s_x)/s_x + sp.cos(s_x)*s_x**2)
    print_solutions([{sp.Symbol('eq_ml'): multiline_expr}], title="Test multi-line pretty print")
