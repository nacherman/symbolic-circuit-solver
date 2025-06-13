# solver_dev_workspace/symbolic_solver.py
import sympy as sp

# Import from sibling all_symbolic_components.py
try:
    from all_symbolic_components import (
        BaseComponent, Resistor, Capacitor, Inductor,
        VoltageSource, CurrentSource,
        VCVS, VCCS, CCVS, CCCS,
        s_sym # Import s_sym directly, can be used if solver needs awareness of it
    )
    print("DEBUG solver_dev_workspace/symbolic_solver.py: Successfully imported from all_symbolic_components.py")
except ImportError as e:
    print(f"CRITICAL ERROR in solver_dev_workspace/symbolic_solver.py: Could not import from all_symbolic_components.py: {e}")
    # Define dummy classes for parsability if import fails
    class BaseComponent: pass
    class Resistor(BaseComponent): pass;
    class Capacitor(BaseComponent): pass;
    class Inductor(BaseComponent): pass;
    class VoltageSource(BaseComponent): pass;
    class CurrentSource(BaseComponent): pass;
    class VCVS(BaseComponent): pass;
    class VCCS(BaseComponent): pass;
    class CCVS(BaseComponent): pass;
    class CCCS(BaseComponent): pass;
    s_sym = sp.Symbol('s_solver_fallback_critical')

# Attempt to import print_solutions from utils, provide a dummy if not found (for __main__ tests)
try:
    from utils import print_solutions
except ImportError:
    print("Warning: Could not import print_solutions from utils. Defining dummy for solver's __main__ tests.")
    def print_solutions(sol, msg=""): print(f"Dummy print_solutions: {msg} - {sol}")


def fully_substitute(expr, subs_dict, max_passes=10):
    # ... (function as previously defined and verified) ...
    if not hasattr(expr, 'subs'): return expr
    current_expr = expr
    for _ in range(max_passes):
        prev_expr = current_expr; current_expr = current_expr.subs(subs_dict)
        if current_expr == prev_expr: break
    return current_expr

def solve_circuit(components, unknowns_to_derive, known_specifications, ground_node='GND'):
    # ... (Full existing solve_circuit logic from the prompt) ...
    if not components and not known_specifications:
        print("Warning: solve_circuit called with no components and no known_specifications.")
    if not unknowns_to_derive:
        print("Warning: No unknowns_to_derive specified.")

    all_equations = []
    all_nodes = set()
    if components:
        for comp in components:
            if not isinstance(comp, BaseComponent):
                raise TypeError(f"Item {comp} in components list is not a BaseComponent.")
            all_equations.extend(comp.expressions)
            all_nodes.add(comp.node1); all_nodes.add(comp.node2)

    ground_subs_dict_for_kcl = {}
    if components:
        node_voltage_symbols_for_kcl = {}
        for node_name in all_nodes:
            if node_name == ground_node:
                node_voltage_symbols_for_kcl[node_name] = sp.Integer(0)
                ground_sym_for_control = sp.Symbol(f"V_{ground_node}")
                if ground_sym_for_control != sp.Integer(0):
                     ground_subs_dict_for_kcl[ground_sym_for_control] = sp.Integer(0)
            else:
                node_voltage_symbols_for_kcl[node_name] = sp.Symbol(f"V_{node_name}")
        for node_name in all_nodes:
            if node_name == ground_node: continue
            currents_into_node = sp.Integer(0)
            for comp in components:
                if comp.node1 == node_name: currents_into_node -= comp.I_comp
                elif comp.node2 == node_name: currents_into_node += comp.I_comp
            if currents_into_node != 0 : all_equations.append(currents_into_node)

    # Convert known_specifications if it's a dict into list of equations
    processed_known_specs = []
    if isinstance(known_specifications, dict):
        for k_sym, v_val in known_specifications.items():
            processed_known_specs.append(sp.Eq(k_sym, v_val))
    elif isinstance(known_specifications, list):
        processed_known_specs = known_specifications

    for spec in (processed_known_specs or []):
        if isinstance(spec, sp.Equality): all_equations.append(spec.lhs - spec.rhs)
        elif isinstance(spec, sp.Expr): all_equations.append(spec) # E.g. for KCL equations that are already expr=0
        else: raise TypeError(f"Known specification '{spec}' must be a Sympy Equality (Eq) or Expression.")

    master_subs = {}
    # Ensure V_GND is 0, handling if ground_node is '0' or other names like 'GND'
    gnd_v_symbol = sp.Symbol(f"V_{ground_node}")
    if gnd_v_symbol != sp.Integer(0): # Avoid adding V_0 = 0 if ground is '0' and V_0 is not a symbol
        master_subs[gnd_v_symbol] = sp.Integer(0)

    fundamental_params = set()
    if components:
        for comp in components:
            if isinstance(comp, Resistor): fundamental_params.add(comp.R_val)
            elif isinstance(comp, Capacitor): fundamental_params.add(comp.C_val)
            elif isinstance(comp, Inductor): fundamental_params.add(comp.L_val)
            elif isinstance(comp, VoltageSource): fundamental_params.add(comp.V_source_val)
            elif isinstance(comp, CurrentSource): fundamental_params.add(comp.I_source_val)
            elif isinstance(comp, VCVS): fundamental_params.add(comp.gain)
            elif isinstance(comp, VCCS): fundamental_params.add(comp.transconductance)
            elif isinstance(comp, CCVS): fundamental_params.add(comp.transresistance)
            elif isinstance(comp, CCCS): fundamental_params.add(comp.gain)
    fundamental_params.add(s_sym)

    processed_equations = list(all_equations)
    MAX_PASSES = 10
    for _pass_num in range(MAX_PASSES):
        new_substitutions_found_in_pass = False
        equations_for_next_pass = []
        current_master_subs_keys = set(master_subs.keys())

        temp_processed_equations = []
        for eq in processed_equations:
            subbed_eq = fully_substitute(eq.subs(master_subs), master_subs, 5)
            if subbed_eq != True and not (hasattr(subbed_eq, 'is_number') and subbed_eq.is_number and subbed_eq == 0): # Check for sp.true
                 temp_processed_equations.append(subbed_eq)
            elif subbed_eq == False or (hasattr(subbed_eq, 'is_number') and subbed_eq.is_number and subbed_eq != 0): # Check for sp.false
                 print(f"DEBUG: Preprocessing: Equation evaluates to {subbed_eq}, system likely inconsistent (Pass {_pass_num + 1}).")
                 return [] # System inconsistent
        processed_equations = temp_processed_equations

        idx_eq_outer = -1
        for eq in processed_equations:
            idx_eq_outer+=1
            if eq == True or eq == False or (hasattr(eq,'is_number') and eq.is_number) : # Should have been filtered
                if eq == False or (hasattr(eq,'is_number') and eq.is_number and eq != 0):
                    print(f"DEBUG: Preprocessing: Equation evaluates to {eq}, system likely inconsistent.")
                continue
            substituted_this_eq = False

            potential_solve_targets = list(eq.free_symbols - current_master_subs_keys)
            symbols_to_try_solving = [
                s for s in potential_solve_targets
                if not (s in fundamental_params and s not in (unknowns_to_derive or []))
            ]

            for symbol_to_solve_for in symbols_to_try_solving:
                try:
                    sol = sp.solve(eq, symbol_to_solve_for, dict=False)
                    if isinstance(sol, list) and len(sol) == 1:
                        expr_val = sol[0]
                        if symbol_to_solve_for in expr_val.free_symbols: continue
                        master_subs[symbol_to_solve_for] = expr_val
                        new_substitutions_found_in_pass = True; substituted_this_eq = True

                        equations_for_next_pass = [fully_substitute(neq.subs({symbol_to_solve_for: expr_val}), master_subs, 3) for neq in equations_for_next_pass]
                        # Apply to subsequent equations in current pass's processed_equations list
                        for i in range(idx_eq_outer + 1, len(processed_equations)):
                            processed_equations[i] = fully_substitute(processed_equations[i].subs({symbol_to_solve_for: expr_val}), master_subs, 3)
                        break
                except Exception: pass
            if not substituted_this_eq: equations_for_next_pass.append(eq)
        processed_equations = equations_for_next_pass
        if not new_substitutions_found_in_pass and not (_pass_num == 0 and master_subs and not current_master_subs_keys) : break # Adjusted break condition
        if _pass_num == MAX_PASSES -1: print("Warning: Max substitution passes reached in solver pre-processing.")

    processed_equations = [fully_substitute(eq, master_subs) for eq in processed_equations]
    processed_equations = [eq for eq in processed_equations if eq != True and not (hasattr(eq,'is_number') and eq.is_number and eq == 0)]
    processed_equations = list(set(processed_equations)) # Remove duplicates

    final_unknowns_list = [s for s in (unknowns_to_derive or []) if s not in master_subs]
    if not final_unknowns_list and processed_equations: # If user asked for no specific unknowns, solve for all remaining
        temp_free_symbols = set()
        for eq in processed_equations: temp_free_symbols.update(eq.free_symbols)
        final_unknowns_list = sorted(list(temp_free_symbols - set(master_subs.keys())), key=str)

    num_eq = len(processed_equations); num_solve_sym = len(final_unknowns_list)
    print(f"DEBUG: Final system before sympy.solve():")
    print(f"DEBUG: Number of equations: {num_eq}")
    print(f"DEBUG: Number of symbols to solve for: {num_solve_sym} -> {final_unknowns_list}")
    if not processed_equations and not final_unknowns_list : print("DEBUG: System fully determined by substitutions.")
    elif num_eq < num_solve_sym: print("DEBUG: System appears under-determined.")
    elif num_eq == num_solve_sym: print("DEBUG: System appears square.")
    elif num_eq > num_solve_sym: print("DEBUG: System appears over-determined.")

    sympy_solutions_list = []
    if not final_unknowns_list and not processed_equations: # Fully solved by substitution
        solution_from_subs = {}
        for s_orig in (unknowns_to_derive or []):
            if s_orig in master_subs: solution_from_subs[s_orig] = fully_substitute(master_subs[s_orig], master_subs)
        return [solution_from_subs] if solution_from_subs or not (unknowns_to_derive or []) else []

    if not final_unknowns_list and processed_equations: # Should be consistent (all equations 0=0)
        consistent = True
        for eq in processed_equations:
            simplified_eq = fully_substitute(eq, master_subs).simplify()
            if simplified_eq != 0: consistent = False; break
        if consistent:
            solution_from_subs = {}
            for s_orig in (unknowns_to_derive or []):
                if s_orig in master_subs: solution_from_subs[s_orig] = fully_substitute(master_subs[s_orig], master_subs)
            return [solution_from_subs] if solution_from_subs or not (unknowns_to_derive or []) else []
        else:
            print("DEBUG: System has equations but no unknowns to solve, and equations are non-zero. Inconsistent.")
            return []
    try:
        if processed_equations or final_unknowns_list :
            sympy_solutions_list = sp.solve(processed_equations, final_unknowns_list, dict=True)
    except Exception as e: print(f"Error during sympy.solve: {e}"); return []

    output_solutions = []
    if isinstance(sympy_solutions_list, list):
        if not sympy_solutions_list and not processed_equations: # No solutions from sp.solve, and no equations left means it's trivial or based on master_subs
             solution_dict = {}
             for s_derive in (unknowns_to_derive or []):
                 if s_derive in master_subs: solution_dict[s_derive] = fully_substitute(master_subs[s_derive], master_subs)
                 else: solution_dict[s_derive] = s_derive # It's a free parameter if not in master_subs & not solved
             if solution_dict or not unknowns_to_derive : output_solutions.append(solution_dict)

        for sol_dict_sympy in sympy_solutions_list:
            current_res_dict = {}
            for s_solved, expr_val in sol_dict_sympy.items(): current_res_dict[s_solved] = fully_substitute(expr_val, master_subs)
            for s_derive in (unknowns_to_derive or []):
                if s_derive not in current_res_dict and s_derive in master_subs:
                    current_res_dict[s_derive] = fully_substitute(master_subs[s_derive], master_subs)
            # Filter to only include requested unknowns if unknowns_to_derive was provided
            final_dict_for_this_solution = {s: current_res_dict[s] for s in (unknowns_to_derive or current_res_dict.keys()) if s in current_res_dict}
            if final_dict_for_this_solution or not (unknowns_to_derive or []): output_solutions.append(final_dict_for_this_solution)

    elif isinstance(sympy_solutions_list, dict): # Single solution dictionary
        current_res_dict = {s: fully_substitute(v, master_subs) for s,v in sympy_solutions_list.items()}
        for s_derive in (unknowns_to_derive or []):
            if s_derive not in current_res_dict and s_derive in master_subs:
                current_res_dict[s_derive] = fully_substitute(master_subs[s_derive], master_subs)
        final_dict_for_this_solution = {s: current_res_dict[s] for s in (unknowns_to_derive or current_res_dict.keys()) if s in current_res_dict}
        if final_dict_for_this_solution or not (unknowns_to_derive or []): output_solutions.append(final_dict_for_this_solution)

    if not output_solutions and not unknowns_to_derive and not processed_equations: # Case: no unknowns, no equations, solution is {}
        output_solutions.append({})

    return output_solutions


if __name__ == '__main__':
    print("Symbolic Solver (root_solver) - Imports now from all_symbolic_components.py")
    print("\n--- Solver Test: Parameter Protection / Formula Derivation (using new imports) ---")
    V_in_param, I_Rp_param, R_s_param_tc = sp.symbols('V_in_param I_Rp_param R_s_param_tc')
    vs_param_test = VoltageSource("Vs_param", "n_p_in", "GND", voltage_val_sym=V_in_param)
    rp_param_test = Resistor("Rp_param", "n_p_in", "GND", resistance_sym=R_s_param_tc, current_sym=I_Rp_param)
    param_test_comps = [vs_param_test, rp_param_test]

    # Case 1: known_specifications is list of Eq
    known_spec_param_test1_eq = [sp.Eq(V_in_param, 10)]
    unknowns_param_test1 = [I_Rp_param, R_s_param_tc]
    print("Test Case 1 (Eq list): Solving for I_Rp_param and R_s_param_tc; V_in_param=10, R_s_param_tc is parameter.")
    solution_param_test1 = solve_circuit(param_test_comps, unknowns_param_test1, known_spec_param_test1_eq, "GND")
    print_solutions(solution_param_test1, "Parameter Test 1 Solution (I_Rp_param = f(R_s_param_tc), R_s_param_tc=R_s_param_tc)")

    # Case 1b: known_specifications is dict
    known_spec_param_test1_dict = {V_in_param: 10}
    print("Test Case 1b (dict): Solving for I_Rp_param and R_s_param_tc; V_in_param=10, R_s_param_tc is parameter.")
    solution_param_test1b = solve_circuit(param_test_comps, unknowns_param_test1, known_spec_param_test1_dict, "GND")
    print_solutions(solution_param_test1b, "Parameter Test 1b Solution (I_Rp_param = f(R_s_param_tc), R_s_param_tc=R_s_param_tc)")

    known_spec_param_test2_eq = [sp.Eq(V_in_param, 10), sp.Eq(I_Rp_param, 2)]
    unknowns_param_test2 = [R_s_param_tc]
    print("\nTest Case 2 (Eq list): Solving for R_s_param_tc; V_in_param=10, I_Rp_param=2.")
    solution_param_test2 = solve_circuit(param_test_comps, unknowns_param_test2, known_spec_param_test2_eq, "GND")
    print_solutions(solution_param_test2, "Parameter Test 2 Solution (R_s_param_tc = 5)")

    known_spec_param_test2_dict = {V_in_param: 10, I_Rp_param: 2}
    print("\nTest Case 2b (dict): Solving for R_s_param_tc; V_in_param=10, I_Rp_param=2.")
    solution_param_test2b = solve_circuit(param_test_comps, unknowns_param_test2, known_spec_param_test2_dict, "GND")
    print_solutions(solution_param_test2b, "Parameter Test 2b Solution (R_s_param_tc = 5)")

    # Test case from turn 69 __main__ (modified to use dict for knowns)
    V_in_sym_t1 = sp.Symbol('V_in_t1')
    R1_t1, R2_t1 = sp.symbols('R1_t1 R2_t1')
    vs_t1 = VoltageSource(name='Vs_t1', node1='n_in_t1', node2='GND', voltage_val_sym=V_in_sym_t1)
    r1_t1 = Resistor(name='R1_t1', node1='n_in_t1', node2='n_mid_t1', resistance_sym=R1_t1)
    r2_t1 = Resistor(name='R2_t1', node1='n_mid_t1', node2='GND', resistance_sym=R2_t1)
    components_t1 = [vs_t1, r1_t1, r2_t1]
    known_specs_t1_dict = { V_in_sym_t1: 10, R1_t1: 100, sp.Symbol('V_n_mid_t1'): 2 }
    unknowns_t1 = [R2_t1, sp.Symbol('V_n_mid_t1')] # V_n_mid_t1 is also "known" but good to include
    print("\n--- Original Test Case from turn 69 (dict knowns) ---")
    solution_t1 = solve_circuit(components_t1, unknowns_t1, known_specs_t1_dict, ground_node='GND')
    print_solutions(solution_t1, "Solution T1 (Expected R2_t1=25, V_n_mid_t1=2)")
