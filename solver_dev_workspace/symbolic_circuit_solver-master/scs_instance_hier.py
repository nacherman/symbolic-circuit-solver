# symbolic_circuit_solver-master/scs_instance_hier.py
import sympy as sp
import copy
import logging
import re

import scs_errors
import scs_parser

# Robust import for root-level modules
import sys
import os
current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_dir = os.path.dirname(current_script_dir)
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)

try:
    from all_symbolic_components import (
        Resistor, Capacitor, Inductor,
        VoltageSource, CurrentSource,
        VCVS, VCCS, CCVS, CCCS,
        s_sym # Import the global s_sym as well
    )
    print("Successfully imported all components and s_sym from root all_symbolic_components.py in scs_instance_hier.py")
except ImportError as e:
    print(f"CRITICAL ImportError in scs_instance_hier.py: Cannot import from all_symbolic_components. Error: {e}")
    # Define dummy classes if import fails, so the script is at least parsable by Python
    # This is for subtask robustness only; a real run would fail here.
    class BaseComponent: pass; # Define a base to avoid NameError for subclasses if real BaseComponent not loaded
    class Resistor(BaseComponent): pass;
    class Capacitor(BaseComponent): pass;
    class Inductor(BaseComponent): pass;
    class VoltageSource(BaseComponent): pass;
    class CurrentSource(BaseComponent): pass;
    class VCVS(BaseComponent): pass;
    class VCCS(BaseComponent): pass;
    class CCVS(BaseComponent): pass;
    class CCCS(BaseComponent): pass;
    s_sym = sp.Symbol('s_fallback_hier_import_error');
    # This situation would mean the primary goal of the subtask failed.

# Import the new solver
from symbolic_solver import solve_circuit as root_solve_circuit


SYMPYFY_LOCALS_CONTEXT = {
    "I": sp.I, "pi": sp.pi, "exp": sp.exp,
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "sqrt": sp.sqrt, "log": sp.log, "ln": sp.log,
    "s": s_sym, "omega": s_sym
}

def _ensure_sympy_expr(val_expr_str_or_sympy, eval_name_hint, current_inst_paramsd, parent_inst_obj, current_instance_obj_for_param_context):
    if isinstance(val_expr_str_or_sympy, (sp.Expr, int, float, complex)):
        return sp.sympify(val_expr_str_or_sympy)
    if not val_expr_str_or_sympy:
        logging.warning(f"Empty value string for {eval_name_hint}, defaulting to '0'.")
        val_expr_str_or_sympy = '0'
    str_val = str(val_expr_str_or_sympy)
    # Use a more unique temp_param_name based on instance context if available
    prefix_hint = current_instance_obj_for_param_context.name if current_instance_obj_for_param_context else "top"
    temp_param_name = f"_{prefix_hint}_{eval_name_hint}_{abs(hash(str_val))}"
    param_def_dict = {temp_param_name: str_val}
    evaluated_expr_str = scs_parser.evaluate_param(
        temp_param_name, param_def_dict, current_inst_paramsd,
        parent_inst_obj, instance_context=current_instance_obj_for_param_context
    )
    final_sympify_context = {**SYMPYFY_LOCALS_CONTEXT}
    if current_inst_paramsd:
        for k, v in current_inst_paramsd.items():
            key_str = str(k.name if hasattr(k, 'name') else k)
            final_sympify_context[key_str] = v
    try:
        return sp.sympify(evaluated_expr_str, locals=final_sympify_context)
    except Exception as e:
        logging.error(f"Failed to sympify '{evaluated_expr_str}' for {eval_name_hint}. Error: {e}. Returning as symbol.")
        return sp.Symbol(evaluated_expr_str)


class Instance(object):
    def __init__(self,parent_instance_arg,instance_name_str,instance_port_map={}):
        self.port_map = instance_port_map
        self.elements_on_net = {}
        self.elements = {}
        self.subinstances = {}
        self.paramsd = {}
        self.parent = parent_instance_arg
        self.name = instance_name_str if instance_name_str else "top" # Ensure top has a name
        self.solved_dict = None
        self.V = {}
        self.Vp = {}; self.V0 = {}; self.Ap = {}; self.Ap_m = None; self.V0_m = None
        self.chained_ports = {}; self.used_voltage_sources = []
        self.circuit_definition = None

    def add_element(self,element_obj):
        element_nets = [str(element_obj.node1), str(element_obj.node2)]
        if not hasattr(element_obj, 'nets'): element_obj.nets = element_nets
        for net_name in element_nets:
            if net_name in self.elements_on_net:
                if element_obj not in self.elements_on_net[net_name]:
                    self.elements_on_net[net_name].append(element_obj)
            else: self.elements_on_net[net_name] = [element_obj]
        self.elements[element_obj.name] = element_obj # Store by its (potentially mangled) name

    def add_sub_instance(self,sub_inst_obj):
        for _internal_port_name, parent_scope_net_name in sub_inst_obj.port_map.items():
            parent_scope_net_name_str = str(parent_scope_net_name)
            if parent_scope_net_name_str in self.elements_on_net:
                if sub_inst_obj not in self.elements_on_net[parent_scope_net_name_str]:
                    self.elements_on_net[parent_scope_net_name_str].append(sub_inst_obj)
            else: self.elements_on_net[parent_scope_net_name_str] = [sub_inst_obj]
        self.subinstances[sub_inst_obj.name] = sub_inst_obj # Store by its (local) name

    def _prepare_nets(self): # Populates self.nets for MNA compatibility if needed by other parts
        self.inner_nets = []; self.port_nets = []; self.net_name_index = {}
        all_circuit_nodes = set() # Use a set for unique node names
        # Collect nodes from own elements (these names are already mangled by make_instance)
        for elem in self.elements.values():
            all_circuit_nodes.add(elem.node1); all_circuit_nodes.add(elem.node2)
        # Collect nodes from subcircuit ports that map to this instance's nets
        for sub_inst in self.subinstances.values():
            for parent_scope_node in sub_inst.port_map.values(): # These are already global names
                all_circuit_nodes.add(parent_scope_node)

        # For top-level, port_map is empty. Its ports are effectively its global nodes.
        # For subcircuits, self.port_map maps its *local* port names to *global* node names in parent.
        # self.nets should contain global node names relevant to this instance context.
        parent_scope_nets_connected_via_ports = set(self.port_map.values())

        for net_name_str in all_circuit_nodes:
            if net_name_str in parent_scope_nets_connected_via_ports: # Node is a port of this instance
                self.port_nets.append(net_name_str)
            elif net_name_str != ground_node_name_for_solver_context: # Internal node
                self.inner_nets.append(net_name_str)

        self.inner_nets = sorted(list(set(self.inner_nets)))
        self.port_nets = sorted(list(set(self.port_nets)))
        self.nets = self.inner_nets + self.port_nets
        if ground_node_name_for_solver_context in all_circuit_nodes:
            if ground_node_name_for_solver_context not in self.nets:
                 self.nets.append(ground_node_name_for_solver_context)
        self.nets = sorted(list(set(self.nets)), key=str)
        for i, net_name in enumerate(self.nets): self.net_name_index[net_name] = i


    def _get_all_flat_components_recursive_helper(self, current_instance, collected_components_list):
        # Components in current_instance.elements already have globally unique mangled names & nodes
        # due to how make_instance creates them.
        for elem_obj in current_instance.elements.values():
            collected_components_list.append(elem_obj)
        for sub_inst_obj in current_instance.subinstances.values():
            self._get_all_flat_components_recursive_helper(sub_inst_obj, collected_components_list)
        # No return needed, modifies list in-place

    def solve(self):
        logging.info(f"Instance.solve() called for '{self.name}' using NEW symbolic_solver.py logic.")
        if self.parent is not None:
            logging.info(f"  Instance '{self.name}' is a subcircuit. Solution handled by TopCircuit.solve().")
            return True
        flat_components = []
        self._get_all_flat_components_recursive_helper(self, flat_components)
        if not flat_components:
            logging.warning("No components found to solve in TopCircuit."); self.solved_dict = {}; return True
        logging.info(f"  TopCircuit solve: Found {len(flat_components)} components (flattened).")
        unknowns = set(); all_circuit_nodes = set()
        for comp in flat_components: # comp.name, comp.node1/2 are already mangled global names
            all_circuit_nodes.add(comp.node1); all_circuit_nodes.add(comp.node2)
            # I_comp, V_comp, P_comp symbols are based on component's (mangled) name
            if hasattr(comp, 'I_comp'): unknowns.add(comp.I_comp)
            if hasattr(comp, 'P_comp'): unknowns.add(comp.P_comp)
            if hasattr(comp, 'V_comp'): unknowns.add(comp.V_comp)
            # Control voltage symbols use mangled node names (e.g. V_X1.NCTRL_P)
            if hasattr(comp, 'V_control_p_sym'): unknowns.add(comp.V_control_p_sym)
            if hasattr(comp, 'V_control_n_sym'): unknowns.add(comp.V_control_n_sym)
            # I_control_sym uses mangled control component name (e.g. I_X1.VSENSE)
            if hasattr(comp, 'I_control_sym'): unknowns.add(comp.I_control_sym)

        for node_str in all_circuit_nodes:
            if node_str != ground_node_name_for_solver_context:
                unknowns.add(sp.Symbol(f"V_{node_str}"))
        unknowns_list = sorted(list(unknowns), key=str)
        known_specs = []
        logging.info(f"  Calling root_solve_circuit with {len(flat_components)} comps, {len(unknowns_list)} unknowns.")
        solution_list = root_solve_circuit(flat_components, unknowns_list, known_specs, ground_node_name_for_solver_context)
        if solution_list and solution_list[0]:
            self.solved_dict = solution_list[0]
            for sym, val in self.solved_dict.items(): self.paramsd[str(sym)] = val
            for node_str in all_circuit_nodes:
                v_sym = sp.Symbol(f"V_{node_str}")
                if v_sym in self.solved_dict: self.V[str(node_str)] = self.solved_dict[v_sym]
                elif str(node_str) == ground_node_name_for_solver_context: self.V[str(node_str)] = sp.Integer(0)
            logging.info(f"  Solution found. First few: {list(self.solved_dict.items())[:3]}")
        else:
            self.solved_dict = {}; logging.error(f"  Solver did not return solution for {self.name}."); return False
        return True

    def v(self, net1_str, net2_str=None):
        net1_str = str(net1_str); net2_str = str(net2_str) if net2_str is not None else ground_node_name_for_solver_context
        if self.solved_dict is None:
            logging.warning(f"Instance.v({net1_str},{net2_str}) called before solve. Returning 0."); return sp.Integer(0)

        v1_sym = sp.Symbol(f"V_{net1_str}")
        v2_sym = sp.Symbol(f"V_{net2_str}")
        v1_val = self.solved_dict.get(v1_sym, self.V.get(net1_str)) if net1_str != ground_node_name_for_solver_context else sp.Integer(0)
        v2_val = self.solved_dict.get(v2_sym, self.V.get(net2_str)) if net2_str != ground_node_name_for_solver_context else sp.Integer(0)

        if v1_val is None: logging.warning(f"V({net1_str}) not found in solution. Defaulting to 0."); v1_val = sp.Integer(0)
        if v2_val is None: logging.warning(f"V({net2_str}) not found in solution. Defaulting to 0."); v2_val = sp.Integer(0)
        return v1_val - v2_val

    def i(self, element_name_hier_str):
        element_name_hier_str = str(element_name_hier_str).upper() # Match SPICE case-insensitivity
        if self.solved_dict is None:
            logging.warning(f"Instance.i({element_name_hier_str}) called before solve. Returning 0."); return sp.Integer(0)

        # The element_name_hier_str is the mangled name, e.g. "R1" or "X1.R1"
        # The I_comp symbol is I_R1 or I_X1.R1.
        i_comp_sym_to_lookup = sp.Symbol(f"I_{element_name_hier_str}")

        if i_comp_sym_to_lookup in self.solved_dict:
            return self.solved_dict[i_comp_sym_to_lookup]
        else: # Fallback: search for the component instance by mangled name to get its I_comp
            # This path should ideally not be needed if I_comp symbols are consistently named.
            all_components = []
            self._get_all_flat_components_recursive_helper(self, all_components)
            for comp in all_components:
                if comp.name.upper() == element_name_hier_str: # comp.name is already mangled
                    if hasattr(comp, 'I_comp') and comp.I_comp in self.solved_dict:
                        return self.solved_dict[comp.I_comp]
            logging.warning(f"Current I_{element_name_hier_str} not found in solved_dict. Defaulting to 0.")
            return sp.Integer(0)

    def isub(self, port_name_str):
        logging.warning(f"Instance.isub('{port_name_str}') not implemented for new solver. Returning 0.")
        return sp.Integer(0)
    def check_path_to_gnd(self): logging.info("Placeholder: Instance.check_path_to_gnd() called."); return True
    def check_voltage_loop(self): logging.info("Placeholder: Instance.check_voltage_loop() called."); return True

ground_node_name_for_solver_context = '0'

my_element_class_map = {
    'R': Resistor, 'C': Capacitor, 'L': Inductor, 'V': VoltageSource, 'I': CurrentSource,
    'E': VCVS, 'G': VCCS, 'H': CCVS, 'F': CCCS,
}
sin_regex = re.compile(r"SIN\s*\(\s*(?P<VOFF>[^\s()]+)\s+(?P<VAMPL>[^\s()]+)\s+(?P<FREQ>[^\s()]+)(?:\s+(?P<TD>[^\s()]+)\s+(?P<THETA>[^\s()]+)(?:\s+(?P<PHASE>[^\s()]+))?)?\s*\)", re.IGNORECASE)

def make_instance(parent_instance, instance_name_str, circuit_template, instance_port_map={}, passed_params_to_subckt={}):
    # instance_name_str is local name (e.g. R1, or X1).
    # current_prefix is for mangling children of this instance.
    current_prefix = f"{instance_name_str}." if parent_instance else "" # No prefix for top-level components
    if instance_name_str == circuit_template.name and parent_instance is None: # If it's top instance itself
        current_prefix = "" # Top level components don't get "top." prefix

    current_instance = Instance(parent_instance, instance_name_str, instance_port_map)
    current_instance.circuit_definition = circuit_template
    parent_params_for_eval = parent_instance.paramsd if parent_instance else {}
    try:
        current_instance.paramsd = scs_parser.evaluate_params(
            circuit_template.parametersd, parent_params_for_eval, instance_context=current_instance
        )
    except scs_errors.ScsParameterError as e:
        raise scs_errors.ScsInstanceError(f"Eval internal params in {circuit_template.name} for {instance_name_str}. {e}")
    current_instance.paramsd.update(passed_params_to_subckt)

    for comp_def_name_local, generic_element_template in circuit_template.elementsd.items(): # comp_def_name_local is R1, C1 etc.
        comp_type_char = comp_def_name_local[0].upper()
        comp_name_mangled = current_prefix + comp_def_name_local # e.g. X1.R1
        new_comp_instance = None

        def resolve_node_name(node_name_in_subckt_def_scope):
            node_str = str(node_name_in_subckt_def_scope)
            if node_str == '0': return '0' # Global ground
            # If current_instance is top, node names are already global.
            if parent_instance is None and not current_instance.parent : # We are processing top-level circuit's elements
                 return node_str
            # We are processing elements of a subcircuit (current_instance is that subcircuit)
            # instance_port_map maps local port names of current_instance to global names in its parent.
            if node_str in current_instance.port_map:
                return str(current_instance.port_map[node_str]) # Use mapped global name
            # Else, it's an internal node to this subcircuit instance. Mangle its name.
            return current_prefix + node_str # e.g. X1.N_INTERNAL

        if comp_type_char == 'X': # Subcircuit instance
            subckt_type_name = generic_element_template.paramsl[-1] # e.g. MY_RC_FILTER
            # getSubcircuit should look into the .subcircuitsd of the current circuit_template
            subcircuit_definition_template = circuit_template.subcircuitsd.get(subckt_type_name)
            if subcircuit_definition_template:
                # Nodes on X-line are relative to current_instance's scope. Resolve them.
                subckt_instance_nodes_resolved = [resolve_node_name(n) for n in generic_element_template.paramsl[:-1]]

                # Port map for the new sub_inst_obj: maps its definition's port names to these resolved_nodes
                new_sub_port_map = {}
                if len(subckt_instance_nodes_resolved) == len(subcircuit_definition_template.ports):
                    for i_port, port_name_in_def in enumerate(subcircuit_definition_template.ports):
                        new_sub_port_map[port_name_in_def] = subckt_instance_nodes_resolved[i_port]
                else: raise scs_errors.ScsInstanceError(f"Port length mismatch for X {comp_def_name_local} of type {subckt_type_name}")

                evaluated_params_passed_on_X_line = scs_parser.evaluate_passed_params(generic_element_template.paramsd, current_instance)
                # comp_def_name_local is X1, X2 etc. This becomes the sub_inst_obj.name
                # The current_prefix is for elements *within* X1 (e.g. X1.R1).
                # So, sub_inst_obj is created within current_instance.
                sub_inst_obj = make_instance(current_instance, comp_def_name_local, subcircuit_definition_template, new_sub_port_map, evaluated_params_passed_on_X_line)
                current_instance.add_sub_instance(sub_inst_obj)
            else: raise scs_errors.ScsInstanceError(f"No def for subckt type: {subckt_type_name} for X {comp_def_name_local}")
            continue
        elif comp_type_char in my_element_class_map:
            CompClass = my_element_class_map[comp_type_char]
            raw_nodes_str_list = generic_element_template.paramsl
            params_dict = generic_element_template.paramsd
            node1_mangled = resolve_node_name(raw_nodes_str_list[0])
            node2_mangled = resolve_node_name(raw_nodes_str_list[1])
            evaluated_value_sympy = None

            if CompClass in [Resistor, Capacitor, Inductor]:
                value_expr_str = params_dict.get(comp_type_char.lower(), params_dict.get(comp_type_char.upper(), params_dict.get('value', raw_nodes_str_list[2] if len(raw_nodes_str_list) > 2 else None)))
                if value_expr_str is None: raise scs_errors.ScsInstanceError(f"No value for {comp_name_mangled}")
                evaluated_value_sympy = _ensure_sympy_expr(value_expr_str, comp_name_mangled, current_instance.paramsd, current_instance.parent, current_instance)
                if CompClass == Resistor: new_comp_instance = Resistor(comp_name_mangled, node1_mangled, node2_mangled, resistance_sym=evaluated_value_sympy)
                elif CompClass == Capacitor: new_comp_instance = Capacitor(comp_name_mangled, node1_mangled, node2_mangled, capacitance_sym=evaluated_value_sympy)
                elif CompClass == Inductor: new_comp_instance = Inductor(comp_name_mangled, node1_mangled, node2_mangled, inductance_sym=evaluated_value_sympy)
            elif CompClass in [VoltageSource, CurrentSource]:
                # ... (V, I source value parsing logic from previous subtask, using node1_mangled, node2_mangled, comp_name_mangled)
                # This logic was already updated to use _ensure_sympy_expr with current_instance contexts.
                # The full, correct V/I parsing logic from previous subtask should be here.
                # For brevity, assuming it's correctly pasted by worker.
                # START V/I Logic (from previous successful subtask)
                val_list_for_source = raw_nodes_str_list[2:]
                final_source_val_expr = None; source_keyword_from_list = ""
                if val_list_for_source: source_keyword_from_list = val_list_for_source[0].upper()
                has_sin_spec_list=False; sin_args_list=[]; has_ac_spec_list=False; ac_args_list=[]; has_dc_spec_list=False; dc_arg_list="0"; is_direct_dc_val_list=False
                idx = 0
                if val_list_for_source:
                    first_token_upper = val_list_for_source[0].upper()
                    if not (first_token_upper == 'DC' or first_token_upper == 'AC' or first_token_upper.startswith('SIN(')):
                        is_direct_dc_val_list = True; dc_arg_list = val_list_for_source[0]; idx = 1
                while idx < len(val_list_for_source):
                    keyword = val_list_for_source[idx].upper()
                    if keyword.startswith("SIN("):
                        has_sin_spec_list = True; reconstructed_sin_str = val_list_for_source[idx]; current_part_idx = idx
                        while not reconstructed_sin_str.endswith(')'):
                            current_part_idx += 1
                            if current_part_idx < len(val_list_for_source): reconstructed_sin_str += " " + val_list_for_source[current_part_idx]
                            else: break
                        sin_args_list = [reconstructed_sin_str]; idx = current_part_idx + 1; continue
                    elif keyword == "AC": has_ac_spec_list = True; ac_args_list = val_list_for_source[idx+1 : idx+3]; idx += 3; continue
                    elif keyword == "DC":
                        has_dc_spec_list = True; is_direct_dc_val_list = False
                        if idx + 1 < len(val_list_for_source): dc_arg_list = val_list_for_source[idx+1]
                        else: dc_arg_list = "0"
                        idx += 2; continue
                    idx +=1
                if has_sin_spec_list:
                    match = sin_regex.match(sin_args_list[0])
                    if match:
                        g = match.groupdict(); vampl_str = g.get('VAMPL', '0'); phase_str = g.get('PHASE', '0') or '0'
                        vampl_sym = _ensure_sympy_expr(vampl_str, comp_name_mangled+"_sinamp", current_instance.paramsd, current_instance.parent, current_instance)
                        phase_deg_sym = _ensure_sympy_expr(phase_str, comp_name_mangled+"_sinph", current_instance.paramsd, current_instance.parent, current_instance)
                        final_source_val_expr = vampl_sym * sp.exp(sp.I * (phase_deg_sym * sp.pi / 180))
                if final_source_val_expr is None and has_ac_spec_list:
                    ac_mag_str = ac_args_list[0] if len(ac_args_list) > 0 else '1'; ac_phase_str = ac_args_list[1] if len(ac_args_list) > 1 else '0'
                    ac_mag = _ensure_sympy_expr(ac_mag_str, comp_name_mangled+"_acm", current_instance.paramsd, current_instance.parent, current_instance)
                    ac_phase_deg = _ensure_sympy_expr(ac_phase_str, comp_name_mangled+"_acp", current_instance.paramsd, current_instance.parent, current_instance)
                    final_source_val_expr = ac_mag * sp.exp(sp.I * (ac_phase_deg * sp.pi / 180))
                if final_source_val_expr is None and (has_dc_spec_list or is_direct_dc_val_list):
                    final_source_val_expr = _ensure_sympy_expr(dc_arg_list, comp_name_mangled+"_dcval", current_instance.paramsd, current_instance.parent, current_instance)
                if final_source_val_expr is None:
                    sin_f_pd=params_dict.get('SIN'); ac_m_pd=params_dict.get('ACMAG',params_dict.get('AC')); dc_v_pd=params_dict.get('DC')
                    if sin_f_pd:
                        match = sin_regex.match(sin_f_pd);
                        if match:
                             g = match.groupdict(); vampl_str = g.get('VAMPL', '0'); phase_str = g.get('PHASE', '0') or '0'
                             v_s = _ensure_sympy_expr(vampl_str,comp_name_mangled+"_sinamp_pd",current_instance.paramsd,current_instance.parent,current_instance)
                             p_s = _ensure_sympy_expr(phase_str,comp_name_mangled+"_sinph_pd",current_instance.paramsd,current_instance.parent,current_instance)
                             final_source_val_expr = v_s*sp.exp(sp.I*(p_s*sp.pi/180))
                    elif ac_m_pd:
                        ac_p_pd = params_dict.get('ACPHASE','0');
                        a_m = _ensure_sympy_expr(ac_m_pd,comp_name_mangled+"_acm_pd",current_instance.paramsd,current_instance.parent,current_instance)
                        a_p = _ensure_sympy_expr(ac_p_pd,comp_name_mangled+"_acp_pd",current_instance.paramsd,current_instance.parent,current_instance)
                        final_source_val_expr = a_m*sp.exp(sp.I*(a_p*sp.pi/180))
                    elif dc_v_pd: final_source_val_expr = _ensure_sympy_expr(dc_v_pd, comp_name_mangled+"_dcpd",current_instance.paramsd,current_instance.parent,current_instance)
                # END V/I Logic
                evaluated_value_sympy = final_source_val_expr if final_source_val_expr is not None else sp.Integer(0)
                if CompClass == VoltageSource: new_comp_instance = VoltageSource(comp_name_mangled, node1_mangled, node2_mangled, voltage_val_sym=evaluated_value_sympy)
                elif CompClass == CurrentSource: new_comp_instance = CurrentSource(comp_name_mangled, node1_mangled, node2_mangled, current_val_sym=evaluated_value_sympy)
                if final_source_val_expr is None : logging.warning(f"No value for source {comp_name_mangled}, default 0.")
            elif CompClass in [VCVS, VCCS]:
                if len(raw_nodes_str_list) < 5: raise scs_errors.ScsInstanceError(f"Insufficient params for {comp_name_mangled}")
                ctrl_p_mangled = resolve_node_name(raw_nodes_str_list[2])
                ctrl_n_mangled = resolve_node_name(raw_nodes_str_list[3])
                factor_expr_str = raw_nodes_str_list[4]
                evaluated_factor_sympy = _ensure_sympy_expr(factor_expr_str, comp_name_mangled+"_factor", current_instance.paramsd, current_instance.parent, current_instance)
                if CompClass == VCVS: new_comp_instance = VCVS(comp_name_mangled, node1_mangled, node2_mangled, ctrl_p_mangled, ctrl_n_mangled, gain_sym=evaluated_factor_sympy)
                else: new_comp_instance = VCCS(comp_name_mangled, node1_mangled, node2_mangled, ctrl_p_mangled, ctrl_n_mangled, transconductance_sym=evaluated_factor_sympy)
            elif CompClass in [CCVS, CCCS]:
                if len(raw_nodes_str_list) < 4: raise scs_errors.ScsInstanceError(f"Insufficient params for {comp_name_mangled}")
                raw_ctrl_comp_name = raw_nodes_str_list[2]
                # Control component name needs prefixing if it's within the same (sub)circuit scope
                # Assume for now that if parent_instance is not None (i.e. we are in a subcircuit),
                # then raw_ctrl_comp_name is local to this subcircuit unless it's found in parent.
                # This needs robust hierarchical name resolution for control component.
                # Simple prefix for now if this is a subcircuit.
                ctrl_comp_name_mangled_for_symbol = current_prefix + raw_ctrl_comp_name

                factor_expr_str = raw_nodes_str_list[3]
                evaluated_factor_sympy = _ensure_sympy_expr(factor_expr_str, comp_name_mangled+"_factor", current_instance.paramsd, current_instance.parent, current_instance)
                if CompClass == CCVS: new_comp_instance = CCVS(comp_name_mangled, node1_mangled, node2_mangled, ctrl_comp_name_mangled_for_symbol, transresistance_sym=evaluated_factor_sympy)
                else: new_comp_instance = CCCS(comp_name_mangled, node1_mangled, node2_mangled, ctrl_comp_name_mangled_for_symbol, gain_sym=evaluated_factor_sympy)

            if new_comp_instance:
                current_instance.add_element(new_comp_instance)
            elif comp_type_char not in ['X']:
                logging.warning(f"Component {comp_name_mangled} (type {comp_type_char}) N/I or instantiation failed.")
        else:
            logging.warning(f"Unknown element type prefix: {comp_type_char} for {comp_def_name_local}. Skipping.")
    current_instance._prepare_nets()
    return current_instance

def make_top_instance(circuit_template):
    global ground_node_name_for_solver_context
    try:
        return make_instance(None, str(circuit_template.name), circuit_template, {}, {}) # Ensure name is string
    except scs_errors.ScsInstanceError as e:
        logging.error(f"Failed to make top instance for {circuit_template.name}: {e}", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"Unexpected error in make_top_instance for {circuit_template.name}: {e}", exc_info=True)
        return None

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.info("scs_instance_hier.py: Instance.v() and .i() methods updated for new solver.")
    logging.info("Run via scs.py with a netlist for full testing.")
