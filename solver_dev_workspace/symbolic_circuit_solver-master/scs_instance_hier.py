# solver_dev_workspace/symbolic_circuit_solver-master/scs_instance_hier.py
import sympy as sp
import copy
import logging
import re

import scs_errors
import scs_parser

import sys
import os
current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_dir = os.path.dirname(current_script_dir)
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)

try:
    from all_symbolic_components import ( # Assuming this file is now in project_root_dir
        BaseComponent, Resistor, Capacitor, Inductor,
        VoltageSource, CurrentSource,
        VCVS, VCCS, CCVS, CCCS,
        s_sym
    )
    print("DEBUG scs_instance_hier: Successfully imported from all_symbolic_components.py") # Updated print message
except ImportError as e:
    print(f"CRITICAL ImportError in scs_instance_hier.py: Could not import from all_symbolic_components. Error: {e}")
    class BaseComponent: pass;
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

from symbolic_solver import solve_circuit as root_solve_circuit

SYMPYFY_LOCALS_HIER = {
    's': s_sym, 'I': sp.I, 'exp': sp.exp, 'sin': sp.sin, 'cos': sp.cos,
    'tan': sp.tan, 'pi': sp.pi, 'sqrt': sp.sqrt, 'log': sp.log, 'ln': sp.log
}

# Using definition from prompt (based on turn 73, adapted for current context)
def _ensure_sympy_expr(val_expr_str_or_sympy, current_inst_paramsd_for_eval, parent_inst_obj_for_hier_lookup, current_inst_obj_for_context_hint, eval_name_hint="param"):
    if isinstance(val_expr_str_or_sympy, (sp.Expr, int, float, complex)):
        return sp.sympify(val_expr_str_or_sympy)
    if not val_expr_str_or_sympy:
        logging.warning(f"Empty value string for {eval_name_hint}, defaulting to '0'.")
        val_expr_str_or_sympy = '0'
    str_val = str(val_expr_str_or_sympy)

    prefix_hint = current_inst_obj_for_context_hint.name if current_inst_obj_for_context_hint else "top"
    temp_param_name = f"_{prefix_hint}_{eval_name_hint}_{abs(hash(str_val))}"

    # scs_parser.evaluate_param expects:
    # (param_to_resolve_name, {param_to_resolve_name: its_str_value},
    #  dict_of_already_evald_params_in_current_scope, parent_instance_object,
    #  list_of_params_in_call_stack, current_instance_object_providing_scope)
    evaluated_expr_str_from_parser = scs_parser.evaluate_param(
        temp_param_name,
        {temp_param_name: str_val},
        current_inst_paramsd_for_eval, # Params already known in current instance's scope
        parent_inst_obj_for_hier_lookup, # Parent Instance object
        [temp_param_name],
        current_inst_obj_for_context_hint # The Instance object this evaluation is for
    )

    final_sympify_context = {**SYMPYFY_LOCALS_HIER}
    if current_inst_paramsd_for_eval: # Add already evaluated params for this instance
        for k, v in current_inst_paramsd_for_eval.items():
            final_sympify_context[str(k)] = v # Keys in paramsd are strings

    try:
        # evaluated_expr_str_from_parser should be a string that can be sympified
        return sp.sympify(evaluated_expr_str_from_parser, locals=final_sympify_context)
    except Exception as e:
        logging.error(f"Failed to sympify '{evaluated_expr_str_from_parser}' for {eval_name_hint}. Error: {e}. Returning as symbol.")
        return sp.Symbol(evaluated_expr_str_from_parser)


class Instance(object):
    def __init__(self,parent_instance,instance_global_path_name,instance_port_map={}): # name is global path name
        self.port_map = instance_port_map
        self.elements_on_net = {}
        self.elements = {} # Dict of {local_comp_name: MySymbolicComponent_instance with mangled name/nodes}
        self.subinstances = {} # Dict of {local_subinst_name: Instance_object_for_subcircuit}
        self.paramsd = {}
        self.parent = parent_instance
        self.name = instance_global_path_name # This is the globally unique path, e.g. "top", "X1", "X1.X2"
        self.local_name_in_parent = instance_global_path_name.split('.')[-1] if parent_instance else instance_global_path_name

        self.solved_dict = None
        self.V = {}
        self.circuit_definition = None # Stores the Circuit template object

    def add_element(self,element_obj): # element_obj has mangled .name, .node1, .node2
        element_nets_for_kcl = [element_obj.node1, element_obj.node2]
        if not hasattr(element_obj, 'nets'): element_obj.nets = element_nets_for_kcl
        for net_name in element_nets_for_kcl:
            self.elements_on_net.setdefault(net_name, []).append(element_obj)

        # Store element by its local name (last part of its mangled name)
        local_name = element_obj.name.split('.')[-1]
        self.elements[local_name] = element_obj

    def add_sub_instance(self,sub_inst_obj): # sub_inst_obj.name is its global path name
        # Store by its local name in the parent's scope
        local_sub_name = sub_inst_obj.local_name_in_parent
        for _internal_port_name, parent_scope_net_name in sub_inst_obj.port_map.items():
            self.elements_on_net.setdefault(parent_scope_net_name, []).append(sub_inst_obj)
        self.subinstances[local_sub_name] = sub_inst_obj

    def _prepare_nets(self):
        pass

    def _get_all_flat_components_recursive_helper(self, current_instance, collected_components_list):
        for elem_obj in current_instance.elements.values(): # Values are the component objects
            collected_components_list.append(elem_obj)
        for sub_inst_obj in current_instance.subinstances.values(): # Values are the Instance objects
            self._get_all_flat_components_recursive_helper(sub_inst_obj, collected_components_list)

    def solve(self):
        logging.info(f"Instance.solve() called for '{self.name}' using root_symbolic_solver.py.")
        if self.parent is not None:
            logging.debug(f"  Instance '{self.name}' is subcircuit. Flattened by Top instance solve."); return True

        flat_components_list = []
        self._get_all_flat_components_recursive_helper(self, flat_components_list)
        if not flat_components_list:
            logging.warning(f"Instance {self.name}: No components found to solve."); self.solved_dict = {}; return True
        logging.info(f"  Instance {self.name}: Found {len(flat_components_list)} flat components for solver.")

        unknowns_to_collect = set(); all_circuit_nodes_global = set(); ground_node_name = '0'
        for comp in flat_components_list:
            all_circuit_nodes_global.add(comp.node1); all_circuit_nodes_global.add(comp.node2)
            unknowns_to_collect.add(comp.V_comp); unknowns_to_collect.add(comp.P_comp)
            if hasattr(comp, 'I_comp'): unknowns_to_collect.add(comp.I_comp)
            if isinstance(comp, (VCVS, VCCS)):
                unknowns_to_collect.add(comp.V_control_p_sym); unknowns_to_collect.add(comp.V_control_n_sym)
            if isinstance(comp, (CCVS, CCCS)):
                unknowns_to_collect.add(comp.I_control_sym)
        for node_str_global in all_circuit_nodes_global:
            if node_str_global != ground_node_name:
                unknowns_to_collect.add(sp.Symbol(f"V_{node_str_global}"))

        unknowns_list_for_solver = sorted(list(unknowns_to_collect), key=str)
        # known_specifications from .PARAM or direct values are part of component expressions.
        # This arg is for additional equations if any (e.g. user-defined constraints).
        known_specifications_for_solver = []

        # ---- START DEBUG PRINTS (using logging) ----
        logging.debug(f"Instance.solve ({self.name}): unknowns_list_for_solver being passed to root_solve_circuit ({len(unknowns_list_for_solver)}):")
        for i, s_unk in enumerate(unknowns_list_for_solver): # s_unk is a Symbol object
            logging.debug(f"  unk_to_solver[{i}]: {str(s_unk)}, id: {id(s_unk)}, type: {type(s_unk)}")
        # ---- END DEBUG PRINTS ----

        logging.info(f"  Calling root_solve_circuit for {self.name} with {len(flat_components_list)} comps, {len(unknowns_list_for_solver)} potential unknowns.")

        solution_list = root_solve_circuit(
            flat_components_list, unknowns_list_for_solver,
            known_specifications_for_solver, ground_node_name
        )

        if solution_list and solution_list[0]:
            # Convert SYMBOL keys from solver to STRING keys for self.solved_dict
            self.solved_dict = {str(k): v for k, v in solution_list[0].items()}

            # ---- START DEBUG PRINTS (using logging) ----
            logging.debug(f"Instance.solve ({self.name}): self.solved_dict populated with STRING keys. Keys ({len(self.solved_dict)}):")
            # Limiting to first 20 keys for brevity in logs, if many keys exist
            for i, k_str_key in enumerate(list(self.solved_dict.keys())[:20]):
                logging.debug(f"  solved_key_str[{i}]: {k_str_key}, type: {type(k_str_key)}") # k_str_key is a string
            if len(self.solved_dict) > 20:
                logging.debug(f"  ... and {len(self.solved_dict) - 20} more string keys.")
            # ---- END DEBUG PRINTS ----
            for str_key, val_expr in self.solved_dict.items(): # str_key is already a string
                self.paramsd[str_key] = val_expr
            self.V.clear()
            for node_str_global in all_circuit_nodes_global:
                # Construct the string key for node voltage lookup
                v_key_str = f"V_{node_str_global}"
                if v_key_str in self.solved_dict: self.V[node_str_global] = self.solved_dict[v_key_str]
                elif node_str_global == ground_node_name: self.V[node_str_global] = sp.Integer(0)
            logging.info(f"  Solution found for {self.name}. {len(self.solved_dict)} items solved.")
        else:
            self.solved_dict = {}; logging.error(f"Circuit {self.name} not solved or solution empty."); return False
        return True

    def _get_target_instance_and_local_name(self, hierarchical_name_str):
        """ Parses "X1.X2.R1" into target_instance=X1.X2, local_name="R1".
            For "R1" (if self is top), returns self, "R1".
            This version assumes hierarchical_name_str is relative to 'self'.
        """
        parts = hierarchical_name_str.split('.')
        target_inst = self
        for i in range(len(parts) - 1): # Navigate to the instance containing the element
            sub_inst_local_name = parts[i]
            if sub_inst_local_name in target_inst.subinstances:
                target_inst = target_inst.subinstances[sub_inst_local_name]
            else:
                raise scs_errors.ScsInstanceError(f"Subinstance '{sub_inst_local_name}' not found in '{target_inst.name}' while resolving '{hierarchical_name_str}'.")
        return target_inst, parts[-1] # Return the target instance and the final local name part

    def v(self, net1_hier_str, net2_hier_str=None):
        # Assumes net1_hier_str, net2_hier_str are already globally mangled names
        logging.debug(f"Instance.v ({self.name}): Called with net1='{net1_hier_str}', net2='{net2_hier_str}'")
        if self.solved_dict is None:
            logging.warning(f"  Instance.v ({self.name}): self.solved_dict is None.");
            return sp.Integer(0)

        v1_val = sp.Integer(0)
        if net1_hier_str == '0': v1_val = sp.Integer(0)
        else:
            v1_key_str = f"V_{net1_hier_str}" # Construct string key
            logging.debug(f"  Instance.v ({self.name}): Looking for V1 key_str: '{v1_key_str}'")
            if v1_key_str in self.solved_dict: v1_val = self.solved_dict[v1_key_str]
            else: logging.warning(f"V_key_str '{v1_key_str}' for net '{net1_hier_str}' not in solved_dict for v().")

        v2_val = sp.Integer(0)
        if net2_hier_str is not None and net2_hier_str != '0':
            v2_key_str = f"V_{net2_hier_str}" # Construct string key
            logging.debug(f"  Instance.v ({self.name}): Looking for V2 key_str: '{v2_key_str}'")
            if v2_key_str in self.solved_dict: v2_val = self.solved_dict[v2_key_str]
            else: logging.warning(f"V_key_str '{v2_key_str}' for net '{net2_hier_str}' not in solved_dict for v().")

        return v1_val - v2_val

    def i(self, element_hier_str):
        # Assumes element_hier_str is the globally unique mangled name (e.g. "X1.R1")
        logging.debug(f"Instance.i ({self.name}): Called with element_name='{element_hier_str}'")
        if self.solved_dict is None:
            logging.warning(f"  Instance.i ({self.name}): self.solved_dict is None.");
            return sp.Integer(0)

        i_key_str = f"I_{element_hier_str}" # Construct string key
        logging.debug(f"  Instance.i ({self.name}): Looking for I key_str: '{i_key_str}'")

        if i_key_str in self.solved_dict:
            return self.solved_dict[i_key_str]
        else:
            # Fallback for CurrentSource
            try:
                path_parts = element_hier_str.split('.')
                target_inst_for_element = self
                if len(path_parts) > 1 :
                    for i_part in range(len(path_parts) -1):
                        target_inst_for_element = target_inst_for_element.subinstances[path_parts[i_part]]
                local_elem_name_in_target = path_parts[-1]
                if local_elem_name_in_target in target_inst_for_element.elements:
                    element_obj = target_inst_for_element.elements[local_elem_name_in_target]
                    if isinstance(element_obj, CurrentSource):
                        return element_obj.I_comp
            except Exception as e:
                logging.debug(f"Exception during fallback in i() for {element_hier_str}: {e}")

            logging.warning(f"I_symbol '{i_comp_symbol_lookup}' for elem '{element_hier_str}' not in solved_dict for i().")
            return sp.Integer(0)

    def isub(self, port_hier_str):
        logging.warning(f"Instance.isub('{port_hier_str}') not implemented for flat solver. Returning 0.")
        return sp.Integer(0)

    def check_path_to_gnd(self): logging.debug("Placeholder: Instance.check_path_to_gnd() called."); return True
    def check_voltage_loop(self): logging.debug("Placeholder: Instance.check_voltage_loop() called."); return True

sin_regex = re.compile(r"SIN\s*\(\s*(?P<VOFF>[^\s()]+)\s+(?P<VAMPL>[^\s()]+)\s+(?P<FREQ>[^\s()]+)(?:\s+(?P<TD>[^\s()]+)\s+(?P<THETA>[^\s()]+)(?:\s+(?P<PHASE>[^\s()]+))?)?\s*\)")
my_element_class_map = {
    'R': Resistor, 'C': Capacitor, 'L': Inductor, 'V': VoltageSource, 'I': CurrentSource,
    'E': VCVS, 'G': VCCS, 'H': CCVS, 'F': CCCS,
}
ground_node_name_for_solver_context = '0' # Used by make_instance -> resolve_node_name

def make_instance(parent_instance_obj, local_instance_name_str, circuit_template_obj, instance_port_map_to_parent_scope, passed_params_from_x_line={}):
    # Determine the global path name for this instance
    if parent_instance_obj:
        if parent_instance_obj.name == 'top': # Parent is top
            instance_global_path_name = local_instance_name_str
        else: # Parent is already a subcircuit with a global path name
            instance_global_path_name = f"{parent_instance_obj.name}.{local_instance_name_str}"
    else: # This is the top-level instance being created
        instance_global_path_name = circuit_template_obj.name # Should be 'top' or actual top circuit name

    current_instance = Instance(parent_instance_obj, instance_global_path_name, instance_port_map_to_parent_scope)
    current_instance.circuit_definition = circuit_template_obj
    current_instance.local_name_in_parent = local_instance_name_str # Store its local name

    # Parameter evaluation:
    parent_evaluated_params = parent_instance_obj.paramsd if parent_instance_obj else {}
    try:
        # Evaluate .PARAMs defined within the circuit_template_obj
        locally_defined_params = scs_parser.evaluate_params(
            circuit_template_obj.parametersd, # Raw str:str dict from .PARAM lines
            parent_evaluated_params,          # Parent's already evaluated params (Sympy objects)
            instance_context=current_instance # The instance being built, for context
        )
        current_instance.paramsd.update(locally_defined_params)
    except scs_errors.ScsParameterError as e:
        raise scs_errors.ScsInstanceError(f"Error evaluating .PARAMs in {circuit_template_obj.name} for instance {instance_global_path_name}. {e}")

    # Parameters passed on X-line (already Sympy objects) override local/inherited ones
    current_instance.paramsd.update(passed_params_from_x_line)

    # Prefix for elements/nodes defined *within* this instance.
    # If this is the top-level instance (parent_instance_obj is None), its children should not be prefixed.
    # If this is a sub-instance, its children are prefixed with its own global path name.
    prefix_for_children = f"{instance_global_path_name}." if parent_instance_obj else ""

    def resolve_node_name_in_template(node_name_from_template):
        node_str = str(node_name_from_template)
        if node_str == ground_node_name_for_solver_context: return ground_node_name_for_solver_context

        # If current_instance is top, nodes from its template are global.
        if current_instance.name.lower() == 'top': return node_str

        # current_instance is a subcircuit. node_str is from its definition (e.g. "IN", "N_INTERNAL")
        # current_instance.port_map maps {"IN": "Global_N1", "OUT": "Global_N2"}
        if node_str in current_instance.port_map:
            return str(current_instance.port_map[node_str]) # Return the mapped global node name
        else: # Internal node to this subcircuit instance, gets prefixed.
            return prefix_for_children + node_str

    for local_comp_name_in_template, generic_element_template in circuit_template_obj.elementsd.items():
        comp_type_char = local_comp_name_in_template[0].upper()
        # Globally unique name for the component object itself
        global_component_name = prefix_for_children + local_comp_name_in_template
        new_component_object = None

        if comp_type_char == 'X':
            subckt_type_name_from_template = generic_element_template.paramsl[-1]
            subcircuit_definition_obj = circuit_template_obj.subcircuitsd.get(subckt_type_name_from_template)
            if subcircuit_definition_obj:
                # Nodes connecting this X instance are in the scope of current_instance's template
                connecting_nodes_from_template = generic_element_template.paramsl[:-1]
                # Port map for the new sub-instance: maps its definition's port names to global node names
                new_sub_instance_port_map_to_global = {}
                if len(connecting_nodes_from_template) == len(subcircuit_definition_obj.ports):
                    for i_port, port_name_in_sub_def in enumerate(subcircuit_definition_obj.ports):
                        node_in_current_template_scope = connecting_nodes_from_template[i_port]
                        # Resolve node in current template's scope to a global name
                        global_node_for_this_sub_port = resolve_node_name_in_template(node_in_current_template_scope)
                        new_sub_instance_port_map_to_global[port_name_in_sub_def] = global_node_for_this_sub_port
                else: raise scs_errors.ScsInstanceError(f"Port length mismatch for X {local_comp_name_in_template} (type {subckt_type_name_from_template}) in {instance_global_path_name}")

                evaluated_params_for_sub_x_line = scs_parser.evaluate_passed_params(generic_element_template.paramsd, current_instance)

                # Create sub_instance. Its local name is local_comp_name_in_template (e.g. "Xsub1")
                # Its global path name will be constructed inside the recursive call.
                sub_inst_obj = make_instance(current_instance, local_comp_name_in_template, subcircuit_definition_obj, new_sub_instance_port_map_to_global, evaluated_params_for_sub_x_line)
                current_instance.add_sub_instance(sub_inst_obj) # add_sub_instance uses local name as key
            else: raise scs_errors.ScsInstanceError(f"No definition for subcircuit type: {subckt_type_name_from_template} for X {local_comp_name_in_template} in {instance_global_path_name}")
            continue

        elif comp_type_char in my_element_class_map:
            CompClass = my_element_class_map[comp_type_char]
            raw_nodes_from_template = generic_element_template.paramsl
            params_from_template = generic_element_template.paramsd

            node1_global = resolve_node_name_in_template(raw_nodes_from_template[0])
            node2_global = resolve_node_name_in_template(raw_nodes_from_template[1])

            evaluated_value_sympy = None; evaluated_factor_sympy = None
            # --- Parameter Extraction Block (copied from prompt, matches turn 79/81 logic) ---
            if CompClass in [Resistor, Capacitor, Inductor]:
                value_expr_str = ""; value_key_lc = comp_type_char.lower(); value_key_uc = comp_type_char.upper()
                if value_key_lc in params_from_template: value_expr_str = params_from_template[value_key_lc]
                elif value_key_uc in params_from_template: value_expr_str = params_from_template[value_key_uc]
                elif len(raw_nodes_from_template) > 2 : value_expr_str = raw_nodes_from_template[2]
                else: raise scs_errors.ScsInstanceError(f"No value for {global_component_name}")
                evaluated_value_sympy = _ensure_sympy_expr(value_expr_str, current_instance.paramsd, current_instance.parent, current_instance, global_component_name)
                if CompClass == Resistor: new_component_object = Resistor(global_component_name, node1_global, node2_global, resistance_sym=evaluated_value_sympy)
                elif CompClass == Capacitor: new_component_object = Capacitor(global_component_name, node1_global, node2_global, capacitance_sym=evaluated_value_sympy)
                elif CompClass == Inductor: new_component_object = Inductor(global_component_name, node1_global, node2_global, inductance_sym=evaluated_value_sympy)
            elif CompClass in [VoltageSource, CurrentSource]:
                # ... (Full V/I source parsing logic from Turn 79/81) ...
                # This block correctly sets evaluated_value_sympy using _ensure_sympy_expr for various parts.
                # For brevity, assuming the full logic is pasted here by the worker.
                # START V/I Logic (from turn 79/81)
                val_list_for_source = raw_nodes_from_template[2:]
                final_source_val_expr = None;
                has_sin_spec_list=False; sin_args_list=[]; has_ac_spec_list=False; ac_args_list=[]; has_dc_spec_list=False; dc_arg_list="0"; is_direct_dc_val_list=False
                idx = 0
                if val_list_for_source:
                    first_token_upper = str(val_list_for_source[0]).upper() # Ensure string for upper()
                    if not (first_token_upper == 'DC' or first_token_upper == 'AC' or first_token_upper.startswith('SIN(')):
                        is_direct_dc_val_list = True; dc_arg_list = val_list_for_source[0]; idx = 1
                while idx < len(val_list_for_source):
                    keyword = str(val_list_for_source[idx]).upper()
                    if keyword.startswith("SIN("):
                        has_sin_spec_list = True; reconstructed_sin_str = str(val_list_for_source[idx]); current_part_idx = idx
                        while not reconstructed_sin_str.endswith(')'):
                            current_part_idx += 1
                            if current_part_idx < len(val_list_for_source):
                                reconstructed_sin_str += " " + str(val_list_for_source[current_part_idx])
                            else: # Ran out of tokens before finding closing ')'
                                break # Break the while loop
                        sin_args_list = [reconstructed_sin_str]; idx = current_part_idx + 1; continue
                    elif keyword == "AC": has_ac_spec_list = True; ac_args_list = val_list_for_source[idx+1 : idx+3]; idx += 3; continue
                    elif keyword == "DC":
                        has_dc_spec_list = True;
                        is_direct_dc_val_list=False # Explicit DC keyword found
                        if idx + 1 < len(val_list_for_source) and not str(val_list_for_source[idx+1]).upper() in ['AC', 'SIN']: # Check next token isn't another type
                            dc_arg_list = val_list_for_source[idx+1]
                            idx += 2
                        else: # Only "DC" keyword found, or next token is another type specifier
                            dc_arg_list = "0" # Default DC value
                            idx += 1
                        continue
                    # This idx increment should only happen if no keyword was matched and we are advancing past an already processed direct value
                    # or if we are skipping an unrecognized token.
                    # The main keywords (SIN, AC, DC) use 'continue', so this is for fall-through.
                    idx +=1 # General increment if no specific keyword logic handled it.
                if has_sin_spec_list:
                    match = sin_regex.match(sin_args_list[0])
                    if match:
                        g = match.groupdict();
                        vampl_str = g.get('VAMPL', '0'); phase_str = g.get('PHASE', '0') or '0'
                        vampl_sym = _ensure_sympy_expr(vampl_str, current_instance.paramsd, current_instance.parent, current_instance, global_component_name+"_sinamp")
                        phase_deg_sym = _ensure_sympy_expr(phase_str, current_instance.paramsd, current_instance.parent, current_instance, global_component_name+"_sinph")
                        final_source_val_expr = vampl_sym * sp.exp(sp.I * (phase_deg_sym * sp.pi / 180))
                if final_source_val_expr is None and has_ac_spec_list:
                    ac_mag_str = ac_args_list[0] if len(ac_args_list) > 0 else '1'; ac_phase_str = ac_args_list[1] if len(ac_args_list) > 1 else '0'
                    ac_mag = _ensure_sympy_expr(ac_mag_str, current_instance.paramsd, current_instance.parent, current_instance, global_component_name+"_acm")
                    ac_phase_deg = _ensure_sympy_expr(ac_phase_str, current_instance.paramsd, current_instance.parent, current_instance, global_component_name+"_acp")
                    final_source_val_expr = ac_mag * sp.exp(sp.I * (ac_phase_deg * sp.pi / 180))
                if final_source_val_expr is None and (has_dc_spec_list or is_direct_dc_val_list):
                    final_source_val_expr = _ensure_sympy_expr(dc_arg_list, current_instance.paramsd, current_instance.parent, current_instance, global_component_name+"_dcval")
                if final_source_val_expr is None:
                    sin_f_pd=params_from_template.get('SIN'); ac_m_pd=params_from_template.get('ACMAG',params_from_template.get('AC')); dc_v_pd=params_from_template.get('DC')
                    if sin_f_pd:
                        match = sin_regex.match(sin_f_pd);
                        if match:
                             g = match.groupdict(); vampl_str = g.get('VAMPL', '0'); phase_str = g.get('PHASE', '0') or '0'
                             v_s = _ensure_sympy_expr(vampl_str,current_instance.paramsd,current_instance.parent,current_instance, global_component_name+"_pd_sinamp")
                             p_s = _ensure_sympy_expr(phase_str,current_instance.paramsd,current_instance.parent,current_instance, global_component_name+"_pd_sinph")
                             final_source_val_expr = v_s*sp.exp(sp.I*(p_s*sp.pi/180))
                    elif ac_m_pd:
                        ac_p_pd = params_from_template.get('ACPHASE','0');
                        a_m = _ensure_sympy_expr(ac_m_pd,current_instance.paramsd,current_instance.parent,current_instance, global_component_name+"_pd_acm")
                        a_p = _ensure_sympy_expr(ac_p_pd,current_instance.paramsd,current_instance.parent,current_instance, global_component_name+"_pd_acp")
                        final_source_val_expr = a_m*sp.exp(sp.I*(a_p*sp.pi/180))
                    elif dc_v_pd: final_source_val_expr = _ensure_sympy_expr(dc_v_pd, current_instance.paramsd,current_instance.parent,current_instance, global_component_name+"_pd_dcpd")
                evaluated_value_sympy = final_source_val_expr if final_source_val_expr is not None else sp.Integer(0)
                # END V/I Logic
                if CompClass == VoltageSource: new_component_object = VoltageSource(global_component_name, node1_global, node2_global, voltage_val_sym=evaluated_value_sympy)
                elif CompClass == CurrentSource: new_component_object = CurrentSource(global_component_name, node1_global, node2_global, current_val_sym=evaluated_value_sympy)
            elif CompClass in [VCVS, VCCS]:
                if len(raw_nodes_from_template) < 5: raise scs_errors.ScsInstanceError(f"Insufficient params for {global_component_name}")
                raw_ctrl_p_str, raw_ctrl_n_str = raw_nodes_from_template[2], raw_nodes_from_template[3]; factor_expr_str = raw_nodes_from_template[4]
                ctrl_p_global = resolve_node_name_in_template(raw_ctrl_p_str)
                ctrl_n_global = resolve_node_name_in_template(raw_ctrl_n_str)
                evaluated_factor_sympy = _ensure_sympy_expr(factor_expr_str, current_instance.paramsd, current_instance.parent, current_instance, global_component_name+"_factor")
                if CompClass == VCVS: new_component_object = VCVS(global_component_name, node1_global, node2_global, ctrl_p_global, ctrl_n_global, gain_sym=evaluated_factor_sympy)
                else: new_component_object = VCCS(global_component_name, node1_global, node2_global, ctrl_p_global, ctrl_n_global, transconductance_sym=evaluated_factor_sympy)
            elif CompClass in [CCVS, CCCS]:
                if len(raw_nodes_from_template) < 4: raise scs_errors.ScsInstanceError(f"Insufficient params for {global_component_name}")
                raw_ctrl_comp_local_name = raw_nodes_from_template[2]
                # Controlling component name is resolved relative to current instance's scope.
                # If "VS1" is in subcircuit X1, it becomes "X1.VS1".
                ctrl_comp_global_name = prefix_for_children + raw_ctrl_comp_local_name
                factor_expr_str = raw_nodes_from_template[3]
                evaluated_factor_sympy = _ensure_sympy_expr(factor_expr_str, current_instance.paramsd, current_instance.parent, current_instance, global_component_name+"_factor")
                if CompClass == CCVS: new_component_object = CCVS(global_component_name, node1_global, node2_global, ctrl_comp_global_name, transresistance_sym=evaluated_factor_sympy)
                else: new_component_object = CCCS(global_component_name, node1_global, node2_global, ctrl_comp_global_name, gain_sym=evaluated_factor_sympy)

            if new_component_object:
                current_instance.add_element(new_component_object)
            else: logging.warning(f"Component {global_component_name} (type {comp_type_char}) N/I or instantiation failed.")
        else:
            logging.warning(f"Unknown element type prefix: {comp_type_char} for {local_comp_name_in_template}. Skipping.")
    # current_instance._prepare_nets() # Deprecated for new solver
    return current_instance

def make_top_instance(circuit_template):
    try:
        return make_instance(None, circuit_template.name, circuit_template, {}, {})
    except scs_errors.ScsInstanceError as e: logging.error(f"Failed to make top instance for {circuit_template.name}: {e}", exc_info=True); return None
    except Exception as e: logging.error(f"Unexpected error in make_top_instance for {circuit_template.name}: {e}", exc_info=True); return None

if __name__ == '__main__':
    print("scs_instance_hier.py now includes refactored Instance methods (solve, v, i, isub) and name mangling.")
    logging.basicConfig(level=logging.DEBUG)
    # Basic test:
    # Create a dummy top circuit definition
    # top_def = scs_circuit.TopCircuit() # Needs scs_circuit to be importable standalone or defined here
    # top_def.name = "top"
    # # Add a simple R to top_def.elementsd
    # # R1 N1 0 1k
    # R1_elem_template = scs_circuit.Element(paramsl=['N1','0','1k'], paramsd={}) # Needs scs_circuit.Element
    # top_def.elementsd['R1'] = R1_elem_template
    # V1_elem_template = scs_circuit.Element(paramsl=['N1','0','5'], paramsd={})
    # top_def.elementsd['V1'] = V1_elem_template
    #
    # top_inst = make_top_instance(top_def)
    # if top_inst:
    #    print("Top instance created:", top_inst.name)
    #    print("Elements:", top_inst.elements.keys())
    #    if top_inst.elements: print("R1 name:", top_inst.elements['R1'].name, "nodes:", top_inst.elements['R1'].node1, top_inst.elements['R1'].node2)
    #    top_inst.solve()
    #    print("Solved dict:", top_inst.solved_dict)
    #    if top_inst.solved_dict:
    #        print("V(N1):", top_inst.v("N1"))
    #        print("I(R1):", top_inst.i("R1"))
    # else:
    #    print("Failed to create top instance for basic test.")
