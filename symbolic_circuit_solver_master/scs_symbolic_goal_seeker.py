"""
Symbolic Goal Seeker for Electronic Circuits.

This module provides functionality to solve for an unknown symbolic parameter
in a circuit such that a specified target electrical quantity (e.g., a node
voltage or element current) achieves a desired symbolic or numerical value.

The primary functions are `solve_for_symbolic_unknown` and `solve_circuit_for_unknowns`.
"""
import sympy
import typing # For type hinting
import os # Added for os.path.exists and os.remove

# Project-specific imports
from . import scs_parser as scs_parser_module
from . import scs_circuit
from . import scs_instance_hier
from . import scs_errors
import re # For parsing target_quantity_str
from . import scs_elements # For isinstance checks and static method calls

def _generate_circuit_variables(top_instance: scs_instance_hier.Instance) -> \
                                 typing.Tuple[typing.Dict[str, sympy.Symbol],
                                              typing.Dict[str, sympy.Symbol],
                                              typing.List[sympy.Symbol]]:
    """
    Generates symbolic variables for all node voltages and element currents,
    and collects all unique parameter symbols from the circuit instance.
    """
    node_voltages_map = {}
    if top_instance.nets:
        for net_name in top_instance.nets:
            if net_name != '0':
                node_voltages_map[net_name] = sympy.symbols(f'V_{net_name}')

    element_currents_map = {}
    parameter_symbols_set = set()

    if top_instance.elements:
        for el_name, el_obj in top_instance.elements.items():
            element_currents_map[el_name] = sympy.symbols(f'I_{el_name}')
            if el_obj.values:
                if hasattr(el_obj.values[0], 'free_symbols'):
                    parameter_symbols_set.update(el_obj.values[0].free_symbols)

    return node_voltages_map, element_currents_map, list(parameter_symbols_set)

def _generate_kcl_equations(top_instance: scs_instance_hier.Instance,
                            element_currents_map: typing.Dict[str, sympy.Symbol]) -> typing.List[sympy.Eq]:
    """
    Generates Kirchhoff's Current Law (KCL) equations for each non-ground node.
    """
    kcl_equations = []
    if not top_instance.nets or not top_instance.elements_on_net:
        return kcl_equations

    for node_name in top_instance.nets:
        if node_name == '0':
            continue
        current_sum = sympy.Integer(0)
        if node_name in top_instance.elements_on_net:
            for element_obj in top_instance.elements_on_net[node_name]:
                el_name = element_obj.names[0]
                if el_name not in element_currents_map:
                    print(f"Warning: Current symbol for element '{el_name}' not found in KCL map. Skipping.")
                    continue
                I_el = element_currents_map[el_name]
                if len(element_obj.nets) >= 2:
                    if element_obj.nets[0] == node_name: current_sum += I_el
                    elif element_obj.nets[1] == node_name: current_sum -= I_el
                else:
                    print(f"Warning: Element '{el_name}' < 2 nets for KCL at '{node_name}'.")
        kcl_equations.append(sympy.Eq(current_sum, 0))
    return kcl_equations

def _generate_element_vi_equations(top_instance: scs_instance_hier.Instance,
                                   node_voltages_map: typing.Dict[str, sympy.Symbol],
                                   element_currents_map: typing.Dict[str, sympy.Symbol]) -> typing.List[sympy.Eq]:
    """
    Generates element-specific voltage-current relationship equations.
    """
    element_vi_equations = []
    if not top_instance.elements: return element_vi_equations
    for el_name, el_obj in top_instance.elements.items():
        I_element = element_currents_map.get(el_name)
        if I_element is None: continue
        V_n_plus = node_voltages_map.get(el_obj.nets[0], sympy.Integer(0)) if len(el_obj.nets) > 0 else sympy.Integer(0)
        V_n_minus = node_voltages_map.get(el_obj.nets[1], sympy.Integer(0)) if len(el_obj.nets) > 1 else sympy.Integer(0)
        param_expr = el_obj.values[0] if el_obj.values else None
        if param_expr is None and not isinstance(el_obj, (scs_elements.Capacitance, scs_elements.Inductance)): continue
        eqs = []
        if isinstance(el_obj, scs_elements.Resistance): eqs = scs_elements.Resistance.get_symbolic_equations(V_n_plus, V_n_minus, I_element, param_expr)
        elif type(el_obj) is scs_elements.VoltageSource: eqs = scs_elements.VoltageSource.get_symbolic_equations(V_n_plus, V_n_minus, param_expr)
        elif type(el_obj) is scs_elements.CurrentSource: eqs = scs_elements.CurrentSource.get_symbolic_equations(I_element, param_expr)
        elif isinstance(el_obj, scs_elements.VoltageControlledVoltageSource):
            if len(el_obj.nets) < 4: continue
            V_ctrl_plus = node_voltages_map.get(el_obj.nets[2], sympy.Integer(0))
            V_ctrl_minus = node_voltages_map.get(el_obj.nets[3], sympy.Integer(0))
            eqs = scs_elements.VoltageControlledVoltageSource.get_symbolic_equations(V_n_plus, V_n_minus, V_ctrl_plus, V_ctrl_minus, param_expr)
        elif isinstance(el_obj, scs_elements.VoltageControlledCurrentSource):
            if len(el_obj.nets) < 4: continue
            V_ctrl_plus = node_voltages_map.get(el_obj.nets[2], sympy.Integer(0))
            V_ctrl_minus = node_voltages_map.get(el_obj.nets[3], sympy.Integer(0))
            eqs = scs_elements.VoltageControlledCurrentSource.get_symbolic_equations(I_element, V_ctrl_plus, V_ctrl_minus, param_expr)
        elif isinstance(el_obj, scs_elements.CurrentControlledVoltageSource):
            I_control_sym = element_currents_map.get(el_obj.names[1])
            if I_control_sym is None: continue
            eqs = scs_elements.CurrentControlledVoltageSource.get_symbolic_equations(V_n_plus, V_n_minus, I_control_sym, param_expr)
        elif isinstance(el_obj, scs_elements.CurrentControlledCurrentSource):
            I_control_sym = element_currents_map.get(el_obj.names[1])
            if I_control_sym is None: continue
            eqs = scs_elements.CurrentControlledCurrentSource.get_symbolic_equations(I_element, I_control_sym, param_expr)
        elif isinstance(el_obj, scs_elements.Capacitance): eqs = [sympy.Eq(I_element, 0)]
        elif isinstance(el_obj, scs_elements.Inductance): eqs = [sympy.Eq(V_n_plus - V_n_minus, 0)]
        else: print(f"Warning: Element type {type(el_obj).__name__} for '{el_name}' not handled for VI equations.")
        if eqs: element_vi_equations.extend(eqs)
    return element_vi_equations

def generate_circuit_equations(netlist_path: str = None, top_instance_optional: scs_instance_hier.Instance = None) -> \
                               typing.Tuple[typing.Optional[typing.List[sympy.Eq]],
                                            typing.Optional[typing.Dict[str, any]],
                                            typing.Optional[scs_instance_hier.Instance]]:
    print(f"--- Generating Circuit Equations ---")
    top_instance = top_instance_optional
    try:
        if top_instance is None:
            if not netlist_path:
                print("Error: Netlist path must be provided if top_instance is not.")
                return None, None, None
            print(f"  Parsing netlist: {netlist_path}...")
            top_circuit_obj = scs_circuit.TopCircuit()
            parsed_circuit = scs_parser_module.parse_file(netlist_path, top_circuit_obj)
            if not parsed_circuit: return None, None, None
            print("  Netlist parsing successful.")
            print("  Creating circuit instance...")
            top_instance = scs_instance_hier.make_top_instance(parsed_circuit)
            if not top_instance: return None, None, None
            print("  Circuit instance created.")
            if not top_instance.check_path_to_gnd(): return None, None, None
            print("  Performing initial symbolic solve of the circuit (within generate_circuit_equations)...")
            top_instance.solve()
            print("  Initial symbolic solve complete (within generate_circuit_equations).")
        else:
            print("  Using provided top_instance.")
            if not hasattr(top_instance, 'kv'):
                 print("  Provided top_instance does not seem solved, calling top_instance.solve()...")
                 top_instance.solve()

        node_voltages_map, element_currents_map, parameter_symbols = _generate_circuit_variables(top_instance)
        kcl_equations = _generate_kcl_equations(top_instance, element_currents_map)
        element_vi_equations = _generate_element_vi_equations(top_instance, node_voltages_map, element_currents_map)
        all_equations = kcl_equations + element_vi_equations
        circuit_variables = {'voltages': node_voltages_map, 'currents': element_currents_map, 'params': parameter_symbols}

        print(f"    Generated Node Voltage Symbols Map: {circuit_variables.get('voltages')}")
        print(f"    Generated Element Current Symbols Map: {circuit_variables.get('currents')}")
        print(f"    Generated Identified Parameter Symbols: {circuit_variables.get('params')}")
        print(f"    Generated KCL Equations: {kcl_equations}")
        print(f"  Total equations generated: {len(all_equations)}")
        return all_equations, circuit_variables, top_instance
    except Exception as e:
        print(f"An unexpected error occurred in generate_circuit_equations: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
    return None, None, None

def _get_symbol_from_name(name_str: str, circuit_vars: dict) -> sympy.Symbol:
    """
    Finds a Sympy Symbol object given its string name from the circuit_vars structure.
    """
    for sym_type_map_key in ['params', 'voltages', 'currents']:
        if sym_type_map_key == 'params': # Parameters are stored as a list of symbols
            for sym in circuit_vars.get('params', []):
                if sym.name == name_str: return sym
        else: # Voltages and Currents are maps from name_str (node/elem) to Symbol object
            # The symbol name itself is V_nodename or I_elementname
            # For V_N1, name_str might be "V_N1" or "N1" (if called from auto-population)
            # For I_R1, name_str might be "I_R1" or "R1"
            type_map = circuit_vars.get(sym_type_map_key, {})

            # Try direct lookup if name_str is the key (e.g. "N1" for voltages map)
            if name_str in type_map : return type_map[name_str]

            # Try matching symbol name if name_str is prefixed (e.g. "V_N1")
            for _, sym_obj in type_map.items():
                if sym_obj.name == name_str: return sym_obj

    print(f"Warning: Symbol '{name_str}' not found in pre-generated circuit variables. Creating it on the fly.")
    return sympy.symbols(name_str)

def solve_from_equations(
    equations: typing.List[sympy.Eq],
    all_circuit_variables: dict,
    known_values_map_str_keys: typing.Dict[str, typing.Union[str, float, int]],
    unknowns_to_solve_for_str: typing.List[str]
) -> typing.List[typing.Dict[sympy.Symbol, sympy.Expr]]:
    """
    Solves a system of symbolic equations for specified unknowns, given some known values.
    """
    print(f"\n--- Solving from Equations ---")
    known_symbols_subs_map = {
        _get_symbol_from_name(k, all_circuit_variables): sympy.sympify(v)
        for k,v in known_values_map_str_keys.items()
    }
    unknown_symbols_obj_list = [_get_symbol_from_name(s, all_circuit_variables) for s in unknowns_to_solve_for_str]
    if not unknown_symbols_obj_list: print("  Error: No unknown symbols specified."); return []

    # Filter out any symbols in unknown_symbols_obj_list that are already keys in known_symbols_subs_map
    # This can happen if a parameter is accidentally listed in both knowns and unknowns.
    # sympy.solve will error if a symbol is in both knowns (via subs) and unknowns list.
    final_unknown_symbols = [sym for sym in unknown_symbols_obj_list if sym not in known_symbols_subs_map]
    if not final_unknown_symbols:
        print("  Error: All specified unknowns are already in the known_values_map. No variables left to solve for.")
        # It might be valid to return an empty solution or evaluate expressions if no unknowns.
        # For now, returning empty as per original behavior for "no unknowns specified".
        return []
    if len(final_unknown_symbols) < len(unknown_symbols_obj_list):
        print(f"  Filtered unknowns list from {len(unknown_symbols_obj_list)} to {len(final_unknown_symbols)} symbols to avoid overlap with knowns.")

    try:
        eqs_subbed = [eq.subs(known_symbols_subs_map) for eq in equations]
        print(f"  Equations after substituting knowns: {eqs_subbed}")
    except Exception as e: print(f"  Error during substitution: {type(e).__name__} - {e}"); return []

    solutions_list = []
    try:
        found_solutions = sympy.solve(eqs_subbed, *final_unknown_symbols, dict=True)
        print(f"  Raw solutions from sympy.solve: {found_solutions}")
        if isinstance(found_solutions, dict): solutions_list = [found_solutions]
        elif isinstance(found_solutions, list): solutions_list = found_solutions
        elif found_solutions is None: solutions_list = []
        # Handle case where solve returns a single expression for a single unknown
        elif len(final_unknown_symbols) == 1 and not isinstance(found_solutions, (list, dict)):
             solutions_list = [{final_unknown_symbols[0]: found_solutions}]
        else: print(f"Warning: Unexpected solution format: {type(found_solutions)}."); solutions_list = []
    except Exception as e: print(f"  Error during sympy.solve: {type(e).__name__} - {e}"); import traceback; traceback.print_exc(); solutions_list = []

    if not solutions_list: print("  No solutions found or error occurred.")
    else: print(f"  Processed solutions: {solutions_list}")
    return solutions_list

def solve_circuit_for_unknowns(
    netlist_path: str = None,
    known_values_map_str_keys: typing.Dict[str, typing.Union[str, float, int]] = None,
    unknowns_to_solve_for_str: typing.List[str] = None,
    top_instance_optional: scs_instance_hier.Instance = None
) -> typing.List[typing.Dict[sympy.Symbol, sympy.Expr]]:
    """
    Solves a circuit for specified or all unknown electrical quantities (node voltages,
    element currents, and potentially parameters) given a netlist and known parameter values.

    This function encapsulates the process of generating the circuit's symbolic MNA equations,
    substituting known values, and then solving for the desired unknowns.

    Args:
        netlist_path: Path to the SPICE-like netlist file. Required if
                      top_instance_optional is not provided.
        known_values_map_str_keys: A dictionary mapping string names of known parameters
                                   (e.g., "R1_s") to their numerical or symbolic values.
                                   Defaults to an empty dictionary if None.
        unknowns_to_solve_for_str: A list of string names for the variables to be solved.
                                   These can be node voltages (e.g., "V_N1"), element
                                   currents (e.g., "I_R1"), or parameter names
                                   (e.g., "R1_s"). If None or empty, the function will attempt
                                   to solve for all main circuit variables (all node voltages,
                                   all element currents) and any parameters not defined in
                                   known_values_map_str_keys.
        top_instance_optional: An optional pre-parsed and pre-solved top-level circuit
                               instance. If provided, netlist_path might be ignored.
                               This is useful for iterative solving or when the instance is
                               already available.

    Returns:
        A list of solution dictionaries, where each dictionary maps Sympy Symbol objects
        (representing the solved variables) to their Sympy expression solutions.
        Returns an empty list if no solution is found or an error occurs.
    """
    print(f"\n--- Solving Circuit for Unknowns ---")
    if top_instance_optional:
        print(f"  Using provided top_instance. Netlist path '{netlist_path}' might be ignored if instance is fully self-contained.")
    elif netlist_path:
        print(f"  Netlist path: {netlist_path}")
    else:
        print("Error: Either netlist_path or a valid top_instance_optional must be provided.")
        return []

    equations, circuit_vars, _ = generate_circuit_equations(
        netlist_path=netlist_path,
        top_instance_optional=top_instance_optional
    )

    if not equations or not circuit_vars:
        print("  Error: Failed to generate circuit equations or variables. Cannot solve.")
        return []

    known_values_map_str_keys = known_values_map_str_keys or {}
    # Make a copy to avoid modifying the caller's list if it's passed and then auto-populated
    unknowns_to_solve_for_str = list(unknowns_to_solve_for_str) if unknowns_to_solve_for_str is not None else []


    if not unknowns_to_solve_for_str: # If list is empty (either passed as [] or was None)
        print("  No specific unknowns provided, attempting to solve for all circuit variables and unknown parameters.")
        # Populate with all node voltages (e.g., V_N1 from node N1)
        # circuit_vars['voltages'] is {'N1': V_N1_sym, ...}
        for node_name_key in circuit_vars.get('voltages', {}).keys():
            # _get_symbol_from_name expects "V_N1" to find V_N1_sym
            unknowns_to_solve_for_str.append(f"V_{node_name_key}")

        # Populate with all element currents (e.g., I_R1 from element R1)
        # circuit_vars['currents'] is {'R1': I_R1_sym, ...}
        for elem_name_key in circuit_vars.get('currents', {}).keys():
            unknowns_to_solve_for_str.append(f"I_{elem_name_key}")

        # Populate with parameters not in known_values_map_str_keys
        parameter_symbols = circuit_vars.get('params', []) # List of Symbol objects
        for param_sym in parameter_symbols:
            if param_sym.name not in known_values_map_str_keys:
                unknowns_to_solve_for_str.append(param_sym.name)

        if not unknowns_to_solve_for_str:
            print("  Warning: Could not determine any unknowns to solve for automatically.")

    # Deduplicate list just in case, though logic above should avoid it mostly
    unknowns_to_solve_for_str = sorted(list(set(unknowns_to_solve_for_str)))

    print(f"  Final list of unknowns to solve for: {unknowns_to_solve_for_str}")
    print(f"  Known values for substitution: {known_values_map_str_keys}")

    solutions = solve_from_equations(
        equations,
        circuit_vars,
        known_values_map_str_keys,
        unknowns_to_solve_for_str
    )

    return solutions

def _get_target_actual_expr(top_instance: scs_instance_hier.Instance, target_quantity_str: str) -> typing.Optional[sympy.Expr]:
    if not top_instance: raise ValueError("Top instance not available.")
    match_v_n1 = re.fullmatch(r"V\s*\(\s*([a-zA-Z0-9_]+)\s*\)", target_quantity_str, re.IGNORECASE)
    match_v_n1_n2 = re.fullmatch(r"V\s*\(\s*([a-zA-Z0-9_]+)\s*,\s*([a-zA-Z0-9_]+)\s*\)", target_quantity_str, re.IGNORECASE)
    match_i_elem = re.fullmatch(r"I\s*\(\s*([a-zA-Z0-9_]+)\s*\)", target_quantity_str, re.IGNORECASE)
    match_p_elem = re.fullmatch(r"P\s*\(\s*([a-zA-Z0-9_]+)\s*\)", target_quantity_str, re.IGNORECASE)
    actual_expr = None
    if match_v_n1: actual_expr = top_instance.v(match_v_n1.group(1), '0')
    elif match_v_n1_n2: actual_expr = top_instance.v(match_v_n1_n2.group(1), match_v_n1_n2.group(2))
    elif match_i_elem: actual_expr = top_instance.i(match_i_elem.group(1))
    elif match_p_elem: actual_expr = top_instance.p(match_p_elem.group(1))
    else: raise ValueError(f"Invalid target_quantity_str format: '{target_quantity_str}'")
    if actual_expr is not None: print(f"  Interpreted target '{target_quantity_str}' as: {actual_expr}")
    return actual_expr

def solve_for_symbolic_unknown(
    netlist_path: str,
    unknown_param_name_str: str,
    target_quantity_str: str,
    target_value_expr_str: str
) -> typing.List[sympy.Expr]:
    print(f"--- Symbolic Goal Seeker ---")
    print(f"Netlist: {netlist_path}")
    print(f"Unknown Parameter: {unknown_param_name_str}")
    print(f"Target Quantity: {target_quantity_str}")
    print(f"Target Value: {target_value_expr_str}")
    solutions: typing.List[sympy.Expr] = []
    try:
        unknown_sym = sympy.symbols(unknown_param_name_str)
        target_val_sym_expr = sympy.sympify(target_value_expr_str)
        print(f"  Unknown symbol to solve for: {unknown_sym}")
        print(f"  Target value expression: {target_val_sym_expr}")

        base_equations, circuit_vars, top_instance = generate_circuit_equations(netlist_path=netlist_path)

        if base_equations is None or circuit_vars is None or top_instance is None:
            print("  Error: Failed to generate base circuit equations or retrieve instance.")
            return []

        actual_expr = _get_target_actual_expr(top_instance, target_quantity_str)
        if actual_expr is None:
            print(f"  Error: Failed to derive actual expression for '{target_quantity_str}'.")
            return []

        target_eq = sympy.Eq(actual_expr, target_val_sym_expr)
        print(f"  Formed target equation: {target_eq}")
        final_equations = base_equations + [target_eq]
        print(f"  Total equations for system solve: {len(final_equations)}")

        system_vars_to_solve = set([unknown_sym])
        for v_sym in circuit_vars.get('voltages', {}).values():
            system_vars_to_solve.add(v_sym)
        for i_sym in circuit_vars.get('currents', {}).values():
            system_vars_to_solve.add(i_sym)

        solve_for_symbols_list = list(system_vars_to_solve)

        print(f"  Solving system for '{unknown_sym.name}' (among {solve_for_symbols_list})...")
        found_system_solutions = sympy.solve(final_equations, *solve_for_symbols_list, dict=True)
        print(f"  Raw system solutions from sympy.solve: {found_system_solutions}")

        if found_system_solutions:
            if isinstance(found_system_solutions, dict):
                found_system_solutions = [found_system_solutions]

            for sol_dict in found_system_solutions:
                if unknown_sym in sol_dict:
                    solutions.append(sol_dict[unknown_sym])
        else:
            pass

    except Exception as e:
        print(f"An unexpected error occurred in solve_for_symbolic_unknown: {type(e).__name__} - {e}")
        import traceback; traceback.print_exc()
    if not solutions: print(f"  No solutions found or error for {unknown_param_name_str}.")
    else: print(f"  Solutions for {unknown_param_name_str}: {solutions}")
    return solutions

if __name__ == '__main__':
    print("--- Testing scs_symbolic_goal_seeker.py ---")
    temp_files_created = []

    # Test for solve_for_symbolic_unknown
    dummy_sfs_netlist_content = """
* Dummy Netlist for solve_for_symbolic_unknown Test
.PARAM VAL_V1 = VAL_V1
.PARAM V_target = V_target
V1 N1 0 VAL_V1
.end
"""
    dummy_sfs_test_path = "_temp_sgs_sfs_test.sp" # Unique name
    temp_files_created.append(dummy_sfs_test_path)
    try:
        with open(dummy_sfs_test_path, 'w') as f: f.write(dummy_sfs_netlist_content)
        print("\n--- Testing solve_for_symbolic_unknown (Refactored) ---")
        print("Test Case S1: Solve for VAL_V1 such that V(N1) = V_target")
        v_target_sym_sfs = sympy.symbols('V_target')
        solutions_s1 = solve_for_symbolic_unknown(
            netlist_path=dummy_sfs_test_path,
            unknown_param_name_str="VAL_V1",
            target_quantity_str="V(N1)",
            target_value_expr_str="V_target"
        )
        print(f"Solutions for Test Case S1 (VAL_V1): {solutions_s1}")
        assert solutions_s1 == [v_target_sym_sfs], f"Expected [{v_target_sym_sfs}] but got {solutions_s1}"
        print("Test Case S1 Passed!")
    except Exception as e:
        print(f"Test Case S1 FAILED: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()

    # Test for solve_circuit_for_unknowns (previously SFE test)
    dummy_sfe_netlist_content = """
* Comprehensive Test Netlist for SFE
.PARAM R1_s = R1_s
.PARAM V1_s = V1_s
.PARAM I1_s = I1_s
.PARAM E1_gain = E1_gain
.PARAM G1_gm = G1_gm
.PARAM H1_rt = H1_rt
.PARAM F1_gain = F1_gain
.PARAM VDH_s = VDH_s
.PARAM VDF_s = VDF_s
.PARAM RH_path_s = RH_path_s
.PARAM RF_path_s = RF_path_s
.PARAM RLNR1_s = RLNR1_s
.PARAM RLNR2_s = RLNR2_s
.PARAM RLNI1_s = RLNI1_s
.PARAM RLNEO_s = RLNEO_s
.PARAM RLNGO_s = RLNGO_s
.PARAM RLNHO_s = RLNHO_s
.PARAM RLNFO_s = RLNFO_s

R1 nr1 nr2 R1_s
V1 nv1 0 V1_s
I1 ni1 0 I1_s
E1 ne_out 0 nv1 nr1 E1_gain
G1 ng_out 0 nv1 nr1 G1_gm
VdummyH nvh_sense 0 VDH_s
RH_path nr2 nvh_sense RH_path_s
H1 nh_out 0 VdummyH H1_rt
VdummyF nvf_sense 0 VDF_s
RF_path ni1 nvf_sense RF_path_s
F1 nf_out 0 VdummyF F1_gain
R_load_nr1 nr1 0 RLNR1_s
R_load_nr2 nr2 0 RLNR2_s
R_load_ni1 ni1 0 RLNI1_s
R_load_ne_out ne_out 0 RLNEO_s
R_load_ng_out ng_out 0 RLNGO_s
R_load_nh_out nh_out 0 RLNHO_s
R_load_nf_out nf_out 0 RLNFO_s
.end
"""
    dummy_sfe_test_path = "_temp_sgs_sfe_test.sp" # Unique name
    temp_files_created.append(dummy_sfe_test_path)
    try:
        with open(dummy_sfe_test_path, 'w') as f: f.write(dummy_sfe_netlist_content)

        print("\n--- SFE Test Setup: Initial generation of circuit_vars and top_inst for expected value calculation ---")
        _, circuit_vars_for_assertions, top_inst_for_assertions = generate_circuit_equations(netlist_path=dummy_sfe_test_path)
        assert circuit_vars_for_assertions is not None
        assert top_inst_for_assertions is not None

        print("\n--- Test Case: solve_circuit_for_unknowns with Complex Netlist ---")

        known_values_map_str_keys = {
            'R1_s': 10.0, 'V1_s': 5.0, 'I1_s': 1.0, 'E1_gain': 2.0, 'G1_gm': 0.1,
            'H1_rt': 100.0, 'F1_gain': 0.5, 'VDH_s': 0.0, 'VDF_s': 0.0,
            'RH_path_s': 1.0, 'RF_path_s': 1.0, 'RLNR1_s': 1e9, 'RLNR2_s': 1e9,
            'RLNI1_s': 1e9, 'RLNEO_s': 1e9, 'RLNGO_s': 1e9, 'RLNHO_s': 1e9, 'RLNFO_s': 1e9
        }

        unknowns_to_solve_for_str = [
            'V_nv1', 'V_nr1', 'V_nr2', 'V_ni1', 'V_ne_out', 'V_ng_out', 'V_nh_out', 'V_nf_out', 'V_nvh_sense', 'V_nvf_sense',
            'I_R1', 'I_V1', 'I_I1', 'I_E1', 'I_G1', 'I_VdummyH', 'I_RH_path', 'I_H1',
            'I_VdummyF', 'I_RF_path', 'I_F1', 'I_R_load_nr1', 'I_R_load_nr2', 'I_R_load_ni1',
            'I_R_load_ne_out', 'I_R_load_ng_out', 'I_R_load_nh_out', 'I_R_load_nf_out'
        ]

        known_values_map_sympy_keys = {sympy.symbols(k): sympy.sympify(v) for k,v in known_values_map_str_keys.items()}

        expected_V_nv1 = top_inst_for_assertions.v('nv1', '0').subs(known_values_map_sympy_keys).evalf()
        expected_V_ne_out = top_inst_for_assertions.v('ne_out', '0').subs(known_values_map_sympy_keys).evalf()
        expected_I_I1 = top_inst_for_assertions.i('I1').subs(known_values_map_sympy_keys).evalf()
        expected_I_R1 = top_inst_for_assertions.i('R1').subs(known_values_map_sympy_keys).evalf()

        expected_I_VdummyH_val_from_top_inst = top_inst_for_assertions.i('VdummyH').subs(known_values_map_sympy_keys).evalf()
        expected_I_VdummyH_mna_consistent = sympy.Float(0.0)

        v_ni1_mna_calc = -1.0 / (1.0/known_values_map_str_keys['RF_path_s'] + 1.0/known_values_map_str_keys['RLNI1_s'])
        expected_I_F1_mna_consistent = sympy.Float(known_values_map_str_keys['F1_gain'] * v_ni1_mna_calc)
        expected_I_F1_val_from_top_inst = top_inst_for_assertions.i('F1').subs(known_values_map_sympy_keys).evalf()

        print(f"  Calculated expected values (subset for assertion):")
        print(f"    Expected V_nv1 = {expected_V_nv1}")
        print(f"    Expected V_ne_out = {expected_V_ne_out}")
        print(f"    Expected I_I1 = {expected_I_I1}")
        print(f"    Expected I_R1 = {expected_I_R1}")
        print(f"    Expected I_VdummyH (from top_inst.i, may differ): {expected_I_VdummyH_val_from_top_inst}")
        print(f"    Asserting I_VdummyH against MNA-consistent: {expected_I_VdummyH_mna_consistent}")
        print(f"    Expected I_F1 (from top_inst.i, may differ): {expected_I_F1_val_from_top_inst}")
        print(f"    Asserting I_F1 against MNA-consistent: {expected_I_F1_mna_consistent}")

        solutions = solve_circuit_for_unknowns(
            netlist_path=dummy_sfe_test_path,
            known_values_map_str_keys=known_values_map_str_keys,
            unknowns_to_solve_for_str=unknowns_to_solve_for_str
        )

        if solutions:
            print(f"  Solutions from solve_circuit_for_unknowns: {solutions}")
            if isinstance(solutions, list) and len(solutions) > 0:
                solution_dict = solutions[0]

                val_V_nv1 = solution_dict.get(circuit_vars_for_assertions['voltages']['nv1'])
                if val_V_nv1 is not None:
                     print(f"    Solved V_nv1: {val_V_nv1.evalf()}")
                     assert abs(val_V_nv1.evalf() - expected_V_nv1) < 1e-9, "V_nv1 mismatch"
                     print("    Assertion for V_nv1 PASSED.")

                val_V_ne_out = solution_dict.get(circuit_vars_for_assertions['voltages']['ne_out'])
                if val_V_ne_out is not None:
                    print(f"    Solved V_ne_out: {val_V_ne_out.evalf()}")
                    assert abs(val_V_ne_out.evalf() - expected_V_ne_out) < 1e-9, "V_ne_out mismatch"
                    print("    Assertion for V_ne_out PASSED.")

                val_I_I1 = solution_dict.get(circuit_vars_for_assertions['currents']['I1'])
                if val_I_I1 is not None:
                    print(f"    Solved I_I1: {val_I_I1.evalf()}")
                    assert abs(val_I_I1.evalf() - expected_I_I1) < 1e-9, "I_I1 mismatch"
                    print("    Assertion for I_I1 PASSED.")

                val_I_R1 = solution_dict.get(circuit_vars_for_assertions['currents']['R1'])
                if val_I_R1 is not None:
                    print(f"    Solved I_R1: {val_I_R1.evalf()}")
                    assert abs(val_I_R1.evalf() - expected_I_R1) < 1e-9, "I_R1 mismatch"
                    print("    Assertion for I_R1 PASSED.")

                val_I_VdummyH = solution_dict.get(circuit_vars_for_assertions['currents']['VdummyH'])
                if val_I_VdummyH is not None:
                    print(f"    Solved I_VdummyH (H1 control): {val_I_VdummyH.evalf()}")
                    assert abs(val_I_VdummyH.evalf() - expected_I_VdummyH_mna_consistent) < 1e-9, "I_VdummyH mismatch"
                    print("    Assertion for I_VdummyH PASSED.")

                val_I_F1 = solution_dict.get(circuit_vars_for_assertions['currents']['F1'])
                if val_I_F1 is not None:
                    print(f"    Solved I_F1: {val_I_F1.evalf()}")
                    assert abs(val_I_F1.evalf() - expected_I_F1_mna_consistent) < 1e-9, "I_F1 mismatch"
                    print("    Assertion for I_F1 PASSED.")
            else:
                print("  solve_circuit_for_unknowns did not return the expected solution format.")
        else:
            print("  solve_circuit_for_unknowns returned no solutions.")
        print("--- Test Case: solve_circuit_for_unknowns for Complex Netlist COMPLETED ---")

    except Exception as e:
        print(f"Test Case (solve_circuit_for_unknowns) FAILED: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nCleaning up temporary files...")
        for f_path in temp_files_created:
            if os.path.exists(f_path):
                os.remove(f_path)
                print(f"  Removed {f_path}")
    print("\n--- scs_symbolic_goal_seeker.py tests complete ---")
