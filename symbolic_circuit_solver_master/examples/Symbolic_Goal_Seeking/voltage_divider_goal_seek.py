"""
Example script demonstrating the use of the symbolic goal seeker to solve for
unknown circuit parameters in a voltage divider circuit.
"""
import os
import sys
import sympy

# Adjust sys.path to allow importing from the parent package
# Adjust sys.path to allow importing from the parent package
# This assumes the script is in examples/Symbolic_Goal_Seeking/
# and the package root is symbolic_circuit_solver_master's parent.
script_dir = os.path.dirname(os.path.abspath(__file__))
# project_root is symbolic_circuit_solver_master/examples/
project_root_relative_to_script = os.path.dirname(script_dir)
# symbolic_circuit_solver_master_dir is symbolic_circuit_solver_master/
symbolic_circuit_solver_master_dir = os.path.dirname(project_root_relative_to_script)
# path_to_add is the parent of symbolic_circuit_solver_master/ (e.g., /app)
path_to_add = os.path.dirname(symbolic_circuit_solver_master_dir)

if path_to_add not in sys.path:
    sys.path.insert(0, path_to_add)

from symbolic_circuit_solver_master.scs_symbolic_goal_seeker import solve_for_symbolic_unknown, generate_circuit_equations, solve_from_equations

def main():
    """
    Runs several test cases for symbolic goal seeking and equation solving
    using a voltage divider circuit.
    """
    print("--- Running Voltage Divider Goal Seeking Examples ---")

    temp_files_to_clean = []

    # --- Test Case 1: Solve for Vin_unknown ---
    try:
        print("\n--- Test Case 1: Solve for Vin_unknown ---")
        netlist_vdiv1_content = """
* Voltage Divider - Goal Seek for Vin_unknown
VS Vin 0 Vin_unknown
R1 Vin N_out R1_val
R2 N_out 0 R2_val
.PARAM Vin_unknown = Vin_unknown ; The unknown to solve for
.PARAM R1_val = R1_val           ; Symbolic parameter
.PARAM R2_val = R2_val           ; Symbolic parameter
.PARAM V_target = V_target       ; Symbolic parameter for the target output voltage
.end
"""
        netlist_vdiv1_path = "_temp_vdiv_gs_test1.sp"
        temp_files_to_clean.append(netlist_vdiv1_path)

        with open(netlist_vdiv1_path, 'w') as f:
            f.write(netlist_vdiv1_content)

        print(f"Solving for 'Vin_unknown' such that V(N_out,0) = V_target")
        solutions_vin = solve_for_symbolic_unknown(
            netlist_path=netlist_vdiv1_path,
            unknown_param_name_str='Vin_unknown',
            target_quantity_str='V(N_out,0)',
            target_value_expr_str='V_target'
        )
        print(f"Solutions for Vin_unknown: {solutions_vin}")

        R1s, R2s, VTs = sympy.symbols('R1_val R2_val V_target')
        expected_vin_expr = VTs * (R1s + R2s) / R2s

        if solutions_vin and len(solutions_vin) == 1:
            if sympy.simplify(solutions_vin[0] - expected_vin_expr) == 0:
                print(f"Test Case 1 PASSED. Expected: {expected_vin_expr}, Got: {solutions_vin[0]}")
            else:
                print(f"Test Case 1 FAILED. Expected: {expected_vin_expr}, Got: {solutions_vin[0]}")
                print(f"Simplified difference: {sympy.simplify(solutions_vin[0] - expected_vin_expr)}")
        else:
            print(f"Test Case 1 FAILED. Expected one solution: {expected_vin_expr}, Got: {solutions_vin}")
    except Exception as e:
        print(f"Error in Test Case 1: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()

    # --- Test Case 2: Solve for R1_unknown ---
    try:
        print("\n--- Test Case 2: Solve for R1_unknown ---")
        netlist_vdiv2_content = """
* Voltage Divider - Goal Seek for R1_unknown
VS Vin 0 Vin_val
R1 Vin N_out R1_unknown
R2 N_out 0 R2_val
.PARAM Vin_val = Vin_val         ; Symbolic parameter for input voltage
.PARAM R1_unknown = R1_unknown   ; The unknown to solve for
.PARAM R2_val = R2_val           ; Symbolic parameter
.PARAM V_target = V_target       ; Symbolic parameter for the target output voltage
.end
"""
        netlist_vdiv2_path = "_temp_vdiv_gs_test2.sp"
        temp_files_to_clean.append(netlist_vdiv2_path)

        with open(netlist_vdiv2_path, 'w') as f:
            f.write(netlist_vdiv2_content)

        print(f"Solving for 'R1_unknown' such that V(N_out) = V_target")
        solutions_r1 = solve_for_symbolic_unknown(
            netlist_path=netlist_vdiv2_path,
            unknown_param_name_str='R1_unknown',
            target_quantity_str='V(N_out)',
            target_value_expr_str='V_target'
        )
        print(f"Solutions for R1_unknown: {solutions_r1}")

        Vins, R2s, VTs = sympy.symbols('Vin_val R2_val V_target')
        expected_r1_expr = R2s * (Vins / VTs - 1)

        if solutions_r1 and len(solutions_r1) == 1:
            if sympy.simplify(solutions_r1[0] - expected_r1_expr) == 0:
                print(f"Test Case 2 PASSED. Expected: {expected_r1_expr}, Got: {solutions_r1[0]}")
            else:
                print(f"Test Case 2 FAILED. Expected: {expected_r1_expr}, Got: {solutions_r1[0]}")
                print(f"Simplified difference: {sympy.simplify(solutions_r1[0] - expected_r1_expr)}")
        else:
            print(f"Test Case 2 FAILED. Expected one solution: {expected_r1_expr}, Got: {solutions_r1}")
    except Exception as e:
        print(f"Error in Test Case 2: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()

    # --- Test Case 3: Solve full MNA system for a voltage divider ---
    try:
        print("\n--- Test Case 3: Solve full MNA system for a voltage divider using solve_from_equations ---")
        netlist_vdiv3_content = """
* Voltage Divider - Full MNA system solve
VS Vin_node 0 Vin_known_sym
R1 Vin_node N_out R1_known_sym
R2 N_out 0 R2_known_sym
.PARAM Vin_known_sym = Vin_known_sym ; Symbolic parameter for input voltage
.PARAM R1_known_sym = R1_known_sym   ; Symbolic parameter for R1
.PARAM R2_known_sym = R2_known_sym   ; Symbolic parameter for R2
.end
"""
        netlist_vdiv3_path = "_temp_vdiv_gs_test3.sp"
        temp_files_to_clean.append(netlist_vdiv3_path)

        with open(netlist_vdiv3_path, 'w') as f:
            f.write(netlist_vdiv3_content)

        print(f"Generating equations for voltage divider: {netlist_vdiv3_path}")
        equations, circuit_vars, top_inst = generate_circuit_equations(netlist_path=netlist_vdiv3_path)

        if equations and circuit_vars:
            S_Vin, S_R1, S_R2 = sympy.symbols('SOURCE_V RES_R1 RES_R2')
            known_values_for_solve = {
                'Vin_known_sym': S_Vin,
                'R1_known_sym': S_R1,
                'R2_known_sym': S_R2
            }
            unknowns_str_list = ['V_Vin_node', 'V_N_out', 'I_VS', 'I_R1', 'I_R2']
            print(f"Solving system with knowns: {known_values_for_solve}, for unknowns: {unknowns_str_list}")

            solutions_list = solve_from_equations(
                equations, circuit_vars, known_values_for_solve, unknowns_str_list
            )
            print(f"Solutions from solve_from_equations: {solutions_list}")

            if solutions_list and len(solutions_list) == 1:
                sol_dict = solutions_list[0]
                V_N_out_sym = circuit_vars['voltages']['N_out']
                I_R1_sym = circuit_vars['currents']['R1']
                I_R2_sym = circuit_vars['currents']['R2']
                I_VS_sym = circuit_vars['currents']['VS']

                expected_V_N_out_expr = S_Vin * S_R2 / (S_R1 + S_R2)
                expected_I_R1_expr = S_Vin / (S_R1 + S_R2)
                expected_I_R2_expr = S_Vin / (S_R1 + S_R2)
                expected_I_VS_expr = -S_Vin / (S_R1 + S_R2)

                assert sympy.simplify(sol_dict.get(V_N_out_sym, sympy.Integer(-1)) - expected_V_N_out_expr) == 0, \
                    f"V_N_out mismatch. Expected: {expected_V_N_out_expr}, Got: {sol_dict.get(V_N_out_sym)}"
                print(f"  V_N_out PASSED: {sol_dict.get(V_N_out_sym)}")

                assert sympy.simplify(sol_dict.get(I_R1_sym, sympy.Integer(-1)) - expected_I_R1_expr) == 0, \
                    f"I_R1 mismatch. Expected: {expected_I_R1_expr}, Got: {sol_dict.get(I_R1_sym)}"
                print(f"  I_R1 PASSED: {sol_dict.get(I_R1_sym)}")

                assert sympy.simplify(sol_dict.get(I_R2_sym, sympy.Integer(-1)) - expected_I_R2_expr) == 0, \
                    f"I_R2 mismatch. Expected: {expected_I_R2_expr}, Got: {sol_dict.get(I_R2_sym)}"
                print(f"  I_R2 PASSED: {sol_dict.get(I_R2_sym)}")

                assert sympy.simplify(sol_dict.get(I_VS_sym, sympy.Integer(-1)) - expected_I_VS_expr) == 0, \
                    f"I_VS mismatch. Expected: {expected_I_VS_expr}, Got: {sol_dict.get(I_VS_sym)}"
                print(f"  I_VS PASSED: {sol_dict.get(I_VS_sym)}")

                print("Test Case 3 PASSED.")
            else:
                print(f"Test Case 3 FAILED. Unexpected solution format or no solution: {solutions_list}")
        else:
            print("Test Case 3 FAILED. generate_circuit_equations did not return equations/variables.")
    except Exception as e:
        print(f"Error in Test Case 3: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()

    finally: # This is the overall finally for cleanup
        print("\nCleaning up temporary files...")
        for f_path in temp_files_to_clean:
            if os.path.exists(f_path):
                os.remove(f_path)
                print(f"  Removed {f_path}")

if __name__ == '__main__':
    main()
