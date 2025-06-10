import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import tempfile
import sympy
import json

from . import scs_parser
from . import scs_instance_hier
from . import scs_circuit
from . import scs_errors


class CircuitGUI(tk.Tk):
    def __init__(self):
        self.top_instance = None
        self.active_symbols_info = {}
        self.selected_component_to_place = None
        self.placed_graphical_items = []
        self.currently_selected_canvas_item_gui_name = None
        self.last_selection_coords = None

        # New state variables for wiring
        self.wiring_mode = False
        self.wire_start_coords = None
        self.drawn_wires = []
        self.next_wire_id = 0
        self.temp_wire_start_indicator = None

        super().__init__()
        self.title("Symbolic Circuit Simulator GUI - Phase 1")
        self.geometry("1000x700")

        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Left Frame (Component Palette) ---
        self.palette_frame = ttk.LabelFrame(self.main_frame, text="Components", padding="10")
        self.palette_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        ttk.Label(self.palette_frame, text="Select component:").pack(pady=5)
        ttk.Button(self.palette_frame, text="Resistor", command=lambda: self._select_component_for_placement("Resistor")).pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="V_Source_DC", command=lambda: self._select_component_for_placement("V_Source_DC")).pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="I_Source_DC", command=lambda: self._select_component_for_placement("I_Source_DC")).pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="Wire", command=self._select_wire_tool).pack(fill=tk.X, pady=2) # New Wire button

        # --- Right Frame (Results/Formulas Display) ---
        self.results_frame = ttk.LabelFrame(self.main_frame, text="Formulas & Results", padding="10")
        self.results_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.results_text = tk.Text(self.results_frame, wrap=tk.WORD, height=15, state=tk.DISABLED)
        self.results_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # --- Center Frame (Canvas & Inputs & Properties) ---
        self.center_frame = ttk.Frame(self.main_frame, padding="10")
        self.center_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas_frame_container = ttk.LabelFrame(self.center_frame, text="Circuit Canvas", padding="10")
        self.canvas_frame_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5, padx=(0,5))
        self.canvas = tk.Canvas(self.canvas_frame_container, bg="white", width=550, height=350)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        self.properties_editor_frame = ttk.LabelFrame(self.center_frame, text="Properties Editor", padding="10")
        self.properties_editor_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5,0), pady=5)
        self.prop_selected_label = ttk.Label(self.properties_editor_frame, text="Selected: None")
        self.prop_selected_label.pack(pady=(0,5), anchor=tk.W)
        self.prop_type_label = ttk.Label(self.properties_editor_frame, text="Type: N/A")
        self.prop_type_label.pack(pady=(0,10), anchor=tk.W)
        # ... (rest of properties editor widgets as defined previously) ...
        prop_name_frame = ttk.Frame(self.properties_editor_frame)
        prop_name_frame.pack(fill=tk.X, pady=2)
        ttk.Label(prop_name_frame, text="GUI Name:").pack(side=tk.LEFT)
        self.prop_name_entry = ttk.Entry(prop_name_frame, width=15)
        self.prop_name_entry.pack(side=tk.LEFT, padx=5, expand=True)
        prop_value_frame = ttk.Frame(self.properties_editor_frame)
        prop_value_frame.pack(fill=tk.X, pady=2)
        ttk.Label(prop_value_frame, text="Value/Sym:").pack(side=tk.LEFT)
        self.prop_value_entry = ttk.Entry(prop_value_frame, width=15)
        self.prop_value_entry.pack(side=tk.LEFT, padx=5, expand=True)
        prop_n1_frame = ttk.Frame(self.properties_editor_frame)
        prop_n1_frame.pack(fill=tk.X, pady=2)
        ttk.Label(prop_n1_frame, text="Node 1:").pack(side=tk.LEFT)
        self.prop_n1_entry = ttk.Entry(prop_n1_frame, width=15)
        self.prop_n1_entry.pack(side=tk.LEFT, padx=5, expand=True)
        prop_n2_frame = ttk.Frame(self.properties_editor_frame)
        prop_n2_frame.pack(fill=tk.X, pady=2)
        ttk.Label(prop_n2_frame, text="Node 2:").pack(side=tk.LEFT)
        self.prop_n2_entry = ttk.Entry(prop_n2_frame, width=15)
        self.prop_n2_entry.pack(side=tk.LEFT, padx=5, expand=True)
        self.update_props_button = ttk.Button(self.properties_editor_frame, text="Update Properties", command=self._update_component_properties, state=tk.DISABLED)
        self.update_props_button.pack(pady=10)

        self.input_area_frame = ttk.LabelFrame(self.main_frame, text="Programmatic Circuit Definition & Analysis Targets", padding="10")
        self.input_area_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5, expand=False)

        self.components_list_container_frame = ttk.Frame(self.input_area_frame)
        self.components_list_container_frame.pack(fill=tk.X, expand=True, pady=(0,5))
        self.component_entries = []

        self.action_buttons_frame = ttk.Frame(self.input_area_frame)
        self.action_buttons_frame.pack(fill=tk.X, pady=5)
        self.add_comp_button = ttk.Button(self.action_buttons_frame, text="Add Component", command=self._add_component_row)
        self.add_comp_button.pack(side=tk.LEFT, padx=5)
        self.remove_comp_button = ttk.Button(self.action_buttons_frame, text="Remove Last Component", command=self._remove_last_component_row)
        self.remove_comp_button.pack(side=tk.LEFT, padx=5)
        self.save_circuit_button = ttk.Button(self.action_buttons_frame, text="Save Circuit", command=self._save_circuit_to_file)
        self.save_circuit_button.pack(side=tk.LEFT, padx=5)
        self.load_circuit_button = ttk.Button(self.action_buttons_frame, text="Load Circuit", command=self._load_circuit_from_file)
        self.load_circuit_button.pack(side=tk.LEFT, padx=5)
        self.derive_button = ttk.Button(self.action_buttons_frame, text="Derive Formulas", command=self.on_derive_formulas)
        self.derive_button.pack(side=tk.LEFT, padx=5)
        self.calculate_button = ttk.Button(self.action_buttons_frame, text="Calculate Numerical Values", command=self.on_calculate_numerical)
        self.calculate_button.pack(side=tk.LEFT, padx=5)

        self.analysis_options_frame = ttk.LabelFrame(self.input_area_frame, text="Analysis & Calculation Targets", padding="10")
        self.analysis_options_frame.pack(fill=tk.X, pady=(10,0), side=tk.TOP)
        ttk.Label(self.analysis_options_frame, text="Target Comp. Name (GUI Name):").pack(side=tk.LEFT, padx=5)
        self.target_comp_name_entry = ttk.Entry(self.analysis_options_frame, width=10)
        self.target_comp_name_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(self.analysis_options_frame, text="Target Node (for V(node,'0')):") .pack(side=tk.LEFT, padx=5)
        self.target_node_name_entry = ttk.Entry(self.analysis_options_frame, width=10)
        self.target_node_name_entry.pack(side=tk.LEFT, padx=5)

        self._add_component_row(load_data={'type':"V_Source_DC", 'name':"S1", 'value':"US_sym", 'n1':"n1", 'n2':"0"})
        self._add_component_row(load_data={'type':"Resistor", 'name':"R1", 'value':"R1_sym", 'n1':"n1", 'n2':"n2"})
        self._add_component_row(load_data={'type':"Resistor", 'name':"R2", 'value':"R2_sym", 'n1':"n2", 'n2':"0"})
        for _ in range(1): self._add_component_row()

    def display_message(self, title, message):
        self.results_text.config(state=tk.NORMAL)
        self.results_text.insert(tk.END, f"--- {title} ---\n{message}\n\n")
        self.results_text.see(tk.END)
        self.results_text.config(state=tk.DISABLED)

    def on_derive_formulas(self):
        self.results_text.config(state=tk.NORMAL); self.results_text.delete('1.0', tk.END); self.results_text.config(state=tk.DISABLED)
        circuit_data = self._collect_circuit_data()
        if not circuit_data: self.display_message("Input Error", "No valid component data entered."); return
        spice_string = self._generate_spice_netlist(circuit_data)
        self.display_message("Generated SPICE Netlist", spice_string)
        temp_spice_file_path = ""
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sp', dir='.', encoding='utf-8') as tmp_file:
                tmp_file.write(spice_string); temp_spice_file_path = tmp_file.name
            self.display_message("Solver Status", f"Parsing: {os.path.basename(temp_spice_file_path)}")
            top_circuit = scs_parser.parse_file(temp_spice_file_path, scs_circuit.TopCircuit())
            if not top_circuit: raise scs_errors.ScsParserError("Parse failed.")
            self.display_message("Solver Status", "Parsed. Instantiating...")
            self.top_instance = scs_instance_hier.make_top_instance(top_circuit)
            if not self.top_instance: raise scs_errors.ScsInstanceError("Instantiation failed.")
            self.display_message("Solver Status", "Instantiated. Checking...")
            if not self.top_instance.check_path_to_gnd(): raise scs_errors.ScsInstanceError("Check fail: No path to ground.")
            if not self.top_instance.check_voltage_loop(): raise scs_errors.ScsInstanceError("Check fail: Voltage loop.")
            self.display_message("Solver Status", "Checks OK. Solving...")
            self.top_instance.solve()
            self.display_message("Solver Status", "Solved.")
            formulas_str = "Derived Symbolic Formulas:\n"
            target_comp_gui_name = self.target_comp_name_entry.get().strip()
            target_node_name = self.target_node_name_entry.get().strip()
            if not target_comp_gui_name and not target_node_name:
                formulas_str += "  No target specified. Enter GUI Comp. Name or Node Name.\n"
            else:
                if target_comp_gui_name:
                    comp_details = self._get_component_details_from_gui_name(target_comp_gui_name, circuit_data)
                    if comp_details:
                        formulas_str += f"  --- For Comp (GUI: {target_comp_gui_name}, SPICE: {comp_details['spice_name']}) ---\n"
                        try: formulas_str += f"    V({comp_details['n1']},{comp_details['n2']}): {sympy.pretty(self.top_instance.v(comp_details['n1'], comp_details['n2']))}\n"
                        except Exception as e: formulas_str += f"    Error V: {e}\n"
                        try: formulas_str += f"    I({comp_details['spice_name']}): {sympy.pretty(self.top_instance.i(comp_details['spice_name']))}\n"
                        except Exception as e: formulas_str += f"    Error I: {e}\n"
                        try: formulas_str += f"    P({comp_details['spice_name']}): {sympy.pretty(self.top_instance.p(comp_details['spice_name']))}\n"
                        except Exception as e: formulas_str += f"    Error P: {e}\n"
                    else: formulas_str += f"  Comp GUI Name '{target_comp_gui_name}' not found.\n"
                if target_node_name:
                    formulas_str += f"  --- For Node {target_node_name} ---\n"
                    try: formulas_str += f"    V({target_node_name},'0'): {sympy.pretty(self.top_instance.v(target_node_name, '0'))}\n"
                    except Exception as e: formulas_str += f"    Error V({target_node_name},'0'): {e}\n"
            self.display_message("Symbolic Formulas", formulas_str)
        except (scs_errors.ScsParserError, scs_errors.ScsInstanceError, ValueError, FileNotFoundError) as e:
            self.display_message("Solver Error", f"{type(e).__name__}: {e}")
        except Exception as e:
            self.display_message("Unexpected Error", f"{type(e).__name__}: {e}\n(See console for traceback)")
            import traceback; traceback.print_exc()
        finally:
            if temp_spice_file_path and os.path.exists(temp_spice_file_path):
                try: os.remove(temp_spice_file_path)
                except Exception as e: print(f"Error removing temp file: {e}")
        self.active_symbols_info.clear()
        if self.top_instance and self.top_instance.paramsd:
            defined_free_symbols = {str(s_obj) for s_obj in self.top_instance.paramsd if self.top_instance.paramsd[s_obj] == s_obj}
            for comp_gui_dict in circuit_data:
                gui_name = comp_gui_dict['name']; val_str_from_gui = comp_gui_dict['value']
                if val_str_from_gui in defined_free_symbols:
                    prefix = {"Resistor":"R", "V_Source_DC":"V", "I_Source_DC":"I"}.get(comp_gui_dict['type'], "X")
                    actual_spice_name = prefix + gui_name
                    self.active_symbols_info[gui_name] = {'symbol': sympy.Symbol(val_str_from_gui),
                                                          'spice_name': actual_spice_name, 'n1': comp_gui_dict['n1'],
                                                          'n2': comp_gui_dict['n2'] if comp_gui_dict['n2'] else '0'}
            self.display_message("Solver Status", f"Active symbols for numerics: {list(self.active_symbols_info.keys())}")

    def _get_component_details_from_gui_name(self, target_gui_name_str, circuit_data):
        if not target_gui_name_str: return None
        for comp_dict in circuit_data:
            if comp_dict['name'] == target_gui_name_str:
                prefix = {"Resistor":"R", "V_Source_DC":"V", "I_Source_DC":"I"}.get(comp_dict['type'], "X")
                actual_spice_name = prefix + comp_dict['name']
                return {'gui_name': comp_dict['name'], 'spice_name': actual_spice_name,
                        'n1': comp_dict['n1'], 'n2': comp_dict['n2'] if comp_dict['n2'] else '0',
                        'type': comp_dict['type'], 'value_str': comp_dict['value']}
        return None

    def _eval_expr_to_float(self, expr, default_on_error="N/A (eval error)"):
        try:
            if hasattr(expr, 'free_symbols') and expr.free_symbols: pass
            return float(expr.evalf())
        except: return default_on_error

    def _add_component_row(self, load_data=None):
        if load_data is None: load_data = {}
        row_frame = ttk.Frame(self.components_list_container_frame)
        row_frame.pack(fill=tk.X, pady=2, padx=2)
        component_types = ["", "Resistor", "V_Source_DC", "I_Source_DC"]
        ttk.Label(row_frame, text=f"Comp {len(self.component_entries) + 1}:").pack(side=tk.LEFT, padx=(0,2))
        type_combo = ttk.Combobox(row_frame, values=component_types, width=12, state="readonly")
        type_combo.set(load_data.get('type', '')); type_combo.pack(side=tk.LEFT, padx=2)
        if not load_data.get('type'): type_combo.current(0)
        ttk.Label(row_frame, text="Name:").pack(side=tk.LEFT, padx=(5,0))
        name_entry = ttk.Entry(row_frame, width=8); name_entry.insert(0, load_data.get('name', '')); name_entry.pack(side=tk.LEFT, padx=(0,2))
        ttk.Label(row_frame, text="Val/Sym:").pack(side=tk.LEFT, padx=(5,0))
        value_entry = ttk.Entry(row_frame, width=10); value_entry.insert(0, load_data.get('value', '')); value_entry.pack(side=tk.LEFT, padx=(0,2))
        ttk.Label(row_frame, text="N1:").pack(side=tk.LEFT, padx=(5,0))
        n1_entry = ttk.Entry(row_frame, width=5); n1_entry.insert(0, load_data.get('n1', '')); n1_entry.pack(side=tk.LEFT, padx=(0,2))
        ttk.Label(row_frame, text="N2:").pack(side=tk.LEFT, padx=(5,0))
        n2_entry = ttk.Entry(row_frame, width=5); n2_entry.insert(0, load_data.get('n2', '')); n2_entry.pack(side=tk.LEFT, padx=(0,2))
        row_widgets = {'frame': row_frame, 'type': type_combo, 'name': name_entry, 'value': value_entry,
                       'n1': n1_entry, 'n2': n2_entry}
        self.component_entries.append(row_widgets)

    def _remove_last_component_row(self):
        if self.component_entries: self.component_entries.pop()['frame'].destroy()

    def _collect_circuit_data(self):
        data = []
        for widgets in self.component_entries:
            if widgets['type'].get() and widgets['name'].get().strip():
                data.append({'type': widgets['type'].get(), 'name': widgets['name'].get().strip(),
                             'value': widgets['value'].get().strip(), 'n1': widgets['n1'].get().strip(),
                             'n2': widgets['n2'].get().strip()})
        return data

    def _generate_spice_netlist(self, circuit_data):
        lines = ['* GUI Netlist']; params = []; sym_ensure = set()
        def is_num(s): try: float(s); return True; except: return False
        for comp in circuit_data:
            val_param = comp['name'] + "_val"; val_str = comp['value']; sym_to_use = val_str
            if not val_str:
                if comp['type']=="Resistor": sym_to_use=comp['name']+"_sym"
                elif "Source" in comp['type']: sym_to_use=comp['name']+"_src_sym"
                else: val_str="0" # Default unknown empty to 0
                if val_str!="0": params.append(f".PARAM {val_param} = {sym_to_use}"); sym_ensure.add(f".PARAM {sym_to_use} = {sym_to_use}")
                else: params.append(f".PARAM {val_param} = {val_str}")
            elif not is_num(val_str): params.append(f".PARAM {val_param} = {sym_to_use}"); sym_ensure.add(f".PARAM {sym_to_use} = {sym_to_use}")
            else: params.append(f".PARAM {val_param} = {val_str}")
            prefix = {"Resistor":"R","V_Source_DC":"V","I_Source_DC":"I"}.get(comp['type'],"X")
            lines.append(f"{prefix}{comp['name']} {comp['n1']} {comp['n2']} {val_param}")
        return "\n".join(lines[:1] + params + sorted(list(sym_ensure)) + lines[1:] + [".END"])

    def on_calculate_numerical(self):
        self.results_text.config(state=tk.NORMAL); self.results_text.delete('1.0', tk.END)
        if not hasattr(self,'top_instance') or not self.top_instance: self.display_message("Error","Derive formulas first."); return
        if not self.active_symbols_info: self.display_message("Error","No active symbols found."); return
        subs = {}; circuit_data = self._collect_circuit_data(); all_ok = True
        gui_vals = {item['name']:item['value'] for item in circuit_data}
        for name,info in self.active_symbols_info.items():
            val_str = gui_vals.get(name)
            if val_str and val_str.strip()!="":
                try: subs[info['symbol']] = float(val_str)
                except ValueError: self.display_message("Input Error",f"Value '{val_str}' for '{name}' (symbol '{info['symbol']}') not number.");all_ok=False;break
            else: self.display_message("Input Error",f"Missing value for '{name}' (symbol '{info['symbol']}')");all_ok=False;break
        if not all_ok: self.display_message("Calc Status","Aborted.");return
        if subs: self.display_message("Numerical Calc",f"Substituting: {{ {', '.join([f'{str(k)}:{v}' for k,v in subs.items()])} }}")

        res_str="Numerical Results:\n"; comp_name=self.target_comp_name_entry.get().strip(); node_name=self.target_node_name_entry.get().strip()
        if not comp_name and not node_name: res_str+="  No target. Enter GUI Comp. Name or Node Name.\n"
        else:
            if comp_name:
                details = self._get_component_details_from_gui_name(comp_name, circuit_data)
                if details:
                    res_str+=f"  --- For Comp (GUI:{comp_name}, SPICE:{details['spice_name']}) ---\n"
                    try:
                        v=self.top_instance.v(details['n1'],details['n2']); i=self.top_instance.i(details['spice_name']); p=self.top_instance.p(details['spice_name'])
                        val_own=sympy.sympify(details['value_str']) if details['value_str'] else sympy.Float(0)
                        v_n=self._eval_expr_to_float(v.subs(subs)); i_n=self._eval_expr_to_float(i.subs(subs)); p_n=self._eval_expr_to_float(p.subs(subs))
                        val_own_n=self._eval_expr_to_float(val_own.subs(subs) if hasattr(val_own,'subs') else val_own)
                        unit={"Resistor":"Ω","V_Source_DC":"V","I_Source_DC":"A"}.get(details['type'],"")
                        if "Source" not in details['type']: res_str+=f"    Value: {val_own_n if isinstance(val_own_n,str) else f'{val_own_n:.4f}'} {unit}\n"
                        res_str+=f"    Voltage: {v_n if isinstance(v_n,str) else f'{v_n:.4f}'} V\n"
                        res_str+=f"    Current: {i_n if isinstance(i_n,str) else f'{i_n*1000:.4f}'} mA\n"
                        res_str+=f"    Power: {p_n if isinstance(p_n,str) else f'{p_n*1000:.4f}'} mW\n"
                    except Exception as e: res_str+=f"    Error V/I/P for '{comp_name}': {e}\n"
                else: res_str+=f"  Comp GUI Name '{comp_name}' not found.\n"
            if node_name:
                res_str+=f"  --- For Node {node_name} ---\n"
                try:
                    v_node=self.top_instance.v(node_name,'0'); v_n_n=self._eval_expr_to_float(v_node.subs(subs))
                    res_str+=f"    V({node_name},'0'): {v_n_n if isinstance(v_n_n,str) else f'{v_n_n:.4f}'} V\n"
                except Exception as e: res_str+=f"    Error V({node_name},'0'): {e}\n"
        self.display_message("Numerical Results", res_str)

    def _save_circuit_to_file(self):
        circuit_data = self._collect_circuit_data()
        if not circuit_data: messagebox.showwarning("Save Circuit", "No circuit data to save."); return
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")], title="Save Circuit As", initialdir=os.path.join(os.getcwd(), "examples"))
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(circuit_data, f, indent=4)
            self.display_message("Save Circuit", f"Circuit saved to {os.path.basename(filepath)}")
        except Exception as e: self.display_message("Save Error", f"Failed to save: {e}")

    def _load_circuit_from_file(self):
        filepath = filedialog.askopenfilename(defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")], title="Load Circuit From", initialdir=os.path.join(os.getcwd(), "examples"))
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8') as f: loaded_data = json.load(f)
            if not isinstance(loaded_data, list): raise ValueError("File not valid list of components.")
            while self.component_entries: self._remove_last_component_row()
            for component_data in loaded_data:
                if not isinstance(component_data, dict) or not all(k in component_data for k in ['type', 'name', 'value', 'n1', 'n2']):
                    self.display_message("Load Warning", f"Skipping invalid data: {component_data}"); continue
                self._add_component_row(load_data=component_data)
            self.display_message("Load Circuit", f"Circuit loaded from {os.path.basename(filepath)}")
            self.results_text.config(state=tk.NORMAL); self.results_text.delete('1.0', tk.END); self.results_text.config(state=tk.DISABLED)
            if hasattr(self, 'top_instance'): self.top_instance = None
            if hasattr(self, 'active_symbols_info'): self.active_symbols_info.clear()
        except FileNotFoundError: self.display_message("Load Error", f"File not found: {filepath}")
        except json.JSONDecodeError: self.display_message("Load Error", "Not valid JSON.")
        except ValueError as ve: self.display_message("Load Error", str(ve))
        except Exception as e: self.display_message("Load Error", f"Failed to load: {e}")

    def _select_component_for_placement(self, comp_type):
        self.selected_component_to_place = comp_type
        self.wiring_mode = False
        self.wire_start_coords = None
        if self.temp_wire_start_indicator:
            self.canvas.delete(self.temp_wire_start_indicator)
            self.temp_wire_start_indicator = None
        if comp_type:
            self.display_message("Status", f"{comp_type} selected. Click on canvas.")
            self._clear_selection_and_properties_editor()
        else:
            self.display_message("Status", "Placement mode off.")

    def _select_wire_tool(self):
        self.wiring_mode = True
        self.selected_component_to_place = None
        self._clear_selection_and_properties_editor()
        if self.temp_wire_start_indicator:
            self.canvas.delete(self.temp_wire_start_indicator)
            self.temp_wire_start_indicator = None
        self.wire_start_coords = None
        self.display_message("Status", "Wire tool selected. Click start, then end point.")

    def _on_canvas_click(self, event):
        if self.wiring_mode:
            if self.wire_start_coords is None:
                self.wire_start_coords = (event.x, event.y)
                if self.temp_wire_start_indicator: self.canvas.delete(self.temp_wire_start_indicator)
                self.temp_wire_start_indicator = self.canvas.create_oval(event.x-3, event.y-3, event.x+3, event.y+3, fill="red", outline="red")
                self.display_message("Wiring", f"Wire started at ({event.x},{event.y}). Click end point.")
            else:
                x1, y1 = self.wire_start_coords; x2, y2 = event.x, event.y
                wire_id_str = f"wire_{self.next_wire_id}"; self.next_wire_id += 1
                line_canvas_id = self.canvas.create_line(x1, y1, x2, y2, fill="black", width=2, tags=("wire", wire_id_str))
                self.drawn_wires.append({'id': wire_id_str, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'canvas_line_id': line_canvas_id})
                self.display_message("Wiring", f"Wire {wire_id_str} drawn from ({x1},{y1}) to ({x2},{y2}).")
                self.wire_start_coords = None
                if self.temp_wire_start_indicator: self.canvas.delete(self.temp_wire_start_indicator); self.temp_wire_start_indicator = None
            return

        if self.selected_component_to_place:
            x, y = event.x, event.y; comp_type = self.selected_component_to_place
            base_name = {"Resistor":"R", "V_Source_DC":"VS", "I_Source_DC":"IS"}.get(comp_type, "X")
            current_names = {entry['name'].get() for entry in self.component_entries}
            num = 1; gen_name = f"{base_name}{num}"
            while gen_name in current_names: num += 1; gen_name = f"{base_name}{num}"
            def_sym_val = f"{gen_name}_sym"
            canvas_ids = self._draw_component_symbol(x, y, comp_type, gen_name)
            self.placed_graphical_items.append({'id': gen_name, 'type': comp_type, 'x': x, 'y': y, 'canvas_item_ids': canvas_ids})
            self._add_component_row(load_data={'type': comp_type, 'name': gen_name, 'value': def_sym_val, 'n1': "?", 'n2': "?"})
            self.display_message("Canvas", f"Placed {comp_type} '{gen_name}'. Added to list.")
        else:
            clicked_item_gui_name = None
            for item_info in reversed(self.placed_graphical_items):
                ix, iy, radius = item_info['x'], item_info['y'], 25
                if (ix - radius <= event.x <= ix + radius and iy - radius <= event.y <= iy + radius):
                    clicked_item_gui_name = item_info['id']; break
            if clicked_item_gui_name:
                if self.currently_selected_canvas_item_gui_name == clicked_item_gui_name and self.last_selection_coords == (event.x, event.y):
                    self._clear_selection_and_properties_editor()
                else:
                    if self.currently_selected_canvas_item_gui_name and self.currently_selected_canvas_item_gui_name != clicked_item_gui_name:
                        old_tag = f"comp_{self.currently_selected_canvas_item_gui_name}"
                        for cid in self.canvas.find_withtag(old_tag):
                            if self.canvas.type(cid) not in ["text","line"]: self.canvas.itemconfig(cid, outline="black", width=1)
                    self.currently_selected_canvas_item_gui_name = clicked_item_gui_name
                    self.last_selection_coords = (event.x, event.y)
                    new_tag = f"comp_{clicked_item_gui_name}"
                    for cid in self.canvas.find_withtag(new_tag):
                        if self.canvas.type(cid) not in ["text","line"]: self.canvas.itemconfig(cid, outline="red", width=2)
                    self._populate_properties_editor(clicked_item_gui_name)
            else: self._clear_selection_and_properties_editor()

    def _draw_component_symbol(self, x, y, comp_type, gui_name):
        tag = f"comp_{gui_name}"; canvas_ids = []; size = 20
        if comp_type == "Resistor":
            canvas_ids.append(self.canvas.create_rectangle(x-size*1.5,y-size*0.5,x+size*1.5,y+size*0.5,outline="black",fill="lightblue",tags=(tag,)))
        elif comp_type == "V_Source_DC":
            canvas_ids.append(self.canvas.create_oval(x-size,y-size,x+size,y+size,outline="black",fill="lightgreen",tags=(tag,)))
            canvas_ids.append(self.canvas.create_line(x,y-size*0.6,x,y-size*0.2,tags=(tag,))); canvas_ids.append(self.canvas.create_line(x-size*0.2,y-size*0.4,x+size*0.2,y-size*0.4,tags=(tag,))) # Plus
            canvas_ids.append(self.canvas.create_line(x-size*0.2,y+size*0.4,x+size*0.2,y+size*0.4,width=2,tags=(tag,))) # Minus
        elif comp_type == "I_Source_DC":
            canvas_ids.append(self.canvas.create_oval(x-size,y-size,x+size,y+size,outline="black",fill="lightpink",tags=(tag,)))
            canvas_ids.append(self.canvas.create_line(x,y+size*0.6,x,y-size*0.6,tags=(tag,))); canvas_ids.append(self.canvas.create_line(x,y-size*0.6,x-size*0.2,y-size*0.3,x+size*0.2,y-size*0.3,x,y-size*0.6,smooth=True,tags=(tag,))) # Arrow
        else: canvas_ids.append(self.canvas.create_text(x,y,text=f"{comp_type[:3]}?",tags=(tag,)))
        canvas_ids.append(self.canvas.create_text(x,y-size-7,text=gui_name,font=("Arial",8),tags=(tag,)))
        return canvas_ids

    def _populate_properties_editor(self, gui_name):
        found_entry_dict = None
        for entry_widgets_dict in self.component_entries:
            if entry_widgets_dict['name'].get() == gui_name: found_entry_dict = entry_widgets_dict; break
        if found_entry_dict:
            self.prop_selected_label.config(text=f"Selected: {gui_name}")
            self.prop_type_label.config(text=f"Type: {found_entry_dict['type'].get()}")
            for prop, widget in {'name':self.prop_name_entry, 'value':self.prop_value_entry, 'n1':self.prop_n1_entry, 'n2':self.prop_n2_entry}.items():
                widget.config(state=tk.NORMAL); widget.delete(0,tk.END); widget.insert(0, found_entry_dict[prop].get())
            self.update_props_button.config(state=tk.NORMAL)
        else: self._clear_selection_and_properties_editor()

    def _clear_selection_and_properties_editor(self):
        if self.currently_selected_canvas_item_gui_name:
            old_tag = f"comp_{self.currently_selected_canvas_item_gui_name}"
            for cid in self.canvas.find_withtag(old_tag):
                if self.canvas.type(cid) not in ["text","line"]: self.canvas.itemconfig(cid, outline="black",width=1)
        self.currently_selected_canvas_item_gui_name = None; self.last_selection_coords = None
        self.prop_selected_label.config(text="Selected: None"); self.prop_type_label.config(text="Type: N/A")
        for widget in [self.prop_name_entry,self.prop_value_entry,self.prop_n1_entry,self.prop_n2_entry]:
            widget.delete(0,tk.END); widget.config(state=tk.DISABLED)
        self.update_props_button.config(state=tk.DISABLED)

    def _update_component_properties(self):
        if not self.currently_selected_canvas_item_gui_name: return
        old_gui_name = self.currently_selected_canvas_item_gui_name
        new_gui_name = self.prop_name_entry.get().strip()
        if not new_gui_name: messagebox.showerror("Error","Component GUI Name cannot be empty."); return

        target_entry_widgets_idx = -1; name_already_exists = False
        for i, entry_widgets in enumerate(self.component_entries):
            if entry_widgets['name'].get() == old_gui_name: target_entry_widgets_idx = i
            if entry_widgets['name'].get() == new_gui_name and old_gui_name != new_gui_name : name_already_exists = True

        if name_already_exists: messagebox.showerror("Error", f"GUI Name '{new_gui_name}' already exists."); return

        if target_entry_widgets_idx != -1:
            entry_widgets = self.component_entries[target_entry_widgets_idx]
            entry_widgets['name'].delete(0,tk.END); entry_widgets['name'].insert(0, new_gui_name)
            entry_widgets['value'].delete(0,tk.END); entry_widgets['value'].insert(0, self.prop_value_entry.get().strip())
            entry_widgets['n1'].delete(0,tk.END); entry_widgets['n1'].insert(0, self.prop_n1_entry.get().strip())
            entry_widgets['n2'].delete(0,tk.END); entry_widgets['n2'].insert(0, self.prop_n2_entry.get().strip())

        canvas_item_info_to_update_idx = -1
        for i, item_info in enumerate(self.placed_graphical_items):
            if item_info['id'] == old_gui_name: canvas_item_info_to_update_idx = i; break

        if canvas_item_info_to_update_idx != -1:
            item_info = self.placed_graphical_items[canvas_item_info_to_update_idx]
            item_info['id'] = new_gui_name # Critical: update ID in placed_graphical_items
            if old_gui_name != new_gui_name:
                old_tag = f"comp_{old_gui_name}"; new_tag = f"comp_{new_gui_name}"
                label_updated_on_canvas = False
                for c_id in item_info['canvas_item_ids']:
                    current_tags = list(self.canvas.gettags(c_id))
                    try: current_tags.remove(old_tag)
                    except ValueError: pass
                    current_tags.append(new_tag)
                    self.canvas.itemconfig(c_id, tags=tuple(current_tags))
                    # Update text of the label item
                    # This assumes label is the last item and is of type 'text'
                    if c_id == item_info['canvas_item_ids'][-1] and self.canvas.type(c_id) == "text":
                       self.canvas.itemconfig(c_id, text=new_gui_name)
                       label_updated_on_canvas = True
                if not label_updated_on_canvas: # Fallback if assumption failed (e.g. label not last)
                    for c_id in self.canvas.find_withtag(new_tag): # Search by new tag
                         if self.canvas.type(c_id) == "text":
                             # Check if this text item belongs to the component (e.g. by coords or more specific tag)
                             # For now, this might re-label other text items if not careful.
                             # A more robust way is to have a specific, unique tag for the label text item itself.
                             # Example: self.canvas.itemconfig(the_actual_label_id_stored_separately, text=new_gui_name)
                             # For now, we assume the last item is the label.
                             pass # The above heuristic is kept.

        self.currently_selected_canvas_item_gui_name = new_gui_name
        self.prop_selected_label.config(text=f"Selected: {new_gui_name}")
        self.display_message("Properties", f"Properties for '{old_gui_name}' updated to '{new_gui_name}'.")

if __name__ == '__main__':
    app = CircuitGUI()
    app.mainloop()
