import sympy as sp
from sympy.solvers.solveset import linsolve
from symbolic_components import BaseComponent, Resistor, Inductor, Capacitor, VoltageSource, CurrentSource, VCVS, VCCS, CCVS, CCCS, omega as omega_sym_global
from utils import print_solutions


def solve_circuit(components, unknown_symbols_to_solve_for, known_substitutions=None, additional_equations=None, ground_node='GND'):
    if not components and not additional_equations:
        raise ValueError("Components list or additional_equations must be provided.")

    current_equations = []
    all_nodes = set()
    node_voltage_symbols = {}

    parameter_symbols = {omega_sym_global}
    user_requested_symbols_set = {sp.sympify(s) for s in (unknown_symbols_to_solve_for or [])}


    if components:
        for comp in components:
            if not isinstance(comp, BaseComponent):
                raise TypeError(f"Item {comp} in components list is not a BaseComponent.")
            current_equations.extend(comp.expressions)
            all_nodes.add(comp.node1)
            all_nodes.add(comp.node2)
            if isinstance(comp, Resistor): parameter_symbols.add(comp.R_val)
            elif isinstance(comp, Inductor): parameter_symbols.add(comp.L_val)
            elif isinstance(comp, Capacitor): parameter_symbols.add(comp.C_val)
            elif isinstance(comp, VoltageSource): parameter_symbols.add(comp.V_source_val)
            elif isinstance(comp, CurrentSource): parameter_symbols.add(comp.I_source_val)
            elif isinstance(comp, VCVS): parameter_symbols.add(comp.gain)
            elif isinstance(comp, VCCS): parameter_symbols.add(comp.transconductance)
            elif isinstance(comp, CCVS): parameter_symbols.add(comp.transresistance)
            elif isinstance(comp, CCCS): parameter_symbols.add(comp.gain)

        ground_subs_dict = {}
        if ground_node in all_nodes :
            for node_name in all_nodes:
                if node_name == ground_node:
                    node_voltage_symbols[node_name] = sp.Integer(0)
                    ground_sym_in_comp = sp.Symbol(f"V_{ground_node}")
                    if ground_sym_in_comp != sp.Integer(0):
                         ground_subs_dict[ground_sym_in_comp] = sp.Integer(0)
                else:
                    node_voltage_symbols[node_name] = sp.Symbol(f"V_{node_name}")
            if ground_subs_dict:
                current_equations = [eq.subs(ground_subs_dict) for eq in current_equations]
        else:
            for node_name in all_nodes:
                 node_voltage_symbols[node_name] = sp.Symbol(f"V_{node_name}")

        kcl_equations = []
        nodes_for_kcl = all_nodes
        if ground_node in all_nodes:
            nodes_for_kcl = set(n for n in all_nodes if n != ground_node)
        for node_name in nodes_for_kcl:
            currents_into_node = sp.Integer(0)
            for comp in components:
                if comp.node1 == node_name: currents_into_node -= comp.I_comp
                elif comp.node2 == node_name: currents_into_node += comp.I_comp
            if currents_into_node != 0:
                kcl_equations.append(currents_into_node)
        current_equations.extend(kcl_equations)

    master_subs = {sp.sympify(s): sp.sympify(v) for s, v in (known_substitutions or {}).items()}
    current_equations = [eq.subs(master_subs) for eq in current_equations]
    if additional_equations:
        current_equations.extend([eq.subs(master_subs) for eq in additional_equations])

    MAX_PASSES = 15
    for _pass_num in range(MAX_PASSES):
        new_substitutions_found_in_pass = False
        next_round_equations = []
        equations_to_process_this_pass = list(current_equations)
        current_equations = []
        eq_idx = 0
        while eq_idx < len(equations_to_process_this_pass):
            eq = equations_to_process_this_pass[eq_idx]

            simplified_eq_check = eq.simplify() if hasattr(eq, 'simplify') else eq
            if simplified_eq_check == True or simplified_eq_check == sp.true or \
               (hasattr(simplified_eq_check, 'is_number') and simplified_eq_check.is_number and simplified_eq_check == 0) :
                eq_idx += 1; continue
            if simplified_eq_check == False or simplified_eq_check == sp.false or \
               (hasattr(simplified_eq_check, 'is_number') and simplified_eq_check.is_number and simplified_eq_check != 0) :
                print(f"DEBUG: Equation evaluates to {simplified_eq_check}, system likely inconsistent (Pass {_pass_num + 1}). Original eq: {sp.pretty(eq)}")
                return []

            substituted_this_eq_for_a_symbol = False
            symbols_in_eq = sorted(list(eq.free_symbols), key=str)
            for symbol in symbols_in_eq:
                is_parameter_explicitly_known = symbol in (known_substitutions or {})

                if symbol in master_subs and not is_parameter_explicitly_known:
                    continue
                # MODIFIED Parameter Protection: Do not solve for a parameter symbol UNLESS it's explicitly requested as an unknown
                if symbol in parameter_symbols and not is_parameter_explicitly_known and symbol not in user_requested_symbols_set:
                    continue

                try:
                    sol = sp.solve(eq, symbol, dict=False)
                    if isinstance(sol, list) and len(sol) == 1:
                        expr_val = sol[0]
                        if symbol in expr_val.free_symbols: continue

                        # print(f"  Preprocessing (Pass {_pass_num+1}): From {sp.pretty(eq)}=0, derived {symbol}={sp.pretty(expr_val)}") # DEBUG

                        current_substitution = {symbol: expr_val}
                        master_subs[symbol] = expr_val
                        new_substitutions_found_in_pass = True
                        substituted_this_eq_for_a_symbol = True

                        next_round_equations = [neq.subs(current_substitution).simplify() for neq in next_round_equations]
                        for i in range(eq_idx + 1, len(equations_to_process_this_pass)):
                            equations_to_process_this_pass[i] = equations_to_process_this_pass[i].subs(current_substitution).simplify()
                        break
                except Exception: pass

            if not substituted_this_eq_for_a_symbol: next_round_equations.append(eq)
            eq_idx +=1

        current_equations = next_round_equations
        if not new_substitutions_found_in_pass : break

    processed_equations = [eq for eq in current_equations if not (eq == True or eq == sp.true or (hasattr(eq, 'is_number') and eq.is_number and eq == 0))]
    processed_equations = list(set(processed_equations))

    symbols_to_solve = set()
    # user_requested_symbols_set was created at the beginning
    for s_usr_sym in user_requested_symbols_set:
        if s_usr_sym not in master_subs: symbols_to_solve.add(s_usr_sym)

    if components:
        for node, v_sym in node_voltage_symbols.items():
            is_ground_node = (ground_node in all_nodes and node == ground_node)
            if not is_ground_node and v_sym not in master_subs: symbols_to_solve.add(v_sym)
        for comp in components:
            for sym_attr_name in ['V_comp', 'I_comp', 'P_comp']:
                 sym_attr = getattr(comp, sym_attr_name, None)
                 if sym_attr and sym_attr not in master_subs: symbols_to_solve.add(sym_attr)

    all_free_symbols_in_equations = set()
    for eq in processed_equations: all_free_symbols_in_equations.update(eq.free_symbols)
    for s in all_free_symbols_in_equations:
        if s not in master_subs: symbols_to_solve.add(s)

    final_symbols_to_solve_list = sorted(list(symbols_to_solve), key=lambda s: str(s))

    master_subs_print = { (s.name if hasattr(s,'name') else str(s)) : v for s,v in master_subs.items()}
    print(f"DEBUG: Master substitutions made: {master_subs_print}")
    print(f"DEBUG: Equations to solve ({len(processed_equations)}):")
    for i, eq_debug in enumerate(processed_equations): print(f"  Eq{i+1}: {sp.pretty(eq_debug)}")
    print(f"DEBUG: Symbols to solve for ({len(final_symbols_to_solve_list)}): {[s.name if hasattr(s,'name') else str(s) for s in final_symbols_to_solve_list]}")

    def fully_substitute(expr, subs_dict, max_depth=MAX_PASSES):
        if not hasattr(expr, 'subs') or not hasattr(expr, 'free_symbols'): return expr
        current_expr = expr
        for _ in range(max_depth):
            prev_expr = current_expr
            symbols_in_current_expr = current_expr.free_symbols
            relevant_subs = {s: subs_dict[s] for s in symbols_in_current_expr if s in subs_dict}
            if not relevant_subs: break
            current_expr = current_expr.subs(relevant_subs)
            if current_expr == prev_expr: break
        return current_expr

    if not final_symbols_to_solve_list:
        is_consistent_or_empty = True
        if processed_equations:
            # print("DEBUG: No symbols for sympy.solve, but equations remain. Checking consistency.")
            for eq in processed_equations:
                simplified_eq = fully_substitute(eq, master_subs).simplify()
                if not (simplified_eq == True or simplified_eq == sp.true or simplified_eq == 0):
                    is_consistent_or_empty = False; print(f"DEBUG: Inconsistency: {sp.pretty(eq)} -> {sp.pretty(simplified_eq)}")
                    break
        if is_consistent_or_empty:
            # print("DEBUG: System consistent/empty. Solution from master_subs for requested unknowns.")
            solution_dict = {}
            for s_req in user_requested_symbols_set: # Use the set of original requested symbols
                if s_req in master_subs: solution_dict[s_req] = fully_substitute(master_subs[s_req], master_subs)
                else: solution_dict[s_req] = s_req
            return [solution_dict] if solution_dict or not user_requested_symbols_set else [{}]
        else: return []

    sympy_solution_list = []
    try:
        if processed_equations or final_symbols_to_solve_list :
            sympy_solution_list = sp.solve(processed_equations, final_symbols_to_solve_list, dict=True)
            if sympy_solution_list is None: sympy_solution_list = []
            if not isinstance(sympy_solution_list, list): sympy_solution_list = [sympy_solution_list]
    except Exception as e:
        print(f"Error during symbolic solution with sympy.solve: {e}"); return []

    final_solutions = []
    if sympy_solution_list and (isinstance(sympy_solution_list[0], dict) and sympy_solution_list[0]):
        for sol_dict_from_sympy in sympy_solution_list:
            current_processed_solution_dict = {}
            temp_master_subs_plus_sympy_sol = {**master_subs, **sol_dict_from_sympy}
            for s_solved, val_expr in sol_dict_from_sympy.items():
                current_processed_solution_dict[s_solved] = fully_substitute(val_expr, temp_master_subs_plus_sympy_sol)
            for s_req in user_requested_symbols_set:
                if s_req not in current_processed_solution_dict:
                    if s_req in master_subs:
                        current_processed_solution_dict[s_req] = fully_substitute(master_subs[s_req], temp_master_subs_plus_sympy_sol)
                    elif s_req in final_symbols_to_solve_list:
                         current_processed_solution_dict[s_req] = s_req
            final_solutions.append(current_processed_solution_dict)
        return final_solutions
    else:
        # print("DEBUG: sympy.solve() empty or [{}]. Constructing from master_subs.")
        solution_dict_from_subs = {}
        if user_requested_symbols_set:
            for s_req in user_requested_symbols_set:
                if s_req in master_subs:
                    solution_dict_from_subs[s_req] = fully_substitute(master_subs[s_req], master_subs)
                elif s_req in final_symbols_to_solve_list and not processed_equations:
                    solution_dict_from_subs[s_req] = s_req
        if solution_dict_from_subs or not user_requested_symbols_set :
            final_solutions.append(solution_dict_from_subs if solution_dict_from_subs else {})
    return final_solutions


if __name__ == '__main__':
    # (Omitting previous test cases for brevity, they should still pass)
    print("Symbolic Solver (v9 - Corrected Parameter Protection for solving symbolic R3)")

    print("\n--- Test Case: Parameter Protection (R_s_param should remain symbolic) ---")
    R_s_param = sp.Symbol('R_s_param')
    V_s_applied_sym = sp.Symbol('V_s_applied')

    vs_applied = VoltageSource("Vs_app", "np1", "GND", voltage_val_sym=V_s_applied_sym)
    # Let Resistor auto-generate its current symbol I_Rp
    res_param = Resistor("Rp", "np1", "GND", resistance_sym=R_s_param)

    components_param = [vs_applied, res_param]
    knowns_param = {V_s_applied_sym: 10}

    # We want to find current through Rp (res_param.I_comp) and R_s_param itself
    unknowns_param = [res_param.I_comp, R_s_param]

    solution_param = solve_circuit(components_param, unknowns_param, knowns_param, additional_equations=None, ground_node='GND')
    print_solutions(solution_param, "Solution for Parameter Protection Test")
    # Expected: res_param.I_comp (I_Rp) = 10/R_s_param, R_s_param = R_s_param (remains symbol)

    print("\n--- Test Case 1: Voltage Divider (V_n_mid_t1 should be 2) ---")
    V_in_sym_t1 = sp.Symbol('V_in_t1')
    R1_t1, R2_t1 = sp.symbols('R1_t1 R2_t1')
    vs_t1 = VoltageSource(name='Vs_t1', node1='n_in_t1', node2='GND', voltage_val_sym=V_in_sym_t1)
    r1_t1 = Resistor(name='R1_t1', node1='n_in_t1', node2='n_mid_t1', resistance_sym=R1_t1)
    r2_t1 = Resistor(name='R2_t1', node1='n_mid_t1', node2='GND', resistance_sym=R2_t1)
    components_t1 = [vs_t1, r1_t1, r2_t1]
    knowns_t1 = {V_in_sym_t1: 10, R1_t1: 100}
    constraints_t1 = [sp.Symbol('V_n_mid_t1') - 2]
    unknowns_t1 = [R2_t1, sp.Symbol('V_n_mid_t1')]
    solution_t1 = solve_circuit(components_t1, unknowns_t1, knowns_t1, constraints_t1, 'GND')
    print_solutions(solution_t1, "Solution T1 (Expected R2_t1=25, V_n_mid_t1=2)")
