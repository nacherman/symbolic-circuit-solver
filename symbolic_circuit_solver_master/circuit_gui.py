import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import tempfile
import sympy
import json
import math

from . import scs_parser
from . import scs_instance_hier
from . import scs_circuit
from . import scs_errors
from symbolic_circuit_solver_master.scs_symbolic_solver_tool import SymbolicCircuitProblemSolver


class CircuitGUI(tk.Tk):
    def __init__(self):
        self.top_instance = None
        self.active_symbols_info = {}
        self.selected_component_to_place = None
        self.placed_graphical_items = []
        self.currently_selected_canvas_item_gui_name = None
        self.last_selection_coords = None

        self.wiring_mode = False
        self.wire_start_coords = None
        self.wire_pending_connection_start = None
        self.drawn_wires = []
        self.next_wire_id = 0
        self.temp_wire_start_indicator = None
        self.next_auto_node_id = 1
        self.currently_selected_wire_info = None

        self.drag_data = {
            'item_gui_name': None,
            'press_mouse_x_canvas': 0, 'press_mouse_y_canvas': 0,
            'current_drag_mouse_x_canvas': 0, 'current_drag_mouse_y_canvas': 0,
            'original_item_logical_x': 0, 'original_item_logical_y': 0
        }

        self.canvas_scale = 1.0
        self.show_grid = tk.BooleanVar(value=True)

        super().__init__()
        self.title("Symbolic Circuit Simulator GUI - Phase 1")
        self.geometry("1000x750") # Increased height slightly for new section

        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Left Frame (Component Palette) ---
        self.palette_frame = ttk.LabelFrame(self.main_frame, text="Components", padding="10")
        self.palette_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        ttk.Label(self.palette_frame, text="Select tool:").pack(pady=5)
        ttk.Button(self.palette_frame, text="Select", command=self._select_select_tool).pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="Resistor", command=lambda: self._select_component_for_placement("Resistor")).pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="V_Source_DC", command=lambda: self._select_component_for_placement("V_Source_DC")).pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="I_Source_DC", command=lambda: self._select_component_for_placement("I_Source_DC")).pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="Wire", command=self._select_wire_tool).pack(fill=tk.X, pady=2)

        # --- Right Frame (Results/Formulas Display) ---
        self.results_frame = ttk.LabelFrame(self.main_frame, text="Formulas & Results", padding="10")
        self.results_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.results_text = tk.Text(self.results_frame, wrap=tk.WORD, height=15, state=tk.DISABLED)
        self.results_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # --- Center Frame (Canvas & Properties) ---
        self.center_frame_top = ttk.Frame(self.main_frame, padding="5")
        self.center_frame_top.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        zoom_button_frame = ttk.Frame(self.center_frame_top)
        zoom_button_frame.pack(side=tk.TOP, fill=tk.X, pady=2)
        ttk.Button(zoom_button_frame, text="Zoom In (+)", command=self._zoom_in).pack(side=tk.LEFT, padx=5)
        ttk.Button(zoom_button_frame, text="Zoom Out (-)", command=self._zoom_out).pack(side=tk.LEFT, padx=5)
        self.scale_label = ttk.Label(zoom_button_frame, text=f"Scale: {self.canvas_scale:.2f}")
        self.scale_label.pack(side=tk.LEFT, padx=5)
        self.grid_checkbutton = ttk.Checkbutton(zoom_button_frame, text="Show Grid", variable=self.show_grid, command=self._redraw_canvas)
        self.grid_checkbutton.pack(side=tk.LEFT, padx=5)

        self.canvas_frame_container = ttk.LabelFrame(self.center_frame_top, text="Circuit Canvas", padding="10")
        self.canvas_frame_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5, padx=(0,5))
        self.canvas = tk.Canvas(self.canvas_frame_container, bg="white", width=550, height=350)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_button_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_button_release)
        self.canvas.bind("<ButtonPress-2>", self._pan_start)
        self.canvas.bind("<ButtonPress-3>", self._pan_start)
        self.canvas.bind("<B2-Motion>", self._pan_move)
        self.canvas.bind("<B3-Motion>", self._pan_move)
        self.canvas.config(scrollregion=(-20000, -20000, 20000, 20000))

        self.properties_editor_frame = ttk.LabelFrame(self.center_frame_top, text="Properties Editor", padding="10")
        self.properties_editor_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5,0), pady=5)
        self.prop_selected_label = ttk.Label(self.properties_editor_frame, text="Selected: None")
        self.prop_selected_label.pack(pady=(0,5), anchor=tk.W)
        self.prop_type_label = ttk.Label(self.properties_editor_frame, text="Type: N/A")
        self.prop_type_label.pack(pady=(0,10), anchor=tk.W)
        prop_name_frame = ttk.Frame(self.properties_editor_frame); prop_name_frame.pack(fill=tk.X, pady=2)
        ttk.Label(prop_name_frame, text="GUI Name:").pack(side=tk.LEFT)
        self.prop_name_entry = ttk.Entry(prop_name_frame, width=15); self.prop_name_entry.pack(side=tk.LEFT, padx=5, expand=True)
        prop_value_frame = ttk.Frame(self.properties_editor_frame); prop_value_frame.pack(fill=tk.X, pady=2)
        ttk.Label(prop_value_frame, text="Value/Sym:").pack(side=tk.LEFT)
        self.prop_value_entry = ttk.Entry(prop_value_frame, width=15); self.prop_value_entry.pack(side=tk.LEFT, padx=5, expand=True)
        prop_n1_frame = ttk.Frame(self.properties_editor_frame); prop_n1_frame.pack(fill=tk.X, pady=2)
        ttk.Label(prop_n1_frame, text="Node 1:").pack(side=tk.LEFT)
        self.prop_n1_entry = ttk.Entry(prop_n1_frame, width=15); self.prop_n1_entry.pack(side=tk.LEFT, padx=5, expand=True)
        prop_n2_frame = ttk.Frame(self.properties_editor_frame); prop_n2_frame.pack(fill=tk.X, pady=2)
        ttk.Label(prop_n2_frame, text="Node 2:").pack(side=tk.LEFT)
        self.prop_n2_entry = ttk.Entry(prop_n2_frame, width=15); self.prop_n2_entry.pack(side=tk.LEFT, padx=5, expand=True)
        self.update_props_button = ttk.Button(self.properties_editor_frame, text="Update Properties", command=self._update_component_properties, state=tk.DISABLED)
        self.update_props_button.pack(pady=10)

        self.input_area_main_frame = ttk.LabelFrame(self.main_frame, text="Circuit Definition & Solver Controls", padding="10")
        self.input_area_main_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5, expand=False)

        # Frame for programmatic component list and its action buttons
        programmatic_list_frame = ttk.Frame(self.input_area_main_frame)
        programmatic_list_frame.pack(fill=tk.X, expand=True, pady=(0,5))

        self.components_list_container_frame = ttk.Frame(programmatic_list_frame)
        self.components_list_container_frame.pack(fill=tk.X, expand=True, pady=(0,5))
        self.component_entries = []

        self.action_buttons_frame = ttk.Frame(programmatic_list_frame)
        self.action_buttons_frame.pack(fill=tk.X, pady=5)
        self.add_comp_button = ttk.Button(self.action_buttons_frame, text="Add Component", command=self._add_component_row); self.add_comp_button.pack(side=tk.LEFT, padx=5)
        self.remove_comp_button = ttk.Button(self.action_buttons_frame, text="Remove Last Component", command=self._remove_last_component_row); self.remove_comp_button.pack(side=tk.LEFT, padx=5)
        self.delete_button = ttk.Button(self.action_buttons_frame, text="Delete Selected", command=self._delete_selected, state=tk.DISABLED)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        self.save_circuit_button = ttk.Button(self.action_buttons_frame, text="Save Circuit", command=self._save_circuit_to_file); self.save_circuit_button.pack(side=tk.LEFT, padx=5)
        self.load_circuit_button = ttk.Button(self.action_buttons_frame, text="Load Circuit", command=self._load_circuit_from_file); self.load_circuit_button.pack(side=tk.LEFT, padx=5)
        self.derive_button = ttk.Button(self.action_buttons_frame, text="Derive Formulas", command=self.on_derive_formulas); self.derive_button.pack(side=tk.LEFT, padx=5)
        self.calculate_button = ttk.Button(self.action_buttons_frame, text="Calculate Numerical Values", command=self.on_calculate_numerical); self.calculate_button.pack(side=tk.LEFT, padx=5)

        self.analysis_options_frame = ttk.LabelFrame(self.input_area_main_frame, text="General Analysis Targets", padding="10")
        self.analysis_options_frame.pack(fill=tk.X, pady=(5,0), side=tk.TOP)
        ttk.Label(self.analysis_options_frame, text="Target Comp. Name (GUI Name):").pack(side=tk.LEFT, padx=5)
        self.target_comp_name_entry = ttk.Entry(self.analysis_options_frame, width=10); self.target_comp_name_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(self.analysis_options_frame, text="Target Node (for V(node,'0')):") .pack(side=tk.LEFT, padx=5)
        self.target_node_name_entry = ttk.Entry(self.analysis_options_frame, width=10); self.target_node_name_entry.pack(side=tk.LEFT, padx=5)

        # --- Advanced Solve Mode Frame ---
        self.advanced_solve_frame = ttk.LabelFrame(self.input_area_main_frame, text="Solve for Unknowns (Targeted Solver)", padding="10")
        self.advanced_solve_frame.pack(fill=tk.X, pady=(5,0), side=tk.TOP)

        params_frame = ttk.Frame(self.advanced_solve_frame)
        params_frame.pack(fill=tk.X, pady=2)
        ttk.Label(params_frame, text="Params to Solve (symbols, comma-sep):").pack(side=tk.LEFT, padx=2)
        self.adv_params_to_solve_entry = ttk.Entry(params_frame, width=40)
        self.adv_params_to_solve_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        ttk.Label(self.advanced_solve_frame, text="Known Conditions:").pack(anchor=tk.W, pady=(5,2))
        self.adv_known_condition_entries = []
        for i in range(3): # Create 3 rows for conditions
            cond_frame = ttk.Frame(self.advanced_solve_frame)
            cond_frame.pack(fill=tk.X, pady=1)
            type_combo = ttk.Combobox(cond_frame, values=["", "voltage", "current", "power"], width=8, state="readonly")
            type_combo.pack(side=tk.LEFT, padx=2); type_combo.current(0)
            ttk.Label(cond_frame, text="El/N1:").pack(side=tk.LEFT, padx=2)
            el_n1_entry = ttk.Entry(cond_frame, width=10); el_n1_entry.pack(side=tk.LEFT, padx=2)
            ttk.Label(cond_frame, text="N2:").pack(side=tk.LEFT, padx=2)
            n2_entry = ttk.Entry(cond_frame, width=5); n2_entry.pack(side=tk.LEFT, padx=2)
            ttk.Label(cond_frame, text="Val:").pack(side=tk.LEFT, padx=2)
            val_entry = ttk.Entry(cond_frame, width=10); val_entry.pack(side=tk.LEFT, padx=2)
            self.adv_known_condition_entries.append({'type': type_combo, 'el_n1': el_n1_entry, 'n2': n2_entry, 'val': val_entry})

        self.adv_solve_button = ttk.Button(self.advanced_solve_frame, text="Run Advanced Solve", command=self._run_advanced_solve)
        self.adv_solve_button.pack(pady=5)

        self._add_component_row(load_data={'type':"V_Source_DC", 'name':"S1", 'value':"US_sym", 'n1':"n1", 'n2':"0"})
        self._add_component_row(load_data={'type':"Resistor", 'name':"R1", 'value':"R1_sym", 'n1':"n1", 'n2':"n2"})
        self._add_component_row(load_data={'type':"Resistor", 'name':"R2", 'value':"R2_sym", 'n1':"n2", 'n2':"0"})
        for _ in range(1): self._add_component_row()
        self._redraw_canvas()

    # ... (Coordinate Conversion, Zoom, Pan, Redraw methods as defined in previous subtask) ...
    def _canvas_to_logical_coords(self, canvas_x, canvas_y):
        logical_x = self.canvas.canvasx(canvas_x) / self.canvas_scale
        logical_y = self.canvas.canvasy(canvas_y) / self.canvas_scale
        return logical_x, logical_y

    def _logical_to_canvas_coords(self, logical_x, logical_y):
        canvas_x = logical_x * self.canvas_scale
        canvas_y = logical_y * self.canvas_scale
        return canvas_x, canvas_y

    def _zoom(self, factor):
        self.canvas_scale *= factor
        self.canvas_scale = min(max(self.canvas_scale, 0.1), 5.0)
        self.scale_label.config(text=f"Scale: {self.canvas_scale:.2f}")
        self._redraw_canvas()

    def _zoom_in(self): self._zoom(1.2); self.display_message("Canvas", f"Zoom In. Scale: {self.canvas_scale:.2f}")
    def _zoom_out(self): self._zoom(1/1.2); self.display_message("Canvas", f"Zoom Out. Scale: {self.canvas_scale:.2f}")
    def _pan_start(self, event): self.canvas.scan_mark(event.x, event.y)
    def _pan_move(self, event): self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _redraw_canvas(self):
        self.canvas.delete("all")
        if self.show_grid.get():
            logical_grid_spacing = 50
            canvas_view_x0 = self.canvas.canvasx(0); canvas_view_y0 = self.canvas.canvasy(0)
            canvas_view_x1 = self.canvas.canvasx(self.canvas.winfo_width()); canvas_view_y1 = self.canvas.canvasy(self.canvas.winfo_height())
            logical_view_x0 = canvas_view_x0 / self.canvas_scale; logical_view_y0 = canvas_view_y0 / self.canvas_scale
            logical_view_x1 = canvas_view_x1 / self.canvas_scale; logical_view_y1 = canvas_view_y1 / self.canvas_scale
            start_lx = math.floor(logical_view_x0 / logical_grid_spacing) * logical_grid_spacing
            end_lx = math.ceil(logical_view_x1 / logical_grid_spacing) * logical_grid_spacing
            for lx in range(int(start_lx), int(end_lx) + 1, logical_grid_spacing):
                cx_start, _ = self._logical_to_canvas_coords(lx, logical_view_y0)
                self.canvas.create_line(cx_start, canvas_view_y0, cx_start, canvas_view_y1, fill="#e0e0e0", tags="grid_line")
            start_ly = math.floor(logical_view_y0 / logical_grid_spacing) * logical_grid_spacing
            end_ly = math.ceil(logical_view_y1 / logical_grid_spacing) * logical_grid_spacing
            for ly in range(int(start_ly), int(end_ly) + 1, logical_grid_spacing):
                _, cy_start = self._logical_to_canvas_coords(logical_view_x0, ly)
                self.canvas.create_line(canvas_view_x0, cy_start, canvas_view_x1, cy_start, fill="#e0e0e0", tags="grid_line")

        for item_info in self.placed_graphical_items:
            canvas_item_center_x, canvas_item_center_y = self._logical_to_canvas_coords(item_info['x'], item_info['y'])
            item_info['canvas_item_ids'] = self._draw_component_symbol(canvas_item_center_x, canvas_item_center_y, item_info['type'], item_info['id'], scale=self.canvas_scale)
            if item_info['id'] == self.currently_selected_canvas_item_gui_name:
                for c_id in item_info['canvas_item_ids']:
                    if self.canvas.type(c_id) not in ["text", "line"]: self.canvas.itemconfig(c_id, outline='red', width=max(1, int(2*self.canvas_scale)))
        for wire_info in self.drawn_wires:
            lx1,ly1,lx2,ly2 = wire_info['x1'],wire_info['y1'],wire_info['x2'],wire_info['y2']
            cx1,cy1 = self._logical_to_canvas_coords(lx1,ly1); cx2,cy2 = self._logical_to_canvas_coords(lx2,ly2)
            wire_w = max(1,int(2*self.canvas_scale)); fc = 'blue' if self.currently_selected_wire_info and self.currently_selected_wire_info['id']==wire_info['id'] else 'black'
            wire_info['canvas_line_id'] = self.canvas.create_line(cx1,cy1,cx2,cy2,fill=fc,width=wire_w,tags=("wire",wire_info['id']))
        if self.temp_wire_start_indicator and self.wire_start_coords:
            csx,csy = self._logical_to_canvas_coords(self.wire_start_coords[0],self.wire_start_coords[1])
            self.temp_wire_start_indicator = self.canvas.create_oval(csx-3,csy-3,csx+3,csy+3,fill="red",outline="red",tags="temp_indicator")

    def display_message(self, title, message):
        self.results_text.config(state=tk.NORMAL); self.results_text.insert(tk.END, f"--- {title} ---\n{message}\n\n"); self.results_text.see(tk.END); self.results_text.config(state=tk.DISABLED)

    def on_derive_formulas(self):
        self.results_text.config(state=tk.NORMAL); self.results_text.delete('1.0', tk.END); self.results_text.config(state=tk.DISABLED)
        circuit_data = self._collect_circuit_data()
        if not circuit_data: self.display_message("Input Error", "No valid component data entered."); return

        # Pass circuit_data to _generate_spice_netlist, which now might display its own warning for skipped components
        spice_string = self._generate_spice_netlist(circuit_data)
        # _generate_spice_netlist already displays warning if any component is skipped

        self.display_message("Generated SPICE Netlist", spice_string) # This will appear after any warning from _generate_spice_netlist

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
                    comp_details = self._get_component_details_from_gui_name(target_comp_gui_name, circuit_data) # Use circuit_data from this run
                    if comp_details:
                        formulas_str += f"  --- For Comp (GUI:{target_comp_gui_name}, SPICE:{comp_details['spice_name']}) ---\n"
                        try: formulas_str += f"    V({comp_details['n1']},{comp_details['n2']}): {sympy.pretty(self.top_instance.v(comp_details['n1'], comp_details['n2']))}\n"
                        except Exception as e: formulas_str += f"    Error V: {type(e).__name__} - {e}\n"
                        try: formulas_str += f"    I({comp_details['spice_name']}): {sympy.pretty(self.top_instance.i(comp_details['spice_name']))}\n"
                        except Exception as e: formulas_str += f"    Error I: {type(e).__name__} - {e}\n"
                        try: formulas_str += f"    P({comp_details['spice_name']}): {sympy.pretty(self.top_instance.p(comp_details['spice_name']))}\n"
                        except Exception as e: formulas_str += f"    Error P: {type(e).__name__} - {e}\n"
                    else: formulas_str += f"  Comp GUI Name '{target_comp_gui_name}' not found.\n"
                if target_node_name:
                    formulas_str += f"  --- For Node {target_node_name} ---\n"
                    try: formulas_str += f"    V({target_node_name},'0'): {sympy.pretty(self.top_instance.v(target_node_name, '0'))}\n"
                    except Exception as e: formulas_str += f"    Error V({target_node_name},'0'): {type(e).__name__} - {e}\n"
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

    def _collect_advanced_solve_inputs(self):
        params_str = self.adv_params_to_solve_entry.get().strip()
        if not params_str: self.display_message("Input Error", "No params to solve specified."); return None, None
        params_to_solve_list = [p.strip() for p in params_str.split(',') if p.strip()]
        if not params_to_solve_list: self.display_message("Input Error", "Params to solve list empty."); return None, None
        known_conditions_list = []
        for cond_widgets in self.adv_known_condition_entries:
            cond_type = cond_widgets['type'].get(); el_n1_str = cond_widgets['el_n1'].get().strip(); val_str = cond_widgets['val'].get().strip()
            if cond_type and el_n1_str and val_str:
                try: num_value = float(val_str)
                except ValueError: self.display_message("Input Error", f"Invalid value '{val_str}'."); return None, None
                condition = {'type': cond_type, 'value': num_value}
                if cond_type == 'voltage': condition['node1'] = el_n1_str; condition['node2'] = cond_widgets['n2'].get().strip() or '0'
                elif cond_type in ['current', 'power']: condition['element'] = el_n1_str
                else: self.display_message("Input Error", f"Unknown condition type: {cond_type}"); return None, None
                known_conditions_list.append(condition)
        if not known_conditions_list: self.display_message("Input Error", "No valid conditions specified."); return None, None
        return params_to_solve_list, known_conditions_list

    def _run_advanced_solve(self):
        self.results_text.config(state=tk.NORMAL); self.results_text.delete('1.0', tk.END); self.results_text.config(state=tk.DISABLED)
        circuit_data = self._collect_circuit_data()
        if not circuit_data: self.display_message("Circuit Error", "No circuit defined."); return
        spice_string = self._generate_spice_netlist(circuit_data)
        if not spice_string or "Error" in spice_string : self.display_message("SPICE Error", "Failed to gen SPICE."); return
        self.display_message("Adv. Solve SPICE", spice_string)
        params_to_solve, known_conditions = self._collect_advanced_solve_inputs()
        if not params_to_solve or not known_conditions: return
        temp_spice_file_path = ""
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sp', dir='.') as tmp_file:
                tmp_file.write(spice_string); temp_spice_file_path = tmp_file.name
            self.display_message("Adv. Solver", f"SPICE: {os.path.basename(temp_spice_file_path)}, Params: {params_to_solve}, Conditions: {known_conditions}")
            adv_solver = SymbolicCircuitProblemSolver(netlist_path=temp_spice_file_path)
            solution = adv_solver.solve_for_unknowns(known_conditions, params_to_solve)
            solution_str = "Adv. Solve Solution:\n"
            if not solution: solution_str += "  No solution found.\n"
            else:
                for var, val in solution.items():
                    solution_str += f"  {str(var)} = {sympy.pretty(val) if hasattr(val, '_pretty') else str(val)}\n"
                    if hasattr(val, 'evalf'):
                        try: solution_str += f"    Numerical: {val.evalf():.4g}\n"
                        except: solution_str += f"    Numerical: (evalf failed)\n"
            self.display_message("Adv. Solution", solution_str)
        except (scs_errors.ScsParserError, scs_errors.ScsInstanceError, scs_errors.ScsToolError, ValueError) as e:
            self.display_message("Adv. Solver Error", f"{type(e).__name__}: {e}")
        except Exception as e:
            self.display_message("Adv. Solver Error (Unexpected)", f"{type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
        finally:
            if temp_spice_file_path and os.path.exists(temp_spice_file_path):
                try: os.remove(temp_spice_file_path)
                except Exception as e: print(f"Error removing temp file: {e}")

    # ... (Methods from _get_component_details_from_gui_name to _update_nodes_from_wire as previously defined) ...
    # ... (This includes: _get_component_details_from_gui_name, _eval_expr_to_float, _add_component_row, _remove_last_component_row)
    # ... (_collect_circuit_data, _generate_spice_netlist, on_calculate_numerical, _save_circuit_to_file, _load_circuit_from_file)
    # ... (_select_component_for_placement, _select_wire_tool, _select_select_tool)
    # ... (_on_canvas_button_press, _on_canvas_drag_motion, _on_canvas_button_release, _draw_component_symbol)
    # ... (_populate_properties_editor, _clear_selection_and_properties_editor, _update_component_properties)
    # ... (_update_button_states, _delete_wire_by_id, _delete_selected)
    # ... (_update_pin_node_after_wire_deletion, _get_node_for_pin, _set_node_for_pin, _update_nodes_from_wire)
    # --- Re-inserting all methods from _get_component_details_from_gui_name onwards from previous state ---
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

    def _add_component_row(self, load_data=None): # Copied
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

    def _remove_last_component_row(self): # Copied
        if self.component_entries: self.component_entries.pop()['frame'].destroy()

    def _collect_circuit_data(self): # Copied
        data = []
        for widgets in self.component_entries:
            if widgets['type'].get() and widgets['name'].get().strip():
                data.append({'type': widgets['type'].get(), 'name': widgets['name'].get().strip(),
                             'value': widgets['value'].get().strip(), 'n1': widgets['n1'].get().strip(),
                             'n2': widgets['n2'].get().strip()})
        return data

    def _generate_spice_netlist(self, circuit_data): # Modified for warning display
        lines = ['* Generated SPICE Netlist from GUI']; params = []; sym_ensure = set()
        skipped_components_info = []
        def is_num(s): try: float(s); return True; except: return False

        for comp in circuit_data:
            n1_val = comp.get('n1', '').strip(); n2_val = comp.get('n2', '').strip()
            if not n1_val or n1_val == "?" or not n2_val or n2_val == "?":
                skipped_components_info.append(f"{comp.get('type','UnknownType')} '{comp.get('name','Unnamed')}' (Nodes: '{n1_val}', '{n2_val}')")
                continue

            val_param = comp['name'] + "_val"; val_str = comp['value']; sym_to_use = val_str
            if not val_str:
                if comp['type']=="Resistor": sym_to_use=comp['name']+"_sym"
                elif "Source" in comp['type']: sym_to_use=comp['name']+"_src_sym"
                else: self.display_message("Netlist Gen Error", f"Empty value for {comp['name']} type {comp['type']}. Defaulting to 0."); val_str = "0"; sym_to_use = "0"
                if val_str == "0": params.append(f".PARAM {val_param} = 0")
                else: params.append(f".PARAM {val_param} = {sym_to_use}"); sym_ensure.add(f".PARAM {sym_to_use} = {sym_to_use}")
            elif not is_num(val_str): params.append(f".PARAM {val_param} = {sym_to_use}"); sym_ensure.add(f".PARAM {sym_to_use} = {sym_to_use}")
            else: params.append(f".PARAM {val_param} = {val_str}")
            prefix = {"Resistor":"R","V_Source_DC":"V","I_Source_DC":"I"}.get(comp['type'],"X")
            lines.append(f"{prefix}{comp['name']} {comp['n1']} {comp['n2']} {val_param}")

        if skipped_components_info:
            self.display_message("SPICE Generation Warning", "Skipped components due to undefined nodes:\n- " + "\n- ".join(skipped_components_info))

        unique_symbol_ensure_lines = sorted(list(sym_ensure))
        netlist_parts = [lines[0]]
        if params: netlist_parts.extend(params)
        if unique_symbol_ensure_lines: netlist_parts.extend(unique_symbol_ensure_lines)
        netlist_parts.extend(lines[1:])
        netlist_parts.append(".END")
        return "\n".join(netlist_parts)

    def on_calculate_numerical(self): # Copied
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
        if not comp_name and not node_name: res_str+="  No target specified. Enter GUI Comp. Name or Node Name.\n"
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

    def _save_circuit_to_file(self): # Copied
        circuit_data = self._collect_circuit_data()
        if not circuit_data: messagebox.showwarning("Save Circuit", "No circuit data to save."); return
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")], title="Save Circuit As", initialdir=os.path.join(os.getcwd(), "examples"))
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(circuit_data, f, indent=4)
            self.display_message("Save Circuit", f"Circuit saved to {os.path.basename(filepath)}")
        except Exception as e: self.display_message("Save Error", f"Failed to save: {e}")

    def _load_circuit_from_file(self): # Copied
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

    def _select_component_for_placement(self, comp_type): # Modified
        if self.currently_selected_wire_info:
            try: self.canvas.itemconfig(self.currently_selected_wire_info['canvas_line_id'], fill='black', width=max(1, int(2*self.canvas_scale)))
            except tk.TclError: pass
            self.currently_selected_wire_info = None
        self._clear_selection_and_properties_editor()

        self.selected_component_to_place = comp_type
        self.wiring_mode = False
        self.wire_start_coords = None
        if self.temp_wire_start_indicator:
            self.canvas.delete(self.temp_wire_start_indicator)
            self.temp_wire_start_indicator = None

        if comp_type:
            self.display_message("Status", f"{comp_type} selected. Click on canvas to place.")
        else:
            self.display_message("Status", "Component placement deselected.")
        self._update_button_states()


    def _select_wire_tool(self): # Modified
        if self.currently_selected_wire_info:
            try: self.canvas.itemconfig(self.currently_selected_wire_info['canvas_line_id'], fill='black', width=max(1, int(2*self.canvas_scale)))
            except tk.TclError: pass
            self.currently_selected_wire_info = None
        self._clear_selection_and_properties_editor()

        self.wiring_mode = True
        self.selected_component_to_place = None
        if self.temp_wire_start_indicator:
            self.canvas.delete(self.temp_wire_start_indicator)
            self.temp_wire_start_indicator = None
        self.wire_start_coords = None
        self.wire_pending_connection_start = None
        self._update_button_states()
        self.display_message("Status", "Wire tool selected. Click start, then end point.")

    def _select_select_tool(self): # New
        self.wiring_mode = False
        self.selected_component_to_place = None
        if self.temp_wire_start_indicator:
            self.canvas.delete(self.temp_wire_start_indicator)
            self.temp_wire_start_indicator = None
        self.wire_start_coords = None
        self._update_button_states()
        self.display_message("Status", "Select tool active. Click on components or wires.")

    def _on_canvas_button_press(self, event): # Modified
        logical_x, logical_y = self._canvas_to_logical_coords(event.x, event.y)

        if self.wiring_mode:
            clicked_pin_info = self._find_pin_at_coords(logical_x, logical_y)
            if self.wire_start_coords is None:
                if clicked_pin_info:
                    self.wire_start_coords = clicked_pin_info['coords']
                    self.wire_pending_connection_start = {'gui_name': clicked_pin_info['gui_name'], 'pin_index': clicked_pin_info['pin_index']}
                    self.display_message("Wiring", f"Wire started from {clicked_pin_info['gui_name']} pin {clicked_pin_info['pin_index']}.")
                else:
                    self.wire_start_coords = (logical_x, logical_y)
                    self.wire_pending_connection_start = None
                    self.display_message("Wiring", f"Wire started at logical ({logical_x:.0f},{logical_y:.0f}).")
                if self.temp_wire_start_indicator: self.canvas.delete(self.temp_wire_start_indicator)
                csx, csy = self._logical_to_canvas_coords(self.wire_start_coords[0], self.wire_start_coords[1])
                oval_radius = 3 # Screen pixels, not scaled for this indicator
                self.temp_wire_start_indicator = self.canvas.create_oval(csx-oval_radius, csy-oval_radius, csx+oval_radius, csy+oval_radius, fill="red", outline="red", tags="temp_indicator")
            else:
                lx1, ly1 = self.wire_start_coords
                lx2, ly2 = logical_x, logical_y
                pending_end_info = None
                if clicked_pin_info:
                    lx2, ly2 = clicked_pin_info['coords']
                    pending_end_info = {'gui_name': clicked_pin_info['gui_name'], 'pin_index': clicked_pin_info['pin_index']}
                    self.display_message("Wiring", f"Wire end snapped to {clicked_pin_info['gui_name']} pin {clicked_pin_info['pin_index']}.")
                wire_id_str = f"wire_{self.next_wire_id}"; self.next_wire_id += 1
                new_wire_entry = {'id': wire_id_str, 'x1': lx1, 'y1': ly1, 'x2': lx2, 'y2': ly2,
                                 'start_comp': self.wire_pending_connection_start,
                                 'end_comp': pending_end_info,
                                 'canvas_line_id': None}
                self.drawn_wires.append(new_wire_entry)
                self.display_message("Wiring", f"Wire {wire_id_str} drawn (logically).")
                if self.wire_pending_connection_start and pending_end_info :
                    self._update_nodes_from_wire(self.wire_pending_connection_start, pending_end_info)
                self.wire_start_coords = None; self.wire_pending_connection_start = None
                if self.temp_wire_start_indicator: self.canvas.delete(self.temp_wire_start_indicator); self.temp_wire_start_indicator = None
                self._redraw_canvas()
            self._update_button_states()
            return

        if self.selected_component_to_place:
            comp_type = self.selected_component_to_place
            base_name = {"Resistor":"R", "V_Source_DC":"VS", "I_Source_DC":"IS"}.get(comp_type, "X")
            current_names = {entry['name'].get() for entry in self.component_entries}
            num = 1; gen_name = f"{base_name}{num}"
            while gen_name in current_names: num += 1; gen_name = f"{base_name}{num}"
            def_sym_val = f"{gen_name}_sym"
            self.placed_graphical_items.append({'id': gen_name, 'type': comp_type,
                                                'x': logical_x, 'y': logical_y,
                                                'canvas_item_ids': [] })
            self._add_component_row(load_data={'type': comp_type, 'name': gen_name, 'value': def_sym_val, 'n1': "?", 'n2': "?"})
            self.display_message("Canvas", f"Placed {comp_type} '{gen_name}' at logical ({logical_x:.0f},{logical_y:.0f}). Added to list.")
            self._redraw_canvas()
            self._update_button_states()
            return

        self._clear_selection_and_properties_editor()
        clicked_item_gui_name = None
        logical_click_radius = 25 / self.canvas_scale
        for item_info in reversed(self.placed_graphical_items):
            item_lx, item_ly = item_info['x'], item_info['y']
            if (item_lx - logical_click_radius <= logical_x <= item_lx + logical_click_radius and \
                item_ly - logical_click_radius <= logical_y <= item_ly + logical_click_radius):
                clicked_item_gui_name = item_info['id']
                self.drag_data['item_gui_name'] = clicked_item_gui_name
                self.drag_data['press_mouse_x_canvas'] = event.x; self.drag_data['press_mouse_y_canvas'] = event.y
                self.drag_data['current_drag_mouse_x_canvas'] = event.x; self.drag_data['current_drag_mouse_y_canvas'] = event.y
                self.drag_data['original_item_logical_x'] = item_info['x']; self.drag_data['original_item_logical_y'] = item_info['y']
                break

        if clicked_item_gui_name:
            self.currently_selected_canvas_item_gui_name = clicked_item_gui_name
            self.last_selection_coords = (event.x, event.y)
            self._populate_properties_editor(clicked_item_gui_name)
            self._redraw_canvas() # To show selection highlight
        else:
            clicked_wire_info = None
            canvas_search_x, canvas_search_y = event.x, event.y
            item_ids_under_click = self.canvas.find_overlapping(canvas_search_x-2, canvas_search_y-2, canvas_search_x+2, canvas_search_y+2)
            for cid in reversed(item_ids_under_click):
                tags = self.canvas.gettags(cid)
                if "wire" in tags:
                    for wire_data_iter in self.drawn_wires:
                        if wire_data_iter['canvas_line_id'] == cid:
                            clicked_wire_info = wire_data_iter; break
                    if clicked_wire_info: break
            if clicked_wire_info:
                self.currently_selected_wire_info = clicked_wire_info
                self.prop_selected_label.config(text=f"Selected: {clicked_wire_info['id']}")
                self.prop_type_label.config(text="Type: Wire")
                self._redraw_canvas() # To highlight wire
        self._update_button_states()

    def _on_canvas_drag_motion(self, event): # Modified for wire updates
        if self.drag_data.get('item_gui_name'):
            item_gui_name = self.drag_data['item_gui_name']
            dx_canvas = event.x - self.drag_data['current_drag_mouse_x_canvas']
            dy_canvas = event.y - self.drag_data['current_drag_mouse_y_canvas']
            self.canvas.move(f"comp_{item_gui_name}", dx_canvas, dy_canvas)
            self.drag_data['current_drag_mouse_x_canvas'] = event.x
            self.drag_data['current_drag_mouse_y_canvas'] = event.y

            # Calculate current logical center of the component being dragged for pin calculations
            current_logical_drag_x = self.drag_data['original_item_logical_x'] + (self._canvas_to_logical_coords(event.x, 0)[0] - self._canvas_to_logical_coords(self.drag_data['press_mouse_x_canvas'], 0)[0])
            current_logical_drag_y = self.drag_data['original_item_logical_y'] + (self._canvas_to_logical_coords(0, event.y)[1] - self._canvas_to_logical_coords(0, self.drag_data['press_mouse_y_canvas'])[1])

            new_pin_logical_coords_list = self._get_component_pin_coords(item_gui_name, override_x=current_logical_drag_x, override_y=current_logical_drag_y)
            if not new_pin_logical_coords_list: return

            for wire_info in self.drawn_wires:
                needs_visual_update = False
                temp_new_wire_canvas_coords = list(self.canvas.coords(wire_info['canvas_line_id']))
                if wire_info.get('start_comp') and wire_info['start_comp']['gui_name'] == item_gui_name:
                    target_pin_index = wire_info['start_comp']['pin_index']
                    for pin_lx, pin_ly, p_idx in new_pin_logical_coords_list:
                        if p_idx == target_pin_index:
                            temp_new_wire_canvas_coords[0], temp_new_wire_canvas_coords[1] = self._logical_to_canvas_coords(pin_lx, pin_ly)
                            needs_visual_update = True; break
                if wire_info.get('end_comp') and wire_info['end_comp']['gui_name'] == item_gui_name:
                    target_pin_index = wire_info['end_comp']['pin_index']
                    for pin_lx, pin_ly, p_idx in new_pin_logical_coords_list:
                        if p_idx == target_pin_index:
                            temp_new_wire_canvas_coords[2], temp_new_wire_canvas_coords[3] = self._logical_to_canvas_coords(pin_lx, pin_ly)
                            needs_visual_update = True; break
                if needs_visual_update:
                    self.canvas.coords(wire_info['canvas_line_id'],
                                       temp_new_wire_canvas_coords[0], temp_new_wire_canvas_coords[1],
                                       temp_new_wire_canvas_coords[2], temp_new_wire_canvas_coords[3])

    def _on_canvas_button_release(self, event): # Modified for wire data finalization
        moved_comp_gui_name_final = self.drag_data.get('item_gui_name')
        if moved_comp_gui_name_final:
            final_logical_x = self.drag_data['original_item_logical_x'] + (self._canvas_to_logical_coords(event.x, 0)[0] - self._canvas_to_logical_coords(self.drag_data['press_mouse_x_canvas'], 0)[0])
            final_logical_y = self.drag_data['original_item_logical_y'] + (self._canvas_to_logical_coords(0, event.y)[1] - self._canvas_to_logical_coords(0, self.drag_data['press_mouse_y_canvas'])[1])

            for item_info in self.placed_graphical_items:
                if item_info['id'] == moved_comp_gui_name_final:
                    item_info['x'] = final_logical_x; item_info['y'] = final_logical_y; break

            final_pin_logical_coords_list = self._get_component_pin_coords(moved_comp_gui_name_final)
            if final_pin_logical_coords_list:
                for wire_info in self.drawn_wires:
                    if (wire_info.get('start_comp') and wire_info['start_comp']['gui_name'] == moved_comp_gui_name_final) or \
                       (wire_info.get('end_comp') and wire_info['end_comp']['gui_name'] == moved_comp_gui_name_final):
                        if wire_info.get('start_comp') and wire_info['start_comp']['gui_name'] == moved_comp_gui_name_final:
                            pin_idx = wire_info['start_comp']['pin_index']
                            for lx,ly,idx in final_pin_logical_coords_list:
                                if idx == pin_idx: wire_info['x1'], wire_info['y1'] = lx,ly; break
                        if wire_info.get('end_comp') and wire_info['end_comp']['gui_name'] == moved_comp_gui_name_final:
                            pin_idx = wire_info['end_comp']['pin_index']
                            for lx,ly,idx in final_pin_logical_coords_list:
                                if idx == pin_idx: wire_info['x2'], wire_info['y2'] = lx,ly; break

            self.display_message("Canvas", f"Moved {moved_comp_gui_name_final} to logical ({final_logical_x:.0f}, {final_logical_y:.0f}).")
            if self.currently_selected_canvas_item_gui_name == moved_comp_gui_name_final:
                 self._populate_properties_editor(moved_comp_gui_name_final)
            self._redraw_canvas()

        self.drag_data = {'item_gui_name': None, 'press_mouse_x_canvas': 0, 'press_mouse_y_canvas': 0,
                          'current_drag_mouse_x_canvas':0, 'current_drag_mouse_y_canvas':0,
                          'original_item_logical_x':0, 'original_item_logical_y':0}
        self._update_button_states() # Ensure delete button state is correct after drag

    def _draw_component_symbol(self, canvas_x, canvas_y, comp_type, gui_name, scale=1.0): # Modified
        tag = f"comp_{gui_name}"; canvas_ids = [];
        scaled_size = 20 * scale
        line_width = max(1, int(1 * scale))
        source_line_width = max(1, int(2 * scale))
        font_size = max(6, int(8*scale))

        if comp_type == "Resistor":
            canvas_ids.append(self.canvas.create_rectangle(canvas_x - scaled_size*1.5, canvas_y - scaled_size*0.5,
                                                           canvas_x + scaled_size*1.5, canvas_y + scaled_size*0.5,
                                                           outline="black",fill="lightblue",tags=(tag,), width=line_width))
        elif comp_type == "V_Source_DC":
            canvas_ids.append(self.canvas.create_oval(canvas_x - scaled_size, canvas_y - scaled_size,
                                                      canvas_x + scaled_size, canvas_y + scaled_size,
                                                      outline="black",fill="lightgreen",tags=(tag,), width=line_width))
            canvas_ids.append(self.canvas.create_line(canvas_x, canvas_y - scaled_size*0.6, canvas_x, canvas_y - scaled_size*0.2, tags=(tag,), width=line_width))
            canvas_ids.append(self.canvas.create_line(canvas_x - scaled_size*0.2, canvas_y - scaled_size*0.4, canvas_x + scaled_size*0.2, canvas_y - scaled_size*0.4, tags=(tag,), width=line_width))
            canvas_ids.append(self.canvas.create_line(canvas_x - scaled_size*0.2, canvas_y + scaled_size*0.4, canvas_x + scaled_size*0.2, canvas_y + scaled_size*0.4, width=source_line_width,tags=(tag,)))
        elif comp_type == "I_Source_DC":
            canvas_ids.append(self.canvas.create_oval(canvas_x - scaled_size, canvas_y - scaled_size,
                                                      canvas_x + scaled_size, canvas_y + scaled_size,
                                                      outline="black",fill="lightpink",tags=(tag,), width=line_width))
            canvas_ids.append(self.canvas.create_line(canvas_x, canvas_y + scaled_size*0.6, canvas_x, canvas_y - scaled_size*0.6, tags=(tag,), width=line_width))
            canvas_ids.append(self.canvas.create_line(canvas_x, canvas_y - scaled_size*0.6,
                                                      canvas_x - scaled_size*0.2, canvas_y - scaled_size*0.3,
                                                      canvas_x + scaled_size*0.2, canvas_y - scaled_size*0.3,
                                                      canvas_x, canvas_y - scaled_size*0.6, smooth=True,tags=(tag,), width=line_width))
        else: canvas_ids.append(self.canvas.create_text(canvas_x,canvas_y,text=f"{comp_type[:3]}?",tags=(tag,), font=("Arial", font_size)))
        canvas_ids.append(self.canvas.create_text(canvas_x, canvas_y - scaled_size - (font_size/2 + 2), text=gui_name,font=("Arial",font_size),tags=(tag,)))
        return canvas_ids

    def _populate_properties_editor(self, gui_name): # Modified
        if self.currently_selected_wire_info:
            try: self.canvas.itemconfig(self.currently_selected_wire_info['canvas_line_id'], fill='black', width=max(1, int(2*self.canvas_scale)))
            except tk.TclError: pass
            self.currently_selected_wire_info = None

        found_entry_dict = None
        for entry_widgets_dict in self.component_entries:
            if entry_widgets_dict['name'].get() == gui_name: found_entry_dict = entry_widgets_dict; break

        if found_entry_dict:
            self.currently_selected_canvas_item_gui_name = gui_name
            self.prop_selected_label.config(text=f"Selected: {gui_name}")
            self.prop_type_label.config(text=f"Type: {found_entry_dict['type'].get()}")
            for prop, widget in {'name':self.prop_name_entry, 'value':self.prop_value_entry, 'n1':self.prop_n1_entry, 'n2':self.prop_n2_entry}.items():
                widget.config(state=tk.NORMAL); widget.delete(0,tk.END); widget.insert(0, found_entry_dict[prop].get())
        else: self._clear_selection_and_properties_editor()
        self._update_button_states()


    def _clear_selection_and_properties_editor(self): # Modified
        if self.currently_selected_canvas_item_gui_name:
            old_tag = f"comp_{self.currently_selected_canvas_item_gui_name}"
            for cid in self.canvas.find_withtag(old_tag):
                if self.canvas.type(cid) not in ["text","line"]: self.canvas.itemconfig(cid, outline="black",width=max(1, int(1*self.canvas_scale)))
        if self.currently_selected_wire_info:
            try: self.canvas.itemconfig(self.currently_selected_wire_info['canvas_line_id'], fill='black', width=max(1, int(2*self.canvas_scale)))
            except tk.TclError: pass
            self.currently_selected_wire_info = None

        self.currently_selected_canvas_item_gui_name = None; self.last_selection_coords = None
        self.prop_selected_label.config(text="Selected: None"); self.prop_type_label.config(text="Type: N/A")
        for widget in [self.prop_name_entry,self.prop_value_entry,self.prop_n1_entry,self.prop_n2_entry]:
            widget.config(state=tk.DISABLED); widget.delete(0,tk.END)
        # self._update_button_states() # Called by the context that calls this typically

    def _update_component_properties(self): # Modified
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
        updated_placed_item_info = None
        for i, item_info in enumerate(self.placed_graphical_items):
            if item_info['id'] == old_gui_name:
                canvas_item_info_to_update_idx = i
                updated_placed_item_info = item_info; break

        if updated_placed_item_info:
            updated_placed_item_info['id'] = new_gui_name
            if old_gui_name != new_gui_name:
                self.currently_selected_canvas_item_gui_name = new_gui_name
                self._redraw_canvas() # Redraw to update tags and labels

        self.prop_selected_label.config(text=f"Selected: {new_gui_name}")
        self.display_message("Properties", f"Properties for '{old_gui_name}' updated to '{new_gui_name}'.")
        self._update_button_states()

    def _update_button_states(self): # New
        has_component_selection = bool(self.currently_selected_canvas_item_gui_name)
        has_wire_selection = bool(self.currently_selected_wire_info)
        if has_component_selection or has_wire_selection: self.delete_button.config(state=tk.NORMAL)
        else: self.delete_button.config(state=tk.DISABLED)
        if has_component_selection:
            self.update_props_button.config(state=tk.NORMAL)
            for widget in [self.prop_name_entry, self.prop_value_entry, self.prop_n1_entry, self.prop_n2_entry]:
                widget.config(state=tk.NORMAL)
        else:
            self.update_props_button.config(state=tk.DISABLED)
            for widget in [self.prop_name_entry, self.prop_value_entry, self.prop_n1_entry, self.prop_n2_entry]:
                widget.config(state=tk.DISABLED)


    def _delete_wire_by_id(self, wire_id_to_delete): # New
        wire_info_to_delete = None
        for wire in self.drawn_wires:
            if wire['id'] == wire_id_to_delete: wire_info_to_delete = wire; break
        if not wire_info_to_delete: return

        self.canvas.delete(wire_info_to_delete['canvas_line_id']) # Delete from canvas
        self.drawn_wires.remove(wire_info_to_delete) # Delete from data structure

        start_comp_info = wire_info_to_delete.get('start_comp')
        end_comp_info = wire_info_to_delete.get('end_comp')
        if start_comp_info: self._update_pin_node_after_wire_deletion(start_comp_info['gui_name'], start_comp_info['pin_index'])
        if end_comp_info: self._update_pin_node_after_wire_deletion(end_comp_info['gui_name'], end_comp_info['pin_index'])

        self.display_message("Delete", f"Wire '{wire_id_to_delete}' deleted.")
        self._redraw_canvas() # Redraw to reflect changes

    def _delete_selected(self): # Modified
        if self.currently_selected_canvas_item_gui_name:
            gui_name = self.currently_selected_canvas_item_gui_name
            wire_ids_to_delete = []
            for wire_info_iter in list(self.drawn_wires): # Iterate copy for safe removal
                if (wire_info_iter.get('start_comp') and wire_info_iter['start_comp']['gui_name'] == gui_name) or \
                   (wire_info_iter.get('end_comp') and wire_info_iter['end_comp']['gui_name'] == gui_name):
                    wire_ids_to_delete.append(wire_info_iter['id'])
            for wire_id_val in wire_ids_to_delete: self._delete_wire_by_id(wire_id_val) # This handles node updates

            self.canvas.delete(f"comp_{gui_name}")
            self.placed_graphical_items = [item for item in self.placed_graphical_items if item['id'] != gui_name]
            idx_to_remove = -1
            for i, entry_dict in enumerate(self.component_entries):
                if entry_dict['name'].get() == gui_name:
                    entry_dict['frame'].destroy(); idx_to_remove = i; break
            if idx_to_remove != -1: del self.component_entries[idx_to_remove]
            self.display_message("Delete", f"Component '{gui_name}' and connected wires deleted.")
            self._clear_selection_and_properties_editor() # Resets selection state
        elif self.currently_selected_wire_info:
            self._delete_wire_by_id(self.currently_selected_wire_info['id'])
            self._clear_selection_and_properties_editor()
        self._update_button_states()
        self._redraw_canvas() # Ensure canvas is clean after deletions


    def _update_pin_node_after_wire_deletion(self, comp_gui_name, pin_idx): # New
        if comp_gui_name is None: return
        current_node_name = self._get_node_for_pin(comp_gui_name, pin_idx)
        if not current_node_name or current_node_name == "?" or not current_node_name.startswith("node_auto_"): return

        pin_still_has_other_wires = False
        for wire in self.drawn_wires:
            if wire.get('start_comp') and wire['start_comp']['gui_name'] == comp_gui_name and wire['start_comp']['pin_index'] == pin_idx: pin_still_has_other_wires = True; break
            if wire.get('end_comp') and wire['end_comp']['gui_name'] == comp_gui_name and wire['end_comp']['pin_index'] == pin_idx: pin_still_has_other_wires = True; break
        if pin_still_has_other_wires: return

        auto_node_globally_used_by_others = False
        for comp_row_widgets in self.component_entries:
            other_comp_gui_name = comp_row_widgets['name'].get()
            for other_pin_idx_iter in [0, 1]:
                if other_comp_gui_name == comp_gui_name and other_pin_idx_iter == pin_idx: continue
                if self._get_node_for_pin(other_comp_gui_name, other_pin_idx_iter) == current_node_name:
                    for wire in self.drawn_wires:
                        if (wire.get('start_comp') and wire['start_comp']['gui_name'] == other_comp_gui_name and wire['start_comp']['pin_index'] == other_pin_idx_iter) or \
                           (wire.get('end_comp') and wire['end_comp']['gui_name'] == other_comp_gui_name and wire['end_comp']['pin_index'] == other_pin_idx_iter):
                            auto_node_globally_used_by_others = True; break
                    if auto_node_globally_used_by_others: break
            if auto_node_globally_used_by_others: break

        if not auto_node_globally_used_by_others:
            self._set_node_for_pin(comp_gui_name, pin_idx, "?")
            self.display_message("Node Update", f"Pin {pin_idx} of '{comp_gui_name}' (node '{current_node_name}') reset to '?'.")
            if self.currently_selected_canvas_item_gui_name == comp_gui_name: self._populate_properties_editor(comp_gui_name)

    def _get_node_for_pin(self, gui_name, pin_index): # Copied
        for entry_widgets in self.component_entries:
            if entry_widgets['name'].get() == gui_name:
                return entry_widgets['n1'].get() if pin_index == 0 else entry_widgets['n2'].get()
        return "?"

    def _set_node_for_pin(self, gui_name, pin_index, node_name): # Copied
        for entry_widgets in self.component_entries:
            if entry_widgets['name'].get() == gui_name:
                target_entry = entry_widgets['n1'] if pin_index == 0 else entry_widgets['n2']
                target_entry.delete(0, tk.END); target_entry.insert(0, node_name)
                if self.currently_selected_canvas_item_gui_name == gui_name:
                    self._populate_properties_editor(gui_name)
                return
        self.display_message("Error", f"Could not set node for component {gui_name} (not found).")

    def _update_nodes_from_wire(self, start_comp_info, end_comp_info): # Copied
        if not (start_comp_info and end_comp_info):
            if start_comp_info or end_comp_info:
                 self.display_message("Wiring", "One end of the wire is floating. Node names not automatically assigned to that end.")
            return

        node_start_val = self._get_node_for_pin(start_comp_info['gui_name'], start_comp_info['pin_index'])
        node_end_val = self._get_node_for_pin(end_comp_info['gui_name'], end_comp_info['pin_index'])
        is_node_start_valid = node_start_val not in ["", "?"]
        is_node_end_valid = node_end_val not in ["", "?"]
        final_node_name = ""

        if is_node_start_valid and is_node_end_valid:
            if node_start_val == node_end_val: final_node_name = node_start_val
            else: final_node_name = node_start_val; self.display_message("Wiring Warning", f"Connecting nodes '{node_start_val}' and '{node_end_val}'. Merged to node '{final_node_name}'. All items on '{node_end_val}' are now on '{node_start_val}'.")
        elif is_node_start_valid: final_node_name = node_start_val
        elif is_node_end_valid: final_node_name = node_end_val
        else: final_node_name = f"node_auto_{self.next_auto_node_id}"; self.next_auto_node_id += 1

        self._set_node_for_pin(start_comp_info['gui_name'], start_comp_info['pin_index'], final_node_name)
        self._set_node_for_pin(end_comp_info['gui_name'], end_comp_info['pin_index'], final_node_name)
        self.display_message("Wiring", f"Connected {start_comp_info['gui_name']}[pin{start_comp_info['pin_index']}] and {end_comp_info['gui_name']}[pin{end_comp_info['pin_index']}] to node '{final_node_name}'.")

if __name__ == '__main__':
    app = CircuitGUI()
    app.mainloop()
