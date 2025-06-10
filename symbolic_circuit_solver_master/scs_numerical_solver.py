import numpy as np
import sympy # May be needed for type checking or symbol manipulation
from .scs_instance_hier import Instance # Assuming Instance is in scs_instance_hier
from .scs_elements import (
    Resistance, VoltageSource, CurrentSource, # Changed Resistor to Resistance
    VoltageControlledVoltageSource, CurrentControlledVoltageSource,
    VoltageControlledCurrentSource, CurrentControlledCurrentSource
)
# from . import scs_errors # Uncomment if specific errors are raised

def build_numerical_mna(instance: Instance, param_values: dict):
    """
    Builds the numerical Modified Nodal Analysis (MNA) matrices A and z
    for DC analysis of a given circuit instance and parameter values.

    Args:
        instance: The circuit instance object (assumed to be flattened for now).
        param_values: A dictionary mapping Sympy symbols (or their string names)
                      to numerical values for all circuit parameters.

    Returns:
        A tuple (A_num, z_num, node_to_index, vsource_to_current_idx):
            A_num: The numerical MNA matrix A.
            z_num: The numerical MNA vector z.
            node_to_index: A dictionary mapping node names to matrix indices.
            vsource_to_current_idx: Dictionary mapping V_source names to their current's index in solution vector.
        Returns (None, None, None, None) if matrix construction fails.
    """
    # --- 1. Identify all unique nodes and assign indices ---
    # Ground node '0' is reference and usually not explicitly in the matrix rows/cols.
    all_nets = set()
    if not instance or not instance.elements:
        print("Warning: Instance is None or has no elements.")
        return None, None, None, None

    for el_name, element_obj in instance.elements.items():
        # Ensure element_obj and element_obj.nets are valid
        if not hasattr(element_obj, 'nets') or not element_obj.nets:
            print(f"Warning: Element {el_name} has no nets defined. Skipping.")
            continue

        # Typically, the first two nets are the connection points for stamping.
        # For multi-terminal devices, this might need adjustment or specific handling.
        # For now, let's consider up to the first two nets.
        # Controlled sources might have more nets listed (control nets),
        # but their stamping is handled by their specific rules.
        nets_to_consider = element_obj.nets
        if isinstance(element_obj, Resistance): # Changed Resistor to Resistance
             nets_to_consider = element_obj.nets[:2]
        # TODO: Add similar handling for other element types if nets_to_consider needs specific logic
        # For VoltageSource and CurrentSource, all their listed nets are usually relevant for connections
        # or control, but for node collection for MNA, usually the first two are main connection points.
        # However, the current approach of adding all listed nets (unless specifically shortened for Resistor)
        # to all_nets set, and then filtering by '0', should be generally safe for node collection.

        for net_name in nets_to_consider:
            if net_name != '0': # Exclude ground
                all_nets.add(net_name)

    # For subinstances, recursively collect nets if not already handled by flattening.
    # Current assumption: instance.elements contains all relevant elements, possibly flattened.
    # If instance.sub_instances is populated and not flattened, traversal would be needed.

    node_list = sorted(list(all_nets)) # Consistent ordering
    node_to_index = {name: i for i, name in enumerate(node_list)}
    num_nodes = len(node_list)

    # --- Count independent voltage sources and prepare for matrix sizing ---
    v_sources_list = []
    # To identify independent sources, we check their exact type.
    # Controlled sources also add a current unknown.
    for el_name, element_obj in instance.elements.items():
        # Independent Voltage Source
        if type(element_obj) is VoltageSource:
            v_sources_list.append(element_obj)
        # Voltage Controlled Voltage Source
        elif isinstance(element_obj, VoltageControlledVoltageSource): # Use isinstance for class hierarchy
            v_sources_list.append(element_obj)
        elif isinstance(element_obj, CurrentControlledVoltageSource): # CCVS - H element
            v_sources_list.append(element_obj)
        # CCCS elements do not add to v_sources_list as they don't introduce a new current unknown for MNA

    num_additional_current_unknowns = len(v_sources_list)

    matrix_size = num_nodes + num_additional_current_unknowns

    if num_nodes == 0 and num_additional_current_unknowns == 0 : # Handle empty or ground-only circuits
         print("Warning: No non-ground nodes and no (independent or controlled) voltage sources found for MNA matrix.")
         # Return empty matrices or specific indication if preferred
         return np.array([]).reshape(0,0), np.array([]), {}, {}


    A_num = np.zeros((matrix_size, matrix_size), dtype=float)
    z_num = np.zeros(matrix_size, dtype=float)

    # Create mapping for voltage source current variables
    vsource_to_current_idx = {vs_obj.names[0]: (num_nodes + i) for i, vs_obj in enumerate(v_sources_list)}

    # --- 2. Stamp elements ---
    for el_name, element_obj in instance.elements.items():
        if not hasattr(element_obj, 'nets') or not element_obj.nets:
            continue

        # Order of checks: More specific types first (if we were adding controlled sources),
        # then Resistor, then specific independent sources.
        if isinstance(element_obj, Resistance): # Changed Resistor to Resistance
            val = element_obj.get_numerical_dc_value(param_values)
            conductance = 0.0
            if val == float('inf'): # Open circuit
                conductance = 0.0
            elif val == 0.0: # Short circuit (ideal wire)
                # This is problematic for standard MNA if nodes are distinct,
                # as it implies V_n1 = V_n2.
                # Using a very large conductance can approximate this.
                # Alternatively, node merging/equation substitution is needed for exactness.
                print(f"Warning: Resistor {el_name} has zero resistance. Approximating with large conductance.")
                conductance = 1e12 # Arbitrarily large conductance
            elif isinstance(val, (float, int)) and val > 0: # val is not None and is a number
                conductance = 1.0 / val
            elif isinstance(val, (float, int)) and val < 0:
                 print(f"Warning: Resistor {el_name} has negative resistance ({val}). Using its conductance.")
                 conductance = 1.0 / val # Negative conductance
            else:
                # This case handles if val is None, or not a float/int (e.g. still symbolic)
                print(f"Warning: Could not get valid numerical resistance for {el_name}. Value: {val}. Skipping.")
                continue

            n1_name, n2_name = element_obj.nets[0], element_obj.nets[1]

            # Stamp resistor into the G submatrix (upper-left of A_num)
            if n1_name != '0':
                idx1 = node_to_index[n1_name]
                A_num[idx1, idx1] += conductance
                if n2_name != '0':
                    idx2 = node_to_index[n2_name]
                    A_num[idx1, idx2] -= conductance
                    A_num[idx2, idx1] -= conductance
                    A_num[idx2, idx2] += conductance
                # If n2_name is '0', its contribution is only to A_num[idx1, idx1], already handled.
            elif n2_name != '0': # n1 is '0', but n2 is not
                idx2 = node_to_index[n2_name]
                A_num[idx2, idx2] += conductance
            # If both n1_name and n2_name are '0', it's a resistor across ground.
            # It draws current but doesn't affect node voltage equations in this basic MNA form
            # unless current through it is explicitly asked for.

        elif isinstance(element_obj, VoltageControlledVoltageSource): # VCVS - E element
            gain = element_obj.get_numerical_dc_value(param_values)
            if not isinstance(gain, (float, int)):
                print(f"Warning: Could not get valid numerical gain for VCVS {el_name}. Value: {gain}. Skipping.")
                continue

            n_plus, n_minus = element_obj.nets[0], element_obj.nets[1]
            nc_plus, nc_minus = element_obj.nets[2], element_obj.nets[3]
            current_idx = vsource_to_current_idx[element_obj.names[0]] # Name of E element

            # Branch current definition part (current I_e flows from n_plus to n_minus)
            if n_plus != '0':
                A_num[node_to_index[n_plus], current_idx] += 1.0
            if n_minus != '0':
                A_num[node_to_index[n_minus], current_idx] -= 1.0

            # Constitutive equation: V(n_plus) - V(n_minus) - gain * (V(nc_plus) - V(nc_minus)) = 0
            # This is the row for the current unknown I_e (current_idx)
            if n_plus != '0':
                A_num[current_idx, node_to_index[n_plus]] += 1.0
            if n_minus != '0':
                A_num[current_idx, node_to_index[n_minus]] -= 1.0

            if nc_plus != '0':
                A_num[current_idx, node_to_index[nc_plus]] -= gain
            if nc_minus != '0':
                A_num[current_idx, node_to_index[nc_minus]] += gain

            # z_num[current_idx] is 0 for this form of equation

        elif isinstance(element_obj, CurrentControlledVoltageSource): # CCVS - H element
            r_val = element_obj.get_numerical_dc_value(param_values) # Transresistance
            if not isinstance(r_val, (float, int)):
                print(f"Warning: Could not get valid numerical transresistance for CCVS {el_name}. Value: {r_val}. Skipping.")
                continue

            n_plus, n_minus = element_obj.nets[0], element_obj.nets[1]
            ccvs_name = element_obj.names[0]
            controlling_vsource_name = element_obj.names[1] # Name of the V source whose current is controlling

            ccvs_branch_current_idx = vsource_to_current_idx[ccvs_name]

            if controlling_vsource_name not in vsource_to_current_idx:
                print(f"Error: Controlling voltage source '{controlling_vsource_name}' for CCVS '{ccvs_name}' not found in voltage source list for MNA indexing. Skipping.")
                continue
            controlling_current_idx = vsource_to_current_idx[controlling_vsource_name]

            # Branch current definition part (KCL contribution for I_h)
            if n_plus != '0':
                A_num[node_to_index[n_plus], ccvs_branch_current_idx] += 1.0
            if n_minus != '0':
                A_num[node_to_index[n_minus], ccvs_branch_current_idx] -= 1.0

            # Constitutive equation: V(n_plus) - V(n_minus) - r_val * I_controlling_vsource = 0
            # This is the row for the ccvs_branch_current_idx
            if n_plus != '0':
                A_num[ccvs_branch_current_idx, node_to_index[n_plus]] += 1.0
            if n_minus != '0':
                A_num[ccvs_branch_current_idx, node_to_index[n_minus]] -= 1.0
            A_num[ccvs_branch_current_idx, controlling_current_idx] -= r_val # Coefficient for the controlling current

            # z_num[ccvs_branch_current_idx] is 0

        elif isinstance(element_obj, VoltageControlledCurrentSource): # VCCS - G element
            gm = element_obj.get_numerical_dc_value(param_values)
            if not isinstance(gm, (float, int)):
                print(f"Warning: Could not get valid numerical transconductance for VCCS {el_name}. Value: {gm}. Skipping.")
                continue

            n_plus, n_minus = element_obj.nets[0], element_obj.nets[1]
            nc_plus, nc_minus = element_obj.nets[2], element_obj.nets[3]

            # Stamp contributions to KCL equations
            # Current = gm * (V(nc_plus) - V(nc_minus))
            # This current flows from n_plus to n_minus
            # Current I = gm * (V(nc_plus) - V(nc_minus)) flows from n_plus to n_minus.
            # Contribution to KCL at n_plus: -I --> -gm * V(nc_plus) + gm * V(nc_minus)
            # Contribution to KCL at n_minus: +I --> +gm * V(nc_plus) - gm * V(nc_minus)
            if n_plus != '0':
                if nc_plus != '0':
                    A_num[node_to_index[n_plus], node_to_index[nc_plus]] -= gm
                if nc_minus != '0':
                    A_num[node_to_index[n_plus], node_to_index[nc_minus]] += gm
            if n_minus != '0':
                if nc_plus != '0':
                    A_num[node_to_index[n_minus], node_to_index[nc_plus]] += gm
                if nc_minus != '0':
                    A_num[node_to_index[n_minus], node_to_index[nc_minus]] -= gm

        elif isinstance(element_obj, CurrentControlledCurrentSource): # CCCS - F element
            gain = element_obj.get_numerical_dc_value(param_values) # Current gain
            if not isinstance(gain, (float, int)):
                print(f"Warning: Could not get valid numerical gain for CCCS {el_name}. Value: {gain}. Skipping.")
                continue

            n_plus, n_minus = element_obj.nets[0], element_obj.nets[1]
            # cccs_name = element_obj.names[0] # Not directly used in MNA matrix if not adding a row
            controlling_vsource_name = element_obj.names[1]

            if controlling_vsource_name not in vsource_to_current_idx:
                print(f"Error: Controlling voltage source '{controlling_vsource_name}' for CCCS '{el_name}' not found in MNA current index map. Skipping.")
                continue
            controlling_current_idx = vsource_to_current_idx[controlling_vsource_name]

            # Current I_f = gain * I_controlling_vsource flows from n_plus to n_minus
            # Contribution to KCL at n_plus: -I_f => -gain * I_controlling_vsource
            # This affects the column of the controlling current in the KCL equation for n_plus.
            if n_plus != '0':
                A_num[node_to_index[n_plus], controlling_current_idx] -= gain

            # Contribution to KCL at n_minus: +I_f => +gain * I_controlling_vsource
            if n_minus != '0':
                A_num[node_to_index[n_minus], controlling_current_idx] += gain

        elif type(element_obj) is VoltageSource: # Independent Voltage Source (must come AFTER specific controlled V sources)
            v_val = element_obj.get_numerical_dc_value(param_values)
            if not isinstance(v_val, (float, int)):
                print(f"Warning: Could not get valid numerical value for VoltageSource {el_name}. Value: {v_val}. Skipping.")
                continue

            n1_name, n2_name = element_obj.nets[0], element_obj.nets[1] # Positive, Negative
            current_idx = vsource_to_current_idx[element_obj.names[0]]

            if n1_name != '0':
                A_num[node_to_index[n1_name], current_idx] += 1.0
            if n2_name != '0':
                A_num[node_to_index[n2_name], current_idx] -= 1.0

            if n1_name != '0':
                A_num[current_idx, node_to_index[n1_name]] += 1.0
            if n2_name != '0':
                A_num[current_idx, node_to_index[n2_name]] -= 1.0

            z_num[current_idx] = v_val

        elif type(element_obj) is CurrentSource: # Independent Current Source
            i_val = element_obj.get_numerical_dc_value(param_values)
            if not isinstance(i_val, (float, int)):
                print(f"Warning: Could not get valid numerical value for CurrentSource {el_name}. Value: {i_val}. Skipping.")
                continue

            n1_name, n2_name = element_obj.nets[0], element_obj.nets[1] # Current flows FROM n1 TO n2

            if n1_name != '0':
                z_num[node_to_index[n1_name]] -= i_val
            if n2_name != '0':
                z_num[node_to_index[n2_name]] += i_val

        # CCCS logic was added here in a previous step, ensuring it's before independent CurrentSource
        # No further TODO needed here if CCCS is already handled by an elif before CurrentSource

    return A_num, z_num, node_to_index, vsource_to_current_idx

def solve_dc_numerically_from_instance(instance: Instance, param_values: dict):
    A_num, z_num, node_to_index, vsource_to_current_idx = build_numerical_mna(instance, param_values)

    if A_num is None or z_num is None or node_to_index is None or vsource_to_current_idx is None:
        print("Error: MNA matrix construction failed.")
        return None

    # Check if the matrix is empty (e.g. circuit with only ground node)
    # build_numerical_mna now returns empty dicts for node_to_index and vsource_to_current_idx in such cases.
    if A_num.shape[0] == 0 and A_num.shape[1] == 0 :
        if not node_to_index and not vsource_to_current_idx : # Truly empty circuit from MNA perspective
             print("Circuit has no non-ground nodes and no voltage sources. DC solution is trivial (all 0V relative to ground).")
             return {} # Or specific format indicating this
        # If there are nodes/vsources but matrix is 0x0, it's an issue from build_numerical_mna
        print("Warning: MNA matrix is 0x0 but node/vsource maps are not empty. Check build_numerical_mna.")
        return {}


    try:
        solution_vector = np.linalg.solve(A_num, z_num)

        results_dict = {}
        # Node voltages
        for node_name, index in node_to_index.items():
            results_dict[f"V({node_name})"] = solution_vector[index]

        # Node voltages (store under 'node_voltages' key for clarity)
        results_dict['node_voltages'] = {}
        for node_name, index in node_to_index.items():
            results_dict['node_voltages'][node_name] = solution_vector[index]

        # Currents through voltage sources (V, E, H types)
        results_dict['vsource_currents'] = {}
        for v_name, index in vsource_to_current_idx.items():
            # MNA current variable is defined as leaving the positive terminal of the source.
            results_dict['vsource_currents'][v_name] = solution_vector[index]

        # Calculate and add currents through resistors
        results_dict['element_currents'] = {}
        # Calculate element power
        results_dict['element_power'] = {}

        for el_name, element_obj in instance.elements.items():
            n1_name, n2_name = element_obj.nets[0], element_obj.nets[1]
            v1 = results_dict['node_voltages'].get(n1_name, 0.0) if n1_name != '0' else 0.0
            v2 = results_dict['node_voltages'].get(n2_name, 0.0) if n2_name != '0' else 0.0
            voltage_across_element = v1 - v2 # V(n1) - V(n2)

            if isinstance(element_obj, Resistance):
                R_val = element_obj.get_numerical_dc_value(param_values)
                current = float('nan')
                power = float('nan')
                if R_val is not None and isinstance(R_val, (float, int)):
                    if R_val == 0:
                        print(f"Warning: Resistor {el_name} has zero resistance. Current calculation via Ohm's law problematic.")
                        # Current would be determined by rest of circuit; power could be zero if V1=V2, or infinite.
                    else:
                        current = voltage_across_element / R_val
                        power = voltage_across_element * current # (V1-V2)^2 / R or I*(V1-V2)
                else:
                    print(f"Warning: Could not get valid numerical resistance for {el_name} for current/power. Value: {R_val}.")
                results_dict['element_currents'][el_name] = current
                results_dict['element_power'][el_name] = power

            elif type(element_obj) is VoltageSource or \
                 isinstance(element_obj, VoltageControlledVoltageSource) or \
                 isinstance(element_obj, CurrentControlledVoltageSource):
                # V, E, H elements. Their current is in 'vsource_currents'.
                # Power absorbed: V_element * (-I_variable) because I_variable is current leaving n+
                # V_element is (v1-v2)
                if el_name in results_dict['vsource_currents']:
                    source_current_var_value = results_dict['vsource_currents'][el_name]
                    power = voltage_across_element * (-source_current_var_value)
                    results_dict['element_power'][el_name] = power
                else:
                    results_dict['element_power'][el_name] = float('nan')


            elif type(element_obj) is CurrentSource: # Independent Current Source
                i_val = element_obj.get_numerical_dc_value(param_values)
                if i_val is not None and isinstance(i_val, (float, int)):
                    # Current i_val flows from n1 to n2. Power absorbed = (v1-v2)*i_val
                    results_dict['element_currents'][el_name] = i_val # Its own current
                    results_dict['element_power'][el_name] = voltage_across_element * i_val
                else:
                    results_dict['element_currents'][el_name] = float('nan')
                    results_dict['element_power'][el_name] = float('nan')

            elif isinstance(element_obj, VoltageControlledCurrentSource): # VCCS (G element)
                gm = element_obj.get_numerical_dc_value(param_values)
                nc_plus_name, nc_minus_name = element_obj.nets[2], element_obj.nets[3]
                v_nc_plus = results_dict['node_voltages'].get(nc_plus_name, 0.0) if nc_plus_name != '0' else 0.0
                v_nc_minus = results_dict['node_voltages'].get(nc_minus_name, 0.0) if nc_minus_name != '0' else 0.0
                controlled_current = float('nan')
                if gm is not None and isinstance(gm, (float, int)):
                    controlled_current = gm * (v_nc_plus - v_nc_minus)
                    results_dict['element_currents'][el_name] = controlled_current
                    # This current flows from n1 to n2. Power absorbed = (v1-v2)*controlled_current
                    results_dict['element_power'][el_name] = voltage_across_element * controlled_current
                else:
                    results_dict['element_currents'][el_name] = float('nan')
                    results_dict['element_power'][el_name] = float('nan')

            elif isinstance(element_obj, CurrentControlledCurrentSource): # CCCS (F element)
                gain = element_obj.get_numerical_dc_value(param_values)
                controlling_vsource_name = element_obj.names[1]
                controlled_current = float('nan')
                if gain is not None and isinstance(gain, (float, int)):
                    if controlling_vsource_name in results_dict['vsource_currents']:
                        I_control = results_dict['vsource_currents'][controlling_vsource_name]
                        controlled_current = gain * I_control
                        results_dict['element_currents'][el_name] = controlled_current
                        # This current flows from n1 to n2. Power absorbed = (v1-v2)*controlled_current
                        results_dict['element_power'][el_name] = voltage_across_element * controlled_current
                    else:
                        print(f"Warning: Controlling source {controlling_vsource_name} for CCCS {el_name} not found in vsource_currents.")
                        results_dict['element_currents'][el_name] = float('nan')
                        results_dict['element_power'][el_name] = float('nan')
                else:
                    results_dict['element_currents'][el_name] = float('nan')
                    results_dict['element_power'][el_name] = float('nan')

        return results_dict
    except np.linalg.LinAlgError:
        print(f"Error: Singular matrix (determinant is zero). Circuit may be ill-defined for DC analysis (e.g., floating parts, redundant voltage sources, or unstable). A_matrix:\n{A_num}\nz_vector:\n{z_num}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during numerical solution: {e}")
        return None

# Imports for the new solve_dc_numerically logic
from . import scs_parser as scs_parser_module # Alias to avoid conflict if Parser class is named same
from . import scs_circuit
from . import scs_instance_hier
from . import scs_errors # For catching specific parsing/instancing errors

def solve_dc_numerically(netlist_path: str, param_values: dict):
    """
    Parses a netlist file using scs_parser and scs_instance_hier,
    then builds and solves the numerical MNA matrices for DC operating point.
    Returns node voltages and currents through independent voltage sources.
    """
    top_circuit_obj = None
    top_instance = None
    try:
        # 1. Create a TopCircuit object
        top_circuit_obj = scs_circuit.TopCircuit()

        # 2. Parse the netlist file into this TopCircuit object
        # parse_file returns the circuit object back if successful, or None on error
        parsed_circuit = scs_parser_module.parse_file(netlist_path, top_circuit_obj)
        if not parsed_circuit: # Check if parse_file indicated an error by returning None
            # parse_file itself should log specific errors via logging module
            print(f"Error: Failed to parse the netlist file: {netlist_path}. Check logs for details.")
            return None
        top_circuit_obj = parsed_circuit # Keep the populated circuit object

        # 3. Create the top-level instance from the parsed circuit definition
        # make_top_instance might take param_valsd for default top-level params,
        # not the runtime param_values used for substitution in MNA.
        # If param_values are meant for top-level default overrides, this needs clarification.
        # Assuming param_values are for MNA substitution.
        # make_top_instance uses the circuit's own parametersd by default.
        top_instance = scs_instance_hier.make_top_instance(top_circuit_obj)
        if not top_instance:
            print("Error: Failed to create top-level instance from parsed circuit.")
            return None

        # Perform basic checks (optional here, but good practice from SymbolicCircuitProblemSolver)
        # These might raise scs_errors.ScsInstanceError
        if not top_instance.check_path_to_gnd():
             print("Circuit check failed: No path to ground for some nets. Cannot solve.")
             return None # Or raise error
        if not top_instance.check_voltage_loop():
             print("Circuit check failed: Voltage loop detected. Cannot solve with basic MNA.")
             return None # Or raise error

        # Note: The original SymbolicCircuitProblemSolver also calls top_instance.solve() (symbolic) here.
        # This step is crucial as it populates internal symbolic solution structures within the instance
        # that element_obj.get_numerical_dc_value might rely on if parameters are expressions
        # involving node voltages or other symbols solved by the symbolic part.
        # For a purely numerical MNA from a fully defined netlist (no symbolic params to solve first),
        # this might not be strictly needed if get_numerical_dc_value only uses .PARAM values.
        # However, to be safe and align with how elements get their values (which might be symbolic
        # expressions derived from the circuit's symbolic solution), we should call it.
        top_instance.solve()


    except FileNotFoundError:
        print(f"Error: Netlist file not found at {netlist_path}")
        return None
    except scs_errors.ScsParserError as e:
        print(f"Parser Error: {e}")
        return None
    except scs_errors.ScsInstanceError as e:
        print(f"Instance Error: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during parsing or instancing: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        return None

    # If all successful, call the instance solver
    return solve_dc_numerically_from_instance(top_instance, param_values)

if __name__ == '__main__':
    import os
    import sys

    # Adjust sys.path to allow relative imports of package components
    # This assumes the script is in symbolic_circuit_solver_master/
    # and the package root is symbolic_circuit_solver_master's parent.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    if project_root not in sys.path: # Avoid adding duplicate paths
        sys.path.insert(0, project_root)

    # After path adjustment, the top-level imports in this file should work when run as a script.
    # No need to re-import within __main__.

    print("--- Running DC Numerical Solver Tests ---")

    # Test Case 1: Simple Voltage Divider
    test_netlist_divider_content = """
* Simple DC Test Circuit - Voltage Divider
V1 N1 0 10
R1 N1 N2 1000
R2 N2 0 1000
.end
"""
    test_netlist_divider_filename = "temp_test_divider.sp"
    try:
        with open(test_netlist_divider_filename, 'w') as f: f.write(test_netlist_divider_content)
        print(f"\n--- Test Case 1: Voltage Divider ---")
        results_divider = solve_dc_numerically(test_netlist_divider_filename, {})
        if results_divider:
            print("  Simulation Results (Divider):")
            for key, value in sorted(results_divider.items()):
                if key == 'element_currents': print(f"    Currents: {{ {', '.join([f'{k2}: {v2:.6f}' for k2, v2 in sorted(value.items())])} }}")
                elif isinstance(value, float): print(f"    {key}: {value:.6f}")
                else: print(f"    {key}: {value}")
            print("  Expected (Divider): V(N1)=10.0, V(N2)=5.0, I(V1)=-0.005, I(R1)=0.005, I(R2)=0.005")
        else: print("  Solver did not return results for Test Case 1.")
    finally:
        if os.path.exists(test_netlist_divider_filename): os.remove(test_netlist_divider_filename)
        print(f"  Cleaned up {test_netlist_divider_filename}.")

    # Test Case 2: VCVS
    test_netlist_vcvs_content = """
* VCVS Test Circuit
V_in N_in 0 1.0
R_sense N_in N_sense 1000
R_ground N_sense 0 1000 ; V(N_sense) = 0.5 * V(N_in) = 0.5V
E_vcvs N_out 0 N_sense 0 2.0 ; V(N_out) = 2 * V(N_sense)
R_load N_out 0 1000
.end
"""
    test_netlist_vcvs_filename = "temp_test_vcvs.sp"
    try:
        with open(test_netlist_vcvs_filename, 'w') as f: f.write(test_netlist_vcvs_content)
        print(f"\n--- Test Case 2: VCVS ---")
        results_vcvs = solve_dc_numerically(test_netlist_vcvs_filename, {})
        if results_vcvs:
            print("  Simulation Results (VCVS):")
            for key, value in sorted(results_vcvs.items()):
                if key == 'element_currents': print(f"    Currents: {{ {', '.join([f'{k2}: {v2:.6f}' for k2, v2 in sorted(value.items())])} }}")
                elif isinstance(value, float): print(f"    {key}: {value:.6f}")
                else: print(f"    {key}: {value}")
            print("  Expected (VCVS): V(N_in)=1.0, V(N_sense)=0.5, V(N_out)=1.0, I(E_vcvs)=-0.001, I(V_in)=-0.0005")
        else: print("  Solver did not return results for Test Case 2.")
    finally:
        if os.path.exists(test_netlist_vcvs_filename): os.remove(test_netlist_vcvs_filename)
        print(f"  Cleaned up {test_netlist_vcvs_filename}.")

    # Test Case 3: VCCS
    test_netlist_vccs_content = """
* VCCS Test Circuit
V_in N_ctrl 0 1.0 ; Control voltage V(N_ctrl) = 1V
R_dummy N_ctrl 0 1k ; Dummy load for V_in
G_vccs N_out 0 N_ctrl 0 0.01 ; I(G_vccs) from N_out to 0 is 0.01 * V(N_ctrl)
R_load N_out 0 100
.end
"""
    test_netlist_vccs_filename = "temp_test_vccs.sp"
    try:
        with open(test_netlist_vccs_filename, 'w') as f: f.write(test_netlist_vccs_content)
        print(f"\n--- Test Case 3: VCCS ---")
        results_vccs_sim = solve_dc_numerically(test_netlist_vccs_filename, {})
        if results_vccs_sim:
            print("  Simulation Results (VCCS):")
            for key, value in sorted(results_vccs_sim.items()):
                if key == 'element_currents': print(f"    Currents: {{ {', '.join([f'{k2}: {v2:.6f}' for k2, v2 in sorted(value.items())])} }}")
                elif isinstance(value, float): print(f"    {key}: {value:.6f}")
                else: print(f"    {key}: {value}")
            print("  Expected (VCCS): V(N_ctrl)=1.0, V(N_out)=1.0, I(V_in)=-0.001")
        else: print("  Solver did not return results for Test Case 3.")
    finally:
        if os.path.exists(test_netlist_vccs_filename): os.remove(test_netlist_vccs_filename)
        print(f"  Cleaned up {test_netlist_vccs_filename}.")

    # Test Case 4: CCVS
    test_netlist_ccvs_content = """
* CCVS Test Circuit
V_drive N_in 0 1.0
R_sense N_in N_sense 100
V_dummy N_sense 0 0
H_ccvs N_out 0 V_dummy 50
R_load N_out 0 1000
.end
"""
    test_netlist_ccvs_filename = "temp_test_ccvs.sp"
    try:
        with open(test_netlist_ccvs_filename, 'w') as f: f.write(test_netlist_ccvs_content)
        print(f"\n--- Test Case 4: CCVS ---")
        results_ccvs_sim = solve_dc_numerically(test_netlist_ccvs_filename, {})
        if results_ccvs_sim:
            print("  Simulation Results (CCVS):")
            for key, value in sorted(results_ccvs_sim.items()):
                if key == 'element_currents': print(f"    Currents: {{ {', '.join([f'{k2}: {v2:.6f}' for k2, v2 in sorted(value.items())])} }}")
                elif isinstance(value, float): print(f"    {key}: {value:.6f}")
                else: print(f"    {key}: {value}")
            # V_drive=1V. V(N_in)=1V. V(N_sense)=0V (due to V_dummy).
            # I(V_dummy) = (V(N_in) - V(N_sense)) / R_sense = (1-0)/100 = 0.01A. (Current flows into N_sense from N_in, so out of V_dummy's positive terminal)
            # So, the current variable for V_dummy in MNA should be -0.01A.
            # V(N_out) = H_ccvs_gain * I(V_dummy) = 50 * (-0.01A) = -0.5V.
            # Let's check SPICE sign convention for H element current.
            # If H_ccvs uses current flowing V_dummy from positive to negative terminal as positive, then I(V_dummy) in MNA is positive if it flows that way.
            # Current through R_sense: (N_in -> N_sense) = 0.01A. V_dummy is (N_sense -> 0). Current flows out of V_dummy's N_sense node.
            # Standard MNA for Vsource: Current I_vsource flows from its + to its - terminal.
            # Current through R_sense: (N_in -> N_sense) is (1V-0V)/100ohm = 0.01A.
            # This 0.01A current flows from N_sense (V_dummy's +) to 0 (V_dummy's -). So I(V_dummy) = +0.01A.
            # V(N_out) = H_ccvs_gain * I(V_dummy) = 50 * 0.01A = 0.5V.
            # Current I(H_ccvs) (defined as flowing from N_out to 0 for H_ccvs) = V(N_out)/R_load = 0.5V/1k = 0.0005A.
            # The MNA variable I(H_ccvs) is defined as current entering N_out from H_ccvs. So, it should be -0.0005A.
            print("  Expected (CCVS): V(N_in)=1.0, V(N_sense)=0.0, V(N_out)=0.5, I(V_dummy)=0.01, I(H_ccvs)=-0.0005")
        else: print("  Solver did not return results for Test Case 4.")
    finally:
        if os.path.exists(test_netlist_ccvs_filename): os.remove(test_netlist_ccvs_filename)
        print(f"  Cleaned up {test_netlist_ccvs_filename}.")

    # Test Case 5: CCCS
    test_netlist_cccs_content = """
* CCCS Test Circuit
V_drive N_in 0 1.0
R_sense N_in N_sense 100 ; I through R_sense (and V_dummy) = 1V / 100ohm = 0.01A
V_dummy N_sense 0 0 ; Zero-volt source to measure current for F_cccs
F_cccs N_out 0 V_dummy 10 ; I(F_cccs) from N_out to 0 is 10 * I(V_dummy)
R_load N_out 0 1000
.end
"""
    test_netlist_cccs_filename = "temp_test_cccs.sp"
    try:
        with open(test_netlist_cccs_filename, 'w') as f: f.write(test_netlist_cccs_content)
        print(f"\n--- Test Case 5: CCCS ---")
        results_cccs_sim = solve_dc_numerically(test_netlist_cccs_filename, {})
        if results_cccs_sim:
            print("  Simulation Results (CCCS):")
            for key, value in sorted(results_cccs_sim.items()):
                if key == 'element_currents': print(f"    Currents: {{ {', '.join([f'{k2}: {v2:.6f}' for k2, v2 in sorted(value.items())])} }}")
                elif isinstance(value, float): print(f"    {key}: {value:.6f}")
                else: print(f"    {key}: {value}")
            # I(V_dummy) = 0.01A (as in CCVS case, current from N_sense to 0).
            # I_F_cccs = 10 * I(V_dummy) = 10 * 0.01A = 0.1A. This current flows from N_out to 0.
            # V(N_out) = I_F_cccs * R_load = 0.1A * 1000ohm = 100V.
            # (Note: I(F_cccs) is not a variable in MNA, its effect is on KCL at N_out and 0)
            print("  Expected (CCCS): V(N_in)=1.0, V(N_sense)=0.0, V(N_out)=100.0, I(V_dummy)=0.01")
        else: print("  Solver did not return results for Test Case 5.")
    finally:
        if os.path.exists(test_netlist_cccs_filename): os.remove(test_netlist_cccs_filename)
        print(f"  Cleaned up {test_netlist_cccs_filename}.")

    print("\nAll tests finished.")
