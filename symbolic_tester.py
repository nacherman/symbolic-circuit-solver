import sympy as sp
import sys
import os
import logging # Added for logging consistency

# Add symbolic_circuit_solver-master to path
master_proj_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'symbolic_circuit_solver-master')
if master_proj_path not in sys.path:
    sys.path.insert(0, master_proj_path)

try:
    # From scs_parser, using parse_file as it seems to be the main entry point there
    from scs_parser import parse_file as scs_parse_netlist # Renamed to avoid conflict
    from scs_instance_hier import make_top_instance
    from scs_circuit import TopCircuit
except ImportError as e:
    print(f"ERROR: Could not import from symbolic_circuit_solver-master: {e}")
    logging.error(f"ERROR: Could not import from symbolic_circuit_solver-master: {e}")
    # Define dummies so the rest of the file can be parsed
    def parse_netlist(filename, circ_obj): print(f"Dummy parse_netlist for {filename}"); return None
    def make_top_instance(c): print("Dummy make_top_instance"); return None
    class TopCircuit:
        def __init__(self):
            self.elementsd = {}
            self.parametersd = {}
            self.subcircuitsd = {}

# Import my component classes for type checking
from symbolic_components import Resistor, Capacitor, Inductor, VoltageSource, CurrentSource, \
                                VCVS, VCCS, CCVS, CCCS, s_sym
# from utils import print_solutions # Not strictly needed for this instantiation test

# --- Placeholder for other test functions from the original file ---
# To keep the file clean for this focused test, these are omitted in the final overwrite
# but would be present in a real scenario if appending.
# --- End of Placeholders ---

def test_make_instance_comprehensive():
    print("\n--- Testing Comprehensive Instantiation via scs_instance_hier.make_top_instance ---")
    logging.info("--- Testing Comprehensive Instantiation via scs_instance_hier.make_top_instance ---")

    netlist_filename = os.path.join(master_proj_path, 'test_comprehensive.sp')

    if not os.path.exists(netlist_filename):
        msg = f"ERROR: Netlist file {netlist_filename} not found. Ensure it's created by the subtask."
        print(msg); logging.error(msg)
        return

    msg = f"Attempting to parse netlist: {netlist_filename}"; print(msg); logging.info(msg)
    top_circuit_def = TopCircuit()
    parsed_top_circuit = scs_parse_netlist(netlist_filename, top_circuit_def)

    if not parsed_top_circuit or not parsed_top_circuit.elementsd: # elementsd is for top-level
        msg = "ERROR: Netlist parsing failed or resulted in no top-level elements."
        print(msg); logging.error(msg)
        return

    print(f"Netlist parsed. Top-level element definitions: {len(parsed_top_circuit.elementsd)}")
    logging.info(f"Netlist parsed. Top-level element definitions: {len(parsed_top_circuit.elementsd)}")
    print(f"Subcircuit definitions: {list(parsed_top_circuit.subcircuitsd.keys())}")
    logging.info(f"Subcircuit definitions: {list(parsed_top_circuit.subcircuitsd.keys())}")

    msg = "Attempting to instantiate circuit using make_top_instance..."; print(msg); logging.info(msg)
    top_instance = make_top_instance(parsed_top_circuit)

    if not top_instance:
        msg = "ERROR: make_top_instance failed to return a top_instance."
        print(msg); logging.error(msg)
        return
    if not top_instance.elements and not top_instance.subinstances :
        msg = "ERROR: make_top_instance resulted in an empty top_instance (no elements or subinstances)."
        print(msg); logging.error(msg)
        return

    print(f"Circuit instantiation complete. Top-level elements: {len(top_instance.elements)}, Subinstances: {len(top_instance.subinstances)}")
    logging.info(f"Circuit instantiation complete. Top-level elements: {len(top_instance.elements)}, Subinstances: {len(top_instance.subinstances)}")
    print("\nVerifying component types and symbolic values:")
    logging.info("\nVerifying component types and symbolic values:")

    all_checks_passed = True

    expected_top_level = {
        'VS1': (VoltageSource, 'voltage'),
        'R_INPUT': (Resistor, 'resistance'),
        'C_MAIN': (Capacitor, 'capacitance'),
        'L_MAIN': (Inductor, 'inductance'),
        'E_VCVS': (VCVS, 'gain'),
        'VS_SENSE': (VoltageSource, 'voltage'),
        'R_SENSE_PATH': (Resistor, 'resistance'),
        'H_CCVS': (CCVS, 'transresistance'),
        'F_CCCS': (CCCS, 'gain'),
        'R_LOAD_X': (Resistor, 'resistance')
    }

    for name, expected_type_tuple in expected_top_level.items():
        expected_type, value_key = expected_type_tuple
        if name not in top_instance.elements:
            msg = f"  ERROR: Top-level component {name} not found in instantiated elements."
            print(msg); logging.error(msg); all_checks_passed = False; continue

        elem_instance = top_instance.elements[name]
        print(f"  Component: {name} (Type: {elem_instance.__class__.__name__})")
        if not isinstance(elem_instance, expected_type):
            msg = f"    ERROR: Expected type {expected_type.__name__} but got {elem_instance.__class__.__name__}"
            print(msg); logging.error(msg); all_checks_passed = False
        else:
            print(f"    OK: Type is {expected_type.__name__}.")
            main_val = elem_instance.values.get(value_key)
            if main_val is None:
                msg = f"    ERROR: Main value key '{value_key}' not found in .values for {name}."
                print(msg); logging.error(msg); all_checks_passed = False
            elif not isinstance(main_val, sp.Expr):
                msg = f"    ERROR: Main value for {name} is not a Sympy expression: {main_val} (Type: {type(main_val)})"
                print(msg); logging.error(msg); all_checks_passed = False
            else:
                print(f"    OK: Main value '{value_key}': {main_val} (Type: {type(main_val)})")
                if name == 'VS1':
                    # Netlist: SIN({0} {VSIN_AMP} {1K} {0} {0} {VSIN_PHASE_DEG})
                    # Params: VSIN_AMP = 2, VSIN_PHASE_DEG = 45
                    # Expected AC phasor: 2 * exp(I * 45 * pi/180)
                    target_vs1_val = sp.sympify(2) * sp.exp(sp.I * sp.sympify('45') * sp.pi / 180)
                    # Note: sp.simplify might be needed if expression forms differ but are equivalent
                    if sp.simplify(main_val - target_vs1_val) != 0:
                         msg = f"    ERROR: VS1 value mismatch. Got {main_val.evalf(chop=True)}, Expected approx {target_vs1_val.evalf(chop=True)}"
                         print(msg); logging.error(msg); all_checks_passed = False
                    else: print(f"    OK: VS1 value matches expected phasor {target_vs1_val.evalf(chop=True)}.")

    if 'X_FILTER1' not in top_instance.subinstances:
        msg = "  ERROR: Subcircuit X_FILTER1 not found."
        print(msg); logging.error(msg); all_checks_passed = False
    else:
        x1_instance = top_instance.subinstances['X_FILTER1']
        print(f"\n  Subcircuit Instance: X_FILTER1 (Type: {x1_instance.__class__.__name__})")
        logging.info(f"  Subcircuit Instance: X_FILTER1 (Type: {x1_instance.__class__.__name__})")
        # PARAM CAP_VAL = {0.1uF * 2} -> 0.2uF
        # X_FILTER1 C_SUBCKT={CAP_VAL/2} -> 0.1uF
        expected_r_subckt = sp.sympify("2000.0")
        expected_c_subckt = sp.sympify("0.1e-6")

        # Parameters in instance.paramsd are stored with string keys by scs_parser.evaluate_params
        r_subckt_val_from_inst = x1_instance.paramsd.get('R_SUBCKT')
        c_subckt_val_from_inst = x1_instance.paramsd.get('C_SUBCKT')

        print(f"    X_FILTER1 Parameters (evaluated): R_SUBCKT={r_subckt_val_from_inst}, C_SUBCKT={c_subckt_val_from_inst}")
        logging.info(f"    X_FILTER1 Parameters (evaluated): R_SUBCKT={r_subckt_val_from_inst}, C_SUBCKT={c_subckt_val_from_inst}")

        if not (r_subckt_val_from_inst is not None and abs(r_subckt_val_from_inst.evalf() - expected_r_subckt.evalf()) < 1e-9 and \
                c_subckt_val_from_inst is not None and abs(c_subckt_val_from_inst.evalf() - expected_c_subckt.evalf()) < 1e-9):
            msg = f"    ERROR: X_FILTER1 parameters not evaluated as expected. Expected R_SUBCKT={expected_r_subckt}, C_SUBCKT={expected_c_subckt}. Got R_SUBCKT={r_subckt_val_from_inst}, C_SUBCKT={c_subckt_val_from_inst}"
            print(msg); logging.error(msg); all_checks_passed = False
        else:
            print(f"    OK: X_FILTER1 parameters R_SUBCKT={r_subckt_val_from_inst}, C_SUBCKT={c_subckt_val_from_inst} evaluated correctly.")

        expected_sub_elements = {
            # The values for R_SUB, C_SUB inside subcircuit will be the evaluated numerical values
            # because scs_parser.evaluate_params (called by _ensure_sympy_expr) resolves them using
            # the subcircuit instance's parametersd (which has R_SUBCKT=2000, C_SUBCKT=0.1u).
            'R_SUB': (Resistor, 'resistance', expected_r_subckt),
            'C_SUB': (Capacitor, 'capacitance', expected_c_subckt),
            'G_VCCS_SUB': (VCCS, 'transconductance', sp.sympify("0.1"))
        }
        for name, expected_sub_type_tuple in expected_sub_elements.items():
            expected_type, value_key, expected_numerical_val = expected_sub_type_tuple
            if name not in x1_instance.elements:
                msg = f"    ERROR: Sub-element {name} not found in X_FILTER1."
                print(msg); logging.error(msg); all_checks_passed = False; continue

            elem_instance = x1_instance.elements[name]
            print(f"    Sub-element: {name} (Type: {elem_instance.__class__.__name__})")
            if not isinstance(elem_instance, expected_type):
                msg = f"      ERROR: Expected type {expected_type.__name__} but got {elem_instance.__class__.__name__}"
                print(msg); logging.error(msg); all_checks_passed = False
            else:
                print(f"      OK: Type is {expected_type.__name__}.")
                main_val = elem_instance.values.get(value_key)
                if main_val is None:
                     msg = f"      ERROR: Main value key '{value_key}' not found for {name}."
                     print(msg); logging.error(msg); all_checks_passed = False
                elif not isinstance(main_val, sp.Expr):
                     msg = f"      ERROR: Main value for {name} is not a Sympy expression: {main_val}"
                     print(msg); logging.error(msg); all_checks_passed = False
                elif abs(main_val.evalf() - expected_numerical_val.evalf()) > 1e-9 :
                     msg = f"      ERROR: Value mismatch for {name}. Got {main_val.evalf()}, Expected {expected_numerical_val.evalf()}"
                     print(msg); logging.error(msg); all_checks_passed = False
                else:
                     print(f"      OK: Value for {name} matches expected {expected_numerical_val.evalf()}.")

    if all_checks_passed:
        msg = "\nComprehensive Instantiation Test PASSED: All components and subcircuit parts correctly instantiated."
        print(msg); logging.info(msg)
    else:
        msg = "\nComprehensive Instantiation Test FAILED: Errors detailed above."
        print(msg); logging.error(msg)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    test_make_instance_comprehensive()
