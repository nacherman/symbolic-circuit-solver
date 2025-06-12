import sympy as sp
# Ensure global omega is imported correctly if components use it directly at module level
from symbolic_components import (
    Resistor, VoltageSource, CurrentSource,
    VCVS, VCCS, CCVS, CCCS,
    Capacitor, Inductor, omega as omega_sym
)
from symbolic_solver import solve_circuit
from utils import print_solutions, format_symbolic_expression # Added format_symbolic_expression

# --- Placeholder for other test functions ---
def setup_detailed_h_bridge_components(): # Original setup, not used by the new symbolic function directly
    print("\n--- (Skipping setup_detailed_h_bridge_components in this run) ---")
    return [], {}

def solve_detailed_h_bridge_symbolically(components, symbols_map): # Old symbolic attempt
    print("\n--- (Skipping solve_detailed_h_bridge_symbolically in this run) ---")

def solve_detailed_h_bridge_for_numerical_R3(components, symbols_map): # Old numerical attempt
    print("\n--- (Skipping solve_detailed_h_bridge_for_numerical_R3 in this run) ---")

def run_power_calculation_tests():
    print("\n--- (Skipping Power Calculation Tests in this run) ---")

def run_controlled_sources_tests():
    print("\n--- (Skipping Controlled Sources Tests in this run) ---")

def run_ac_circuit_tests():
    print("\n--- (Skipping AC Circuit Tests in this run) ---")
# --- End of Placeholders ---


def solve_detailed_h_bridge_fully_symbolic_R3():
    print("\n--- Solving Detailed H-Bridge for FULLY SYMBOLIC R3_unknown ---")
    print("   Then substituting all numerical values from problem description.")

    # Define unique symbols for ALL parameters to keep them symbolic in the formula
    U_param_s = sp.Symbol('U_source_param')
    R1_param_s = sp.Symbol('R1_param')
    R2_param_s = sp.Symbol('R2_param')
    R3_unknown_param_s = sp.Symbol('R3_to_find') # This is our main target
    R4_param_s = sp.Symbol('R4_param')
    R5_param_s = sp.Symbol('R5_param')
    R6_param_s = sp.Symbol('R6_param')

    V_R6_target_param_s = sp.Symbol('V_R6_target_val')
    I_R4_target_param_s = sp.Symbol('I_R4_target_val')

    I_R4h_actual_sym = sp.Symbol('I_R4h_actual')

    # Node voltage symbols that the solver will use for nodes not GND
    # We will request some of these in unknowns_to_solve to see their symbolic form
    V_n_source_out_s = sp.Symbol('V_n_source_out')
    V_n_L1_s = sp.Symbol('V_n_L1')
    V_n_L_mid_s = sp.Symbol('V_n_L_mid')
    V_n_R_mid_s = sp.Symbol('V_n_R_mid')

    components = [
        VoltageSource(name='Usrc', node1='n_source_out', node2='GND', voltage_val_sym=U_param_s),
        Resistor(name='R1h', node1='n_source_out', node2='n_L1', resistance_sym=R1_param_s),
        Resistor(name='R2h', node1='n_L1', node2='n_L_mid', resistance_sym=R2_param_s),
        Resistor(name='R3h', node1='n_L1', node2='n_L_mid', resistance_sym=R3_unknown_param_s),
        Resistor(name='R4h', node1='n_L_mid', node2='n_R_mid', resistance_sym=R4_param_s, current_sym=I_R4h_actual_sym),
        Resistor(name='R5h', node1='n_source_out', node2='n_R_mid', resistance_sym=R5_param_s),
        Resistor(name='R6h', node1='n_R_mid', node2='GND', resistance_sym=R6_param_s)
    ]

    constraint_V_target = V_n_R_mid_s - V_R6_target_param_s
    constraint_I_target = I_R4h_actual_sym - I_R4_target_param_s
    additional_equations = [constraint_V_target, constraint_I_target]
    known_substitutions_symbolic = {}

    unknowns_to_solve = [
        R3_unknown_param_s,
        V_n_source_out_s, V_n_L1_s, V_n_L_mid_s, V_n_R_mid_s, # Key node voltages
        I_R4h_actual_sym, # Key current
        # Request currents through other main path resistors to see their expressions
        components[1].I_comp, # I_R1h
        components[2].I_comp, # I_R2h
        # components[3].I_comp, # I_R3h (current in R3_unknown_param_s) - this is I_R3h_unknown
        components[5].I_comp, # I_R5h
        components[6].I_comp, # I_R6h
        components[0].I_comp, # I_Usrc (total current from source U_param_s)
    ]

    print("Attempting to solve for fully symbolic R3 formula...")
    solution_list_sym = solve_circuit(
        components,
        unknowns_to_solve,
        known_substitutions=known_substitutions_symbolic,
        additional_equations=additional_equations,
        ground_node='GND'
    )

    print_solutions(solution_list_sym, title=f"Fully Symbolic Solution for H-Bridge (Target: {R3_unknown_param_s.name})")

    r3_formula = None
    if solution_list_sym and solution_list_sym[0] and R3_unknown_param_s in solution_list_sym[0]:
        r3_formula = solution_list_sym[0][R3_unknown_param_s]
        # The formula is likely already simplified by the solver's fully_substitute.
        # If not, uncomment: r3_formula = sp.simplify(r3_formula)
        print(f"\n** Fully Symbolic Formula for {R3_unknown_param_s.name}: **")
        print(format_symbolic_expression(r3_formula))

        numerical_subs_dict = {
            U_param_s: 1.0, R1_param_s: 180.0, R2_param_s: 100.0, R4_param_s: 22.0,
            R5_param_s: 39.0, R6_param_s: 39.0, V_R6_target_param_s: 0.1,
            I_R4_target_param_s: 559e-6
        }

        print(f"\nSubstituting numerical values into R3 formula: { {s.name:v for s,v in numerical_subs_dict.items()} }")
        r3_numerical_value = r3_formula.subs(numerical_subs_dict)

        print(f"** Numerical value for {R3_unknown_param_s.name}: {r3_numerical_value.evalf(n=7, chop=True)} **")
        print("(Expected from problem description's manual calculation: ~16.0 Ohms)")

        if V_n_L_mid_s in solution_list_sym[0]:
            v_n_l_mid_formula = solution_list_sym[0][V_n_L_mid_s]
            v_n_l_mid_numerical = v_n_l_mid_formula.subs(numerical_subs_dict)
            print(f"  Solved V_n_L_mid (numerical, from its formula): {v_n_l_mid_numerical.evalf(n=7, chop=True)}")
            # V_n_L_mid = V_n_R_mid + I_LtoR * R4. V_n_R_mid is V_R6_target_param_s. I_LtoR is I_R4_target_param_s.
            v_n_l_mid_expected_manual = numerical_subs_dict[V_R6_target_param_s] + \
                                      numerical_subs_dict[I_R4_target_param_s] * numerical_subs_dict[R4_param_s]
            print(f"  Expected V_n_L_mid (manual calc): {v_n_l_mid_expected_manual:.7f}")
    else:
        print(f"Could not find a fully symbolic formula for {R3_unknown_param_s.name}.")

if __name__ == '__main__':
    print("\n--- Activating Fully Symbolic H-Bridge R3 Test ---")
    solve_detailed_h_bridge_fully_symbolic_R3()
    print("\nFully symbolic H-Bridge R3 problem execution complete.")
