import sys
import os
import sympy

# Add project root to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
# examples_dir is symbolic_circuit_solver_master/examples/Symbolic_Goal_Seeking/.. -> examples/
examples_dir = os.path.dirname(script_dir)
# scs_master_dir is symbolic_circuit_solver_master/examples/.. -> symbolic_circuit_solver_master/
scs_master_dir = os.path.dirname(examples_dir)
# path_to_add is parent of symbolic_circuit_solver_master (e.g., /app)
path_to_add = os.path.dirname(scs_master_dir)
if path_to_add not in sys.path:
    sys.path.insert(0, path_to_add)

from symbolic_circuit_solver_master.scs_symbolic_goal_seeker import generate_circuit_equations, solve_from_equations

def main():
    """
    Demonstrates symbolic goal seeking for an H-bridge circuit.
    This script solves for the required input voltage (Vin_s) and input current (I_Vin)
    to achieve a target load voltage (sVload_target) across Rload,
    given symbolic values for the H-bridge resistors.
    """
    print("--- H-Bridge Symbolic Goal Seeking Analysis ---")

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
    # Using a more unique name for the temporary file
    temp_netlist_filename = "_temp_hbridge_sgs_example.sp"
    temp_netlist_path = os.path.join(script_dir, temp_netlist_filename)
    temp_files_to_clean = [temp_netlist_path]

    try:
        # 2. Write to temporary SPICE file
        with open(temp_netlist_path, 'w') as f:
            f.write(h_bridge_netlist_content)
        print(f"\nGenerated temporary netlist: {temp_netlist_path}")

        # 3. Generate circuit equations and variable maps
        print(f"Generating MNA equations for H-Bridge...")
        eqs, var_maps, circuit_instance = generate_circuit_equations(netlist_path=temp_netlist_path)

        if not eqs or not var_maps:
            print("Error: Failed to generate circuit equations or variable maps.")
            return

        # 4. Define scenario symbols
        # These are the symbols our final answer will be in terms of.
        sRul, sRll, sRur, sRlr, sRload, sVload_target = sympy.symbols(
            'Rul_val Rll_val Rur_val Rlr_val Rload_val Vload_target'
        )

        # 5. Knowns dictionary: map circuit's .PARAM symbols to our scenario symbols
        knowns_str_keys = {
            'Rul_s': sRul,
            'Rll_s': sRll,
            'Rur_s': sRur,
            'Rlr_s': sRlr,
            'Rload_s': sRload
            # Vin_s is an unknown we are solving for.
        }
        print(f"\nCircuit parameters will be substituted with scenario symbols: {knowns_str_keys}")

        # 6. Form the load voltage constraint equation: V(Na) - V(Nb) = sVload_target
        V_Na_sym = var_maps['voltages']['Na']
        V_Nb_sym = var_maps['voltages']['Nb']

        constraint_eq = sympy.Eq(V_Na_sym - V_Nb_sym, sVload_target)
        print(f"Constraint equation to be added: {constraint_eq}")

        # 7. Add constraint to the system of MNA equations
        all_eqs_with_constraint = eqs + [constraint_eq]
        print(f"Total equations including constraint: {len(all_eqs_with_constraint)}")

        # 8. Define unknowns to solve for.
        # Primary unknowns are 'Vin_s' and 'I_Vin' (current of the Vin element).
        primary_unknowns_str = ['Vin_s', 'I_Vin']

        # To get solutions for primary_unknowns_str purely in terms of scenario symbols,
        # all other circuit variables (node voltages, other element currents)
        # must also be part of the list of symbols to solve for, so Sympy can eliminate them.
        all_unknowns_to_solve_for_str = list(primary_unknowns_str)
        for node_key in var_maps['voltages'].keys(): # e.g. 'N_supply', 'Na', 'Nb'
            all_unknowns_to_solve_for_str.append(var_maps['voltages'][node_key].name) # e.g. 'V_N_supply'

        for elem_key in var_maps['currents'].keys(): # e.g. 'Rul', 'Rll', etc.
            if var_maps['currents'][elem_key].name not in primary_unknowns_str: # Avoid duplicating I_Vin
                 all_unknowns_to_solve_for_str.append(var_maps['currents'][elem_key].name) # e.g. 'I_Rul'

        all_unknowns_to_solve_for_str = sorted(list(set(all_unknowns_to_solve_for_str)))

        print(f"\nPrimary unknowns targeted: {primary_unknowns_str}")
        print(f"Full list of unknowns for sympy.solve: {all_unknowns_to_solve_for_str}")

        # 9. Solve the system
        symbolic_solutions = solve_from_equations(
            all_eqs_with_constraint,
            var_maps,
            knowns_str_keys,
            all_unknowns_to_solve_for_str
        )

        # 10. Print problem statement and symbolic solutions
        print("\n--- Symbolic Solutions ---")
        print("Goal: Find Vin_s and I_Vin such that V(Na) - V(Nb) = Vload_target,")
        print("      given symbolic values for Rul, Rll, Rur, Rlr, Rload.")

        if symbolic_solutions:
            sol_dict = symbolic_solutions[0]

            # We need to fetch the original circuit parameter symbols, not the scenario symbols
            vin_s_circuit_sym = sympy.symbols('Vin_s')
            i_vin_element_sym = var_maps['currents']['Vin'] # This is I_Vin

            vin_s_solution_expr = sol_dict.get(vin_s_circuit_sym)
            i_vin_solution_expr = sol_dict.get(i_vin_element_sym)

            if vin_s_solution_expr is not None:
                print(f"\nSymbolic solution for Vin_s (circuit parameter):\nVin_s = {sympy.simplify(vin_s_solution_expr)}")
            else:
                print("\nVin_s (circuit parameter) not found in solutions.")

            if i_vin_solution_expr is not None:
                print(f"\nSymbolic solution for I_Vin (current of element Vin):\nI_Vin = {sympy.simplify(i_vin_solution_expr)}")
            else:
                print("\nI_Vin (current of element Vin) not found in solutions.")

            # 11. Numerical Evaluation
            print("\n--- Numerical Evaluation ---")
            # Scenario: Rul and Rlr are "ON" (low resistance), Rll and Rur are "OFF" (high resistance)
            numerical_subs = {
                sRul: 1.0,      # Upper-left resistor value
                sRll: 1e6,      # Lower-left resistor value (simulating open switch)
                sRur: 1e6,      # Upper-right resistor value (simulating open switch)
                sRlr: 1.0,      # Lower-right resistor value
                sRload: 50.0,   # Load resistor value
                sVload_target: 5.0  # Target voltage across the load
            }
            print(f"Substituting numerical values for scenario symbols: {numerical_subs}")

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
        print(f"An error occurred in the H-bridge analysis script: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 12. Cleanup temp file
        for f_path in temp_files_to_clean:
            if os.path.exists(f_path):
                os.remove(f_path)
                print(f"\nCleaned up temporary file: {f_path}")

if __name__ == "__main__":
    main()
