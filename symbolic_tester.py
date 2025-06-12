import sympy as sp
from symbolic_components import (
    Resistor, VoltageSource, CurrentSource,
    VCVS, VCCS, CCVS, CCCS,
    Capacitor, Inductor, omega as omega_sym
)
from symbolic_solver import solve_circuit
from utils import print_solutions, format_symbolic_expression, generate_node_map_text
from spice_parser import parse_netlist


# --- Placeholder for other test functions ---
def setup_detailed_h_bridge_components():
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
def run_spice_import_and_map_test():
    print("\n--- (Skipping SPICE Import and Node Map Test in this run) ---")
# --- End of Placeholders ---


def solve_h_bridge_r3_final_symbolic():
    print("\n--- Solving User's H-Bridge for FULLY SYMBOLIC R3 (Target: ~56.18 Ohms) ---")
    print("    Using new solver interface: R3 = f(U1_p, R1_p,..., V_N2_target, I_N3toN4_target)")

    # Define top-level symbolic parameters for the formula
    U1_p = sp.Symbol('U1_p')
    R1_p, R2_p, R4_p, R5_p, R6_p = sp.symbols('R1_p R2_p R4_p R5_p R6_p')
    R3_to_solve = sp.Symbol('R3_final')
    V_N2_target = sp.Symbol('V_N2_target')
    I_N3toN4_target = sp.Symbol('I_N3toN4_target')

    # Component's internal value symbols (these will be equated to params via known_specifications)
    V_V1_actual_sym = sp.Symbol('V_V1_actual_val')
    R_R1_actual_sym = sp.Symbol('R_R1_actual_val')
    R_R2_actual_sym = sp.Symbol('R_R2_actual_val')
    R_R4_actual_sym = sp.Symbol('R_R4_actual_val')
    R_R5_actual_sym = sp.Symbol('R_R5_actual_val')
    R_R6_actual_sym = sp.Symbol('R_R6_actual_val')

    # Instantiate Circuit Components based on user's SPICE netlist structure from image "Schaltung_gesamt"
    # Nodes: '0' (GND), '1' (Vsource out), '2' (R1-R2-R4-R6 junction),
    #        '3' (R2-R3-VI junction), '4' (R4-R5-VI junction)

    V1_comp = VoltageSource('V1', '1', '0', voltage_val_sym=V_V1_actual_sym)
    R1_comp = Resistor('R1', '1', '2', resistance_sym=R_R1_actual_sym)
    R2_comp = Resistor('R2', '2', '3', resistance_sym=R_R2_actual_sym)
    R3_comp = Resistor('R3', '3', '0', resistance_sym=R3_to_solve)
    R4_comp = Resistor('R4', '2', '4', resistance_sym=R_R4_actual_sym)
    R5_comp = Resistor('R5', '4', '0', resistance_sym=R_R5_actual_sym)
    R6_comp = Resistor('R6', '2', '0', resistance_sym=R_R6_actual_sym)

    # Dummy source VI to measure/constrain current I from Node 3 to Node 4
    VI_dummy = VoltageSource('VI', '3', '4', voltage_val_sym=sp.Integer(0))

    components = [V1_comp, R1_comp, R2_comp, R3_comp, R4_comp, R5_comp, R6_comp, VI_dummy]

    known_specifications = [
        sp.Eq(V1_comp.V_source_val, U1_p),
        sp.Eq(R1_comp.R_val, R1_p),
        sp.Eq(R2_comp.R_val, R2_p),
        sp.Eq(R4_comp.R_val, R4_p),
        sp.Eq(R5_comp.R_val, R5_p),
        sp.Eq(R6_comp.R_val, R6_p),
        sp.Eq(sp.Symbol('V_2'), V_N2_target),
        sp.Eq(VI_dummy.I_comp, I_N3toN4_target)
    ]

    unknowns_to_derive = [R3_to_solve, sp.Symbol('V_3'), sp.Symbol('V_4')]
    # Adding V_3 and V_4 to see their symbolic expressions as well for verification.
    # Other symbols like node voltages V_1, V_2 and component currents will be solved internally.

    print("Attempting to solve for fully symbolic R3 formula using new solver interface...")
    solution_list_final = solve_circuit(
        components,
        unknowns_to_derive,
        known_specifications,
        ground_node='0'
    )

    print_solutions(solution_list_final, title=f"H-Bridge Final Symbolic Solution (Target: {R3_to_solve.name})")

    r3_formula_final = None
    if solution_list_final and solution_list_final[0] and R3_to_solve in solution_list_final[0]:
        r3_formula_final = solution_list_final[0][R3_to_solve]
        print(f"\n** Fully Symbolic Formula for {R3_to_solve.name}: **")
        print(format_symbolic_expression(r3_formula_final))

        numerical_subs = {
            U1_p: 1.0, R1_p: 180.0, R2_p: 100.0, R4_p: 22.0, R5_p: 39.0, R6_p: 39.0,
            V_N2_target: 0.1,
            I_N3toN4_target: -559e-6 # Current I from Node 3 to Node 4 is -559uA
        }

        print(f"\nSubstituting numerical values into R3 formula: { {s.name:v for s,v in numerical_subs.items()} }")

        # Substitute known numerical values into the symbolic formula for R3
        r3_numerical_value = r3_formula_final.subs(numerical_subs)

        print(f"** Numerical value for {R3_to_solve.name}: {r3_numerical_value.evalf(n=7, chop=True)} **")
        print("(Expected from problem description: ~56.18 Ohms based on U3, U4 values)")

        # Verification of intermediate V_3 (V_n_L_mid in prior terminology) and V_4 (V_n_R_mid)
        V3_sym = sp.Symbol('V_3')
        V4_sym = sp.Symbol('V_4')

        if V3_sym in solution_list_final[0]:
            v3_formula = solution_list_final[0][V3_sym]
            v3_numerical = v3_formula.subs(numerical_subs)
            # Expected V3 (U3 in problem image) = 0.087702V
            # This was calculated in problem as: V_N2_target - R2_p * I_R2 where I_R2 needs to be found.
            # Or, using the problem's direct I(VI) = -559e-6 A (current 3->4)
            # V4 = V3 - I(VI)*R_VI_dummy (but R_VI_dummy is 0 effectively for ideal current measurement)
            # The problem text calculated U3 and U4 based on I_R2345_gesamt and current division.
            # Our solver uses KCL/KVL. Let's see what it gets.
            # The problem states U3 = 0.087702V for R3=56.18.
            print(f"  Solved V_3 (U3 in problem): {v3_numerical.evalf(n=7, chop=True)} (Problem's U3 value for R3=56.18 was ~0.087702V)")

        if V4_sym in solution_list_final[0]:
            v4_formula = solution_list_final[0][V4_sym]
            v4_numerical = v4_formula.subs(numerical_subs)
            # The problem states U4 = 0.1V - R4_p * I_R4 where I_R4 needs to be found.
            # Or, U4 = 0.1V (V_N2_target) - I_R4 * R4_p
            # The problem states U4 = 0.09642V for R3=56.18.
            print(f"  Solved V_4 (U4 in problem): {v4_numerical.evalf(n=7, chop=True)} (Problem's U4 value for R3=56.18 was ~0.09642V)")

    else:
        print(f"Could not find a fully symbolic formula for {R3_to_solve.name}.")


if __name__ == '__main__':
    print("\n--- Activating Fully Symbolic H-Bridge R3 Test (Final Attempt) ---")
    # Comment out other tests
    # run_power_calculation_tests()
    # run_controlled_sources_tests()
    # run_ac_circuit_tests()
    # run_spice_import_and_map_test()

    solve_h_bridge_r3_final_symbolic()
    print("\nFinal H-Bridge R3 symbolic problem execution complete.")
