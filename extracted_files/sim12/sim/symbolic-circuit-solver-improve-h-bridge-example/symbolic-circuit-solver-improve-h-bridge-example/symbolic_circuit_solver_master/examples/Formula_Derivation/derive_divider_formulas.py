import sys
import os
import sympy # For type checking or direct symbol use if needed

# __file__ is .../symbolic_circuit_solver_master/examples/Formula_Derivation/derive_divider_formulas.py
script_dir = os.path.dirname(os.path.abspath(__file__))
# project_root_package_dir is .../symbolic_circuit_solver_master
project_root_package_dir = os.path.dirname(os.path.dirname(script_dir))
# path_to_add_for_package_import is .../ (the directory containing symbolic_circuit_solver_master, i.e. /app)
path_to_add_for_package_import = os.path.dirname(project_root_package_dir)
if path_to_add_for_package_import not in sys.path:
    sys.path.insert(0, path_to_add_for_package_import)

from symbolic_circuit_solver_master import scs_parser
from symbolic_circuit_solver_master import scs_instance_hier
from symbolic_circuit_solver_master import scs_circuit
from symbolic_circuit_solver_master.scs_errors import ScsParserError, ScsInstanceError

def main():
    netlist_file = os.path.join(os.path.dirname(__file__), 'voltage_divider.sp')

    print(f"Attempting to derive formulas for Voltage Divider from netlist: {netlist_file}")
    print("This script demonstrates how to use the base solver components (parser, instance hierarchy)")
    print("to derive general symbolic formulas for circuit quantities (V, I, P)")
    print("in terms of the symbolic parameters defined in the SPICE file.")

    try:
        # --- Step 1: Parse the SPICE netlist ---
        # This creates a circuit template from the netlist.
        # All parameters (US_sym, R1_sym, R2_sym) are defined symbolically in voltage_divider.sp.
        top_circuit = scs_parser.parse_file(netlist_file, scs_circuit.TopCircuit())
        if not top_circuit:
            raise ScsParserError(f"Failed to parse the netlist: {netlist_file}")

        # --- Step 2: Create an instance of the circuit ---
        # This step evaluates .PARAM definitions. Since parameters like R1_val are defined
        # as R1_sym (and R1_sym is defined as R1_sym), the instance will have these
        # as sympy.Symbol objects.
        top_instance = scs_instance_hier.make_top_instance(top_circuit)
        if not top_instance:
            raise ScsInstanceError("Failed to instantiate the circuit.")

        # --- Step 3: Perform basic circuit checks (good practice) ---
        if not top_instance.check_path_to_gnd():
            raise ScsInstanceError("Circuit check failed: No path to ground for some nets.")
        if not top_instance.check_voltage_loop():
            raise ScsInstanceError("Circuit check failed: Voltage loop detected.")

        # --- Step 4: Solve the circuit symbolically ---
        # This solves the circuit's MNA equations, expressing node voltages and currents
        # in terms of the symbolic parameters (US_sym, R1_sym, R2_sym).
        top_instance.solve()
        print("\nCircuit solved symbolically.")

        # --- Step 5: Retrieve and print the derived symbolic formulas ---
        print("\n--- Derived Symbolic Formulas ---")

        # Formula for output voltage V(N_out)
        # Nodes are 'N_out' and '0' (ground) as per SPICE file
        v_out_expr = top_instance.v('N_out', '0')
        print(f"Formula for V(N_out): {v_out_expr}")
        # Expected: US_sym * R2_sym / (R1_sym + R2_sym) after simplification by Sympy

        # Formula for current through R1 (element name 'R1' in SPICE)
        # Positive current for R1 is defined N_source -> N_out
        i_r1_expr = top_instance.i('R1')
        print(f"Formula for I(R1): {i_r1_expr}")
        # Expected: US_sym / (R1_sym + R2_sym) after simplification

        # Formula for current through R2 (element name 'R2' in SPICE)
        # Positive current for R2 is defined N_out -> 0
        i_r2_expr = top_instance.i('R2')
        print(f"Formula for I(R2): {i_r2_expr}")
        # Expected: US_sym * R2_sym / ((R1_sym + R2_sym)*R2_sym) = US_sym / (R1_sym + R2_sym) after simplification

        # Formula for power in R1
        p_r1_expr = top_instance.p('R1')
        print(f"Formula for P(R1): {p_r1_expr}")
        # Expected: (US_sym / (R1_sym + R2_sym))^2 * R1_sym

        # Formula for power in R2
        p_r2_expr = top_instance.p('R2')
        print(f"Formula for P(R2): {p_r2_expr}")
        # Expected: (US_sym * R2_sym / (R1_sym + R2_sym))^2 / R2_sym  or (I(R2))^2 * R2_sym

        print("\nNote: Expressions are as derived by the solver; Sympy's default simplification is applied.")
        print("Further simplification might be possible using sympy.simplify() if needed on these expressions.")
        # Example: print(f"Simplified V(N_out): {sympy.simplify(v_out_expr)}")

    except (ScsParserError, ScsInstanceError, ValueError, FileNotFoundError) as e:
        print(f"An error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {type(e).__name__}: {e}")

if __name__ == '__main__':
    main()
