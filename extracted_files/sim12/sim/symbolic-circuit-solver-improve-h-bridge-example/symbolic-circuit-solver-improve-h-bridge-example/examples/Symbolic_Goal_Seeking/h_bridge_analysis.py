import sys
import os
import sympy

# Add project root to Python path
# __file__ is examples/Symbolic_Goal_Seeking/h_bridge_analysis.py
script_dir = os.path.dirname(os.path.abspath(__file__))
# project_root is symbolic_circuit_solver-master
project_root = os.path.dirname(os.path.dirname(script_dir))
# path_to_add is the parent of symbolic_circuit_solver-master (e.g., /app)
path_to_add = os.path.dirname(project_root)
if path_to_add not in sys.path:
    sys.path.insert(0, path_to_add)

from symbolic_circuit_solver_master.scs_symbolic_goal_seeker import generate_circuit_equations, solve_from_equations

def main():
    # 1. Define SPICE string for H-bridge
    h_bridge_netlist_content = """
* H-Bridge Analysis Example for Symbolic Goal Seeking

* Parameters for component values
.PARAM Vin_s = Vin_s
.PARAM Rul_s = Rul_s
.PARAM Rll_s = Rll_s
.PARAM Rur_s = Rur_s
.PARAM Rlr_s = Rlr_s
.PARAM Rload_s = Rload_s

* Circuit Elements
Vin N_supply 0 Vin_s
Rul N_supply Na Rul_s
Rll Na 0 Rll_s
Rur N_supply Nb Rur_s
Rlr Nb 0 Rlr_s
Rload Na Nb Rload_s

.end
"""
    temp_netlist_filename = "_temp_h_bridge_sgs.sp"
    temp_netlist_path = os.path.join(script_dir, temp_netlist_filename)

    try:
        # 2. Write to _temp_h_bridge.sp
        with open(temp_netlist_path, 'w') as f:
            f.write(h_bridge_netlist_content)

        # 3. Generate circuit equations and variable maps
        # The third returned item (instance) is not needed for this specific example flow.
        print(f"Generating MNA equations for H-Bridge from: {temp_netlist_path}")
        eqs, var_maps, _ = generate_circuit_equations(netlist_path=temp_netlist_path)

        if not eqs or not var_maps:
            print("Error: Failed to generate circuit equations or variable maps.")
            return

        # 4. Define scenario symbols (these represent the values we'll assign to circuit parameters)
        sRul, sRll, sRur, sRlr, sRload, sVload_target = sympy.symbols(
            'Rul_val Rll_val Rur_val Rlr_val Rload_val Vload_target'
        )
        # Vin_s is what we want to solve for, so it's not a scenario symbol here.
        # I_Vin (current through Vin) is also an unknown we want to solve for.

        # 5. Knowns dictionary: map circuit's symbolic parameters to our scenario symbols
        # These are the parameters whose values will be substituted by the scenario symbols before solving.
        knowns_str_keys = {
            'Rul_s': sRul,
            'Rll_s': sRll,
            'Rur_s': sRur,
            'Rlr_s': sRlr,
            'Rload_s': sRload
            # 'Vin_s' is an unknown we are solving for.
        }
        print(f"\nParameters will be substituted with these scenario symbols: {knowns_str_keys}")

        # 6. Form the load voltage constraint equation
        # V(Na) - V(Nb) = Vload_target
        V_Na_sym = var_maps['voltages']['Na'] # Get the Sympy symbol for V_Na from var_maps
        V_Nb_sym = var_maps['voltages']['Nb'] # Get the Sympy symbol for V_Nb from var_maps

        constraint_eq = sympy.Eq(V_Na_sym - V_Nb_sym, sVload_target)
        print(f"Constraint equation: {constraint_eq}")

        # 7. Add constraint to the system of MNA equations
        all_eqs_with_constraint = eqs + [constraint_eq]
        print(f"Total equations including constraint: {len(all_eqs_with_constraint)}")

        # 8. Define unknowns to solve for (as strings)
        # We want to find Vin_s (the circuit parameter) and I_Vin (current through element Vin)
        primary_unknowns_str = ['Vin_s', 'I_Vin']

        # To get solutions for primary_unknowns_str in terms of scenario symbols (e.g. Rul_val),
        # all other circuit variables (other voltages and currents) must also be part of the
        # list of symbols to solve for, so sympy can eliminate them.
        all_unknowns_to_solve_for_str = list(primary_unknowns_str)

        # Add all node voltage symbols (prefix with V_ for convention with _get_symbol_from_name)
        for node_key in var_maps['voltages'].keys():
            # Symbol itself is V_node_key, e.g. V_Na for node 'Na'
            # _get_symbol_from_name will find var_maps['voltages'][node_key] using "V_Na"
            all_unknowns_to_solve_for_str.append(var_maps['voltages'][node_key].name)

        # Add all other element current symbols (prefix with I_ for convention)
        for elem_key in var_maps['currents'].keys():
            # Symbol itself is I_elem_key, e.g. I_Rul for element 'Rul'
            if elem_key != 'Vin': # I_Vin is already a primary unknown
                 all_unknowns_to_solve_for_str.append(var_maps['currents'][elem_key].name)

        # Deduplicate
        all_unknowns_to_solve_for_str = sorted(list(set(all_unknowns_to_solve_for_str)))

        print(f"Primary unknowns: {primary_unknowns_str}")
        print(f"Full list of unknowns for sympy.solve: {all_unknowns_to_solve_for_str}")

        # 9. Solve the system
        # The knowns_str_keys here will substitute Rul_s with sRul (Rul_val), etc.
        # The system will then be solved for all_unknowns_to_solve_for_str.
        # We are interested in the expressions for Vin_s and I_Vin from the solution.
        symbolic_solutions = solve_from_equations(
            all_eqs_with_constraint,
            var_maps,
            knowns_str_keys,
            all_unknowns_to_solve_for_str
        )

        # 10. Print problem statement and symbolic solutions
        print("\n--- Symbolic Solutions ---")
        print("Problem: Find Vin_s and I_Vin such that V(Na) - V(Nb) = Vload_target,")
        print("         given Rul, Rll, Rur, Rlr, Rload.")

        if symbolic_solutions:
            # Assuming one unique solution set for this problem
            sol_dict = symbolic_solutions[0]

            vin_s_solution_expr = sol_dict.get(sympy.symbols('Vin_s'))
            i_vin_solution_expr = sol_dict.get(sympy.symbols('I_Vin'))

            if vin_s_solution_expr is not None:
                print(f"\nSymbolic solution for Vin_s:\nVin_s = {vin_s_solution_expr}")
            else:
                print("\nVin_s not found in solutions.")

            if i_vin_solution_expr is not None:
                print(f"\nSymbolic solution for I_Vin (current from N_supply through Vin to 0):\nI_Vin = {i_vin_solution_expr}")
            else:
                print("\nI_Vin not found in solutions.")

            # 11. Numerical Evaluation
            print("\n--- Numerical Evaluation ---")
            numerical_subs = {
                sRul: 1.0,          # Upper-left resistor
                sRll: 1e6,          # Lower-left resistor (simulating open switch)
                sRur: 1e6,          # Upper-right resistor (simulating open switch)
                sRlr: 1.0,          # Lower-right resistor
                sRload: 50.0,       # Load resistor
                sVload_target: 5.0  # Target voltage across the load
            }
            print(f"Substituting numerical values: {numerical_subs}")

            if vin_s_solution_expr is not None:
                try:
                    vin_s_numeric = vin_s_solution_expr.subs(numerical_subs).evalf()
                    print(f"Numerical Vin_s = {vin_s_numeric:.4f} V")
                except Exception as e:
                    print(f"Could not evaluate Vin_s numerically: {e}")

            if i_vin_solution_expr is not None:
                try:
                    i_vin_numeric = i_vin_solution_expr.subs(numerical_subs).evalf()
                    print(f"Numerical I_Vin = {i_vin_numeric * 1000:.4f} mA")
                except Exception as e:
                    print(f"Could not evaluate I_Vin numerically: {e}")
        else:
            print("No symbolic solutions found.")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 12. Cleanup temp file
        if os.path.exists(temp_netlist_path):
            os.remove(temp_netlist_path)
            print(f"\nCleaned up temporary file: {temp_netlist_path}")

if __name__ == "__main__":
    main()
