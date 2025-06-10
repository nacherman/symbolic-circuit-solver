import sympy

def evaluate_symbolic_expr(expression, subs_dict: dict):
    """
    Substitutes symbols in a Sympy expression with numerical values from a dictionary
    and evaluates the expression to a float.

    Args:
        expression: The Sympy expression.
        subs_dict: A dictionary mapping Sympy symbols (or string names that can be
                   converted to symbols if needed, though direct symbol keys are preferred)
                   to numerical values.

    Returns:
        float: The evaluated numerical result, or None if an error occurs.
    """
    if expression is None:
        return None

    try:
        if not hasattr(expression, 'subs'):
            if subs_dict:
                pass
            else:
                return float(expression)

        substituted_expr = expression.subs(subs_dict)
        evaluated_result = substituted_expr.evalf()
        return float(evaluated_result)

    except (AttributeError, TypeError, ValueError, Exception) as e:
        # print(f"Warning: Could not evaluate expression '{expression}' with subs '{subs_dict}'. Error: {type(e).__name__}: {e}")
        return None

def compare_numerical_values(val1, val2, tolerance=1e-6):
    """
    Compares two numerical values within a given tolerance.

    Args:
        val1: The first numerical value.
        val2: The second numerical value.
        tolerance (float): The maximum allowed absolute difference. Defaults to 1e-6.

    Returns:
        bool: True if the absolute difference is within tolerance, False otherwise.
              Returns False if inputs are not numerical.
    """
    try:
        num1 = float(val1)
        num2 = float(val2)
        return abs(num1 - num2) <= tolerance
    except (TypeError, ValueError, AttributeError):
        return False

def generate_test_points(
    symbols_set: set,
    num_sets: int = 3,
    default_R_values: list = None,
    default_V_values: list = None,
    default_I_values: list = None,
    default_other_values: list = None
) -> list[dict]:
    """
    Generates a list of dictionaries, where each dictionary is a set of parameter values
    for a given set of Sympy symbols. Values are chosen cyclically from default lists
    based on symbol name prefixes (R, V, I, U).

    Args:
        symbols_set (set): A Python set of Sympy symbols.
        num_sets (int): The number of parameter value dictionaries to generate.
        default_R_values (list, optional): List of default values for resistor-like symbols.
        default_V_values (list, optional): List of default values for voltage-like symbols.
        default_I_values (list, optional): List of default values for current-like symbols.
        default_other_values (list, optional): List of default values for other symbols.

    Returns:
        list[dict]: A list of dictionaries, where keys are Sympy symbols and
                    values are their assigned numerical test values.
    """
    if default_R_values is None:
        default_R_values = [100.0, 1000.0, 10000.0]
    if default_V_values is None:
        default_V_values = [1.0, 5.0, 10.0]
    if default_I_values is None:
        default_I_values = [0.001, 0.01, 0.1]
    if default_other_values is None:
        default_other_values = [1.0, 2.0, 0.5]

    if not default_R_values: default_R_values = [1.0]
    if not default_V_values: default_V_values = [1.0]
    if not default_I_values: default_I_values = [1e-3]
    if not default_other_values: default_other_values = [1.0]

    test_point_dictionaries = []
    # Sort symbols by name to ensure consistent output order for dictionaries
    # This makes testing and comparison of generated sets easier.
    sorted_symbols = sorted(list(symbols_set), key=lambda s: s.name)


    for i in range(num_sets):
        current_params_dict = {}
        for symbol in sorted_symbols: # Iterate over sorted symbols
            symbol_name = symbol.name.lower()
            value_list_to_use = default_other_values

            if symbol_name.startswith('r'):
                value_list_to_use = default_R_values
            elif symbol_name.startswith(('v', 'u')):
                value_list_to_use = default_V_values
            elif symbol_name.startswith('i'):
                value_list_to_use = default_I_values

            selected_value = value_list_to_use[i % len(value_list_to_use)]
            current_params_dict[symbol] = selected_value

        test_point_dictionaries.append(current_params_dict)

    return test_point_dictionaries

if __name__ == '__main__':
    print("Testing scs_utils.py...")
    x, y = sympy.symbols('x y') # Define x,y for evaluate_symbolic_expr tests

    # Test evaluate_symbolic_expr
    expr1 = x + y
    subs1 = {x: 2, y: 3}
    print(f"Test 1: expr={expr1}, subs={subs1}, result={evaluate_symbolic_expr(expr1, subs1)}")

    expr2 = x * y
    subs2 = {x: 1.5, y: 2.0}
    print(f"Test 2: expr={expr2}, subs={subs2}, result={evaluate_symbolic_expr(expr2, subs2)}")

    expr3 = x / y
    subs3 = {sympy.Symbol('x'): 10, sympy.Symbol('y'): 4}
    print(f"Test 3: expr={expr3}, subs={subs3}, result={evaluate_symbolic_expr(expr3, subs3)}")

    expr4 = x + y
    subs4 = {x: 2}
    print(f"Test 4: expr={expr4}, subs={subs4}, result={evaluate_symbolic_expr(expr4, subs4)}")

    expr5 = 5.0
    subs5 = {}
    print(f"Test 5: expr={expr5}, subs={subs5}, result={evaluate_symbolic_expr(expr5, subs5)}")

    expr6 = sympy.Integer(10)
    subs6 = {}
    print(f"Test 6: expr={expr6}, subs={subs6}, result={evaluate_symbolic_expr(expr6, subs6)}")

    expr7 = "not_an_expression"
    subs7 = {}
    print(f"Test 7: expr='{expr7}', subs={subs7}, result={evaluate_symbolic_expr(expr7, subs7)}")

    expr8 = x + y
    subs8_str_keys = {'x': 5, 'y': 5}
    print(f"Test 8: expr={expr8}, subs={subs8_str_keys}, result={evaluate_symbolic_expr(expr8, subs8_str_keys)}")

    # Test compare_numerical_values
    print(f"Test C1: compare_numerical_values(1.0000005, 1.0, 1e-6) = {compare_numerical_values(1.0000005, 1.0, 1e-6)}")
    print(f"Test C2: compare_numerical_values(1.0000015, 1.0, 1e-6) = {compare_numerical_values(1.0000015, 1.0, 1e-6)}")
    print(f"Test C3: compare_numerical_values(5, 5.0000001, 1e-7) = {compare_numerical_values(5, 5.0000001, 1e-7)}")
    print(f"Test C4: compare_numerical_values(5, 5.0000002, 1e-7) = {compare_numerical_values(5, 5.0000002, 1e-7)}")
    print(f"Test C5: compare_numerical_values(10, 'abc') = {compare_numerical_values(10, 'abc')}")
    print(f"Test C6: compare_numerical_values(None, 5) = {compare_numerical_values(None, 5)}")
    print(f"Test C7: compare_numerical_values(sympy.Float(1.0000005), 1.0, 1e-6) = {compare_numerical_values(sympy.Float(1.0000005), 1.0, 1e-6)}")
    print(f"Test C8: compare_numerical_values(x, 1.0) = {compare_numerical_values(x, 1.0)}")
    print(f"Test C9: compare_numerical_values(10, 10) = {compare_numerical_values(10,10)}")

    print("\n--- Testing generate_test_points ---")
    R1_sym, R2_sym, Vin_sym, Iin_sym, Xpar_sym, Ugain_sym = sympy.symbols('R1_sym R2_sym Vin_sym Iin_sym Xpar_sym Ugain_sym')
    test_symbols = {R1_sym, R2_sym, Vin_sym, Iin_sym, Xpar_sym, Ugain_sym}

    print("\nTest GTP1: num_sets = 3")
    test_points1 = generate_test_points(test_symbols, num_sets=3)
    for i, point_set in enumerate(test_points1):
        # Sort items for consistent print order
        sorted_items = sorted(point_set.items(), key=lambda item: item[0].name)
        print(f"  Set {i}: {{ {', '.join([f'{str(k)}: {v}' for k, v in sorted_items])} }}")

    print("\nTest GTP2: num_sets = 5 (to show cycling)")
    test_points2 = generate_test_points(test_symbols, num_sets=5)
    for i, point_set in enumerate(test_points2):
        sorted_items = sorted(point_set.items(), key=lambda item: item[0].name)
        print(f"  Set {i}: {{ {', '.join([f'{str(k)}: {v}' for k, v in sorted_items])} }}")

    print("\nTest GTP3: Custom default values")
    custom_R = [50, 150]
    custom_V = [3.3]
    test_points3 = generate_test_points(test_symbols, num_sets=2, default_R_values=custom_R, default_V_values=custom_V)
    for i, point_set in enumerate(test_points3):
        sorted_items = sorted(point_set.items(), key=lambda item: item[0].name)
        print(f"  Set {i}: {{ {', '.join([f'{str(k)}: {v}' for k, v in sorted_items])} }}")

    print("\nTest GTP4: Empty symbol set")
    test_points4 = generate_test_points(set(), num_sets=3)
    for i, point_set in enumerate(test_points4):
        # No items to sort if point_set is empty
        print(f"  Set {i}: {{ {', '.join([f'{str(k)}: {v}' for k, v in point_set.items()])} }}")

    print("\nTest GTP5: num_sets = 0")
    test_points5 = generate_test_points(test_symbols, num_sets=0)
    print(f"  Result for num_sets=0: {test_points5}")

    print("\nTesting finished.")
