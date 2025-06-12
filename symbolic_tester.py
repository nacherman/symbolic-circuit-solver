import sympy as sp
from symbolic_components import Resistor, VoltageSource, CurrentSource, VCVS, VCCS, CCVS, CCCS
from symbolic_solver import solve_circuit
from utils import print_solutions

# --- Existing H-Bridge functions (can be kept or removed if not needed for this focus) ---
def setup_detailed_h_bridge_components():
    # print("\n--- Setting up Detailed H-Bridge Circuit for Symbolic Calculation ---")
    U_sym = sp.Symbol('U_source_val_sym')
    R1_sym = sp.Symbol('R1_h_val')
    R2_sym = sp.Symbol('R2_h_val')
    R3_sym = sp.Symbol('R3_h_val')
    R4_sym = sp.Symbol('R4_h_val')
    R5_sym = sp.Symbol('R5_h_val')
    R6_sym = sp.Symbol('R6_h_val')
    I_R4_comp_sym = sp.Symbol('I_R4_actual')
    detailed_components = [
        VoltageSource(name='U_src', node1='n_source_out', node2='GND', voltage_val_sym=U_sym),
        Resistor(name='R1h', node1='n_source_out', node2='n_L1', resistance_sym=R1_sym),
        Resistor(name='R2h', node1='n_L1', node2='n_L_mid', resistance_sym=R2_sym),
        Resistor(name='R3h', node1='n_L1', node2='n_L_mid', resistance_sym=R3_sym),
        Resistor(name='R4h', node1='n_L_mid', node2='n_R_mid', resistance_sym=R4_sym, current_sym=I_R4_comp_sym),
        Resistor(name='R5h', node1='n_source_out', node2='n_R_mid', resistance_sym=R5_sym),
        Resistor(name='R6h', node1='n_R_mid', node2='GND', resistance_sym=R6_sym)
    ]
    problem_symbols = {
        'U_source_val_sym': U_sym,
        'R1_val_sym': R1_sym, 'R2_val_sym': R2_sym, 'R3_val_sym': R3_sym,
        'R4_val_sym': R4_sym, 'R5_val_sym': R5_sym, 'R6_val_sym': R6_sym,
        'I_R4_comp_sym': I_R4_comp_sym,
        'V_R6_target_val_sym': sp.Symbol('V_R6_target'),
        'I_R4_target_val_sym': sp.Symbol('I_R4_target'),
        'V_n_source_out_actual': sp.Symbol('V_n_source_out'),
        'V_n_L1_actual': sp.Symbol('V_n_L1'),
        'V_n_L_mid_actual': sp.Symbol('V_n_L_mid'),
        'V_n_R_mid_actual': sp.Symbol('V_n_R_mid')
    }
    return detailed_components, problem_symbols

def solve_detailed_h_bridge_symbolically(components, symbols_map):
    print("\n--- (Skipping solve_detailed_h_bridge_symbolically in this run) ---")

def solve_detailed_h_bridge_for_numerical_R3(components, symbols_map):
    print("\n--- (Skipping solve_detailed_h_bridge_for_numerical_R3 in this run) ---")

def run_power_calculation_tests():
    print("\n--- (Skipping Power Calculation Tests in this run) ---")
# --- End of Existing functions ---


def run_controlled_sources_tests():
    print("\n--- Running Controlled Sources Tests ---")

    # --- Test Scenario 1: VCVS (Voltage Amplifier) ---
    print("\nScenario 1: VCVS Test (Voltage Amplifier)")
    Vs_in_e, Rin_e, Rbias_e, Rload_e, Av_e = sp.symbols('Vs_in_e Rin_e Rbias_e Rload_e Av_e')

    vs_e = VoltageSource('VsE', 'n_e_in', 'GND', Vs_in_e)
    r_in_e = Resistor('RinE', 'n_e_in', 'n_e_ctrl', Rin_e)
    r_bias_e = Resistor('RbiasE', 'n_e_ctrl', 'GND', Rbias_e)
    vcvs_e = VCVS('E1', 'n_e_out', 'GND', control_node_p='n_e_ctrl', control_node_n='GND', gain_sym=Av_e)
    r_load_e = Resistor('RloadE', 'n_e_out', 'GND', Rload_e)

    components_e = [vs_e, r_in_e, r_bias_e, vcvs_e, r_load_e]
    knowns_e = { Vs_in_e: 1.0, Rin_e: 100.0, Rbias_e: 900.0, Rload_e: 50.0, Av_e: 10.0 }

    unknowns_e = [sp.Symbol('V_n_e_out'), sp.Symbol('V_n_e_ctrl'), vcvs_e.P_comp, r_load_e.P_comp, vcvs_e.I_comp]
    solution_e = solve_circuit(components_e, unknowns_e, knowns_e, ground_node='GND')
    print_solutions(solution_e, "VCVS Test Solution")
    if solution_e and solution_e[0]:
        v_n_e_out_solved = solution_e[0].get(sp.Symbol('V_n_e_out'))
        if v_n_e_out_solved is not None:
            expected_v_out = knowns_e[Av_e] * (knowns_e[Vs_in_e]*knowns_e[Rbias_e]/(knowns_e[Rin_e]+knowns_e[Rbias_e]))
            print(f"  Solved V(n_e_out): {float(v_n_e_out_solved):.2f} V, Expected V(n_e_out): {expected_v_out:.2f} V")


    # --- Test Scenario 2: VCCS (Transconductance Amplifier) ---
    print("\nScenario 2: VCCS Test (Transconductance Amplifier)")
    Vs_in_g, Rin_g, Rbias_g, Rload_g, Gm_g = sp.symbols('Vs_in_g Rin_g Rbias_g Rload_g Gm_g')

    vs_g = VoltageSource('VsG', 'n_g_in', 'GND', Vs_in_g)
    r_in_g = Resistor('RinG', 'n_g_in', 'n_g_ctrl', Rin_g)
    r_bias_g = Resistor('RbiasG', 'n_g_ctrl', 'GND', Rbias_g)
    vccs_g = VCCS('G1', 'n_g_out', 'GND', control_node_p='n_g_ctrl', control_node_n='GND', transconductance_sym=Gm_g)
    r_load_g = Resistor('RloadG', 'n_g_out', 'GND', Rload_g)

    components_g = [vs_g, r_in_g, r_bias_g, vccs_g, r_load_g]
    knowns_g = { Vs_in_g: 1.0, Rin_g: 100.0, Rbias_g: 900.0, Rload_g: 50.0, Gm_g: 0.1 }

    unknowns_g = [sp.Symbol('V_n_g_out'), sp.Symbol('V_n_g_ctrl'), vccs_g.I_comp, vccs_g.P_comp, r_load_g.P_comp]
    solution_g = solve_circuit(components_g, unknowns_g, knowns_g, ground_node='GND')
    print_solutions(solution_g, "VCCS Test Solution")
    if solution_g and solution_g[0]:
         v_n_g_out_solved = solution_g[0].get(sp.Symbol('V_n_g_out'))
         if v_n_g_out_solved is not None:
            v_ctrl_g = knowns_g[Vs_in_g]*knowns_g[Rbias_g]/(knowns_g[Rin_g]+knowns_g[Rbias_g])
            # i_out_g_vccs = knowns_g[Gm_g] * v_ctrl_g
            # KCL at n_g_out: -I_G1 - I_RloadG = 0 => I_RloadG = -I_G1
            # V_n_g_out = I_RloadG * Rload_g = (-I_G1) * Rload_g
            # I_G1 (VCCS output I_comp) = Gm_g * v_ctrl_g = 0.1 * 0.9 = 0.09A
            expected_v_out_g = -(knowns_g[Gm_g] * v_ctrl_g) * knowns_g[Rload_g] # Corrected expected value
            print(f"  Solved V(n_g_out): {float(v_n_g_out_solved):.2f} V, Expected V(n_g_out): {expected_v_out_g:.2f} V")


    # --- Test Scenario 3: CCVS (Transresistance Amplifier) ---
    print("\nScenario 3: CCVS Test (Transresistance Amplifier)")
    Is_in_h_val, Rsense_h_val, Rload_h_val, Rm_h_val = sp.symbols('Is_in_h_val Rsense_h_val Rload_h_val Rm_h_val')

    is_h = CurrentSource('IsH', 'n_h_sense', 'GND', Is_in_h_val)
    r_sense_h = Resistor('RsenseH', 'n_h_sense', 'GND', Rsense_h_val)
    ccvs_h = CCVS('H1', 'n_h_out', 'GND', control_current_comp_name='RsenseH', transresistance_sym=Rm_h_val)
    r_load_h = Resistor('RloadH', 'n_h_out', 'GND', Rload_h_val)

    components_h = [is_h, r_sense_h, ccvs_h, r_load_h]
    knowns_h = { Is_in_h_val: 0.1, Rsense_h_val: 10.0, Rload_h_val: 50.0, Rm_h_val: 100.0 }

    unknowns_h = [sp.Symbol('V_n_h_out'), r_sense_h.I_comp, ccvs_h.P_comp, r_load_h.P_comp, ccvs_h.I_comp]
    solution_h = solve_circuit(components_h, unknowns_h, knowns_h, ground_node='GND')
    print_solutions(solution_h, "CCVS Test Solution")
    if solution_h and solution_h[0]:
        v_n_h_out_solved = solution_h[0].get(sp.Symbol('V_n_h_out'))
        i_rsense_h_solved = solution_h[0].get(r_sense_h.I_comp)
        if v_n_h_out_solved is not None and i_rsense_h_solved is not None:
            # KCL at n_h_sense: -I_IsH - I_RsenseH = 0 (assuming IsH node1 is n_h_sense, RsenseH node1 is n_h_sense)
            # I_IsH is Is_in_h_val (current source value, defined positive from node1 to node2)
            # So, I_RsenseH = -Is_in_h_val
            expected_i_rsense_h = -knowns_h[Is_in_h_val]
            expected_v_out_h = knowns_h[Rm_h_val] * float(i_rsense_h_solved)
            print(f"  Solved V(n_h_out): {float(v_n_h_out_solved):.2f} V, Expected (using solved I_RsenseH): {expected_v_out_h:.2f} V")
            print(f"  Solved I(RsenseH): {float(i_rsense_h_solved):.3f} A, Expected I(RsenseH): {expected_i_rsense_h:.3f} A")


    # --- Test Scenario 4: CCCS (Current Amplifier) ---
    print("\nScenario 4: CCCS Test (Current Amplifier)")
    Is_in_f_val, Rsense_f_val, Rload_f_val, Ai_f_val = sp.symbols('Is_in_f_val Rsense_f_val Rload_f_val Ai_f_val')

    is_f = CurrentSource('IsF', 'n_f_sense', 'GND', Is_in_f_val)
    r_sense_f = Resistor('RsenseF', 'n_f_sense', 'GND', Rsense_f_val)
    cccs_f = CCCS('F1', 'n_f_out', 'GND', control_current_comp_name='RsenseF', gain_sym=Ai_f_val)
    r_load_f = Resistor('RloadF', 'n_f_out', 'GND', Rload_f_val)

    components_f = [is_f, r_sense_f, cccs_f, r_load_f]
    knowns_f = { Is_in_f_val: 0.1, Rsense_f_val: 10.0, Rload_f_val: 50.0, Ai_f_val: 10.0 }

    unknowns_f = [r_load_f.I_comp, sp.Symbol('V_n_f_out'), r_sense_f.I_comp, cccs_f.I_comp, cccs_f.P_comp, r_load_f.P_comp]
    solution_f = solve_circuit(components_f, unknowns_f, knowns_f, ground_node='GND')
    print_solutions(solution_f, "CCCS Test Solution")
    if solution_f and solution_f[0]:
        i_rload_f_solved = solution_f[0].get(r_load_f.I_comp)
        i_rsense_f_solved = solution_f[0].get(r_sense_f.I_comp)
        if i_rload_f_solved is not None and i_rsense_f_solved is not None:
            expected_i_rsense_f = -knowns_f[Is_in_f_val]
            # I_F1 (output of CCCS) = Ai_f_val * I_RsenseF_control (which is i_rsense_f_solved)
            # KCL at n_f_out: -I_F1 - I_RloadF = 0 => I_RloadF = -I_F1
            expected_i_rload_f = -(knowns_f[Ai_f_val] * float(i_rsense_f_solved))
            print(f"  Solved I(RloadF): {float(i_rload_f_solved):.2f} A, Expected (using solved I_RsenseF): {expected_i_rload_f:.2f} A")
            print(f"  Solved I(RsenseF): {float(i_rsense_f_solved):.3f} A, Expected I(RsenseF): {expected_i_rsense_f:.3f} A")


if __name__ == '__main__':
    print("\n--- Activating Controlled Sources Tests ---")
    # Commenting out other tests to focus output
    # run_power_calculation_tests()
    # detailed_components_list, detailed_symbols_dict = setup_detailed_h_bridge_components()
    # solve_detailed_h_bridge_symbolically(detailed_components_list, detailed_symbols_dict)
    # solve_detailed_h_bridge_for_numerical_R3(detailed_components_list, detailed_symbols_dict)

    run_controlled_sources_tests()
    print("\nControlled sources tests complete.")
