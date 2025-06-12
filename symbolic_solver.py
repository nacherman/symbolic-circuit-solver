import sympy as sp
from sympy.solvers.solveset import linsolve # Not directly used in snippet but good for context
from symbolic_components import BaseComponent

# For test cases at the end
from symbolic_components import VoltageSource, Resistor
from utils import print_solutions # For __main__ tests


def solve_circuit(components, unknown_symbols_to_solve_for, known_substitutions=None, additional_equations=None, ground_node='GND'):
    # --- Initial setup, KCL, and iterative pre-processing logic ---
    # This part is assumed to be the same as the successfully updated version from the previous step,
    # which included the more aggressive pre-processing loop.
    # For brevity, only the core logic parts are shown here, focusing on changes to return logic.

    if not components and not additional_equations:
        raise ValueError("Components list cannot be empty if no additional_equations are provided.")

    current_equations = []
    all_nodes = set()
    node_voltage_symbols = {} # type: dict[str, sp.Expr]

    if components:
        for comp in components:
            if not isinstance(comp, BaseComponent):
                raise TypeError(f"Item {comp} in components list is not a BaseComponent.")
            current_equations.extend(comp.expressions)
            all_nodes.add(comp.node1)
            all_nodes.add(comp.node2)

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

    MAX_PASSES = 10 # Max passes for iterative substitution
    for _pass_num in range(MAX_PASSES):
        new_substitutions_found_in_pass = False
        next_round_equations = []
        equations_to_process_this_pass = list(current_equations)
        current_equations = []

        eq_idx = 0
        while eq_idx < len(equations_to_process_this_pass):
            eq = equations_to_process_this_pass[eq_idx]
            if eq == True or eq == sp.true or (hasattr(eq, 'is_number') and eq.is_number and eq == 0):
                eq_idx += 1; continue
            if eq == False or eq == sp.false or (hasattr(eq, 'is_number') and eq.is_number and eq != 0) :
                print(f"Warning/DEBUG: Equation evaluates to {eq}, system likely inconsistent.")
                return []

            substituted_this_eq_for_a_symbol = False
            symbols_in_eq = sorted(list(eq.free_symbols), key=str)

            for symbol in symbols_in_eq:
                if symbol in master_subs: continue
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
                        # No pop, just don't add current eq to next_round_equations if it's used
                        break
                except Exception: pass

            if not substituted_this_eq_for_a_symbol:
                next_round_equations.append(eq)
            eq_idx +=1

        current_equations = next_round_equations
        if not new_substitutions_found_in_pass: break

    processed_equations = [eq for eq in current_equations if not (eq == True or eq == sp.true or (hasattr(eq, 'is_number') and eq.is_number and eq == 0))]

    symbols_to_solve = set()
    # Ensure unknown_symbols_to_solve_for is a list of actual symbols for processing
    user_requested_symbols = [sp.sympify(s) for s in (unknown_symbols_to_solve_for or [])]

    for s_usr_sym in user_requested_symbols:
        if s_usr_sym not in master_subs:
            symbols_to_solve.add(s_usr_sym)

    if components:
        for node, v_sym in node_voltage_symbols.items():
            is_ground_node = (ground_node in all_nodes and node == ground_node)
            if not is_ground_node and v_sym not in master_subs:
                symbols_to_solve.add(v_sym)
        for comp in components:
            if comp.V_comp not in master_subs: symbols_to_solve.add(comp.V_comp)
            if hasattr(comp, 'I_comp') and comp.I_comp not in master_subs :
                 symbols_to_solve.add(comp.I_comp)

    all_free_symbols_in_equations = set()
    for eq in processed_equations:
        all_free_symbols_in_equations.update(eq.free_symbols)
    for s in all_free_symbols_in_equations:
        if s not in master_subs:
            symbols_to_solve.add(s)

    final_symbols_to_solve_list = sorted(list(symbols_to_solve), key=lambda s: str(s))

    # --- Start of NEW/MODIFIED Return Logic ---
    def fully_substitute(expr, subs_dict, max_depth=MAX_PASSES):
        if not hasattr(expr, 'subs') or not hasattr(expr, 'free_symbols'): return expr

        # Iteratively substitute to resolve multi-level dependencies
        # Only substitute with keys actually present in the expression's free symbols
        for _ in range(max_depth):
            prev_expr = expr
            # Determine which symbols from subs_dict are in the current expression
            symbols_to_sub = expr.free_symbols.intersection(subs_dict.keys())
            if not symbols_to_sub: break # No more known symbols to substitute

            current_pass_subs = {s: subs_dict[s] for s in symbols_to_sub}
            expr = expr.subs(current_pass_subs)
            if expr == prev_expr: break # No change, substitution converged
        return expr

    # DEBUG print moved after fully_substitute is defined
    master_subs_print = { (s.name if hasattr(s,'name') else str(s)) : fully_substitute(v, master_subs) for s,v in master_subs.items()}
    print(f"DEBUG: Master substitutions made (fully resolved, approx numerical): { {k: (v.evalf() if hasattr(v,'evalf') else v) for k,v in master_subs_print.items()} }")
    print(f"DEBUG: Equations to solve ({len(processed_equations)}):")
    for i, eq_debug in enumerate(processed_equations): print(f"  Eq{i+1}: {sp.pretty(eq_debug)}")
    print(f"DEBUG: Symbols to solve for ({len(final_symbols_to_solve_list)}): {[s.name if hasattr(s,'name') else str(s) for s in final_symbols_to_solve_list]}")

    # Case 1 & 2 (modified): System determined by substitutions or consistent with them
    if not final_symbols_to_solve_list: # No symbols left for sympy.solve
        is_consistent_or_empty = True
        if processed_equations: # Equations remain, check their consistency
            print("DEBUG: No symbols for sympy.solve, but equations remain. Checking consistency.")
            for eq in processed_equations:
                simplified_eq = fully_substitute(eq, master_subs).simplify()
                if not (simplified_eq == True or simplified_eq == sp.true or simplified_eq == 0):
                    is_consistent_or_empty = False
                    print(f"DEBUG: Inconsistency: Equation {sp.pretty(eq)} simplifies to {sp.pretty(simplified_eq)} not 0 or True.")
                    break

        if is_consistent_or_empty:
            print("DEBUG: System consistent or empty. Solution constructed from master_subs for requested unknowns.")
            solution_dict = {}
            for s_req in user_requested_symbols:
                if s_req in master_subs:
                    solution_dict[s_req] = fully_substitute(master_subs[s_req], master_subs)
                # else: solution_dict[s_req] = s_req # Or indicate it remained unsolved
            # If no specific unknowns requested, solution_dict can be empty.
            # If specific unknowns were requested and all found in master_subs, it's a valid solution.
            if not user_requested_symbols or all(s in master_subs for s in user_requested_symbols):
                 return [solution_dict] if solution_dict or not user_requested_symbols else [{}] # Ensure [{}] for no specific request but consistent
            else: # Some requested unknowns were not in master_subs
                 print("DEBUG: Some requested unknowns were not found in master_subs, and no equations for sympy.solve.")
                 return [] # Incomplete solution
        else: # Inconsistent
            return []


    # Case 3: Call sympy.solve()
    sympy_solution_list = []
    try:
        if processed_equations or final_symbols_to_solve_list :
            sympy_solution_list = sp.solve(processed_equations, final_symbols_to_solve_list, dict=True)
            if sympy_solution_list is None: sympy_solution_list = [] # Ensure it's a list
            if not isinstance(sympy_solution_list, list): sympy_solution_list = [sympy_solution_list] # Wrap if single dict
    except Exception as e:
        print(f"Error during symbolic solution with sympy.solve: {e}")
        return []

    # Process solution from sympy.solve() or use master_subs if sympy_solution is empty
    final_solutions = []
    if sympy_solution_list: # Got a list of solution dicts from sympy.solve
        for sol_dict_from_sympy in sympy_solution_list:
            current_processed_solution_dict = {}
            for s_solved, val_expr in sol_dict_from_sympy.items():
                current_processed_solution_dict[s_solved] = fully_substitute(val_expr, master_subs)

            for s_req in user_requested_symbols:
                if s_req not in current_processed_solution_dict and s_req in master_subs:
                    current_processed_solution_dict[s_req] = fully_substitute(master_subs[s_req], master_subs)
                elif s_req not in current_processed_solution_dict: # Requested, but not in sympy sol and not in master_subs
                     pass # It remains unsolved. Could add s_req: s_req if desired.
            final_solutions.append(current_processed_solution_dict)

    elif not sympy_solution_list: # sympy.solve() returned empty
        print("DEBUG: sympy.solve() returned an empty solution. Constructing from master_subs for requested unknowns.")
        solution_dict_from_subs = {}
        all_req_unknowns_accounted_for = True # Assume true initially
        if user_requested_symbols:
            for s_req in user_requested_symbols:
                if s_req in master_subs:
                    solution_dict_from_subs[s_req] = fully_substitute(master_subs[s_req], master_subs)
                else: # A requested symbol is not in master_subs and not solved by sympy -> truly unknown/unconstrained
                    # To indicate it's a free parameter if no equations constraint it:
                    # solution_dict_from_subs[s_req] = s_req
                    # For now, if it's not found, we consider the solution incomplete for requested vars.
                    all_req_unknowns_accounted_for = False
                    print(f"DEBUG: Requested symbol {s_req} not found in master_subs and not solved.")

        # Only return a solution if all requested symbols were found or no specific symbols were requested.
        # If specific symbols were requested but not all found, it's an incomplete solution.
        if (user_requested_symbols and all_req_unknowns_accounted_for and solution_dict_from_subs) or \
           (not user_requested_symbols and not processed_equations): # No specific requests, no eqs left.
            final_solutions.append(solution_dict_from_subs if solution_dict_from_subs else {}) # Append at least [{}]
        # If there were processed_equations but sympy found no solution, it's genuinely no solution.

    return final_solutions


if __name__ == '__main__':
    print("Symbolic Solver Preprocessing Test with Enhanced Logic (v2)")

    V_in_sym_t1 = sp.Symbol('V_in_t1')
    R1_t1, R2_t1 = sp.symbols('R1_t1 R2_t1')
    V_n_mid_t1_node_sym = sp.Symbol('V_n_mid_t1')

    vs_t1 = VoltageSource(name='Vs_t1', node1='n_in_t1', node2='GND', voltage_val_sym=V_in_sym_t1)
    r1_t1 = Resistor(name='R1_t1', node1='n_in_t1', node2='n_mid_t1', resistance_sym=R1_t1)
    r2_t1 = Resistor(name='R2_t1', node1='n_mid_t1', node2='GND', resistance_sym=R2_t1)
    components_t1 = [vs_t1, r1_t1, r2_t1]

    knowns_t1 = {V_in_sym_t1: 10, R1_t1: 100}
    # Use the actual node voltage symbol V_n_mid_t1 that solver will see
    constraints_t1 = [sp.Symbol('V_n_mid_t1') - 2]
    unknowns_t1 = [R2_t1, sp.Symbol('V_n_mid_t1')]

    print("\n--- Test Case 1: Voltage Divider (Solve R2, V_n_mid_t1) ---")
    solution_t1 = solve_circuit(components_t1, unknowns_t1, knowns_t1, constraints_t1, 'GND')
    print_solutions(solution_t1, "Solution T1 (Expected R2_t1=25, V_n_mid_t1=2)")

    Vs_val_t2, R1_t2, R2_t2, R3_t2 = sp.symbols('Vs_val_t2 R1_t2 R2_t2 R3_t2')
    vs_t2 = VoltageSource('Vs_t2', 'n_s_t2', 'GND', Vs_val_t2)
    r1_t2 = Resistor('R1t2', 'n_s_t2', 'n1_c', R1_t2)
    r2_t2 = Resistor('R2t2', 'n1_c', 'n2_c', R2_t2)
    r3_t2 = Resistor('R3t2', 'n2_c', 'GND', R3_t2)
    components_t2 = [vs_t2, r1_t2, r2_t2, r3_t2]
    knowns_t2 = {Vs_val_t2: 5, R1_t2: 10, R2_t2: 10}
    constraints_t2 = [ sp.Symbol('V_n2_c') - 1, sp.Symbol('V_n1_c') - (sp.Symbol('V_n2_c') + 2) ]
    unknowns_t2 = [R3_t2, sp.Symbol('V_n1_c'), sp.Symbol('V_n2_c')]
    print("\n--- Test Case 2: Chained Constraints (Solve R3, V_n1_c, V_n2_c) ---")
    solution_t2 = solve_circuit(components_t2, unknowns_t2, knowns_t2, constraints_t2, 'GND')
    print_solutions(solution_t2, "Solution T2 (Expected R3_t2=5, V_n1_c=3, V_n2_c=1)")

    print("\n--- Test Case 3: Fully determined by constraints (No components) ---")
    x_t3, y_t3 = sp.symbols('x_t3 y_t3')
    constraints_t3 = [x_t3 - 5, y_t3 - x_t3*2]
    unknowns_t3 = [x_t3, y_t3]
    solution_t3 = solve_circuit([], unknowns_t3, None, constraints_t3, 'GND')
    print_solutions(solution_t3, "Solution T3 (Expected x_t3=5, y_t3=10)")

    print("\n--- Test Case 4: Inconsistent via constraints (No components) ---")
    x_t4 = sp.Symbol('x_t4')
    constraints_t4 = [x_t4 - 5, x_t4 - 6]
    unknowns_t4 = [x_t4]
    solution_t4 = solve_circuit([], unknowns_t4, None, constraints_t4, 'GND')
    print_solutions(solution_t4, "Solution T4 (Expected empty for inconsistency)")

    V_in_sym_t5 = sp.Symbol('V_in_t5')
    R1_t5_sym, R2_t5_sym = sp.symbols('R1_t5_sym R2_t5_sym')
    vs_t5 = VoltageSource(name='Vs_t5', node1='n_in_t5', node2='GND', voltage_val_sym=V_in_sym_t5)
    r1_t5 = Resistor(name='R1_t5', node1='n_in_t5', node2='n_mid_t5', resistance_sym=R1_t5_sym)
    r2_t5 = Resistor(name='R2_t5', node1='n_mid_t5', node2='GND', resistance_sym=R2_t5_sym)
    components_t5 = [vs_t5, r1_t5, r2_t5]
    knowns_t5 = {V_in_sym_t5: 10, R1_t5_sym: 100}
    constraints_t5 = [sp.Symbol('V_n_mid_t5') - 20]
    unknowns_t5 = [R2_t5_sym, sp.Symbol('V_n_mid_t5')]
    print("\n--- Test Case 5: Negative Resistance Expected ---")
    solution_t5 = solve_circuit(components_t5, unknowns_t5, knowns_t5, constraints_t5, 'GND')
    print_solutions(solution_t5, "Solution T5 (Expected R2_t5_sym=-200, V_n_mid_t5=20)")
