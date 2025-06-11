"""
Utility functions for symbolic circuit analysis and verification.

This module provides helper functions for:
- Evaluating Sympy symbolic expressions with numerical substitutions.
- Comparing numerical values within a tolerance.
- Generating sets of test points (parameter value maps) for systematically
  testing or verifying circuit behavior under different conditions.
"""
import sympy
import random
import math

def evaluate_symbolic_expr(expression, subs_dict: dict):
    """
    Substitutes symbols in a Sympy expression and evaluates it to a float.

    If the expression itself is already a number and `subs_dict` is empty,
    it will be directly converted to float. If `subs_dict` is provided for an already
    numerical expression, it's ignored.
    Handles potential errors during substitution or evaluation by returning None.

    Args:
        expression: The Sympy expression (e.g., `x + y`) or a numerical value.
        subs_dict (dict): A dictionary mapping Sympy symbols (e.g., `sympy.Symbol('x')`)
                          to numerical values (e.g., `1.0`). String keys in `subs_dict`
                          are generally not processed directly by `expression.subs()`
                          unless the expression itself contains symbols matching those
                          string names (which is less common for Sympy expressions
                          created from symbolic analysis). It's recommended to use
                          Sympy symbols as keys in `subs_dict`.

    Returns:
        float or None: The evaluated numerical result as a float.
                       Returns None if the expression is None, or if any error
                       (e.g., AttributeError for non-Sympy objects without `subs`,
                       TypeError for incompatible operations, ValueError for failed
                       conversion to float) occurs during the process.
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
    Compares two numerical values within a specified absolute tolerance.

    Attempts to convert both input values to floats before comparison.
    If conversion fails for either value (e.g., they are not numerical),
    it returns False.

    Args:
        val1 (any): The first numerical value (or value convertible to float).
        val2 (any): The second numerical value (or value convertible to float).
        tolerance (float, optional): The maximum allowed absolute difference
                                     for the values to be considered equal.
                                     Defaults to 1e-6.

    Returns:
        bool: True if the absolute difference between `val1` and `val2`
              is less than or equal to `tolerance`.
              False if the difference is greater than `tolerance`, or if
              either value cannot be converted to a float.
    """
    try:
        num1 = float(val1)
        num2 = float(val2)
        diff = abs(num1 - num2)
        result = diff <= tolerance
        if not result and diff > 1e-9 : # Print only for significant differences, not just minor float dust if tolerance is loose
            print(f"[DEBUG compare_numerical_values] Mismatch: val1={val1}, val2={val2}, num1={num1:.18e}, num2={num2:.18e}, diff={diff:.18e}, tol={tolerance:.18e}, result={result}")
        return result
    except (TypeError, ValueError, AttributeError):
        return False

def generate_test_points(
    symbols_set: set,
    num_sets: int = 3,
    custom_symbol_value_lists: dict = None,
    default_R_values: list = None, # Used for 'cycle' mode
    default_V_values: list = None, # Used for 'cycle' mode
    default_I_values: list = None, # Used for 'cycle' mode
    default_other_values: list = None, # Used for 'cycle' mode
    generation_mode: str = 'cycle', # 'cycle' or 'random'
    random_R_range: tuple = (10.0, 100000.0),
    random_V_range: tuple = (-10.0, 10.0),
    random_I_range: tuple = (-1.0, 1.0),
    random_other_range: tuple = (0.1, 100.0),
    log_scale_random_for_R: bool = False,
    symbol_specific_random_ranges: dict = None
) -> list[dict]:
    """
    Generates sets of parameter values for a given collection of Sympy symbols.

    This function creates a specified number of "test points", where each test point
    is a dictionary mapping Sympy symbols to numerical values. These value sets can be
    generated using different strategies: cycling through predefined lists or
    generating random values (linearly or log-scaled).

    The generation process for each symbol in each test set follows this order of precedence:
    1.  **Custom List**: If the symbol is in `custom_symbol_value_lists` with a non-empty
        list, a value is chosen by cycling through that list (`set_index % list_length`).
    2.  **Random Generation** (if `generation_mode == 'random'` and not covered by custom list):
        a.  **Symbol-Specific Range**: If the symbol (or its string name) is in
            `symbol_specific_random_ranges` with a valid (min, max) tuple, that range is used.
        b.  **Global Type Range**: If no specific range, a global range
            (`random_R_range`, `random_V_range`, etc.) is chosen based on the symbol's
            name prefix ('r', 'v'/'u', 'i', or other).
        c.  **Log-Scale for R-types**: If `log_scale_random_for_R` is True and the symbol
            is R-type and the chosen range is valid for log scaling (min > 0, max > 0),
            the value is generated as `10**random.uniform(log10(min), log10(max))`.
            If the range is invalid for log-scale, a warning is printed, and it falls
            back to linear random generation.
        d.  **Linear Random**: Otherwise, `random.uniform(min, max)` is used.
        e.  Resistance values are ensured to be positive.
    3.  **Cyclic Default Generation** (if `generation_mode == 'cycle'` and not covered by custom list):
        A default list (`default_R_values`, etc.) is chosen based on symbol name prefix.
        A value is selected by cycling through this list (`set_index % list_length`).

    Args:
        symbols_set (set): A Python set of Sympy symbols (e.g., `{sympy.symbols('R1')}`).
        num_sets (int, optional): The number of parameter value dictionaries (test sets)
                                  to generate. Defaults to 3.
        custom_symbol_value_lists (dict, optional): A dictionary mapping Sympy symbols
                                                    or their string names to specific lists
                                                    of values. These values will be cycled
                                                    through for the respective symbols,
                                                    overriding any other generation rules.
                                                    Example: `{sympy.symbols('V_in'): [1.0, 1.5, 2.0]}`
                                                    or `{'V_in': [1.0, 1.5, 2.0]}`.
                                                    Defaults to None.
        default_R_values (list, optional): For `'cycle'` mode, the list of default
                                           values for symbols starting with 'r' or 'R'.
                                           Defaults to `[100.0, 1000.0, 10000.0]`.
        default_V_values (list, optional): For `'cycle'` mode, for symbols starting
                                           with 'v', 'V', 'u', or 'U'.
                                           Defaults to `[1.0, 5.0, 10.0]`.
        default_I_values (list, optional): For `'cycle'` mode, for symbols starting
                                           with 'i' or 'I'.
                                           Defaults to `[0.001, 0.01, 0.1]`.
        default_other_values (list, optional): For `'cycle'` mode, for any other symbols.
                                               Defaults to `[1.0, 2.0, 0.5]`.
        generation_mode (str, optional): Specifies the value generation strategy.
                                         - 'cycle': Values are chosen cyclically from
                                           default lists or custom lists. (Default)
                                         - 'random': Values are chosen randomly within
                                           specified ranges.
        random_R_range (tuple, optional): Default `(min, max)` tuple for R-type symbols
                                          in `'random'` mode. Defaults to `(10.0, 100000.0)`.
                                          Min must be > 0 for log-scaling.
        random_V_range (tuple, optional): Default `(min, max)` for V/U-type symbols
                                          in `'random'` mode. Defaults to `(-10.0, 10.0)`.
        random_I_range (tuple, optional): Default `(min, max)` for I-type symbols
                                          in `'random'` mode. Defaults to `(-1.0, 1.0)`.
        random_other_range (tuple, optional): Default `(min, max)` for other symbols
                                              in `'random'` mode. Defaults to `(0.1, 100.0)`.
        log_scale_random_for_R (bool, optional): If `True` and `generation_mode` is
                                                 `'random'`, R-type symbols will have values
                                                 generated from a log-uniform distribution
                                                 within their range. Defaults to False.
        symbol_specific_random_ranges (dict, optional): Maps Sympy symbols or their string
                                                        names to specific `(min, max)` tuples
                                                        for random generation, overriding the
                                                        global `random_..._range` for those
                                                        symbols. Works with `log_scale_random_for_R`.
                                                        Example: `{sympy.symbols('R_special'): (1, 1e6)}`.
                                                        Defaults to None.

    Returns:
        list[dict]: A list of dictionaries. Each dictionary represents a test set,
                    mapping each Sympy symbol from `symbols_set` to an assigned
                    numerical value. The order of symbols within each dictionary
                    is based on sorting their names alphabetically.
                    Example: `[{R1_sym: 100.0, V_in_sym: 1.0}, {R1_sym: 1000.0, V_in_sym: 5.0}]`

    Raises:
        ValueError: If an invalid `generation_mode` is provided.
    """
    if generation_mode == 'cycle':
        if default_R_values is None: default_R_values = [100.0, 1000.0, 10000.0]
        if default_V_values is None: default_V_values = [1.0, 5.0, 10.0]
        if default_I_values is None: default_I_values = [0.001, 0.01, 0.1]
        if default_other_values is None: default_other_values = [1.0, 2.0, 0.5]

        # Ensure lists are not empty for cycle mode
        if not default_R_values: default_R_values = [1.0]
        if not default_V_values: default_V_values = [1.0]
        if not default_I_values: default_I_values = [1e-3]
        if not default_other_values: default_other_values = [1.0]

    test_point_dictionaries = []
    sorted_symbols = sorted(list(symbols_set), key=lambda s: s.name)

    for i in range(num_sets):
        current_params_dict = {}
        for sym_idx, symbol in enumerate(sorted_symbols): # Use sym_idx for cycle mode if needed
            symbol_name_lower = symbol.name.lower()
            selected_value = None
            used_custom = False

            # 1. Check custom_symbol_value_lists first (applies to both modes)
            if custom_symbol_value_lists:
                # Allow symbol object or symbol name string as key in custom_symbol_value_lists
                custom_list = custom_symbol_value_lists.get(symbol, custom_symbol_value_lists.get(symbol.name))
                if isinstance(custom_list, list) and custom_list:
                    selected_value = custom_list[i % len(custom_list)]
                    used_custom = True

            if not used_custom:
                if generation_mode == 'random':
                    is_resistance = symbol_name_lower.startswith('r')
                    # Determine the range: specific symbol range > global type range
                    specific_range_found = False
                    current_range = None

                    if symbol_specific_random_ranges:
                        potential_range = symbol_specific_random_ranges.get(symbol,
                                                                        symbol_specific_random_ranges.get(symbol.name))
                        if isinstance(potential_range, tuple) and len(potential_range) == 2:
                            current_range = potential_range
                            specific_range_found = True
                            # print(f"Debug: Using specific range {current_range} for symbol {symbol.name}")
                        elif potential_range is not None: # Invalid specific range provided
                            print(f"Warning: Invalid specific range {potential_range} for symbol {symbol.name}. Falling back to global range.")

                    if not specific_range_found:
                        if is_resistance:
                            current_range = random_R_range
                        elif symbol_name_lower.startswith(('v', 'u')):
                            current_range = random_V_range
                        elif symbol_name_lower.startswith('i'):
                            current_range = random_I_range
                        else:
                            current_range = random_other_range

                    # Now current_range is set, either specific or global default for the type
                    val_range = current_range # Use this for subsequent logic

                    if is_resistance and log_scale_random_for_R:
                        min_r, max_r = val_range # val_range is now correctly specific or global
                        if min_r > 0 and max_r > 0:
                            log_min = math.log10(min_r)
                            log_max = math.log10(max_r)
                            selected_value = 10**random.uniform(log_min, log_max)
                        else:
                            print(f"Warning: Cannot use log-scale for R-symbol {symbol.name} due to non-positive range {val_range}. Falling back to linear random.")
                            selected_value = random.uniform(min_r, max_r)
                            # Still ensure positivity for resistance even in fallback
                            if selected_value <= 0:
                                selected_value = abs(selected_value) if selected_value != 0 else min_r if min_r > 0 else 1e-3
                                if selected_value == 0: selected_value = 1e-3 # Final fallback
                    else: # Linear random for non-R types or if log_scale_random_for_R is False
                        selected_value = random.uniform(val_range[0], val_range[1])

                    if is_resistance and selected_value <= 0: # General check for R, esp. after linear or fallback
                        # This check might be redundant if log-scale path is taken and min_r > 0,
                        # but important for linear path or if log-scale fallback occurs with problematic range.
                        original_range_min = val_range[0] if val_range else 0.001 # default small R
                        selected_value = abs(selected_value) if selected_value != 0 else original_range_min
                        if selected_value == 0: selected_value = 1e-3

                elif generation_mode == 'cycle':
                    value_list_to_use = None
                    if symbol_name_lower.startswith('r'):
                        value_list_to_use = default_R_values
                    elif symbol_name_lower.startswith(('v', 'u')):
                        value_list_to_use = default_V_values
                    elif symbol_name_lower.startswith('i'):
                        value_list_to_use = default_I_values
                    else:
                        value_list_to_use = default_other_values
                    # Original cyclic logic used 'i' (set index) + 'sym_idx' (symbol index in sorted list)
                    # to provide more variation across symbols within the same set.
                    # Let's decide if we keep that or simplify to just 'i'.
                    # The original prompt text implies "cyclically from default lists", which `i % len` achieves per symbol.
                    # The previous code was `value_list_to_use[i % len(value_list_to_use)]`
                    # This means all R's get same sequence, all V's get same sequence etc.
                    # If we want R1, R2 to differ within the same set, we need sym_idx.
                    # Reverting to the simpler interpretation for now as per problem description.
                    selected_value = value_list_to_use[i % len(value_list_to_use)]
                else:
                    raise ValueError(f"Invalid generation_mode: {generation_mode}. Must be 'cycle' or 'random'.")

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
    print(f"  Result for num_sets=0 (cycle mode): {test_points5}")
    test_points5_random = generate_test_points(test_symbols, num_sets=0, generation_mode='random')
    print(f"  Result for num_sets=0 (random mode): {test_points5_random}")

    print("\n--- Testing generate_test_points with mode='random' ---")
    R_rand, V_rand, I_rand, Other_rand = sympy.symbols('R_rand V_rand I_rand Other_rand')
    rand_symbols = {R_rand, V_rand, I_rand, Other_rand}

    # Default random ranges for checks
    check_R_range = (10.0, 100000.0)
    check_V_range = (-10.0, 10.0)
    check_I_range = (-1.0, 1.0)
    check_Other_range = (0.1, 100.0)

    print("\nTest GTP_Rand1: Basic random generation (num_sets = 3)")
    rand_points1 = generate_test_points(rand_symbols, num_sets=3, generation_mode='random')
    for i, point_set in enumerate(rand_points1):
        sorted_items = sorted(point_set.items(), key=lambda item: item[0].name)
        print(f"  Set {i}: {{ {', '.join([f'{str(k)}: {v:.4f}' for k, v in sorted_items])} }}")
        for sym, val in point_set.items():
            s_name = sym.name.lower()
            valid_range = True
            if s_name.startswith('r'):
                if not (check_R_range[0] <= val <= check_R_range[1] and val > 0): valid_range = False
            elif s_name.startswith('v'):
                if not (check_V_range[0] <= val <= check_V_range[1]): valid_range = False
            elif s_name.startswith('i'):
                if not (check_I_range[0] <= val <= check_I_range[1]): valid_range = False
            else: # Other
                if not (check_Other_range[0] <= val <= check_Other_range[1]): valid_range = False
            if not valid_range:
                print(f"    ERROR: Symbol {sym.name} value {val} out of expected range for its type!")
            else:
                print(f"    Symbol {sym.name} value {val:.4f} is within expected random range.")


    print("\nTest GTP_Rand2: Random generation with custom list override (num_sets = 5)")
    custom_V_rand_list = [3.3, 5.0, 1.2] # Custom list for V_rand
    # For R_rand, we'll use a custom list. It should override even log-scale attempts.
    custom_R_rand_list = [1.0, 10.0, 100.0, 1000.0, 10000.0]
    rand_points2 = generate_test_points(
        rand_symbols,
        num_sets=5,
        generation_mode='random',
        custom_symbol_value_lists={V_rand: custom_V_rand_list, R_rand.name: custom_R_rand_list} # Test string key for R_rand
    )
    for i, point_set in enumerate(rand_points2):
        sorted_items = sorted(point_set.items(), key=lambda item: item[0].name)
        print(f"  Set {i}: {{ {', '.join([f'{str(k)}: {v:.4f}' if isinstance(v, float) else str(v) for k, v in sorted_items])} }}")
        for sym, val in point_set.items():
            s_name = sym.name.lower()
            valid_range = True
            is_custom = False
            if sym == V_rand:
                is_custom = True
                expected_val = custom_V_rand_list[i % len(custom_V_rand_list)]
                if val != expected_val:
                    print(f"    ERROR: V_rand (custom) expected {expected_val}, got {val}")
                    valid_range = False
                else:
                    print(f"    V_rand (custom) got {val} (matches expected custom cycle).")
            elif sym == R_rand: # R_rand has custom list by name
                is_custom = True
                expected_val_r = custom_R_rand_list[i % len(custom_R_rand_list)]
                if val != expected_val_r:
                    print(f"    ERROR: R_rand (custom by name) expected {expected_val_r}, got {val}")
                    valid_range = False # Not really a range issue, but a deviation from custom
                else:
                    print(f"    R_rand (custom by name) got {val} (matches expected custom cycle).")

            if not is_custom: # For I_rand and Other_rand, check random ranges
                if s_name.startswith('i'): # I_rand
                    if not (check_I_range[0] <= val <= check_I_range[1]): valid_range = False
                elif s_name.startswith('o'): # Other_rand
                    if not (check_Other_range[0] <= val <= check_Other_range[1]): valid_range = False

                if not valid_range: # This valid_range flag is now a bit mixed, true if it matches type's expectation
                    print(f"    ERROR: Symbol {sym.name} value {val} out of expected random range for its type!")
                else:
                    print(f"    Symbol {sym.name} value {val:.4f} is within expected random range.")

    print("\n--- Testing generate_test_points with log_scale_random_for_R=True ---")
    R_log1, R_log2, V_lin_logtest = sympy.symbols('R_log1 R_log2 V_lin_logtest')
    log_test_symbols = {R_log1, R_log2, V_lin_logtest}

    print("\nTest GTP_Log1: Log-scale R, Linear V (num_sets = 5)")
    log_points1 = generate_test_points(
        log_test_symbols,
        num_sets=5,
        generation_mode='random',
        log_scale_random_for_R=True,
        random_R_range=(10, 100000) # Min 10, Max 100k
    )
    for i, point_set in enumerate(log_points1):
        sorted_items = sorted(point_set.items(), key=lambda item: item[0].name)
        print(f"  Set {i}: {{ {', '.join([f'{str(k)}: {v:.4f}' for k, v in sorted_items])} }}")
        for sym, val in point_set.items():
            s_name = sym.name.lower()
            if s_name.startswith('r'): # R_log1, R_log2
                if not (check_R_range[0] <= val <= check_R_range[1] and val > 0):
                     print(f"    ERROR: R-type {sym.name} value {val:.4f} out of range {check_R_range} or non-positive.")
                else:
                     print(f"    R-type {sym.name} value {val:.4f} (log-scale) is within range {check_R_range}.")
                     # Visual check: values should span orders of magnitude more readily.
            elif s_name.startswith('v'): # V_lin_logtest
                if not (check_V_range[0] <= val <= check_V_range[1]):
                     print(f"    ERROR: V-type {sym.name} value {val:.4f} out of range {check_V_range}.")
                else:
                     print(f"    V-type {sym.name} value {val:.4f} (linear) is within range {check_V_range}.")

    print("\nTest GTP_Log2: Log-scale R with custom override for one R")
    R_custom_log, R_actual_log = sympy.symbols('R_custom_log R_actual_log')
    log_override_symbols = {R_custom_log, R_actual_log, V_lin_logtest}
    custom_R_log_list = [1.0, 100.0, 10000.0]
    log_points2 = generate_test_points(
        log_override_symbols,
        num_sets=3,
        generation_mode='random',
        log_scale_random_for_R=True,
        custom_symbol_value_lists={R_custom_log: custom_R_log_list},
        random_R_range=(1.0, 10000.0) # For R_actual_log
    )
    for i, point_set in enumerate(log_points2):
        sorted_items = sorted(point_set.items(), key=lambda item: item[0].name)
        print(f"  Set {i}: {{ {', '.join([f'{str(k)}: {v:.4f}' if isinstance(v, float) else str(v) for k, v in sorted_items])} }}")
        for sym, val in point_set.items():
            if sym == R_custom_log:
                expected_val = custom_R_log_list[i % len(custom_R_log_list)]
                if val != expected_val: print(f"    ERROR: {sym.name} (custom) expected {expected_val}, got {val}")
                else: print(f"    {sym.name} (custom) got {val} (matches expected).")
            elif sym == R_actual_log:
                if not (1.0 <= val <= 10000.0 and val > 0): print(f"    ERROR: {sym.name} (log-random) value {val:.4f} out of range (1.0, 10000.0) or non-positive.")
                else: print(f"    {sym.name} (log-random) value {val:.4f} is within range.")
            elif sym == V_lin_logtest: # Should be linear
                 if not (check_V_range[0] <= val <= check_V_range[1]): print(f"    ERROR: {sym.name} (linear) value {val:.4f} out of range {check_V_range}.")
                 else: print(f"    {sym.name} (linear) value {val:.4f} is within range.")

    print("\nTest GTP_Log3: Invalid range for log-scale R (e.g., min_r <= 0)")
    R_bad_range = sympy.symbols('R_bad_range')
    log_points3 = generate_test_points(
        {R_bad_range},
        num_sets=2,
        generation_mode='random',
        log_scale_random_for_R=True,
        random_R_range=(0, 100) # Global range invalid for log scale for R_bad_range
    )
    # Expect a warning printed by the function, and R_bad_range should use linear random.
    for i, point_set in enumerate(log_points3):
        val = point_set[R_bad_range]
        print(f"  Set {i} for R_bad_range (global range (0,100), expect linear fallback): {R_bad_range.name}={val:.4f}")
        if not (0 <= val <= 100): # Check against linear range
            print(f"    ERROR: R_bad_range value {val:.4f} out of expected linear fallback range (0,100).")
        else:
            print(f"    R_bad_range value {val:.4f} is within linear fallback range (0,100).")

    print("\nTest GTP_Log4: Symbol-specific range that is invalid for log-scale R")
    R_spec_bad_log = sympy.symbols('R_spec_bad_log')
    log_points4 = generate_test_points(
        {R_spec_bad_log},
        num_sets=2,
        generation_mode='random',
        log_scale_random_for_R=True,
        symbol_specific_random_ranges={R_spec_bad_log: (-5, 5)}, # Specific range invalid for log
        random_R_range=(10,1000) # Global R range is fine, but specific should be chosen and fail log
    )
    for i, point_set in enumerate(log_points4):
        val = point_set[R_spec_bad_log]
        print(f"  Set {i} for R_spec_bad_log (specific range (-5,5), expect linear fallback): {R_spec_bad_log.name}={val:.4f}")
        if not (-5 <= val <= 5):
            print(f"    ERROR: R_spec_bad_log value {val:.4f} out of expected linear fallback range (-5,5).")
        else:
            print(f"    R_spec_bad_log value {val:.4f} is within linear fallback range (-5,5).")


    print("\nTest GTP_SpecificRand1: Symbol-specific random ranges overriding global (incl. log-scale interaction)")
    R_spec1, R_spec2_log, V_spec, Other_global = sympy.symbols('R_spec1 R_spec2_log V_spec Other_global')
    spec_rand_symbols = {R_spec1, R_spec2_log, V_spec, Other_global}

    spec_ranges = {
        R_spec1: (1.0, 5.0),  # R_spec1 will use this linear range as log_scale_random_for_R is per-type
        R_spec2_log: (10.0, 1000.0), # R_spec2_log will use this log-scaled
        V_spec: (100.0, 200.0),      # V_spec will use this linear range
        "Other_global_nonexistent": (0,0) # test non-existent symbol key
    }
    # Other_global will use global random_other_range = (0.1, 100.0)

    spec_rand_points = generate_test_points(
        spec_rand_symbols,
        num_sets=3,
        generation_mode='random',
        log_scale_random_for_R=True, # R_spec2_log should be log, R_spec1 should use its specific range linearly (as log scale is for 'R' type)
                                     # Correction: log_scale_random_for_R applies to ALL R-types. So R_spec1 will also be log if its range (1,5) is valid.
        symbol_specific_random_ranges=spec_ranges
    )

    for i, point_set in enumerate(spec_rand_points):
        sorted_items = sorted(point_set.items(), key=lambda item: item[0].name)
        print(f"  Set {i}: {{ {', '.join([f'{str(k)}: {v:.4f}' for k, v in sorted_items])} }}")
        for sym, val in point_set.items():
            s_name = sym.name
            if s_name == 'R_spec1': # Expect log-scale over (1.0, 5.0)
                if not (1.0 <= val <= 5.0 and val > 0): print(f"    ERROR: {s_name} value {val:.4f} out of range (1.0, 5.0)")
                else: print(f"    {s_name} value {val:.4f} (log-scale over specific 1-5) OK.")
            elif s_name == 'R_spec2_log': # Expect log-scale over (10.0, 1000.0)
                if not (10.0 <= val <= 1000.0 and val > 0): print(f"    ERROR: {s_name} value {val:.4f} out of range (10.0, 1000.0)")
                else: print(f"    {s_name} value {val:.4f} (log-scale over specific 10-1000) OK.")
            elif s_name == 'V_spec': # Expect linear over (100.0, 200.0)
                if not (100.0 <= val <= 200.0): print(f"    ERROR: {s_name} value {val:.4f} out of range (100.0, 200.0)")
                else: print(f"    {s_name} value {val:.4f} (linear over specific 100-200) OK.")
            elif s_name == 'Other_global': # Expect linear over global check_Other_range (0.1, 100.0)
                if not (check_Other_range[0] <= val <= check_Other_range[1]): print(f"    ERROR: {s_name} value {val:.4f} out of global range {check_Other_range}")
                else: print(f"    {s_name} value {val:.4f} (linear over global {check_Other_range}) OK.")
            else:
                print(f"    Unknown symbol {s_name} in test output.")


    print("\nTesting finished.")
