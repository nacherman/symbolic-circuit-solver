import sympy as sp
from sympy.solvers.solveset import linsolve
from symbolic_components import BaseComponent, Resistor, Inductor, Capacitor, VoltageSource, CurrentSource, VCVS, VCCS, CCVS, CCCS, omega as omega_sym_global
from utils import print_solutions


MAX_PREPROCESSING_PASSES = 15

def fully_substitute(expr, subs_dict, max_depth=MAX_PREPROCESSING_PASSES):
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

def solve_circuit(components, unknown_symbols_to_derive, known_specifications, ground_node='GND'):
    if not components and not known_specifications:
        # print("Warning: Both components list and known_specifications are empty. Nothing to solve.")
        return [{}] if not unknown_symbols_to_derive else [{s:s for s in unknown_symbols_to_derive}]

    user_requested_symbols_set = {sp.sympify(s) for s in (unknown_symbols_to_derive or [])}
    all_equations = []
    all_nodes = set()
    node_voltage_symbols = {}
    parameter_symbols = {omega_sym_global}

    if components:
        for comp in components:
            if not isinstance(comp, BaseComponent): raise TypeError(f"Item {comp} not BaseComponent.")
            all_equations.extend(comp.expressions)
            all_nodes.add(comp.node1); all_nodes.add(comp.node2)
            if isinstance(comp, Resistor): parameter_symbols.add(comp.R_val)
            elif isinstance(comp, Inductor): parameter_symbols.add(comp.L_val)
            elif isinstance(comp, Capacitor): parameter_symbols.add(comp.C_val)
            elif isinstance(comp, VoltageSource): parameter_symbols.add(comp.V_source_val)
            elif isinstance(comp, CurrentSource): parameter_symbols.add(comp.I_source_val)
            elif isinstance(comp, VCVS): parameter_symbols.add(comp.gain)
            elif isinstance(comp, VCCS): parameter_symbols.add(comp.transconductance)
            elif isinstance(comp, CCVS): parameter_symbols.add(comp.transresistance)
            elif isinstance(comp, CCCS): parameter_symbols.add(comp.gain)

        ground_subs_dict_for_comp_eqs = {}
        if ground_node in all_nodes :
            for node_name in all_nodes:
                node_sym = sp.Symbol(f"V_{node_name}")
                node_voltage_symbols[node_name] = node_sym
                if node_name == ground_node:
                    if node_sym != sp.Integer(0): ground_subs_dict_for_comp_eqs[node_sym] = sp.Integer(0)
            if ground_subs_dict_for_comp_eqs:
                all_equations = [eq.subs(ground_subs_dict_for_comp_eqs) for eq in all_equations]
        else:
            for node_name in all_nodes: node_voltage_symbols[node_name] = sp.Symbol(f"V_{node_name}")

        kcl_equations = []
        nodes_for_kcl = all_nodes - {ground_node} if ground_node in all_nodes else all_nodes
        for node_name in nodes_for_kcl:
            currents_into_node = sp.Integer(0)
            for comp in components:
                if comp.node1 == node_name: currents_into_node -= comp.I_comp
                elif comp.node2 == node_name: currents_into_node += comp.I_comp
            if currents_into_node != 0 : kcl_equations.append(currents_into_node)
        all_equations.extend(kcl_equations)

    for spec in (known_specifications or []):
        if isinstance(spec, sp.Equality): all_equations.append(spec.lhs - spec.rhs)
        elif isinstance(spec, sp.Expr): all_equations.append(spec)
        else: raise TypeError(f"Known specification '{spec}' must be Sympy Eq or Expr.")

    master_subs = {}
    if ground_node in node_voltage_symbols and node_voltage_symbols[ground_node] != 0:
         master_subs[node_voltage_symbols[ground_node]] = sp.Integer(0)

    current_equations = [eq.subs(master_subs) for eq in all_equations]
    current_equations = [eq for eq in current_equations if eq != True and not (eq.is_number and eq == 0)]

    for _pass_num in range(MAX_PREPROCESSING_PASSES):
        new_substitutions_found_in_pass = False
        equations_for_next_pass = []
        temp_current_equations = list(current_equations)
        current_equations = []
        for eq_idx, eq in enumerate(temp_current_equations):
            simplified_eq_check = eq.simplify() if hasattr(eq, 'simplify') else eq
            if simplified_eq_check == True or simplified_eq_check == sp.true or \
               (hasattr(simplified_eq_check, 'is_number') and simplified_eq_check.is_number and simplified_eq_check == 0) :
                continue
            if simplified_eq_check == False or simplified_eq_check == sp.false or \
               (hasattr(simplified_eq_check, 'is_number') and simplified_eq_check.is_number and simplified_eq_check != 0) :
                print(f"DEBUG: Eq evaluates to {simplified_eq_check}, system inconsistent (Pass {_pass_num + 1}). Orig: {sp.pretty(eq)}")
                return []
            substituted_this_eq = False
            symbols_in_eq = sorted(list(eq.free_symbols - set(master_subs.keys())), key=str)
            for symbol in symbols_in_eq:
                is_explicitly_known = symbol in (known_specifications or {}) # This check is not quite right, known_specifications is list of Eq.
                                                                           # We need to check if symbol was on LHS of an sp.Eq in known_specifications.
                                                                           # For now, rely on parameter_symbols and user_requested_symbols_set.
                if symbol in parameter_symbols and symbol not in master_subs and symbol not in user_requested_symbols_set:
                    continue
                try:
                    sol = sp.solve(eq, symbol, dict=False)
                    if isinstance(sol, list) and len(sol) == 1:
                        expr_val = sol[0]
                        if symbol in expr_val.free_symbols: continue
                        current_substitution = {symbol: expr_val}
                        master_subs[symbol] = expr_val
                        new_substitutions_found_in_pass = True; substituted_this_eq = True
                        equations_for_next_pass = [neq.subs(current_substitution).simplify() for neq in equations_for_next_pass]
                        for i in range(eq_idx + 1, len(temp_current_equations)):
                            temp_current_equations[i] = temp_current_equations[i].subs(current_substitution).simplify()
                        break
                except Exception: pass
            if not substituted_this_eq: equations_for_next_pass.append(eq)
        current_equations = equations_for_next_pass
        if not new_substitutions_found_in_pass : break
        if _pass_num == MAX_PREPROCESSING_PASSES -1: print("Warning: Max substitution passes reached.")

    processed_equations = [eq for eq in current_equations if not (eq == True or eq == sp.true or (hasattr(eq, 'is_number') and eq.is_number and eq == 0))]
    processed_equations = list(set(processed_equations))

    final_unknowns_list = [s for s in user_requested_symbols_set if s not in master_subs]
    all_free_in_eqs = set()
    for eq in processed_equations: all_free_in_eqs.update(eq.free_symbols)
    for s in all_free_in_eqs:
        if s not in master_subs and s not in final_unknowns_list: final_unknowns_list.append(s)
    final_unknowns_list = sorted(final_unknowns_list, key=str)

    num_eq = len(processed_equations); num_solve_sym = len(final_unknowns_list)
    print(f"\nDEBUG: Final system analysis before sympy.solve():")
    print(f"DEBUG: Number of processed equations: {num_eq}")
    print(f"DEBUG: Number of symbols for sympy.solve: {num_solve_sym} ({[s.name if hasattr(s,'name') else str(s) for s in final_unknowns_list]})")
    if not processed_equations and not final_unknowns_list: print("DEBUG: System fully determined by substitutions.")
    elif num_eq < num_solve_sym : print("DEBUG: System appears under-determined for sympy.solve.")
    elif num_eq == num_solve_sym: print("DEBUG: System appears square for sympy.solve.")
    elif num_eq > num_solve_sym : print("DEBUG: System appears over-determined for sympy.solve.")

    # print(f"DEBUG Master subs before solve: {master_subs}") # Verbose debug

    sympy_solution_list = []
    if final_unknowns_list or processed_equations:
        try:
            sympy_solution_list = sp.solve(processed_equations, final_unknowns_list, dict=True)
            if sympy_solution_list is None: sympy_solution_list = []
            if not isinstance(sympy_solution_list, list): sympy_solution_list = [sympy_solution_list]
        except Exception as e: print(f"Error during sympy.solve: {e}"); return []

    output_solutions = []
    if not sympy_solution_list: # sympy.solve() returned empty (e.g. [], or if it was [{}] it's handled by next block)
        if not processed_equations: # System was fully determined by master_subs or is defined by free parameters
            # print("DEBUG: Sympy.solve empty, no equations. Solution from master_subs or free params.") # DEBUG
            solution_dict = {}
            for s_req in user_requested_symbols_set:
                if s_req in master_subs:
                    solution_dict[s_req] = fully_substitute(master_subs[s_req], master_subs)
                elif s_req in final_unknowns_list: # Was a symbol for solve but no equations to constrain it
                    solution_dict[s_req] = s_req # It's a free parameter
            # Add dict if it's populated or if no specific unknowns were requested (indicates consistency)
            if solution_dict or not user_requested_symbols_set: output_solutions.append(solution_dict)
        # else: Equations remained but sympy.solve found no solution
    elif sympy_solution_list and isinstance(sympy_solution_list[0], dict) and not sympy_solution_list[0]: # Got back [{}]
        # print("DEBUG: sympy.solve() returned [{}]. System might be underdetermined for specific unknowns.") # DEBUG
        # Treat as above: try to construct from master_subs for requested, or show free params
        solution_dict = {}
        for s_req in user_requested_symbols_set:
            if s_req in master_subs:
                solution_dict[s_req] = fully_substitute(master_subs[s_req], master_subs)
            elif s_req in final_unknowns_list: # If it was a symbol passed to solve and no equations defined it
                solution_dict[s_req] = s_req
        if solution_dict or not user_requested_symbols_set: output_solutions.append(solution_dict)
    else: # Sympy.solve returned actual solution(s)
        for sol_dict_from_sympy in sympy_solution_list:
            current_res_dict = {}
            temp_master_subs_plus_sympy_sol = {**master_subs, **sol_dict_from_sympy}
            for s_solved, val_expr in sol_dict_from_sympy.items():
                current_res_dict[s_solved] = fully_substitute(val_expr, temp_master_subs_plus_sympy_sol)
            for s_req in user_requested_symbols_set:
                if s_req not in current_res_dict:
                    if s_req in master_subs:
                        current_res_dict[s_req] = fully_substitute(master_subs[s_req], temp_master_subs_plus_sympy_sol)
                    elif s_req in final_unknowns_list:
                         current_res_dict[s_req] = s_req
            output_solutions.append(current_res_dict)

    return output_solutions


if __name__ == '__main__':
    print("Symbolic Solver (New Interface v3 - Parameter Protection & Solution Logic Refined)")

    V_in_sym_t1 = sp.Symbol('V_in_t1')
    R1_t1, R2_t1 = sp.symbols('R1_t1 R2_t1')
    vs_t1 = VoltageSource(name='Vs_t1', node1='n_in_t1', node2='GND', voltage_val_sym=V_in_sym_t1)
    r1_t1 = Resistor(name='R1_t1', node1='n_in_t1', node2='n_mid_t1', resistance_sym=R1_t1)
    r2_t1 = Resistor(name='R2_t1', node1='n_mid_t1', node2='GND', resistance_sym=R2_t1)
    components_t1 = [vs_t1, r1_t1, r2_t1]
    # known_specifications define V_in_t1=10, R1_t1=100, and V_n_mid_t1=2
    known_specs_t1 = [sp.Eq(V_in_sym_t1, 10), sp.Eq(R1_t1, 100), sp.Eq(sp.Symbol('V_n_mid_t1'), 2)]
    unknowns_t1 = [R2_t1, sp.Symbol('V_n_mid_t1')]
    print("\n--- Test Case 1: Voltage Divider (Solve R2, V_n_mid_t1) ---")
    solution_t1 = solve_circuit(components_t1, unknowns_t1, known_specs_t1, ground_node='GND')
    print_solutions(solution_t1, "Solution T1 (Expected R2_t1=25, V_n_mid_t1=2)")

    print("\n--- Test Case 2: Parameter Protection (R_s_param should remain symbolic) ---")
    R_s_param_tc = sp.Symbol('R_s_param_tc')
    V_s_applied_sym_tc = sp.Symbol('V_s_applied_tc')

    vs_applied_tc = VoltageSource("Vs_app_tc", "np1_tc", "GND", voltage_val_sym=V_s_applied_sym_tc)
    res_param_tc = Resistor("Rp_tc", "np1_tc", "GND", resistance_sym=R_s_param_tc)

    components_param_tc = [vs_applied_tc, res_param_tc]
    known_specs_param_tc = [sp.Eq(V_s_applied_sym_tc, 10)] # V_np1_tc will be V_s_applied_tc via Vs_app_tc component

    unknowns_param_tc = [res_param_tc.I_comp, R_s_param_tc]

    solution_param_tc = solve_circuit(components_param_tc, unknowns_param_tc, known_specs_param_tc, ground_node='GND')
    print_solutions(solution_param_tc, "Solution for Parameter Protection Test (New Interface)")
