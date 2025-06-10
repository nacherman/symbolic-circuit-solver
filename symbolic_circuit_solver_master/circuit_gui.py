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
from .scs_symbolic_solver_tool import SymbolicCircuitProblemSolver


class CircuitGUI(tk.Tk):
    VERIFICATION_TOLERANCE = 1e-6 # Class attribute for tolerance

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
        self.logical_grid_spacing = 20
        self.show_grid = tk.BooleanVar(value=True)

        super().__init__()
        self.title("Symbolic Circuit Simulator GUI - Phase 1")
        self.geometry("1000x800")

        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.palette_frame = ttk.LabelFrame(self.main_frame, text="Components", padding="10")
        self.palette_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        ttk.Label(self.palette_frame, text="Select tool:").pack(pady=5)
        ttk.Button(self.palette_frame, text="Select", command=self._select_select_tool).pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="Resistor", command=lambda: self._select_component_for_placement("Resistor")).pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="V_Source_DC", command=lambda: self._select_component_for_placement("V_Source_DC")).pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="I_Source_DC", command=lambda: self._select_component_for_placement("I_Source_DC")).pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="Wire", command=self._select_wire_tool).pack(fill=tk.X, pady=2)

        self.results_frame = ttk.LabelFrame(self.main_frame, text="Formulas & Results", padding="10")
        self.results_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.results_text = tk.Text(self.results_frame, wrap=tk.WORD, height=15, state=tk.DISABLED)
        self.results_text.pack(fill=tk.BOTH, expand=True, pady=5)

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

        self.advanced_solve_frame = ttk.LabelFrame(self.input_area_main_frame,
                                                   text="Solve for Unknowns (Targeted Solver)",
                                                   padding="10")
        self.advanced_solve_frame.pack(fill=tk.X, pady=(10,0), side=tk.TOP)

        adv_params_frame = ttk.Frame(self.advanced_solve_frame)
        adv_params_frame.pack(fill=tk.X, pady=2)
        ttk.Label(adv_params_frame, text="Params to Solve (symbols, comma-sep):").pack(side=tk.LEFT, padx=2)
        self.adv_params_to_solve_entry = ttk.Entry(adv_params_frame, width=50)
        self.adv_params_to_solve_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        ttk.Label(self.advanced_solve_frame, text="Known Conditions:").pack(anchor=tk.W, pady=(5,2))
        self.adv_known_condition_rows = []

        self.adv_conditions_list_container_frame = ttk.Frame(self.advanced_solve_frame)
        self.adv_conditions_list_container_frame.pack(fill=tk.X, expand=True, pady=2)

        adv_cond_buttons_frame = ttk.Frame(self.advanced_solve_frame)
        adv_cond_buttons_frame.pack(fill=tk.X, pady=2)

        self.add_adv_cond_button = ttk.Button(adv_cond_buttons_frame, text="Add Condition", command=self._add_adv_condition_row)
        self.add_adv_cond_button.pack(side=tk.LEFT, padx=5)

        self.remove_adv_cond_button = ttk.Button(adv_cond_buttons_frame, text="Remove Last Condition", command=self._remove_last_adv_condition_row)
        self.remove_adv_cond_button.pack(side=tk.LEFT, padx=5)

        for _ in range(2): self._add_adv_condition_row()

        self.adv_solve_button = ttk.Button(self.advanced_solve_frame, text="Run Advanced Solve", command=self._run_advanced_solve)
        self.adv_solve_button.pack(pady=10)

        self._add_component_row(load_data={'type':"V_Source_DC", 'name':"S1", 'value':"US_sym", 'n1':"n1", 'n2':"0"})
        self._add_component_row(load_data={'type':"Resistor", 'name':"R1", 'value':"R1_sym", 'n1':"n1", 'n2':"n2"})
        self._add_component_row(load_data={'type':"Resistor", 'name':"R2", 'value':"R2_sym", 'n1':"n2", 'n2':"0"})
        for _ in range(1): self._add_component_row()
        self._redraw_canvas()

    def _is_numeric(self, s_val):
        try: float(s_val); return True
        except (ValueError, TypeError): return False

    def _is_spice_sufficient(self, spice_string, circuit_data):
        if not circuit_data: return False
        lines = spice_string.split('\n')
        non_comment_directive_lines = 0
        for line in lines:
            if line.strip() and not line.strip().startswith('*'):
                non_comment_directive_lines +=1
        # Check if there's more than just title, .PARAM lines and .END
        # A simple heuristic: count actual component definition lines.
        comp_lines = [l for l in lines if l.strip() and not l.startswith('*') and not l.lower().startswith('.param') and not l.lower().startswith('.end')]
        return bool(comp_lines)

    def _canvas_to_logical_coords(self, canvas_x, canvas_y):
        logical_x = self.canvas.canvasx(canvas_x) / self.canvas_scale
        logical_y = self.canvas.canvasy(canvas_y) / self.canvas_scale
        return logical_x, logical_y

    def _logical_to_canvas_coords(self, logical_x, logical_y):
        canvas_x = logical_x * self.canvas_scale
        canvas_y = logical_y * self.canvas_scale
        return canvas_x, canvas_y

    def _snap_to_grid(self, logical_x, logical_y):
        if not self.show_grid.get() or self.logical_grid_spacing <= 0:
            return logical_x, logical_y
        snapped_x = round(logical_x / self.logical_grid_spacing) * self.logical_grid_spacing
        snapped_y = round(logical_y / self.logical_grid_spacing) * self.logical_grid_spacing
        return snapped_x, snapped_y

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
            logical_grid_spacing = self.logical_grid_spacing
            canvas_view_x0 = self.canvas.canvasx(0); canvas_view_y0 = self.canvas.canvasy(0)
            canvas_view_x1 = self.canvas.canvasx(self.canvas.winfo_width()); canvas_view_y1 = self.canvas.canvasy(self.canvas.winfo_height())
            logical_view_x0, logical_view_y0 = self._canvas_to_logical_coords(0,0)
            logical_view_x1, logical_view_y1 = self._canvas_to_logical_coords(self.canvas.winfo_width(), self.canvas.winfo_height())
            start_lx = math.floor(logical_view_x0 / logical_grid_spacing) * logical_grid_spacing
            end_lx = math.ceil(logical_view_x1 / logical_grid_spacing) * logical_grid_spacing
            for lx_grid in range(int(start_lx), int(end_lx) + 1, logical_grid_spacing):
                cx_grid_line, _ = self._logical_to_canvas_coords(lx_grid, logical_view_y0)
                self.canvas.create_line(cx_grid_line, canvas_view_y0, cx_grid_line, canvas_view_y1, fill="#e0e0e0", tags="grid_line")
            start_ly = math.floor(logical_view_y0 / logical_grid_spacing) * logical_grid_spacing
            end_ly = math.ceil(logical_view_y1 / logical_grid_spacing) * logical_grid_spacing
            for ly_grid in range(int(start_ly), int(end_ly) + 1, logical_grid_spacing):
                _, cy_grid_line = self._logical_to_canvas_coords(0, ly_grid)
                self.canvas.create_line(canvas_view_x0, cy_grid_line, canvas_view_x1, cy_grid_line, fill="#e0e0e0", tags="grid_line")

        for item_info in self.placed_graphical_items:
            canvas_item_center_x, canvas_item_center_y = self._logical_to_canvas_coords(item_info['x'], item_info['y'])
            item_info['canvas_item_ids'] = self._draw_component_symbol(
                canvas_item_center_x, canvas_item_center_y, item_info['type'], item_info['id'],
                scale=self.canvas_scale
            )
            if item_info['id'] == self.currently_selected_canvas_item_gui_name:
                for c_id in item_info['canvas_item_ids']:
                    item_type_on_canvas = self.canvas.type(c_id)
                    if item_type_on_canvas not in ["text"]:
                        self.canvas.itemconfig(c_id, outline=self.SELECTED_OUTLINE_COLOR,
                                               width=max(1, int(self.SELECTED_COMPONENT_WIDTH * self.canvas_scale)))

        for wire_info in self.drawn_wires:
            lx1,ly1,lx2,ly2 = wire_info['x1'],wire_info['y1'],wire_info['x2'],wire_info['y2']
            cx1,cy1 = self._logical_to_canvas_coords(lx1,ly1); cx2,cy2 = self._logical_to_canvas_coords(lx2,ly2)
            is_selected_wire = self.currently_selected_wire_info and self.currently_selected_wire_info['id'] == wire_info['id']
            current_wire_color = self.SELECTED_WIRE_COLOR if is_selected_wire else self.DEFAULT_WIRE_COLOR
            current_wire_width = self.SELECTED_WIRE_WIDTH if is_selected_wire else self.DEFAULT_WIRE_WIDTH
            wire_info['canvas_line_id'] = self.canvas.create_line(
                cx1,cy1,cx2,cy2,fill=current_wire_color,width=max(1,int(current_wire_width * self.canvas_scale)),tags=("wire",wire_info['id']))

        if self.temp_wire_start_indicator and self.wire_start_coords:
            csx,csy = self._logical_to_canvas_coords(self.wire_start_coords[0],self.wire_start_coords[1])
            oval_radius = 3
            self.temp_wire_start_indicator = self.canvas.create_oval(csx-oval_radius,csy-oval_radius,csx+oval_radius,csy+oval_radius,fill="red",outline="red",tags="temp_indicator")

    def display_message(self, title, message):
        self.results_text.config(state=tk.NORMAL); self.results_text.insert(tk.END, f"--- {title} ---\n{message}\n\n"); self.results_text.see(tk.END); self.results_text.config(state=tk.DISABLED)

    def on_derive_formulas(self):
        self.results_text.config(state=tk.NORMAL); self.results_text.delete('1.0', tk.END); self.results_text.config(state=tk.DISABLED)
        circuit_data = self._collect_circuit_data()
        if not circuit_data: self.display_message("Input Error", "No valid component data entered."); return

        spice_string = self._generate_spice_netlist(circuit_data)

        self.display_message("Generated SPICE Netlist", spice_string)
        temp_spice_file_path = ""
        try:
            if not self._is_spice_sufficient(spice_string, circuit_data):
                self.display_message("SPICE Error", "SPICE netlist seems insufficient. Cannot proceed."); return
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

    def _collect_advanced_solve_inputs(self): # As is
        params_str = self.adv_params_to_solve_entry.get().strip()
        if not params_str: self.display_message("Input Error", "No params to solve specified."); return None, None
        params_to_solve_list = [p.strip() for p in params_str.split(',') if p.strip()]
        if not params_to_solve_list: self.display_message("Input Error", "Params list empty."); return None, None
        known_conditions_list = []
        for cond_widgets in self.adv_known_condition_rows:
            cond_type = cond_widgets['type'].get(); el_n1_str = cond_widgets['el_n1'].get().strip(); val_str = cond_widgets['val'].get().strip()
            if cond_type and el_n1_str and val_str:
                try: num_value = float(val_str)
                except ValueError: self.display_message("Input Error", f"Invalid value '{val_str}'."); return None, None
                condition = {'type': cond_type, 'value': num_value}
                if cond_type == 'voltage': condition['node1'] = el_n1_str; condition['node2'] = cond_widgets['n2'].get().strip() or '0'
                elif cond_type in ['current', 'power']: condition['element'] = el_n1_str
                else: self.display_message("Input Error", f"Unknown condition type: {cond_type}"); return None, None
                known_conditions_list.append(condition)
        if not known_conditions_list: self.display_message("Input Error", "No valid conditions."); return None, None
        return params_to_solve_list, known_conditions_list

    def _run_advanced_solve(self): # Modified for this subtask
        self.results_text.config(state=tk.NORMAL); self.results_text.delete('1.0', tk.END); self.results_text.config(state=tk.DISABLED)
        self.display_message("Advanced Solve", "Starting advanced problem solving...")
        circuit_data = self._collect_circuit_data()
        if not circuit_data: self.display_message("Circuit Error", "No circuit defined."); return

        spice_string = self._generate_spice_netlist(circuit_data)
        if not self._is_spice_sufficient(spice_string, circuit_data):
             self.display_message("SPICE Error", "SPICE netlist seems insufficient. Cannot proceed."); return
        self.display_message("Generated SPICE for Advanced Solve", spice_string)

        params_to_solve, known_conditions = self._collect_advanced_solve_inputs()
        if not params_to_solve or not known_conditions: return

        self.display_message("Advanced Solver Inputs",
                             f"  Parameters to Solve: {params_to_solve}\n" +
                             f"  Known Conditions: {json.dumps(known_conditions, indent=2)}")
        temp_spice_file_path = ""
        all_inconsistencies = [] # For consistency checks
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sp', dir='.') as tmp_file:
                tmp_file.write(spice_string); temp_spice_file_path = tmp_file.name
            self.display_message("Solver Status", f"Running SymbolicCircuitProblemSolver with {os.path.basename(temp_spice_file_path)}...")
            adv_solver = SymbolicCircuitProblemSolver(netlist_path=temp_spice_file_path)
            solution_dict = adv_solver.solve_for_unknowns(known_conditions, params_to_solve)
            solution_str = "--- Solved Parameter Values ---\n"
            if not solution_dict: solution_str += "  No solution found or solution is empty.\n"
            else:
                for var_symbol, val_expr in solution_dict.items():
                    solution_str += f"  {str(var_symbol)} = {sympy.pretty(val_expr) if hasattr(val_expr, '_pretty') else str(val_expr)}\n"
                    num_val_disp = self._eval_expr_to_float(val_expr) # Try to get float for display
                    if num_val_disp is not None:
                        solution_str += f"    Numerical: {num_val_disp:.4g}\n"
                    elif hasattr(val_expr, 'evalf'): # If not float, but can evalf (e.g. symbolic still)
                        solution_str += f"    (Expression evaluated to: {val_expr.evalf()})\n"
                    else: # Neither float nor sympy expr with evalf
                         solution_str += f"    (Value: {val_expr})\n"
            self.display_message("Advanced Solution", solution_str)

            if solution_dict and adv_solver.top_instance:
                self.display_message("Post-Solve Analysis", "Calculating V, I, P with solved values...")
                final_subs_for_vip = {}
                if adv_solver.top_instance.paramsd:
                    for p_sym, p_expr in adv_solver.top_instance.paramsd.items(): final_subs_for_vip[p_sym] = p_expr
                for k_sym, v_expr_s in final_subs_for_vip.items():
                    if hasattr(v_expr_s, 'subs'): final_subs_for_vip[k_sym] = v_expr_s.subs(solution_dict)
                for solved_s, solved_v in solution_dict.items(): final_subs_for_vip[solved_s] = solved_v

                vip_results_str = "\n--- Detailed V, I, P (using solved values) ---\n"
                for comp_data in circuit_data:
                    comp_gui_name = comp_data['name']
                    comp_details_for_nodes = self._get_component_details_from_gui_name(comp_gui_name, circuit_data)
                    if not comp_details_for_nodes: continue
                    actual_spice_name = comp_details_for_nodes['spice_name']
                    vip_results_str += f"--- {comp_gui_name} (as {actual_spice_name}) ---\n"
                    try:
                        v_expr = adv_solver.top_instance.v(comp_details_for_nodes['n1'], comp_details_for_nodes['n2'])
                        i_expr = adv_solver.top_instance.i(actual_spice_name)
                        p_expr = adv_solver.top_instance.p(actual_spice_name)

                        # Get component's own value (e.g. resistance, source value)
                        comp_own_val_expr_str = comp_details_for_nodes['value_str']
                        comp_own_val_sym = sympy.sympify(comp_own_val_expr_str) if not self._is_numeric(comp_own_val_expr_str) else sympy.Float(comp_own_val_expr_str)
                        comp_own_val_num_expr = comp_own_val_sym.subs(final_subs_for_vip) if hasattr(comp_own_val_sym, 'subs') else comp_own_val_sym

                        comp_own_val_num = self._eval_expr_to_float(comp_own_val_num_expr)
                        v_val_num = self._eval_expr_to_float(v_expr.subs(final_subs_for_vip))
                        i_val_num = self._eval_expr_to_float(i_expr.subs(final_subs_for_vip))
                        p_val_num = self._eval_expr_to_float(p_expr.subs(final_subs_for_vip))

                        unit = {"Resistor":"Ω","V_Source_DC":"V","I_Source_DC":"A"}.get(comp_details_for_nodes['type'],"")
                        vip_results_str += f"  Value: {comp_own_val_num if comp_own_val_num is not None else 'N/A'} {unit}\n"
                        vip_results_str += f"  Voltage:    {v_val_num if v_val_num is not None else 'N/A'} V\n"
                        vip_results_str += f"  Current:    {(v_val_num*1000) if v_val_num is not None else 'N/A'} mA\n" # Corrected from i_val_num
                        vip_results_str += f"  Power:      {(p_val_num*1000) if p_val_num is not None else 'N/A'} mW\n"

                        # Consistency Checks
                        comp_type = comp_details_for_nodes['type']
                        numeric_values_present = all(val is not None for val in [v_val_num, i_val_num, p_val_num])
                        if comp_type == "Resistor": numeric_values_present = numeric_values_present and (comp_own_val_num is not None)

                        if numeric_values_present:
                            if comp_type == "Resistor":
                                if abs(comp_own_val_num) > self.VERIFICATION_TOLERANCE:
                                    ohm_law_diff = abs(v_val_num - i_val_num * comp_own_val_num)
                                    if ohm_law_diff > self.VERIFICATION_TOLERANCE:
                                        all_inconsistencies.append(f"  Resistor '{comp_gui_name}': Ohm's Law. |V-IR| = {ohm_law_diff:.2e} (V={v_val_num:.2e}, I={i_val_num:.2e}, R={comp_own_val_num:.2e})")
                                elif abs(v_val_num) > self.VERIFICATION_TOLERANCE: # R is near zero
                                     if abs(i_val_num * comp_own_val_num) > self.VERIFICATION_TOLERANCE and abs(v_val_num - i_val_num*comp_own_val_num) > self.VERIFICATION_TOLERANCE :
                                          all_inconsistencies.append(f"  Resistor '{comp_gui_name}': Ohm's Law (low R). |V-IR| = {abs(v_val_num - i_val_num * comp_own_val_num):.2e} (V={v_val_num:.2e}, I={i_val_num:.2e}, R={comp_own_val_num:.2e})")
                            power_law_diff = abs(p_val_num - v_val_num * i_val_num)
                            if power_law_diff > self.VERIFICATION_TOLERANCE:
                                 all_inconsistencies.append(f"  Component '{comp_gui_name}': Power Law. |P-VI| = {power_law_diff:.2e} (P={p_val_num:.2e}, V={v_val_num:.2e}, I={i_val_num:.2e})")
                        else:
                             all_inconsistencies.append(f"  Component '{comp_gui_name}': Some V,I,P,R values non-numeric, verification incomplete.")
                    except Exception as e_vip: vip_results_str += f"  Error V/I/P details: {type(e_vip).__name__} - {e_vip}\n"
                self.display_message("V/I/P Results", vip_results_str)

            # Display Verification Status
            verification_status_str = "\n--- Numerical Verification Status (Tolerance=" + f"{self.VERIFICATION_TOLERANCE:.0e}" + ") ---\n"
            if not all_inconsistencies:
                verification_status_str += "  All component V, I, R, P values appear self-consistent.\n"
            else:
                verification_status_str += "  Potential inconsistencies found or checks incomplete:\n"
                for entry in all_inconsistencies:
                    verification_status_str += f"{entry}\n"
            self.display_message("Verification Result", verification_status_str)

        except (scs_errors.ScsParserError, scs_errors.ScsInstanceError, scs_errors.ScsToolError, ValueError) as e:
            self.display_message("Advanced Solver Error", f"{type(e).__name__}: {e}")
        except Exception as e:
            self.display_message("Advanced Solver Error (Unexpected)", f"{type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
        finally:
            if temp_spice_file_path and os.path.exists(temp_spice_file_path):
                try: os.remove(temp_spice_file_path)
                except Exception as e_remove: print(f"Error removing temp file: {e_remove}")

    # [Pasted methods from _get_component_details_from_gui_name to _update_nodes_from_wire go here]
    def _get_component_details_from_gui_name(self, target_gui_name_str, circuit_data): # Copied
        if not target_gui_name_str: return None
        for comp_dict in circuit_data:
            if comp_dict['name'] == target_gui_name_str:
                prefix = {"Resistor":"R", "V_Source_DC":"V", "I_Source_DC":"I"}.get(comp_dict['type'], "X")
                actual_spice_name = prefix + comp_dict['name']
                return {'gui_name': comp_dict['name'], 'spice_name': actual_spice_name,
                        'n1': comp_dict['n1'], 'n2': comp_dict['n2'] if comp_dict['n2'] else '0',
                        'type': comp_dict['type'], 'value_str': comp_dict['value']}
        return None

    def _eval_expr_to_float(self, expr): # Modified for this subtask
        try:
            if hasattr(expr, 'is_complex') and expr.is_complex: # Check if sympy says it's complex
                 if hasattr(expr, 'as_real_imag') and abs(float(expr.as_real_imag()[1])) > self.VERIFICATION_TOLERANCE : # Check imag part
                     return None # Cannot convert complex to float for these checks directly
                 else: # Imaginary part is negligible or zero
                     expr = expr.as_real_imag()[0]

            evaluated = expr.evalf()
            return float(evaluated)
        except (AttributeError, TypeError, ValueError, Exception) as e:
            return None

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
            elif not self._is_numeric(val_str): params.append(f".PARAM {val_param} = {sym_to_use}"); sym_ensure.add(f".PARAM {sym_to_use} = {sym_to_use}")
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
                        val_own_expr = sympy.sympify(details['value_str']) if details['value_str'] else sympy.Float(0)
                        val_own_num_expr = val_own_expr.subs(subs) if hasattr(val_own_expr, 'subs') else val_own_expr

                        v_n=self._eval_expr_to_float(v.subs(subs)); i_n=self._eval_expr_to_float(i.subs(subs)); p_n=self._eval_expr_to_float(p.subs(subs))
                        val_own_n=self._eval_expr_to_float(val_own_num_expr)
                        unit={"Resistor":"Ω","V_Source_DC":"V","I_Source_DC":"A"}.get(details['type'],"")

                        vip_results_str_comp = f"    Value: {val_own_n if val_own_n is not None else 'N/A'} {unit}\n" if "Source" not in details['type'] else ""
                        vip_results_str_comp += f"    Voltage: {v_n if v_n is not None else 'N/A'} V\n"
                        vip_results_str_comp += f"    Current: {i_n*1000 if i_n is not None else 'N/A'} mA\n"
                        vip_results_str_comp += f"    Power:   {p_n*1000 if p_n is not None else 'N/A'} mW\n"
                        res_str += vip_results_str_comp
                    except Exception as e: res_str+=f"    Error V/I/P for '{comp_name}': {type(e).__name__} - {e}\n"
                else: res_str+=f"  Comp GUI Name '{comp_name}' not found.\n"
            if node_name:
                res_str+=f"  --- For Node {node_name} ---\n"
                try:
                    v_node=self.top_instance.v(node_name,'0'); v_n_n=self._eval_expr_to_float(v_node.subs(subs))
                    res_str+=f"    V({node_name},'0'): {v_n_n if v_n_n is not None else 'N/A'} V\n"
                except Exception as e: res_str+=f"    Error V({node_name},'0'): {type(e).__name__} - {e}\n"
        self.display_message("Numerical Results", res_str)

    def _save_circuit_to_file(self): # As is
        circuit_data = self._collect_circuit_data()
        if not circuit_data: messagebox.showwarning("Save Circuit", "No circuit data to save."); return
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")], title="Save Circuit As", initialdir=os.path.join(os.getcwd(), "examples"))
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(circuit_data, f, indent=4)
            self.display_message("Save Circuit", f"Circuit saved to {os.path.basename(filepath)}")
        except Exception as e: self.display_message("Save Error", f"Failed to save: {e}")

    def _load_circuit_from_file(self): # As is
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
            self._redraw_canvas() # Redraw after loading
        except FileNotFoundError: self.display_message("Load Error", f"File not found: {filepath}")
        except json.JSONDecodeError: self.display_message("Load Error", "Not valid JSON.")
        except ValueError as ve: self.display_message("Load Error", str(ve))
        except Exception as e: self.display_message("Load Error", f"Failed to load: {e}")

    def _select_component_for_placement(self, comp_type): # Modified for cursor and selection clear
        self.selected_component_to_place = comp_type
        self.wiring_mode = False
        self.wire_start_coords = None
        if self.temp_wire_start_indicator: self.canvas.delete(self.temp_wire_start_indicator); self.temp_wire_start_indicator = None

        self._clear_selection_and_properties_editor() # Clear component and wire selection
        if comp_type:
            self.display_message("Status", f"{comp_type} selected. Click on canvas to place."); self.canvas.config(cursor="crosshair")
        else:
            self.display_message("Status", "Component placement deselected."); self.canvas.config(cursor="arrow")
        self._update_button_states()

    def _select_wire_tool(self): # Modified for cursor and selection clear
        self._clear_selection_and_properties_editor()
        self.wiring_mode = True
        self.selected_component_to_place = None
        if self.temp_wire_start_indicator: self.canvas.delete(self.temp_wire_start_indicator); self.temp_wire_start_indicator = None
        self.wire_start_coords = None; self.wire_pending_connection_start = None
        self._update_button_states()
        self.display_message("Status", "Wire tool selected. Click start, then end point.")
        self.canvas.config(cursor="pencil")

    def _select_select_tool(self): # Modified for cursor
        self.wiring_mode = False
        self.selected_component_to_place = None
        if self.temp_wire_start_indicator: self.canvas.delete(self.temp_wire_start_indicator); self.temp_wire_start_indicator = None
        self.wire_start_coords = None
        # Do not clear selection when select tool is chosen, user might want to re-select or confirm.
        self._update_button_states()
        self.display_message("Status", "Select tool active. Click on components or wires.")
        self.canvas.config(cursor="arrow")

    def _on_canvas_button_press(self, event): # Modified for snap-to-grid and selection highlight
        logical_x, logical_y = self._canvas_to_logical_coords(event.x, event.y)
        snapped_logical_x, snapped_logical_y = self._snap_to_grid(logical_x, logical_y)
        if self.wiring_mode:
            clicked_pin_info = self._find_pin_at_coords(logical_x, logical_y)
            if self.wire_start_coords is None:
                self.wire_start_coords = clicked_pin_info['coords'] if clicked_pin_info else (snapped_logical_x, snapped_logical_y)
                self.wire_pending_connection_start = {'gui_name': clicked_pin_info['gui_name'], 'pin_index': clicked_pin_info['pin_index']} if clicked_pin_info else None
                msg = f"Wire started from {clicked_pin_info['gui_name']} pin {clicked_pin_info['pin_index']}." if clicked_pin_info else f"Wire started at logical ({snapped_logical_x:.0f},{snapped_logical_y:.0f})."
                self.display_message("Wiring", msg)
                if self.temp_wire_start_indicator: self.canvas.delete(self.temp_wire_start_indicator)
                csx, csy = self._logical_to_canvas_coords(self.wire_start_coords[0], self.wire_start_coords[1])
                self.temp_wire_start_indicator = self.canvas.create_oval(csx-3, csy-3, csx+3, csy+3, fill="red", outline="red", tags="temp_indicator")
            else:
                lx1, ly1 = self.wire_start_coords
                lx2, ly2 = snapped_logical_x, snapped_logical_y
                pending_end_info = None
                if clicked_pin_info: lx2,ly2 = clicked_pin_info['coords']; pending_end_info = {'gui_name': clicked_pin_info['gui_name'], 'pin_index': clicked_pin_info['pin_index']}
                wire_id_str = f"wire_{self.next_wire_id}"; self.next_wire_id += 1
                new_wire_entry = {'id': wire_id_str, 'x1': lx1, 'y1': ly1, 'x2': lx2, 'y2': ly2,
                                 'start_comp': self.wire_pending_connection_start,
                                 'end_comp': pending_end_info,
                                 'canvas_line_id': None}
                self.drawn_wires.append(new_wire_entry)
                self.display_message("Wiring", f"Wire {wire_id_str} drawn to logical ({lx2:.0f},{ly2:.0f}).")
                if self.wire_pending_connection_start and pending_end_info : self._update_nodes_from_wire(self.wire_pending_connection_start, pending_end_info)
                self.wire_start_coords = None; self.wire_pending_connection_start = None
                if self.temp_wire_start_indicator: self.canvas.delete(self.temp_wire_start_indicator); self.temp_wire_start_indicator = None
                self._redraw_canvas()
            self._update_button_states(); return
        if self.selected_component_to_place:
            comp_type = self.selected_component_to_place; place_lx, place_ly = snapped_logical_x, snapped_logical_y
            base_name = {"Resistor":"R", "V_Source_DC":"VS", "I_Source_DC":"IS"}.get(comp_type, "X")
            current_names = {entry['name'].get() for entry in self.component_entries}
            num = 1; gen_name = f"{base_name}{num}"
            while gen_name in current_names: num += 1; gen_name = f"{base_name}{num}"
            def_sym_val = f"{gen_name}_sym"
            self.placed_graphical_items.append({'id': gen_name, 'type': comp_type, 'x': place_lx, 'y': place_ly, 'canvas_item_ids': [] })
            self._add_component_row(load_data={'type': comp_type, 'name': gen_name, 'value': def_sym_val, 'n1': "?", 'n2': "?"})
            self.display_message("Canvas", f"Placed {comp_type} '{gen_name}' at logical ({place_lx:.0f},{place_ly:.0f}).")
            self._redraw_canvas(); self._update_button_states(); return

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
        else:
            clicked_wire_info = None
            canvas_search_x, canvas_search_y = event.x, event.y
            item_ids_under_click = self.canvas.find_overlapping(canvas_search_x-2, canvas_search_y-2, canvas_search_x+2, canvas_search_y+2)
            for cid in reversed(item_ids_under_click):
                tags = self.canvas.gettags(cid)
                if "wire" in tags:
                    for wire_data_iter in self.drawn_wires:
                        if wire_data_iter['canvas_line_id'] == cid: clicked_wire_info = wire_data_iter; break
                    if clicked_wire_info: break
            if clicked_wire_info:
                self.currently_selected_wire_info = clicked_wire_info
                self.prop_selected_label.config(text=f"Selected: {clicked_wire_info['id']}")
                self.prop_type_label.config(text="Type: Wire")
        self._redraw_canvas()
        self._update_button_states()

    # ... (Rest of methods as previously defined, including _on_canvas_drag_motion, _on_canvas_button_release, etc.)
    # ... (Make sure they are all present from previous full overwrite state)
    def _on_canvas_drag_motion(self, event): # Copied & adapted for logical coord updates during wire drag
        if self.drag_data.get('item_gui_name'):
            item_gui_name = self.drag_data['item_gui_name']
            dx_canvas = event.x - self.drag_data['current_drag_mouse_x_canvas']
            dy_canvas = event.y - self.drag_data['current_drag_mouse_y_canvas']
            self.canvas.move(f"comp_{item_gui_name}", dx_canvas, dy_canvas)
            self.drag_data['current_drag_mouse_x_canvas'] = event.x
            self.drag_data['current_drag_mouse_y_canvas'] = event.y

            current_logical_drag_x = self.drag_data['original_item_logical_x'] + (self._canvas_to_logical_coords(event.x - self.drag_data['press_mouse_x_canvas'], 0)[0])
            current_logical_drag_y = self.drag_data['original_item_logical_y'] + (self._canvas_to_logical_coords(0, event.y - self.drag_data['press_mouse_y_canvas'])[1])

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

    def _on_canvas_button_release(self, event): # Copied & adapted
        moved_comp_gui_name_final = self.drag_data.get('item_gui_name')
        if moved_comp_gui_name_final:
            final_raw_logical_x = self.drag_data['original_item_logical_x'] + (self._canvas_to_logical_coords(event.x, 0)[0] - self._canvas_to_logical_coords(self.drag_data['press_mouse_x_canvas'], 0)[0])
            final_raw_logical_y = self.drag_data['original_item_logical_y'] + (self._canvas_to_logical_coords(0, event.y)[1] - self._canvas_to_logical_coords(0, self.drag_data['press_mouse_y_canvas'])[1])
            final_snapped_lx, final_snapped_ly = self._snap_to_grid(final_raw_logical_x, final_raw_logical_y)

            for item_info in self.placed_graphical_items:
                if item_info['id'] == moved_comp_gui_name_final:
                    item_info['x'] = final_snapped_lx; item_info['y'] = final_snapped_ly; break

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

            self.display_message("Canvas", f"Moved {moved_comp_gui_name_final} to logical ({final_snapped_lx:.0f}, {final_snapped_ly:.0f}).")
            if self.currently_selected_canvas_item_gui_name == moved_comp_gui_name_final:
                 self._populate_properties_editor(moved_comp_gui_name_final)
            self._redraw_canvas()

        self.drag_data = {'item_gui_name': None, 'press_mouse_x_canvas': 0, 'press_mouse_y_canvas': 0,
                          'current_drag_mouse_x_canvas':0, 'current_drag_mouse_y_canvas':0,
                          'original_item_logical_x':0, 'original_item_logical_y':0}
        self._update_button_states()

    def _draw_component_symbol(self, canvas_x, canvas_y, comp_type, gui_name, scale=1.0): # Modified
        tag = f"comp_{gui_name}"; canvas_ids = [];
        scaled_size = 20 * scale
        # Use constants for default width, apply scaling
        default_scaled_width = max(1, int(self.DEFAULT_COMPONENT_WIDTH * scale))
        selected_scaled_width = max(1, int(self.SELECTED_COMPONENT_WIDTH * scale))

        current_outline_color = self.DEFAULT_OUTLINE_COLOR
        current_line_width = default_scaled_width

        if self.currently_selected_canvas_item_gui_name == gui_name:
            current_outline_color = self.SELECTED_OUTLINE_COLOR
            current_line_width = selected_scaled_width

        font_size = max(6, int(8*scale))

        if comp_type == "Resistor":
            canvas_ids.append(self.canvas.create_rectangle(canvas_x - scaled_size*1.5, canvas_y - scaled_size*0.5,
                                                           canvas_x + scaled_size*1.5, canvas_y + scaled_size*0.5,
                                                           outline=current_outline_color,fill="lightblue",tags=(tag,), width=current_line_width))
        elif comp_type == "V_Source_DC":
            canvas_ids.append(self.canvas.create_oval(canvas_x - scaled_size, canvas_y - scaled_size,
                                                      canvas_x + scaled_size, canvas_y + scaled_size,
                                                      outline=current_outline_color,fill="lightgreen",tags=(tag,), width=current_line_width))
            plus_minus_line_w = default_scaled_width # Internal lines might not always get thicker on selection
            if self.currently_selected_canvas_item_gui_name == gui_name: plus_minus_line_w = selected_scaled_width

            canvas_ids.append(self.canvas.create_line(canvas_x, canvas_y - scaled_size*0.6, canvas_x, canvas_y - scaled_size*0.2, tags=(tag,), width=plus_minus_line_w, fill=current_outline_color))
            canvas_ids.append(self.canvas.create_line(canvas_x - scaled_size*0.2, canvas_y - scaled_size*0.4, canvas_x + scaled_size*0.2, canvas_y - scaled_size*0.4, tags=(tag,), width=plus_minus_line_w, fill=current_outline_color))
            canvas_ids.append(self.canvas.create_line(canvas_x - scaled_size*0.2, canvas_y + scaled_size*0.4, canvas_x + scaled_size*0.2, canvas_y + scaled_size*0.4, width=max(1, int(2*scale)),tags=(tag,), fill=current_outline_color)) # Thicker minus
        elif comp_type == "I_Source_DC":
            canvas_ids.append(self.canvas.create_oval(canvas_x - scaled_size, canvas_y - scaled_size,
                                                      canvas_x + scaled_size, canvas_y + scaled_size,
                                                      outline=current_outline_color,fill="lightpink",tags=(tag,), width=current_line_width))
            arrow_line_w = default_scaled_width
            if self.currently_selected_canvas_item_gui_name == gui_name: arrow_line_w = selected_scaled_width
            canvas_ids.append(self.canvas.create_line(canvas_x, canvas_y + scaled_size*0.6, canvas_x, canvas_y - scaled_size*0.6, tags=(tag,), width=arrow_line_w, fill=current_outline_color))
            canvas_ids.append(self.canvas.create_line(canvas_x, canvas_y - scaled_size*0.6,
                                                      canvas_x - scaled_size*0.2, canvas_y - scaled_size*0.3,
                                                      canvas_x + scaled_size*0.2, canvas_y - scaled_size*0.3,
                                                      canvas_x, canvas_y - scaled_size*0.6, smooth=True,tags=(tag,), width=arrow_line_w, fill=current_outline_color))
        else: canvas_ids.append(self.canvas.create_text(canvas_x,canvas_y,text=f"{comp_type[:3]}?",tags=(tag,), font=("Arial", font_size)))
        canvas_ids.append(self.canvas.create_text(canvas_x, canvas_y - scaled_size - (font_size/2 + 2), text=gui_name,font=("Arial",font_size),tags=(tag,)))
        return canvas_ids

    def _populate_properties_editor(self, gui_name): # Modified
        if self.currently_selected_wire_info:
            try: self.canvas.itemconfig(self.currently_selected_wire_info['canvas_line_id'], fill=self.DEFAULT_WIRE_COLOR, width=max(1, int(self.DEFAULT_WIRE_WIDTH*self.canvas_scale)))
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
            # Find the item to get its canvas_item_ids for precise deselection
            item_to_deselect = next((item for item in self.placed_graphical_items if item['id'] == self.currently_selected_canvas_item_gui_name), None)
            if item_to_deselect:
                for c_id in item_to_deselect['canvas_item_ids']:
                    item_type = self.canvas.type(c_id)
                    if item_type not in ["text"]: # Avoid changing fill of text, only outline for shapes
                         try: self.canvas.itemconfig(c_id, outline=self.DEFAULT_OUTLINE_COLOR, width=max(1, int(self.DEFAULT_COMPONENT_WIDTH*self.canvas_scale)))
                         except tk.TclError: pass # Item might have been deleted
        if self.currently_selected_wire_info:
            try: self.canvas.itemconfig(self.currently_selected_wire_info['canvas_line_id'], fill=self.DEFAULT_WIRE_COLOR, width=max(1, int(self.DEFAULT_WIRE_WIDTH*self.canvas_scale)))
            except tk.TclError: pass
            self.currently_selected_wire_info = None
        self.currently_selected_canvas_item_gui_name = None; self.last_selection_coords = None
        self.prop_selected_label.config(text="Selected: None"); self.prop_type_label.config(text="Type: N/A")
        for widget in [self.prop_name_entry,self.prop_value_entry,self.prop_n1_entry,self.prop_n2_entry]:
            widget.config(state=tk.DISABLED); widget.delete(0,tk.END)
        # self._update_button_states() # Called by context

    def _update_component_properties(self): # Modified for redraw
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

        updated_graphical_item = False
        for item_info in self.placed_graphical_items:
            if item_info['id'] == old_gui_name:
                item_info['id'] = new_gui_name
                updated_graphical_item = True; break

        self.currently_selected_canvas_item_gui_name = new_gui_name
        if old_gui_name != new_gui_name or updated_graphical_item: # If name changed, or any other prop that affects visuals
            self._redraw_canvas() # Redraw to update tags and labels

        self.prop_selected_label.config(text=f"Selected: {new_gui_name}") # Update label in editor
        self.display_message("Properties", f"Properties for '{old_gui_name}' updated to '{new_gui_name}'.")
        self._update_button_states()

    def _update_button_states(self): # As is
        has_comp_sel = bool(self.currently_selected_canvas_item_gui_name)
        has_wire_sel = bool(self.currently_selected_wire_info)
        self.delete_button.config(state=tk.NORMAL if has_comp_sel or has_wire_sel else tk.DISABLED)
        self.update_props_button.config(state=tk.NORMAL if has_comp_sel else tk.DISABLED)
        for widget in [self.prop_name_entry,self.prop_value_entry,self.prop_n1_entry,self.prop_n2_entry]:
            widget.config(state=tk.NORMAL if has_comp_sel else tk.DISABLED)

    def _delete_wire_by_id(self, wire_id_to_delete): # As is
        wire_info_to_delete = None
        for wire in self.drawn_wires:
            if wire['id'] == wire_id_to_delete: wire_info_to_delete = wire; break
        if not wire_info_to_delete: return
        self.canvas.delete(wire_info_to_delete['canvas_line_id'])
        self.drawn_wires.remove(wire_info_to_delete)
        start_comp_info = wire_info_to_delete.get('start_comp')
        end_comp_info = wire_info_to_delete.get('end_comp')
        if start_comp_info: self._update_pin_node_after_wire_deletion(start_comp_info['gui_name'], start_comp_info['pin_index'])
        if end_comp_info: self._update_pin_node_after_wire_deletion(end_comp_info['gui_name'], end_comp_info['pin_index'])
        self.display_message("Delete", f"Wire '{wire_id_to_delete}' deleted.")

    def _delete_selected(self): # Modified for redraw
        if self.currently_selected_canvas_item_gui_name:
            gui_name = self.currently_selected_canvas_item_gui_name
            wire_ids_to_delete = []
            for wire_info_iter in list(self.drawn_wires):
                if (wire_info_iter.get('start_comp') and wire_info_iter['start_comp']['gui_name'] == gui_name) or \
                   (wire_info_iter.get('end_comp') and wire_info_iter['end_comp']['gui_name'] == gui_name):
                    wire_ids_to_delete.append(wire_info_iter['id'])
            for wire_id_val in wire_ids_to_delete: self._delete_wire_by_id(wire_id_val) # This will call _redraw_canvas if nodes change

            # self.canvas.delete(f"comp_{gui_name}") # Will be deleted by _redraw_canvas
            self.placed_graphical_items = [item for item in self.placed_graphical_items if item['id'] != gui_name]
            idx_to_remove = -1
            for i, entry_dict in enumerate(self.component_entries):
                if entry_dict['name'].get() == gui_name:
                    entry_dict['frame'].destroy(); idx_to_remove = i; break
            if idx_to_remove != -1: del self.component_entries[idx_to_remove]
            self.display_message("Delete", f"Component '{gui_name}' and connected wires deleted.")
        elif self.currently_selected_wire_info:
            self._delete_wire_by_id(self.currently_selected_wire_info['id'])

        self._clear_selection_and_properties_editor()
        self._update_button_states()
        self._redraw_canvas()

    def _update_pin_node_after_wire_deletion(self, comp_gui_name, pin_idx): # As is
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

    def _get_node_for_pin(self, gui_name, pin_index): # As is
        for entry_widgets in self.component_entries:
            if entry_widgets['name'].get() == gui_name:
                return entry_widgets['n1'].get() if pin_index == 0 else entry_widgets['n2'].get()
        return "?"

    def _set_node_for_pin(self, gui_name, pin_index, node_name): # As is
        for entry_widgets in self.component_entries:
            if entry_widgets['name'].get() == gui_name:
                target_entry = entry_widgets['n1'] if pin_index == 0 else entry_widgets['n2']
                target_entry.delete(0, tk.END); target_entry.insert(0, node_name)
                if self.currently_selected_canvas_item_gui_name == gui_name:
                    self._populate_properties_editor(gui_name)
                return
        self.display_message("Error", f"Could not set node for component {gui_name} (not found).")

    def _update_nodes_from_wire(self, start_comp_info, end_comp_info): # As is (with node merging refinement)
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
            else:
                final_node_name = node_start_val # Default to start_node_val
                self.display_message("Wiring Warning", f"Nodes '{node_start_val}' and '{node_end_val}' are being merged to node '{final_node_name}'. All components connected to '{node_end_val}' must be manually updated if this was not intended or if they should also connect to '{final_node_name}'.")
                # Update the just-connected end_comp_info pin to the new merged name
                self._set_node_for_pin(end_comp_info['gui_name'], end_comp_info['pin_index'], final_node_name)
                # Iterate all other components and update their pins if they were connected to node_end_val
                for comp_row in self.component_entries:
                    comp_gui_name_iter = comp_row['name'].get()
                    # Skip the two components already handled by the current wire
                    if comp_gui_name_iter == start_comp_info['gui_name'] or comp_gui_name_iter == end_comp_info['gui_name']:
                        continue
                    if self._get_node_for_pin(comp_gui_name_iter, 0) == node_end_val:
                        self._set_node_for_pin(comp_gui_name_iter, 0, final_node_name)
                    if self._get_node_for_pin(comp_gui_name_iter, 1) == node_end_val:
                        self._set_node_for_pin(comp_gui_name_iter, 1, final_node_name)

        elif is_node_start_valid: final_node_name = node_start_val
        elif is_node_end_valid: final_node_name = node_end_val
        else: final_node_name = f"node_auto_{self.next_auto_node_id}"; self.next_auto_node_id += 1

        self._set_node_for_pin(start_comp_info['gui_name'], start_comp_info['pin_index'], final_node_name)
        self._set_node_for_pin(end_comp_info['gui_name'], end_comp_info['pin_index'], final_node_name)
        if not (is_node_start_valid and is_node_end_valid and node_start_val == node_end_val) : # Avoid redundant message if already connected
            self.display_message("Wiring", f"Connected {start_comp_info['gui_name']}[pin{start_comp_info['pin_index']}] and {end_comp_info['gui_name']}[pin{end_comp_info['pin_index']}] to node '{final_node_name}'.")

if __name__ == '__main__':
    app = CircuitGUI()
    app.mainloop()
