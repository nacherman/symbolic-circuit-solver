import sys
import os
import sympy

# Path setup - adjust if subtask execution directory changes
script_run_dir = os.getcwd()
path_to_solver_package = os.path.join(script_run_dir, "extracted_files/sim12/sim/symbolic-circuit-solver-improve-h-bridge-example/symbolic-circuit-solver-improve-h-bridge-example/")
if path_to_solver_package not in sys.path:
    sys.path.insert(0, path_to_solver_package)

try:
    from symbolic_circuit_solver_master.scs_symbolic_goal_seeker import solve_circuit_for_unknowns
    print("Successfully imported solve_circuit_for_unknowns.")
except ImportError as e:
    print(f"Error importing: {e}")
    print(f"Python path: {sys.path}")
    exit(1)

netlist_file_path = os.path.join(script_run_dir, "user_bridge.sp")

known_values_map = {
    'U1_val': 1.0,
    'U2_val': 0.1,
    'R1_val': 180.0,
    'R2_val': 100.0,
    'R4_val': 22.0,
    'R5_val': 39.0,
    'R6_val': 39.0,
    'R3_sym': 56.18 # R3_sym is NOW a known value for this test
}

# We are primarily interested in the circuit variables, especially I(VdummyI34)
# R3_sym is now a known.
unknowns_str_list = [
    'V_s1', 'V_N2', 'V_N3', 'V_N4', # Node voltages
    'I_Vs1', 'I_R1', 'I_Vs2', 'I_R6', 'I_R2', 'I_R3_element', 'I_R4', 'I_R5', 'I_VdummyI34' # Element currents
]

print(f"Attempting to solve for circuit variables (esp. I_VdummyI34) using netlist: {netlist_file_path}")
print(f"Known values (including R3_sym): {known_values_map}")
print(f"Target unknowns for sympy.solve: {unknowns_str_list}")

solutions = solve_circuit_for_unknowns(
    netlist_path=netlist_file_path,
    known_values_map_str_keys=known_values_map,
    unknowns_to_solve_for_str=unknowns_str_list,
)

if solutions:
    print("\n--- Solutions Found ---")
    # Assuming one consistent solution dictionary
    solution_dict = solutions[0]

    # R3_sym is now a known, so we retrieve its value from known_values_map for verification printout
    r3_sym_key = 'R3_sym' # Use string key for the dictionary
    if r3_sym_key in known_values_map: # Check if it was passed as known
        r3_known_value = known_values_map[r3_sym_key]
        print(f"R3_sym was set to known value: {r3_known_value}")
        expected_r3 = 56.18
        if abs(r3_known_value - expected_r3) < 0.001: # Tight tolerance for direct check
             print(f"R3 known value {r3_known_value} matches expected set value {expected_r3}.")
        else:
             print(f"R3 known value {r3_known_value} MISMATCHES expected set value {expected_r3}.")
    # No 'elif' needed here, as R3_sym should not be in solution_dict if it's a known that was substituted.
    else:
        print(f"{r3_sym_key} not found in known_values_map. Check script logic.")

    i_vdummy_obj = sympy.symbols('I_VdummyI34') # Sympy symbol object for solution_dict key
    if i_vdummy_obj in solution_dict:
        i34_solution = solution_dict[i_vdummy_obj]
        print(f"Solved I_VdummyI34 = {i34_solution}")
        try:
            i34_numeric = float(i34_solution)
            print(f"Numeric I_VdummyI34 = {i34_numeric * 1000:.4f} mA")
            # Verification for I
            expected_i_user = -0.559 # mA
            if abs(i34_numeric * 1000 - expected_i_user) < 0.01: # Tolerance
                print(f"I_VdummyI34 matches user's expected current {expected_i_user} mA (within tolerance).")
            else:
                print(f"I_VdummyI34 {i34_numeric*1000:.4f} mA MISMATCHES user's expected current {expected_i_user} mA.")

            # Check against user's manual calculation of -0.78mA (which I recalculated as -0.999mA)
            expected_i_manual_recalc = -0.999 # mA
            if abs(i34_numeric * 1000 - expected_i_manual_recalc) < 0.01:
                 print(f"I_VdummyI34 also matches my recalculated current {expected_i_manual_recalc} mA (within tolerance).")
            else:
                 print(f"I_VdummyI34 {i34_numeric*1000:.4f} mA MISMATCHES my recalculated current {expected_i_manual_recalc} mA.")

        except Exception as e:
            print(f"Could not convert I_VdummyI34 solution to float: {e}. Solution was: {i34_solution}")
    else:
        print("I_VdummyI34 not found in solutions.")

    # print("\nFull solution dictionary:")
    # for var, val in solution_dict.items():
    #     try:
    #         print(f"  {str(var)}: {float(val):.4g}")
    #     except:
    #         print(f"  {str(var)}: {val}")

else:
    print("\nNo solution found or an error occurred.")
