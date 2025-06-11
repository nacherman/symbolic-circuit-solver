import sympy as sp
from symbolic_components import BaseComponent, Resistor, VoltageSource, CurrentSource

# Make sure symbolic_components.py is in the same directory or accessible via PYTHONPATH

def solve_circuit(components, unknown_symbols_to_solve_for, known_substitutions=None, additional_equations=None, ground_node='GND'):
    '''
    Solves a circuit symbolically.

    Args:
        components (list): A list of BaseComponent instances.
        unknown_symbols_to_solve_for (list): A list of sympy Symbols that the user specifically wants to solve for.
                                            These can be component values (like R_unknown), currents, or source values.
        known_substitutions (dict, optional): A dictionary of {symbol: value} for known parameters.
                                             Values can be numeric or other sympy expressions/symbols.
                                             Example: {R1_sym: 100, V_source_sym: sp.Symbol('Vin')}
        additional_equations (list, optional): A list of additional sympy expressions that should equal zero.
                                              Example: [V_output_sym - 0.1] to set V_output_sym to 0.1.
        ground_node (str, optional): The name of the ground node. Its voltage will be set to 0.

    Returns:
        list: A list of solutions (dictionaries) from sympy.solve(), or potentially a single solution dictionary.
              Returns None if the system is unsolvable or other sympy errors occur.
    '''
    if not components:
        raise ValueError("Components list cannot be empty.")
    if not unknown_symbols_to_solve_for:
        raise ValueError("List of unknown symbols to solve for cannot be empty.")

    all_equations = []
    all_nodes = set()
    all_symbols_in_circuit = set() # Includes node voltages, component values, currents

    # 1. Collect all component characteristic equations and identify nodes and symbols
    for comp in components:
        if not isinstance(comp, BaseComponent):
            raise TypeError(f"Item {comp} in components list is not a BaseComponent.")
        all_equations.extend(comp.expressions)
        all_nodes.add(comp.node1)
        all_nodes.add(comp.node2)

        # Add symbols from component.values and component.expressions
        for eq in comp.expressions:
            all_symbols_in_circuit.update(eq.free_symbols)
        for val_sym in comp.values.values():
            if isinstance(val_sym, sp.Symbol):
                all_symbols_in_circuit.add(val_sym)

        # Add V_comp and I_comp symbols
        all_symbols_in_circuit.add(comp.V_comp)
        if hasattr(comp, 'I_comp'): # CurrentSource might not have I_comp as a separate symbol in the same way
             all_symbols_in_circuit.add(comp.I_comp)


    # 2. Define Node Voltage Symbols and handle Ground Node
    node_voltage_symbols = {}
    for node_name in all_nodes:
        if node_name == ground_node:
            node_voltage_symbols[node_name] = sp.Integer(0) # Ground is 0V
        else:
            # Use the V_nodename symbols already created by components if available,
            # otherwise create new ones. This ensures consistency.
            # We search for a V_nodename symbol that would have been created by a component.
            # This relies on the V_node1/V_node2 symbols in BaseComponent.
            potential_symbol = sp.Symbol(f"V_{node_name}")
            node_voltage_symbols[node_name] = potential_symbol
            all_symbols_in_circuit.add(potential_symbol)

    # Substitute node voltage symbols (V_node1, V_node2 from components) with the actual V_nodename symbols
    # And substitute ground node voltage with 0.
    # This is critical because component expressions use generic V_node1, V_node2 symbols.
    # We need to map them to the specific V_N1, V_N2, V_GND=0 etc.

    # Create substitution dictionary for V_node1, V_node2 in component expressions
    # and for the ground node.
    node_subs = {}
    for node_name, voltage_symbol in node_voltage_symbols.items():
        # This maps the generic "V_nodeX" from component.V_node1 to the specific "V_N1"
        # This is implicitly handled by how node_voltage_symbols are created and used if
        # component.V_node1 and component.V_node2 symbols are directly used.
        # The main substitution needed is for the ground node.
        if node_name == ground_node:
             # For any component connected to ground, its V_groundnode symbol becomes 0
            ground_sym_in_comp = sp.Symbol(f"V_{ground_node}") # e.g. V_GND
            node_subs[ground_sym_in_comp] = sp.Integer(0)

    # Apply ground substitution to all equations
    processed_equations = [eq.subs(node_subs) for eq in all_equations]

    # 3. Generate KCL Equations for non-ground nodes
    kcl_equations = []
    for node_name in all_nodes:
        if node_name == ground_node:
            continue

        currents_into_node = sp.Integer(0)
        for comp in components:
            # Current I_comp is defined as flowing from node1 to node2
            if comp.node1 == node_name: # Current flows out of this node via this comp
                currents_into_node -= comp.I_comp
            elif comp.node2 == node_name: # Current flows into this node via this comp
                currents_into_node += comp.I_comp
        kcl_equations.append(currents_into_node) # Sum of currents into node = 0

    processed_equations.extend(kcl_equations)

    # 4. Apply known_substitutions (e.g., R1=100, specific V_source_val = 5)
    if known_substitutions:
        # Ensure values are sympy compatible
        sympy_known_subs = {s: sp.sympify(v) for s, v in known_substitutions.items()}
        processed_equations = [eq.subs(sympy_known_subs) for eq in processed_equations]

    # 5. Add additional_equations (user-defined constraints)
    if additional_equations:
        processed_equations.extend(additional_equations)
        for eq in additional_equations:
             all_symbols_in_circuit.update(eq.free_symbols)


    # 6. Identify all symbols to solve for:
    #    - User-specified unknown_symbols_to_solve_for
    #    - All non-ground node voltage symbols (V_N1, V_N2 etc.)
    #    - All I_comp symbols from components (these are often unknowns like I_R1, I_VS1)
    #    - All V_comp symbols from components (these are often unknowns like V_R1)

    # Start with the user's requested symbols
    symbols_to_solve = set(unknown_symbols_to_solve_for)

    # Add all non-ground node voltages
    for node, v_sym in node_voltage_symbols.items():
        if node != ground_node:
            symbols_to_solve.add(v_sym)

    # Add all component I_comp and V_comp symbols if they are not already part of known_substitutions
    # or part of the definition of a known symbol.
    for comp in components:
        if comp.V_comp not in (known_substitutions or {}):
            symbols_to_solve.add(comp.V_comp)
        if hasattr(comp, 'I_comp') and comp.I_comp not in (known_substitutions or {}):
            symbols_to_solve.add(comp.I_comp)

    # Filter out symbols that might have been substituted if they were in known_substitutions
    final_symbols_to_solve = [s for s in list(symbols_to_solve) if s not in (known_substitutions or {})]

    # Also, ensure all free symbols in the final equations that are not in known_substitutions
    # are considered for solving, if they are not already among the unknowns.
    # This helps catch implicitly defined unknowns.
    current_free_symbols = set()
    for eq in processed_equations:
        current_free_symbols.update(eq.free_symbols)

    for s in current_free_symbols:
        if s not in (known_substitutions or {}) and s not in final_symbols_to_solve:
            # This is a bit broad, might include symbols the user intends to be parameters (e.g. R_load)
            # For now, we primarily rely on explicit unknown_symbols_to_solve_for and node voltages.
            # A more sophisticated system might differentiate parameters from variables.
            pass


    # Remove any symbols that might be in known_substitutions from the final_symbols_to_solve list
    # This is important if a symbol appears in an equation but its value is provided.
    if known_substitutions:
        final_symbols_to_solve = [s for s in final_symbols_to_solve if s not in known_substitutions]


    # Deduplicate
    final_symbols_to_solve = list(set(final_symbols_to_solve))

    print(f"DEBUG: Equations to solve ({len(processed_equations)}):")
    for i, eq in enumerate(processed_equations):
        print(f"  Eq{i+1}: {sp.pretty(eq)}")
    print(f"DEBUG: Symbols to solve for ({len(final_symbols_to_solve)}): {final_symbols_to_solve}")

    # 7. Solve the system
    try:
        solution = sp.solve(processed_equations, final_symbols_to_solve, dict=True)
        return solution
    except Exception as e:
        print(f"Error during symbolic solution: {e}")
        print("Equations handed to sympy.solve:")
        for eq in processed_equations:
            print(sp.pretty(eq))
        print("Symbols handed to sympy.solve:")
        print(final_symbols_to_solve)
        return None

if __name__ == '__main__':
    # Simple Test Case: Voltage Divider
    # V_source --- R1 --- n_mid --- R2 --- GND
    print("Symbolic Solver Test: Voltage Divider")

    # Define symbols
    V_in_sym = sp.Symbol('V_in')
    R1_sym = sp.Symbol('R1')
    R2_sym = sp.Symbol('R2')

    # Component-specific symbols (voltage across, current through)
    # These will be created by the components themselves.
    # V_R1, I_R1, V_R2, I_R2, V_Vs, I_Vs

    # Create components
    # VoltageSource: node1 is positive terminal
    vs = VoltageSource(name='Vs', node1='n_in', node2='GND', voltage_val_sym=V_in_sym)
    r1 = Resistor(name='R1', node1='n_in', node2='n_mid', resistance_sym=R1_sym)
    r2 = Resistor(name='R2', node1='n_mid', node2='GND', resistance_sym=R2_sym)

    components_vd = [vs, r1, r2]

    # We want to solve for V_n_mid (voltage at the middle node) and currents.
    # The node voltage V_n_mid is sp.Symbol('V_n_mid')
    # The component currents are vs.I_comp, r1.I_comp, r2.I_comp

    unknowns_to_find = [sp.Symbol('V_n_mid'), r1.I_comp, r2.I_comp, vs.I_comp]

    # Known values (optional, could leave V_in, R1, R2 symbolic)
    knowns = {
        V_in_sym: 10, # 10 Volts
        R1_sym: 100,  # 100 Ohms
        R2_sym: 100   # 100 Ohms
    }
    # If no knowns, solution will be purely symbolic.
    # solution_symbolic = solve_circuit(components_vd, unknowns_to_find, ground_node='GND')
    # print("\nSymbolic Solution (no specific knowns):")
    # if solution_symbolic:
    #     for sol_dict in solution_symbolic:
    #         for sym, val in sol_dict.items():
    #             print(f"  {sym} = {sp.pretty(val)}")
    # else:
    #     print("  No symbolic solution found or error.")

    print("\nSolution with knowns (Vin=10, R1=100, R2=100):")
    solution_numeric = solve_circuit(components_vd, unknowns_to_find, known_substitutions=knowns, ground_node='GND')

    if solution_numeric:
        # sympy.solve might return a list of solution dictionaries
        for sol_dict in solution_numeric:
            for sym, val in sol_dict.items():
                print(f"  {sym} = {sp.pretty(val)}")
    else:
        print("  No solution found or error.")

    # Expected: V_n_mid = 5V, I_R1 = 0.05A, I_R2 = 0.05A, I_Vs = -0.05A (current leaving positive terminal of Vs)
    # Note: My I_comp for VoltageSource is defined as current *supplied by* the source (out of positive terminal).
    # KCL: At n_in: -vs.I_comp - r1.I_comp = 0  (if I_comp is current *into* node for r1)
    # My KCL: -I_Vs + I_R1 = 0 (currents leaving n_in)
    # My KCL for general node: sum of currents entering = 0
    # Comp.I_comp is current from node1 to node2.
    # KCL at n_in:  -vs.I_comp (current from n_in to GND for Vs)
    #             -r1.I_comp (current from n_in to n_mid for R1)
    # Correct KCL for my I_comp definition (currents_into_node = 0):
    # Node n_in:  -r1.I_comp + vs.I_comp = 0  (vs.I_comp enters n_in from internal of source, r1.I_comp leaves n_in)
    # Node n_mid: r1.I_comp - r2.I_comp = 0
    # The solver implementation uses:
    # if comp.node1 == node_name: currents_into_node -= comp.I_comp (current flows out via comp)
    # if comp.node2 == node_name: currents_into_node += comp.I_comp (current flows in via comp)
    # This is sum of currents leaving node = 0, or sum of currents entering = 0 if we flip signs. It's consistent.
    # So, at n_in:
    #   vs: node1 is n_in. Term: -vs.I_comp (I_Vs, current from n_in to GND).
    #   r1: node1 is n_in. Term: -r1.I_comp (I_R1, current from n_in to n_mid).
    #   KCL eq: -vs.I_comp - r1.I_comp = 0  => vs.I_comp + r1.I_comp = 0.
    #   If I_R1 (n_in to n_mid) is 0.05A, then I_Vs (n_in to GND for the source object) must be -0.05A.
    #   This means the actual current *from* the source positive terminal (n_in) *into the circuit* is 0.05A.
    #   The symbol `vs.I_comp` represents current flowing n_in -> GND *through the source component*.
    #   This interpretation is tricky. It might be more standard to define I_Vs as current *out of* the positive terminal.
    #   In `VoltageSource`, `self.I_comp` is `I_Vs_name`. `self.values['current']` is this `I_Vs_name`.
    #   The equation for VS is `V_comp - V_source_val = 0`.
    #   The KCL for `n_in` using my solver's logic:
    #     `vs` (node1='n_in', node2='GND', I_comp=I_Vs): `currents_into_node -= I_Vs`
    #     `r1` (node1='n_in', node2='n_mid', I_comp=I_R1): `currents_into_node -= I_R1`
    #     Equation: `-I_Vs - I_R1 = 0` => `I_Vs + I_R1 = 0`.
    #   KCL for `n_mid`:
    #     `r1` (node1='n_in', node2='n_mid', I_comp=I_R1): `currents_into_node += I_R1` (enters n_mid from r1)
    #     `r2` (node1='n_mid', node2='GND', I_comp=I_R2): `currents_into_node -= I_R2` (leaves n_mid via r2)
    #     Equation: `I_R1 - I_R2 = 0` => `I_R1 = I_R2`. Correct.
    #
    #   If I_R1 = 0.05A (n_in to n_mid) and I_R2 = 0.05A (n_mid to GND).
    #   Then from `I_Vs + I_R1 = 0`, we get `I_Vs = -I_R1 = -0.05A`.
    #   The symbol `I_Vs` is `vs.I_comp`. So the solver will output `I_Vs: -0.05`.
    #   This means the current associated with the `VoltageSource` component (flowing from its node1 to its node2) is -0.05A.
    #   This is correct: current of 0.05A actually flows from GND (node2) to n_in (node1) *through the source component's internal path*.
    #   This is equivalent to saying the source *supplies* 0.05A out of its positive n_in terminal.
    #   The result `I_Vs = -0.05` for `vs.I_comp` is thus correct under these definitions.

    # Test with a current source
    # GND --- R --- n1 --- CS --- GND (CS pumps current towards n1)
    print("\nSymbolic Solver Test: Current Source with Resistor")
    IsVal_sym = sp.Symbol('Is_val')
    R_cs_sym = sp.Symbol('R_cs')

    cs_test = CurrentSource(name='Is', node1='GND', node2='n1_cs', current_val_sym=IsVal_sym) # Pumps current from GND to n1_cs
    r_cs = Resistor(name='Rcs', node1='n1_cs', node2='GND', resistance_sym=R_cs_sym)

    components_cs = [cs_test, r_cs]
    unknowns_cs = [sp.Symbol('V_n1_cs'), r_cs.I_comp, cs_test.V_comp] # cs_test.I_comp is IsVal_sym
    knowns_cs = {IsVal_sym: 2, R_cs_sym: 5}

    solution_cs = solve_circuit(components_cs, unknowns_cs, known_substitutions=knowns_cs, ground_node='GND')
    if solution_cs:
        for sol_dict in solution_cs:
            for sym, val in sol_dict.items():
                print(f"  {sym} = {sp.pretty(val)}")
    else:
        print("  No solution found or error for CS test.")
    # Expected: V_n1_cs = 10V. I_Rcs = 2A (current from n1_cs to GND). V_Is (across current source) = -10V (V_GND - V_n1_cs)
    # KCL at n1_cs:
    #   cs_test (node1=GND, node2=n1_cs, I_comp=Is_val): current_into_n1_cs += Is_val
    #   r_cs    (node1=n1_cs, node2=GND, I_comp=I_Rcs): current_into_n1_cs -= I_Rcs
    #   Equation: Is_val - I_Rcs = 0 => I_Rcs = Is_val = 2A. Correct.
    #   For r_cs: V_comp_Rcs = V_n1_cs - V_GND = V_n1_cs.  V_comp_Rcs = I_Rcs * R_cs = 2 * 5 = 10V. So V_n1_cs = 10V. Correct.
    #   For cs_test: V_comp_CS = V_GND - V_n1_cs = 0 - 10 = -10V. Correct.
    # The `unknowns_cs` list should include `cs_test.I_comp` if it were an unknown, but it's `IsVal_sym` which is known.
    # `cs_test.V_comp` is the voltage across the current source, which is an unknown.
