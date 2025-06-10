import numpy as np
import sympy # May be needed for type checking or symbol manipulation
from .scs_instance_hier import Instance # Assuming Instance is in scs_instance_hier
from .scs_elements import ( # Reverted to specific imports
    Resistor, VoltageSource, CurrentSource,
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
        if isinstance(element_obj, Resistor): # Directly connected nets
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
    # Controlled sources inherit from VoltageSource/CurrentSource but have more specific types.
    for el_name, element_obj in instance.elements.items():
        if type(element_obj) is VoltageSource: # Exact type check for independent V source
            v_sources_list.append(element_obj)

    num_voltage_sources = len(v_sources_list)

    matrix_size = num_nodes + num_voltage_sources

    if num_nodes == 0 and num_voltage_sources == 0 : # Handle empty or ground-only circuits
         print("Warning: No non-ground nodes and no voltage sources found for MNA matrix.")
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
        if isinstance(element_obj, Resistor):
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

        elif type(element_obj) is VoltageSource: # Independent Voltage Source
            # This check should be specific enough not to catch controlled sources if they are checked first.
            v_val = element_obj.get_numerical_dc_value(param_values)
            if not isinstance(v_val, (float, int)):
                print(f"Warning: Could not get valid numerical value for VoltageSource {el_name}. Value: {v_val}. Skipping.")
                continue

            n1_name, n2_name = element_obj.nets[0], element_obj.nets[1] # Positive, Negative
            current_idx = vsource_to_current_idx[element_obj.names[0]]

            # Stamps for the KCL equations (rows 0 to num_nodes-1)
            if n1_name != '0':
                A_num[node_to_index[n1_name], current_idx] += 1.0
            if n2_name != '0':
                A_num[node_to_index[n2_name], current_idx] -= 1.0

            # Stamps for the voltage source's own equation (row current_idx)
            # V_n1 - V_n2 = v_val  =>  1*V_n1 - 1*V_n2 - v_val = 0
            # So, in A_num * x = z_num, the row is [..., 1, ..., -1, ...] * [..., V_n1, ..., V_n2, ...]^T = v_val
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

            # Current flowing OUT of n1, INTO n2
            if n1_name != '0':
                z_num[node_to_index[n1_name]] -= i_val # Current leaving n1
            if n2_name != '0':
                z_num[node_to_index[n2_name]] += i_val # Current entering n2

        # TODO: Add elif blocks for controlled sources (VCVS, VCCS, CCVS, CCCS)
        # Their isinstance checks should be more specific than base VoltageSource/CurrentSource
        # and ideally come before the checks for independent sources if there's ambiguity.
        # However, using type() as above for independent sources makes it less ambiguous.

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

        # Currents through voltage sources
        for v_name, index in vsource_to_current_idx.items():
            results_dict[f"I({v_name})"] = solution_vector[index]

        return results_dict
    except np.linalg.LinAlgError:
        print(f"Error: Singular matrix (determinant is zero). Circuit may be ill-defined for DC analysis (e.g., floating parts, redundant voltage sources, or unstable). A_matrix:\n{A_num}\nz_vector:\n{z_num}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during numerical solution: {e}")
        return None

# Need to import the main solver tool to parse netlists
from .scs_symbolic_solver_tool import SymbolicCircuitProblemSolver

def solve_dc_numerically(netlist_path: str, param_values: dict):
    """
    Parses a netlist file, builds the numerical MNA matrices, solves for DC operating point,
    and returns node voltages and currents through independent voltage sources.
    """
    try:
        # Instantiate the solver tool.
        solver = SymbolicCircuitProblemSolver(netlist_path=netlist_path)

        # Trigger parsing and instance creation, which also does base symbolic solve.
        # This populates solver.top_circuit and solver.top_instance.
        solver._parse_and_solve_base_circuit() # Call the internal method

        # Now check if top_circuit and top_instance were successfully created
        if not solver.top_circuit:
            print(f"Error: SymbolicCircuitProblemSolver failed to parse top_circuit from {netlist_path}.")
            return None

        if not solver.top_instance:
            print(f"Error: SymbolicCircuitProblemSolver failed to create top_instance from {netlist_path}.")
            if hasattr(solver, 'last_error') and solver.last_error: # Check if solver tool stores errors
                 print(f"Solver's last error: {solver.last_error}")
            return None

    except FileNotFoundError:
        print(f"Error: Netlist file not found at {netlist_path}")
        return None
    except Exception as e: # Catch other parsing related errors
        print(f"Error during netlist parsing or solver instantiation: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        return None

    # This check is now somewhat redundant due to the more specific one above, but kept for safety.
    if not solver.top_instance:
        print("Error: Could not create top_instance from netlist (final check).")
        return None

    # The instance from SymbolicCircuitProblemSolver should be suitable.
    # It's typically the top-level, and element parameters are evaluated.
    # `build_numerical_mna` expects symbolic parameters to be substituted by `param_values`
    # if they are passed in that way. The `SymbolicCircuitProblemSolver` usually creates
    # `self.top_instance.elements` where values are already Sympy expressions or numbers.
    # The `param_values` dict passed here would be for overriding or defining symbols
    # that were part of `.PARAM` lines and are meant to be variable at this stage.
    return solve_dc_numerically_from_instance(solver.top_instance, param_values)

if __name__ == '__main__':
    import os
    import sys

    # Adjust sys.path to allow relative imports of package components
    # This assumes the script is in symbolic_circuit_solver_master/
    # and the package root is symbolic_circuit_solver_master's parent.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    sys.path.insert(0, project_root) # Add parent directory (e.g. /app) to path

    # Now that sys.path is adjusted, re-attempt local imports if they failed for __main__
    # This is a bit of a hack for direct script execution. Ideally, run as part of the package.
    # The imports at the top of the file should now work if this script is run directly.
    # Re-importing here is not standard but can ensure components are loaded after path change.
    # from .scs_symbolic_solver_tool import SymbolicCircuitProblemSolver # Already imported above

    print("Running simple DC numerical solver test...")

    # Define a simple netlist as a string
    test_netlist_content = """
* Simple DC Test Circuit
V1 N1 0 10
R1 N1 N2 1000
R2 N2 0 1000
.end
* End of netlist
"""
    test_netlist_filename = "temp_test_netlist.sp"

    try:
        with open(test_netlist_filename, 'w') as f:
            f.write(test_netlist_content)

        # Define parameter values (empty for this netlist as all values are explicit)
        param_values_test = {}

        print(f"Attempting to solve netlist: {test_netlist_filename}")
        results = solve_dc_numerically(test_netlist_filename, param_values_test)

        if results:
            print("\n--- Simulation Results ---")
            for key, value in results.items():
                if isinstance(value, float):
                    print(f"{key}: {value:.6f}")
                else:
                    print(f"{key}: {value}")

            # Expected results for this circuit:
            # V(N1) = 10V (due to V1)
            # V(N2) = 5V (voltage divider R1, R2)
            # I(V1) = - (10V / (1k + 1k)) = -0.005A = -5mA (current flowing out of V1's positive terminal)
            print("\n--- Expected Results (approx) ---")
            print("V(N1): 10.000000")
            print("V(N2): 5.000000")
            print("I(V1): -0.005000")

        else:
            print("Solver did not return results.")

    finally:
        # Clean up the temporary netlist file
        if os.path.exists(test_netlist_filename):
            os.remove(test_netlist_filename)
        print(f"\nCleaned up {test_netlist_filename}.")

    print("\nTest finished.")
