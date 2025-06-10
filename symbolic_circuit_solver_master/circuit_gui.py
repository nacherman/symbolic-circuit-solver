import tkinter as tk
from tkinter import ttk, messagebox, filedialog # Added messagebox for potential future use, not strictly for this step
import os
import tempfile
import sympy # For sympy.pretty and potentially creating symbols if needed by solver directly
import json # For Save/Load functionality

# Imports for the symbolic circuit solver engine
# Assuming circuit_gui.py is within the symbolic_circuit_solver_master package
from . import scs_parser
from . import scs_instance_hier
from . import scs_circuit
from . import scs_errors


class CircuitGUI(tk.Tk):
    def __init__(self):
        self.top_instance = None # To store the solved circuit instance
        self.active_symbols_info = {} # Stores info about GUI components whose values were defined as symbols
        self.selected_component_to_place = None
        self.placed_graphical_items = []
        self.next_graphical_item_id = 0
        super().__init__()
        self.title("Symbolic Circuit Simulator GUI - Phase 1")
        self.geometry("1000x700") # Initial size

        # Configure main layout frames
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Left Frame (Component Palette) ---
        self.palette_frame = ttk.LabelFrame(self.main_frame, text="Components", padding="10")
        self.palette_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        ttk.Label(self.palette_frame, text="Select component:").pack(pady=5)
        ttk.Button(self.palette_frame, text="Resistor", command=lambda: self._select_component_for_placement("Resistor")).pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="V_Source_DC", command=lambda: self._select_component_for_placement("V_Source_DC")).pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="I_Source_DC", command=lambda: self._select_component_for_placement("I_Source_DC")).pack(fill=tk.X, pady=2)
        # ttk.Button(self.palette_frame, text="Pointer", command=lambda: self._select_component_for_placement(None)).pack(fill=tk.X, pady=5) # For deselecting

        # --- Right Frame (Results/Formulas Display) ---
        self.results_frame = ttk.LabelFrame(self.main_frame, text="Formulas & Results", padding="10")
        self.results_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.results_text = tk.Text(self.results_frame, wrap=tk.WORD, height=15, state=tk.DISABLED)
        self.results_text.pack(fill=tk.BOTH, expand=True, pady=5)
        # Scrollbar for results_text (optional but good for lots of text)
        # results_scrollbar = ttk.Scrollbar(self.results_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        # results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # self.results_text.config(yscrollcommand=results_scrollbar.set)


        # --- Center Frame (Canvas & Inputs) ---
        self.center_frame = ttk.Frame(self.main_frame, padding="10")
        self.center_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Canvas for drawing circuit
        self.canvas_frame_container = ttk.LabelFrame(self.center_frame, text="Circuit Canvas", padding="10")
        self.canvas_frame_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=5)

        self.canvas = tk.Canvas(self.canvas_frame_container, bg="white", width=600, height=400)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        # Programmatic Input Area for dynamic components
        self.input_area_frame = ttk.LabelFrame(self.center_frame, text="Programmatic Circuit Definition", padding="10")
        self.input_area_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        # Container for the dynamic list of component rows
        self.components_list_container_frame = ttk.Frame(self.input_area_frame)
        self.components_list_container_frame.pack(fill=tk.X, expand=True)

        self.component_entries = [] # List to hold dicts of widgets for each component row

        # Action Buttons - now includes Add/Remove
        self.action_buttons_frame = ttk.Frame(self.input_area_frame)
        self.action_buttons_frame.pack(fill=tk.X, pady=10)

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

        # --- Analysis Options Frame ---
        self.analysis_options_frame = ttk.LabelFrame(self.input_area_frame, text="Analysis & Calculation Targets", padding="10")
        self.analysis_options_frame.pack(fill=tk.X, pady=(10,0), side=tk.BOTTOM)

        ttk.Label(self.analysis_options_frame, text="Target Comp. Name (GUI Name):").pack(side=tk.LEFT, padx=5)
        self.target_comp_name_entry = ttk.Entry(self.analysis_options_frame, width=10)
        self.target_comp_name_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(self.analysis_options_frame, text="Target Node (for V(node,'0')):") .pack(side=tk.LEFT, padx=5)
        self.target_node_name_entry = ttk.Entry(self.analysis_options_frame, width=10)
        self.target_node_name_entry.pack(side=tk.LEFT, padx=5)

        # Pre-fill example component rows and add some empty ones
        self._add_component_row(load_data={'type':"V_Source_DC", 'name':"S1", 'value':"US_sym", 'n1':"n1", 'n2':"0"})
        self._add_component_row(load_data={'type':"Resistor", 'name':"1", 'value':"R1_sym", 'n1':"n1", 'n2':"n2"})
        self._add_component_row(load_data={'type':"Resistor", 'name':"2", 'value':"R2_sym", 'n1':"n2", 'n2':"0"})
        for _ in range(3):
            self._add_component_row()


    def display_message(self, title, message):
        # Helper to display messages in the results_text widget
        self.results_text.config(state=tk.NORMAL)
        self.results_text.insert(tk.END, f"--- {title} ---\n{message}\n\n")
        self.results_text.see(tk.END) # Scroll to the end
        self.results_text.config(state=tk.DISABLED)

    def on_derive_formulas(self):
        # Clear previous results
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete('1.0', tk.END)
        self.results_text.config(state=tk.DISABLED)

        circuit_data = self._collect_circuit_data()
        if not circuit_data:
            self.display_message("Input Error", "No valid component data entered.")
            return

        spice_string = self._generate_spice_netlist(circuit_data)
        self.display_message("Generated SPICE Netlist", spice_string)

        temp_spice_file_path = ""
        try:
            # Create a temporary file to save the SPICE netlist
            # Using delete=False and manual removal for more robust error handling visibility
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sp', dir='.', encoding='utf-8') as tmp_file:
                tmp_file.write(spice_string)
                temp_spice_file_path = tmp_file.name

            self.display_message("Solver Status", f"Attempting to parse generated netlist: {os.path.basename(temp_spice_file_path)}")

            # 1. Parse the netlist from the temporary file
            top_circuit = scs_parser.parse_file(temp_spice_file_path, scs_circuit.TopCircuit())
            if not top_circuit:
                # parse_file now returns None on error and logs specifics, so raise a generic error.
                raise scs_errors.ScsParserError(f"Failed to parse the generated SPICE netlist from {temp_spice_file_path}. Check console for logged errors.")

            self.display_message("Solver Status", "SPICE parsed successfully. Instantiating circuit...")

            # 2. Create circuit instance (and store it on self for potential future use by other functions)
            self.top_instance = scs_instance_hier.make_top_instance(top_circuit)
            if not self.top_instance:
                raise scs_errors.ScsInstanceError("Failed to instantiate the circuit from parsed SPICE.")

            self.display_message("Solver Status", "Circuit instantiated. Performing checks...")
            # 3. Perform basic circuit checks
            if not self.top_instance.check_path_to_gnd():
                 raise scs_errors.ScsInstanceError("Circuit check failed: No path to ground for some nets.")
            if not self.top_instance.check_voltage_loop():
                 raise scs_errors.ScsInstanceError("Circuit check failed: Voltage loop detected.")

            self.display_message("Solver Status", "Checks passed. Solving symbolically...")
            # 4. Solve the circuit symbolically
            self.top_instance.solve()
            self.display_message("Solver Status", "Symbolic solution complete.")

            # --- 5. Derive and Display Formulas based on Targets ---
            formulas_str = "Derived Symbolic Formulas:\n"
            target_comp_gui_name = self.target_comp_name_entry.get().strip()
            target_node_name = self.target_node_name_entry.get().strip()

            # circuit_data was collected at the start of this method (passed to _generate_spice_netlist)

            if not target_comp_gui_name and not target_node_name:
                formulas_str += "  No target component or node specified for detailed formula display.\n"
                formulas_str += "  Please enter a component's GUI Name (e.g., 'S1', '1') or a Node Name.\n"

            if target_comp_gui_name:
                comp_details = self._get_component_details_from_gui_name(target_comp_gui_name, circuit_data)
                if comp_details:
                    formulas_str += f"  --- For Component (GUI Name: {target_comp_gui_name}, SPICE Name: {comp_details['spice_name']}) ---\n"
                    try:
                        v_expr = self.top_instance.v(comp_details['n1'], comp_details['n2'])
                        formulas_str += f"    Voltage across (V({comp_details['n1']},{comp_details['n2']})): {sympy.pretty(v_expr)}\n"
                    except Exception as e_v:
                        formulas_str += f"    Could not derive V({comp_details['n1']},{comp_details['n2']}): {type(e_v).__name__} - {e_v}\n"
                    try:
                        i_expr = self.top_instance.i(comp_details['spice_name'])
                        formulas_str += f"    Current through (I({comp_details['spice_name']})): {sympy.pretty(i_expr)}\n"
                    except Exception as e_i:
                        formulas_str += f"    Could not derive I({comp_details['spice_name']}): {type(e_i).__name__} - {e_i}\n"
                    try:
                        p_expr = self.top_instance.p(comp_details['spice_name'])
                        formulas_str += f"    Power (P({comp_details['spice_name']})): {sympy.pretty(p_expr)}\n"
                    except Exception as e_p:
                        formulas_str += f"    Could not derive P({comp_details['spice_name']}): {type(e_p).__name__} - {e_p}\n"
                else:
                    formulas_str += f"  Component with GUI Name '{target_comp_gui_name}' not found in current circuit definition.\n"

            if target_node_name:
                formulas_str += f"  --- For Node {target_node_name} ---\n"
                try:
                    v_node_expr = self.top_instance.v(target_node_name, '0')
                    formulas_str += f"    Voltage V({target_node_name}, '0'): {sympy.pretty(v_node_expr)}\n"
                except Exception as e_vn:
                    formulas_str += f"    Could not derive V({target_node_name}, '0'): {type(e_vn).__name__} - {e_vn}\n"

            self.display_message("Symbolic Formulas", formulas_str)

        except (scs_errors.ScsParserError, scs_errors.ScsInstanceError, ValueError, FileNotFoundError) as e:
            self.display_message("Solver Error", f"An error occurred: {type(e).__name__} - {str(e)}")
        except Exception as e:
            # Catch any other unexpected errors
            self.display_message("Unexpected Error", f"An unexpected error occurred: {type(e).__name__} - {str(e)}\nConsider checking console for more details.")
            import traceback
            traceback.print_exc() # Print full traceback to console for debugging unexpected errors
        finally:
            # Clean up the temporary file
            if temp_spice_file_path and os.path.exists(temp_spice_file_path):
                try:
                    os.remove(temp_spice_file_path)
                    self.display_message("Solver Status", f"Temporary file {os.path.basename(temp_spice_file_path)} removed.")
                except Exception as e_remove:
                    print(f"Error removing temp file {temp_spice_file_path}: {e_remove}") # Log to console

        # After self.top_instance.solve() is successful, populate self.active_symbols_info
        self.active_symbols_info.clear() # Clear from previous run
        if self.top_instance and self.top_instance.paramsd:
            defined_free_symbols = {str(s_obj) for s_obj in self.top_instance.paramsd if self.top_instance.paramsd[s_obj] == s_obj}

            # Use circuit_data that was used to generate the SPICE for this solve session
            # This circuit_data was collected at the start of on_derive_formulas
            for comp_gui_dict in circuit_data:
                gui_name = comp_gui_dict['name']
                val_str_from_gui = comp_gui_dict['value']

                if val_str_from_gui in defined_free_symbols:
                    prefix = 'X'
                    if comp_gui_dict['type'] == "Resistor": prefix = 'R'
                    elif comp_gui_dict['type'] == "V_Source_DC": prefix = 'V'
                    elif comp_gui_dict['type'] == "I_Source_DC": prefix = 'I'
                    actual_spice_name = prefix + gui_name

                    self.active_symbols_info[gui_name] = {
                        'symbol': sympy.Symbol(val_str_from_gui),
                        'spice_name': actual_spice_name,
                        'n1': comp_gui_dict['n1'],
                        'n2': comp_gui_dict['n2'] if comp_gui_dict['n2'] else '0'
                    }
            self.display_message("Solver Status", f"Identified active symbolic inputs for numerical calculation: {list(self.active_symbols_info.keys())}")
    def _get_component_details_from_gui_name(self, target_gui_name_str, circuit_data):
        if not target_gui_name_str:
            return None
        for comp_dict in circuit_data:
            if comp_dict['name'] == target_gui_name_str:
                prefix = 'X' # Default
                comp_type_str = comp_dict['type']
                if comp_type_str == "Resistor": prefix = 'R'
                elif comp_type_str == "V_Source_DC": prefix = 'V'
                elif comp_type_str == "I_Source_DC": prefix = 'I'
                actual_spice_name = prefix + comp_dict['name']

                return {
                    'gui_name': comp_dict['name'],
                    'spice_name': actual_spice_name,
                    'n1': comp_dict['n1'],
                    'n2': comp_dict['n2'] if comp_dict['n2'] else '0',
                    'type': comp_dict['type'],
                    'value_str': comp_dict['value']
                }
        return None

    def _eval_expr_to_float(self, expr, default_on_error="N/A (eval error)"):
        """ Helper to evaluate a sympy expression to float, handling potential errors."""
        try:
            if hasattr(expr, 'free_symbols') and expr.free_symbols:
                 pass
            return float(expr.evalf())
        except (AttributeError, TypeError, sympy.SympifyError, Exception):
            return default_on_error

    def _add_component_row(self, load_data=None):
        if load_data is None:
            load_data = {}

        row_frame = ttk.Frame(self.components_list_container_frame)
        row_frame.pack(fill=tk.X, pady=2, padx=2)

        component_types = ["", "Resistor", "V_Source_DC", "I_Source_DC"] # Duplicated for now, consider class/instance var

        ttk.Label(row_frame, text=f"Comp {len(self.component_entries) + 1}: Type=").pack(side=tk.LEFT, padx=(0,2))
        type_combo = ttk.Combobox(row_frame, values=component_types, width=12, state="readonly")
        type_combo.pack(side=tk.LEFT, padx=2)
        type_combo.set(load_data.get('type', ''))

        ttk.Label(row_frame, text="Name=").pack(side=tk.LEFT, padx=(5,2))
        name_entry = ttk.Entry(row_frame, width=8)
        name_entry.pack(side=tk.LEFT, padx=2)
        name_entry.insert(0, load_data.get('name', ''))

        ttk.Label(row_frame, text="Value/Symbol=").pack(side=tk.LEFT, padx=(5,2))
        value_entry = ttk.Entry(row_frame, width=10)
        value_entry.pack(side=tk.LEFT, padx=2)
        value_entry.insert(0, load_data.get('value', ''))

        ttk.Label(row_frame, text="N1=").pack(side=tk.LEFT, padx=(5,2))
        n1_entry = ttk.Entry(row_frame, width=5)
        n1_entry.pack(side=tk.LEFT, padx=2)
        n1_entry.insert(0, load_data.get('n1', ''))

        ttk.Label(row_frame, text="N2=").pack(side=tk.LEFT, padx=(5,2))
        n2_entry = ttk.Entry(row_frame, width=5)
        n2_entry.pack(side=tk.LEFT, padx=2)
        n2_entry.insert(0, load_data.get('n2', ''))

        row_widgets = {
            'frame': row_frame, 'type': type_combo, 'name': name_entry, 'value': value_entry,
            'n1': n1_entry, 'n2': n2_entry
        }
        self.component_entries.append(row_widgets)

    def _remove_last_component_row(self):
        if self.component_entries:
            last_row_widgets = self.component_entries.pop()
            last_row_widgets['frame'].destroy()
            # Adjust numbering if Comp labels were dynamic (Comp {i+1}) - for now, they are static at creation.

    def _collect_circuit_data(self):
        collected_data = []
        for row_widgets in self.component_entries:
            comp_type = row_widgets['type'].get()
            name = row_widgets['name'].get().strip()
            value_str = row_widgets['value'].get().strip()
            n1_str = row_widgets['n1'].get().strip()
            n2_str = row_widgets['n2'].get().strip()
            # n3_str = row_widgets['n3'].get().strip() # For controlled sources
            # n4_str = row_widgets['n4'].get().strip() # For controlled sources

            if comp_type and name: # Basic validation: type and name must be present
                entry = {'type': comp_type, 'name': name, 'value': value_str,
                         'n1': n1_str, 'n2': n2_str}
                # if comp_type in ["VCVS", "CCCS", "VCCS", "CCVS"]: # Example types for 4-terminal devices
                #    entry['n3'] = n3_str
                #    entry['n4'] = n4_str
                collected_data.append(entry)
        return collected_data

    def _generate_spice_netlist(self, circuit_data):
        spice_lines = ['* Generated SPICE Netlist from GUI']
        param_lines = []
        symbol_ensure_lines = set() # Use a set to avoid duplicate .PARAM X = X lines

        def is_numeric(s):
            try:
                float(s)
                return True
            except ValueError:
                return False

        for comp in circuit_data:
            comp_name_val_param = comp['name'] + "_val" # e.g. R1_val, VS1_val
            val_str = comp['value']

            if not val_str: # Handle empty value string
                # Default to 0 for numeric, or treat as an error, or use a placeholder symbol
                # For now, let's make it a parameter that defaults to 0, or use the component name itself as a symbol
                # This part might need refinement based on desired behavior for empty values.
                # Defaulting to 0 if it's a V/I source, or a symbol if it's a resistor might be one way.
                # Let's assume for now an empty value means it will be a symbol named like the component.
                # E.g., R1 with empty value becomes R1_sym.
                # This is a design choice for how to handle missing GUI input.
                # For now, let's assume user means it to be symbolic by component name if value is empty
                if comp['type'] == "Resistor" and not val_str: # Default R name to R_sym
                    symbol_name = comp['name'] + "_sym"
                elif comp['type'] in ["V_Source_DC", "I_Source_DC"] and not val_str:
                     symbol_name = comp['name'] + "_source_sym" # Default V/I source name to VS_sym
                elif val_str: # Not empty, but might be symbolic
                     symbol_name = val_str # This will be checked by is_numeric next
                else: # Truly empty and not R/V/I, or needs specific handling
                    self.display_message("Netlist Gen Error", f"Empty value for component {comp['name']} of type {comp['type']} is ambiguous. Please provide a value or symbol name.")
                    # Defaulting to 0 for now if truly ambiguous and not caught above
                    symbol_name = "0" # Fallback, will make it numeric '0'
                    val_str = "0" # Ensure it's treated as numeric '0'

            # Check if the value string is intended to be a symbol or is numeric
            if not is_numeric(val_str):
                # It's a symbol (e.g. R1_sym, VS_sym, or user entered text like "my_R_symbol")
                symbol_name_to_use = val_str # The user-entered string is the symbol
                param_lines.append(f".PARAM {comp_name_val_param} = {symbol_name_to_use}")
                # Ensure the base symbol itself is declared if it's not a direct numeric assignment
                symbol_ensure_lines.add(f".PARAM {symbol_name_to_use} = {symbol_name_to_use}")
            else:
                # It's a numeric value
                param_lines.append(f".PARAM {comp_name_val_param} = {val_str}")

            prefix = ""
            if comp['type'] == "Resistor": prefix = "R"
            elif comp['type'] == "V_Source_DC": prefix = "V"
            elif comp['type'] == "I_Source_DC": prefix = "I"
            else: prefix = "X" # Default for unknown, though Combobox restricts types

            # Element line using the parameter name (e.g., R1 N1 N2 R1_val)
            spice_lines.append(f"{prefix}{comp['name']} {comp['n1']} {comp['n2']} {comp_name_val_param}")
            # For 4-terminal devices, this line would need to include comp['n3'], comp['n4']

        # Assemble the netlist string
        # Order: Title, .PARAM for component values, .PARAM for ensuring base symbols, Element lines, .END
        unique_symbol_ensure_lines = sorted(list(symbol_ensure_lines)) # Sort for consistent order

        netlist_parts = [spice_lines[0]] # Title
        if param_lines: netlist_parts.extend(param_lines)
        if unique_symbol_ensure_lines: netlist_parts.extend(unique_symbol_ensure_lines)
        netlist_parts.extend(spice_lines[1:]) # Element lines
        netlist_parts.append(".END")

        return "\n".join(netlist_parts)

    def on_calculate_numerical(self):
        # Clear previous messages, or append after a header
        # For now, let's make it clear it's a new operation
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete('1.0', tk.END) # Clear previous results before showing new ones
        # self.results_text.config(state=tk.DISABLED) # display_message will handle this

        if not hasattr(self, 'top_instance') or not self.top_instance:
            self.display_message("Error", "Please derive formulas first (symbolic solution not available).")
            return

        if not self.active_symbols_info: # Check the refined attribute name
            self.display_message("Error", "No active user-defined symbolic inputs found from the 'Derive Formulas' step to substitute.")
            self.display_message("Info", "This means either no component values were defined as symbols (e.g., 'R1_sym'), or those symbols were not free parameters in the circuit solution.")
            return

        numerical_substitutions = {}
        current_circuit_data = self._collect_circuit_data() # Get current GUI state for component values

        # Build numerical_substitutions dictionary based on self.active_symbols_info
        # and current values in the GUI fields for those components.
        numerical_substitutions = {}
        all_inputs_valid = True
        if not self.active_symbols_info:
             self.display_message("Info", "No symbolic parameters were identified in the previous 'Derive Formulas' step for substitution.")
             # Continue to allow calculation for non-symbolic components or nodes if targeted
        else:
            gui_values_map = {item['name']: item['value'] for item in current_circuit_data}
            for gui_comp_name_key, info in self.active_symbols_info.items():
                symbol_obj = info['symbol']
                current_value_str = gui_values_map.get(gui_comp_name_key)
                if current_value_str is not None and current_value_str.strip() != "":
                    try:
                        num_val = float(current_value_str)
                        numerical_substitutions[symbol_obj] = num_val
                    except ValueError:
                        self.display_message("Input Error", f"Value '{current_value_str}' for component '{gui_comp_name_key}' (symbol '{symbol_obj}') is not a valid number.")
                        all_inputs_valid = False; break
                else:
                    self.display_message("Input Error", f"Missing numerical value for component '{gui_comp_name_key}' (symbol '{symbol_obj}').")
                    all_inputs_valid = False; break

            if not all_inputs_valid: # If any symbolic input was invalid, abort before further calculation
                self.display_message("Calculation Status", "Numerical calculation aborted due to input errors for symbolic parameters.")
                return

            if numerical_substitutions :
                self.display_message("Numerical Calculation", f"Substituting with: { {str(k):v for k,v in numerical_substitutions.items()} }")

        # --- Display numerical results for specified targets ---
        results_str = "Numerical Results:\n"
        target_comp_gui_name = self.target_comp_name_entry.get().strip()
        target_node_name = self.target_node_name_entry.get().strip()

        if not target_comp_gui_name and not target_node_name:
            results_str += "  No target component or node specified for numerical calculation.\n"
            results_str += "  Please enter a component's GUI Name or a Node Name in 'Analysis & Calculation Targets'.\n"

        if target_comp_gui_name:
            comp_details = self._get_component_details_from_gui_name(target_comp_gui_name, current_circuit_data)
            if comp_details:
                results_str += f"  --- For Component (GUI Name: {target_comp_gui_name}, SPICE Name: {comp_details['spice_name']}) ---\n"
                try:
                    v_expr = self.top_instance.v(comp_details['n1'], comp_details['n2'])
                    i_expr = self.top_instance.i(comp_details['spice_name'])
                    p_expr = self.top_instance.p(comp_details['spice_name'])

                    v_val_num_expr = v_expr.subs(numerical_substitutions)
                    i_val_num_expr = i_expr.subs(numerical_substitutions)
                    p_val_num_expr = p_expr.subs(numerical_substitutions)

                    # Get component's own value (e.g. resistance, source value)
                    # The value_str from comp_details might be a number string or a symbol string
                    comp_own_val_expr = sympy.sympify(comp_details['value_str']) if comp_details['value_str'] else sympy.Float(0) # Default to 0 if empty
                    if hasattr(comp_own_val_expr, 'subs'):
                        comp_own_val_num_expr = comp_own_val_expr.subs(numerical_substitutions)
                    else:
                        comp_own_val_num_expr = comp_own_val_expr # Already a number if sympify made it so

                    comp_val_numeric = self._eval_expr_to_float(comp_own_val_num_expr, "N/A (value not fully numeric or symbolic)")
                    v_val_numeric = self._eval_expr_to_float(v_val_num_expr)
                    i_val_numeric = self._eval_expr_to_float(i_val_num_expr)
                    p_val_numeric = self._eval_expr_to_float(p_val_num_expr)

                    comp_type_label = comp_details['type']
                    # Display component's own value with appropriate unit (basic guess)
                    unit_str = ""
                    if comp_type_label == "Resistor": unit_str = "Ω"
                    elif comp_type_label == "V_Source_DC": unit_str = "V"
                    elif comp_type_label == "I_Source_DC": unit_str = "A"
                    # Add more for C, L if they are added to GUI types

                    results_str += f"    Value ({comp_type_label}): {comp_val_numeric if isinstance(comp_val_numeric, str) else f'{comp_val_numeric:.4f}'} {unit_str}\n"

                    results_str += f"    Voltage across: {v_val_numeric if isinstance(v_val_numeric, str) else f'{v_val_numeric:.4f}'} V\n"
                    results_str += f"    Current through: {i_val_numeric if isinstance(i_val_numeric, str) else f'{i_val_numeric * 1000:.4f}'} mA\n"
                    results_str += f"    Power: {p_val_numeric if isinstance(p_val_numeric, str) else f'{p_val_numeric * 1000:.4f}'} mW\n"

                except Exception as e_calc:
                    results_str += f"    Error calculating numerical V/I/P for '{target_comp_gui_name}': {type(e_calc).__name__} - {e_calc}\n"
            else:
                results_str += f"  Component with GUI Name '{target_comp_gui_name}' not found in current circuit definition.\n"

        if target_node_name:
            results_str += f"  --- For Node {target_node_name} ---\n"
            try:
                v_node_expr = self.top_instance.v(target_node_name, '0')
                v_node_num_expr = v_node_expr.subs(numerical_substitutions)
                v_node_numeric = self._eval_expr_to_float(v_node_num_expr)
                results_str += f"    Voltage V({target_node_name}, '0'): {v_node_numeric if isinstance(v_node_numeric, str) else f'{v_node_numeric:.4f}'} V\n"
            except Exception as e_vn_calc:
                results_str += f"    Could not calculate V({target_node_name}, '0'): {type(e_vn_calc).__name__} - {e_vn_calc}\n"

        self.display_message("Numerical Results", results_str)

    def _eval_expr_to_float(self, expr, default_on_error="N/A (eval error)"):
        """ Helper to evaluate a sympy expression to float, handling potential errors."""
        try:
            # Ensure all free symbols are substituted before evalf, otherwise it might not be float
            if hasattr(expr, 'free_symbols') and expr.free_symbols:
                # This indicates not all symbols were substituted by numerical_substitutions
                # This can happen if a component value was numeric "100" but formulas still had "R1_sym"
                # For now, we rely on numerical_substitutions to cover all active symbols.
                # If free_symbols remain, evalf() might return a symbolic expr, not a float.
                 pass # Proceed and let float() attempt conversion.
            return float(expr.evalf())
        except (AttributeError, TypeError, sympy.SympifyError, Exception):
            return default_on_error

    def _save_circuit_to_file(self):
        circuit_data = self._collect_circuit_data()
        if not circuit_data:
            # Using messagebox for interactive feedback, though display_message is also an option
            messagebox.showwarning("Save Circuit", "No circuit data to save.")
            # self.display_message("Save Circuit", "No circuit data to save.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Circuit As",
            initialdir=os.path.join(os.getcwd(), "examples") # Suggest examples directory
        )
        if not filepath: # User cancelled
            return

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(circuit_data, f, indent=4)
            self.display_message("Save Circuit", f"Circuit saved successfully to {os.path.basename(filepath)}")
        except Exception as e:
            self.display_message("Save Error", f"Failed to save circuit: {type(e).__name__} - {e}")

    def _load_circuit_from_file(self):
        filepath = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Circuit From",
            initialdir=os.path.join(os.getcwd(), "examples") # Suggest examples directory
        )
        if not filepath: # User cancelled
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)

            if not isinstance(loaded_data, list):
                raise ValueError("File does not contain a valid list of circuit components.")

            # Clear existing component rows from GUI
            while self.component_entries:
                self._remove_last_component_row()

            # Add new rows from loaded data
            for component_data in loaded_data:
                if not isinstance(component_data, dict) or \
                   not all(k in component_data for k in ['type', 'name', 'value', 'n1', 'n2']):
                    self.display_message("Load Warning", f"Skipping invalid or incomplete component data: {component_data}")
                    continue
                self._add_component_row(load_data=component_data)

            self.display_message("Load Circuit", f"Circuit loaded successfully from {os.path.basename(filepath)}")

            # Clear any previous results/formulas as the circuit has changed
            self.results_text.config(state=tk.NORMAL)
            self.results_text.delete('1.0', tk.END)
            self.results_text.config(state=tk.DISABLED)

            # Invalidate old solved instance and active symbols
            if hasattr(self, 'top_instance'):
                self.top_instance = None
            if hasattr(self, 'active_symbols_info'):
                self.active_symbols_info.clear()

        except FileNotFoundError:
            self.display_message("Load Error", f"File not found: {filepath}")
        except json.JSONDecodeError:
            self.display_message("Load Error", "File is not a valid JSON format.")
        except ValueError as ve:
            self.display_message("Load Error", str(ve))
        except Exception as e:
            self.display_message("Load Error", f"Failed to load circuit: {type(e).__name__} - {e}")

    def _select_component_for_placement(self, comp_type):
        self.selected_component_to_place = comp_type
        if comp_type:
            self.display_message("Status", f"{comp_type} selected. Click on the canvas to place.")
        else: # E.g. if a "Pointer" tool was selected
            self.display_message("Status", "Placement mode deselected (Pointer tool active).")

    def _on_canvas_click(self, event):
        if self.selected_component_to_place:
            x, y = event.x, event.y
            comp_type = self.selected_component_to_place

            logical_item_id = self.next_graphical_item_id
            self.next_graphical_item_id += 1

            canvas_item_ids = self._draw_component_symbol(x, y, comp_type, logical_item_id)

            self.placed_graphical_items.append({
                'id': logical_item_id,
                'type': comp_type,
                'x': x,
                'y': y,
                'canvas_item_ids': canvas_item_ids
            })

            self.display_message("Canvas", f"Placed {comp_type} (ID: {logical_item_id}) at ({x}, {y}).")
            # To place multiple of the same type, keep self.selected_component_to_place active.
            # To place only one, uncomment below:
            # self.selected_component_to_place = None
            # self.display_message("Status", "Placement mode deselected. Select new component.")
        else:
            self.display_message("Canvas", f"Canvas clicked at ({event.x}, {event.y}) - No component type selected from palette.")

    def _draw_component_symbol(self, x, y, comp_type, item_id):
        # item_id is the logical ID of the component instance
        tag = f"comp_{item_id}" # Tag for all parts of this component symbol
        canvas_ids = []
        size = 20 # Half-size for easier coordinate management (e.g. center is x,y)

        if comp_type == "Resistor":
            # Simple rectangle for resistor
            rect_id = self.canvas.create_rectangle(x - size*1.5, y - size*0.5, x + size*1.5, y + size*0.5, outline="black", fill="lightblue", tags=(tag,))
            canvas_ids.append(rect_id)
        elif comp_type == "V_Source_DC":
            # Circle for DC voltage source
            circle_id = self.canvas.create_oval(x - size, y - size, x + size, y + size, outline="black", fill="lightgreen", tags=(tag,))
            # Polarity lines (simple plus/minus) - ensure they are visible relative to size
            plus_id = self.canvas.create_line(x, y - size*0.6, x, y - size*0.2, tags=(tag,)) # Vertical part of +
            self.canvas.create_line(x - size*0.2, y - size*0.4, x + size*0.2, y - size*0.4, tags=(tag,)) # Horizontal part of +
            minus_id = self.canvas.create_line(x - size*0.2, y + size*0.4, x + size*0.2, y + size*0.4, width=2, tags=(tag,)) # Minus
            canvas_ids.extend([circle_id, plus_id, minus_id]) # minus_id is already a list from create_line
        elif comp_type == "I_Source_DC":
            # Circle with an arrow for DC current source
            circle_id = self.canvas.create_oval(x - size, y - size, x + size, y + size, outline="black", fill="lightpink", tags=(tag,))
            # Arrow (pointing up)
            arrow_body_id = self.canvas.create_line(x, y + size*0.6, x, y - size*0.6, tags=(tag,))
            arrow_head_id = self.canvas.create_line(x, y - size*0.6, x - size*0.2, y - size*0.3, x + size*0.2, y - size*0.3, x, y-size*0.6, smooth=True, tags=(tag,))
            canvas_ids.extend([circle_id, arrow_body_id, arrow_head_id])
        else:
            # Default placeholder for unknown types
            text_id = self.canvas.create_text(x, y, text=f"{comp_type[:3]}?", tags=(tag,))
            canvas_ids.append(text_id)

        # Add a small text label with the logical ID for debugging/identification
        label_id = self.canvas.create_text(x, y - size - 7, text=f"{comp_type[0]}{item_id}", font=("Arial", 8), tags=(tag,)) # Adjusted font size and offset
        canvas_ids.append(label_id)

        return canvas_ids


if __name__ == '__main__':
    app = CircuitGUI()
    app.mainloop()
