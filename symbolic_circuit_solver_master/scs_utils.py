import sympy
import random
import math # Added import

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
    symbol_specific_random_ranges: dict = None # New parameter
) -> list[dict]:
    """
    Generates a list of dictionaries, where each dictionary is a set of parameter values
    for a given set of Sympy symbols.

    Args:
        symbols_set (set): A Python set of Sympy symbols.
        num_sets (int): The number of parameter value dictionaries to generate.
        custom_symbol_value_lists (dict, optional): Dictionary mapping symbols (or symbol names)
                                                     to specific lists of values to cycle through.
                                                     Takes precedence over default/random generation.
        default_R_values (list, optional): For 'cycle' mode, list of default values for R-like symbols.
        default_V_values (list, optional): For 'cycle' mode, list of default values for V-like symbols.
        default_I_values (list, optional): For 'cycle' mode, list of default values for I-like symbols.
        default_other_values (list, optional): For 'cycle' mode, list of default values for other symbols.
        generation_mode (str): 'cycle' (default cyclic selection) or 'random' (random selection).
        random_R_range (tuple): (min, max) for random R values. Ensure min > 0.
        random_V_range (tuple): (min, max) for random V values.
        random_I_range (tuple): (min, max) for random I values.
        random_other_range (tuple): (min, max) for random other values.
        log_scale_random_for_R (bool): If True and mode is 'random', R-types use log-scale.
        symbol_specific_random_ranges (dict, optional): Maps symbols (or names) to specific
                                                         (min, max) random ranges, overriding global ones.

    Returns:
        list[dict]: A list of dictionaries, where keys are Sympy symbols and
                    values are their assigned numerical test values.
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
