# utils.py
import sympy as sp
from sympy import simplify, Abs, arg, im, re, deg, N # Explicit imports

def format_symbolic_expression(expr):
    if expr is None: return "None"
    try:
        return sp.pretty(simplify(expr, rational=True))
    except Exception: return sp.pretty(expr)

def print_solutions(solution_list, title="Solution"):
    print(f"\n--- {title} ---")
    if not solution_list:
        print("  No solution found or an error occurred in the solver.")
        return
    if isinstance(solution_list, list) and not any(s for s in solution_list if s):
        print("  No specific solution values found.")
        return
    if not isinstance(solution_list, list):
        print(f"  Unexpected solution format: {solution_list}")
        return

    for i, sol_dict in enumerate(solution_list):
        if not sol_dict:
            print(f"  Solution Set {i+1} is empty.")
            continue
        print(f"  Solution Set {i+1}:")
        try:
            sorted_items = sorted(sol_dict.items(), key=lambda item: str(item[0]))
        except Exception: sorted_items = sol_dict.items()

        for sym, val in sorted_items:
            val_str = ""
            is_multiline_for_print = False
            rest_lines_for_print = []

            processed_as_numerical = False
            # Handle Python native numbers first
            if isinstance(val, (int, float)):
                if abs(val - round(val)) < 1e-9 and isinstance(val, float):
                    val_str = f"{int(round(val))}"
                elif isinstance(val, int):
                     val_str = f"{val}"
                else:
                    val_str = f"{val:.6g}"
                processed_as_numerical = True
            elif hasattr(val, 'evalf'): # For Sympy objects
                try:
                    num_val_evalf = val.evalf(n=15, chop=True)

                    if not num_val_evalf.free_symbols:
                        real_part_val = re(num_val_evalf)
                        imag_part_val = im(num_val_evalf)

                        real_check_tolerance = 1e-12
                        imag_part_as_float = float(imag_part_val.evalf(n=15))

                        if abs(imag_part_as_float) < real_check_tolerance:
                            f_val = float(real_part_val)
                            if abs(f_val - round(f_val)) < 1e-9:
                                val_str = f"{int(round(f_val))}"
                            else:
                                val_str = f"{f_val:.6g}"
                            processed_as_numerical = True
                        else:
                            rp_str = f"{float(real_part_val):.4g}"
                            ip_val_float = float(imag_part_val)

                            if ip_val_float >= 0:
                                val_str = f"{rp_str} + {ip_val_float:.4g}j"
                            else:
                                val_str = f"{rp_str} - {abs(ip_val_float):.4g}j"

                            magnitude = Abs(num_val_evalf)
                            phase_deg_val = deg(arg(num_val_evalf))
                            val_str += f"  (Polar: {float(magnitude):.4g} ∠ {float(phase_deg_val):.2f}°)"
                            processed_as_numerical = True
                except Exception:
                    processed_as_numerical = False

            if not processed_as_numerical:
                pretty_expr = format_symbolic_expression(val)
                lines = pretty_expr.split('\n')
                val_str = lines[0]
                if len(lines) > 1:
                    is_multiline_for_print = True
                    rest_lines_for_print = lines[1:]

            print(f"    {str(sym):<28} = {val_str}")
            if is_multiline_for_print:
                for line_content in rest_lines_for_print:
                    print(f"    {'':<28}   {line_content}")


if __name__ == '__main__':
    s_x, s_y, s_z, s_c1, s_c2 = sp.symbols('s_x s_y s_z s_c1 s_c2')

    print("Testing print_solutions with various cases (v11 - syntax REALLY corrected):")

    expr_unsimplified = (s_x**2 - 1) / (s_x - 1) + s_y * (s_z + 1) - s_y*s_z

    complex_num1 = 3 + 4*sp.I
    complex_num2 = sp.exp(sp.I * sp.pi / 3).evalf(n=15)
    complex_num_real = 5.0 + 1e-13*sp.I

    symbolic_complex = s_x + sp.I * s_y

    example_sol_ac = [{
        s_c1: complex_num1,
        s_c2: complex_num2,
        sp.Symbol('Z_eq_symbolic_complex'): symbolic_complex,
        sp.Symbol('RealNum_from_complex'): complex_num_real,
        sp.Symbol('Formula_to_simplify'): expr_unsimplified,
        sp.Symbol('PythonFloat'): 123.456789,
        sp.Symbol('PythonInt'): 123
    }]
    print_solutions(example_sol_ac, title="Example AC Solution with Complex Numbers & Simplification")

    example_sol_1 = [{s_x: 10, s_y: sp.Rational(1,2)}]
    print_solutions(example_sol_1, title="Example Solution 1 (Numeric)")

    R, I_sym = sp.symbols('R I_sym')
    example_sol_symbolic = [{s_x: I_sym*R, s_y: I_sym**2}]
    print_solutions(example_sol_symbolic, title="Example Solution 2 (Simple Symbolic)")

    example_sol_empty_dict_list = [{}]
    print_solutions(example_sol_empty_dict_list, title="Example Solution 3 (List with one empty dict)")

    example_sol_empty_list = []
    print_solutions(example_sol_empty_list, title="Example Solution 4 (Empty list from solver)")

    example_sol_none = None
    print_solutions(example_sol_none, title="Example Solution 4b (None from solver)")

    # Test with Python floats that should be formatted by the initial check
    example_sol_py_float = [{sp.Symbol('py_float1'): 3.1415926535, sp.Symbol('py_float2'): 2.0}]
    print_solutions(example_sol_py_float, title="Example Solution 5 (Python Floats with .6g formatting)")

    example_sol_multiple_empty = [{}, {}]
    print_solutions(example_sol_multiple_empty, title="Test improved empty message (List of multiple empty dicts)")

    a = sp.Symbol('a')
    complex_expr_sym = a + a + (a**2 - 1)/(a-1) - (a+1) + 5
    print_solutions([ {sp.Symbol('complex_expr_to_simplify'): complex_expr_sym} ], title="Test complex simplification")

    f = sp.Function('f')
    multiline_expr = sp.Eq(f(s_x), sp.sin(s_x)/s_x + sp.cos(s_x)*s_x**2)
    print_solutions([ {sp.Symbol('multiline_equation'): multiline_expr} ], title="Test multi-line pretty print")

    almost_real_num = 1.0 + 1e-15 * sp.I
    print_solutions([ {sp.Symbol('almost_real_num_chop'): almost_real_num} ], title="Test chopping small imaginary part")

    almost_imag_num = 1e-15 + 2.0 * sp.I
    print_solutions([ {sp.Symbol('almost_imag_num_small_real'): almost_imag_num} ], title="Test with small real part")

    pure_imag_num = 2.0 * sp.I
    print_solutions([ {sp.Symbol('pure_imag_num'): pure_imag_num} ], title="Test pure imaginary")

    neg_imag_num = 3 - 2*sp.I
    print_solutions([ {sp.Symbol('neg_imag_num'): neg_imag_num} ], title="Test negative imaginary part")
