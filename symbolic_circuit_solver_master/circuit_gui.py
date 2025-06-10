import tkinter as tk
from tkinter import ttk, messagebox # Added messagebox for potential future use, not strictly for this step
import os
import tempfile
import sympy # For sympy.pretty and potentially creating symbols if needed by solver directly

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
                                      # Structure: { 'gui_comp_name1': {'symbol': sympy.Symbol('Sym1'), 'spice_name': 'RSym1', 'n1':'N1', 'n2':'N0'}, ... }
        super().__init__()
        self.title("Symbolic Circuit Simulator GUI - Phase 1")
        self.geometry("1000x700") # Initial size

        # Configure main layout frames
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Left Frame (Component Palette - Placeholder) ---
        self.palette_frame = ttk.LabelFrame(self.main_frame, text="Components", padding="10")
        self.palette_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        ttk.Label(self.palette_frame, text="(Placeholder for component buttons)").pack(pady=5)
        # Example component buttons (non-functional for now)
        ttk.Button(self.palette_frame, text="Resistor").pack(fill=tk.X, pady=2)
        ttk.Button(self.palette_frame, text="V_Source").pack(fill=tk.X, pady=2)

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

        # Canvas Placeholder
        self.canvas_placeholder_frame = ttk.LabelFrame(self.center_frame, text="Circuit Canvas", padding="10")
        self.canvas_placeholder_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=5)
        ttk.Label(self.canvas_placeholder_frame, text="(Placeholder for graphical circuit drawing - Future)").pack(expand=True)

        # Programmatic Input Area - Refined
        self.input_area_frame = ttk.LabelFrame(self.center_frame, text="Programmatic Circuit Definition", padding="10")
        self.input_area_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        self.component_entries = []
        component_types = ["", "Resistor", "V_Source_DC", "I_Source_DC"]
        num_component_rows = 6

        for i in range(num_component_rows):
            row_frame = ttk.Frame(self.input_area_frame)
            row_frame.pack(fill=tk.X, pady=2)

            ttk.Label(row_frame, text=f"Comp {i+1}: Type=").pack(side=tk.LEFT, padx=(0,2))
            type_combo = ttk.Combobox(row_frame, values=component_types, width=12, state="readonly")
            type_combo.pack(side=tk.LEFT, padx=2)
            type_combo.current(0) # Default to empty

            ttk.Label(row_frame, text="Name=").pack(side=tk.LEFT, padx=(5,2))
            name_entry = ttk.Entry(row_frame, width=8)
            name_entry.pack(side=tk.LEFT, padx=2)

            ttk.Label(row_frame, text="Value/Symbol=").pack(side=tk.LEFT, padx=(5,2))
            value_entry = ttk.Entry(row_frame, width=10)
            value_entry.pack(side=tk.LEFT, padx=2)

            ttk.Label(row_frame, text="N1=").pack(side=tk.LEFT, padx=(5,2))
            n1_entry = ttk.Entry(row_frame, width=5)
            n1_entry.pack(side=tk.LEFT, padx=2)

            ttk.Label(row_frame, text="N2=").pack(side=tk.LEFT, padx=(5,2))
            n2_entry = ttk.Entry(row_frame, width=5)
            n2_entry.pack(side=tk.LEFT, padx=2)

            # For controlled sources, N3 and N4 might be needed. Add placeholders if time allows, or for future.
            # ttk.Label(row_frame, text="N3=").pack(side=tk.LEFT, padx=(5,2))
            # n3_entry = ttk.Entry(row_frame, width=5)
            # n3_entry.pack(side=tk.LEFT, padx=2)
            # ttk.Label(row_frame, text="N4=").pack(side=tk.LEFT, padx=(5,2))
            # n4_entry = ttk.Entry(row_frame, width=5)
            # n4_entry.pack(side=tk.LEFT, padx=2)


            row_widgets = {
                'type': type_combo, 'name': name_entry, 'value': value_entry,
                'n1': n1_entry, 'n2': n2_entry #, 'n3': n3_entry, 'n4': n4_entry
            }
            self.component_entries.append(row_widgets)

        # Action Buttons
        self.action_buttons_frame = ttk.Frame(self.input_area_frame)
        self.action_buttons_frame.pack(fill=tk.X, pady=10)

        self.derive_button = ttk.Button(self.action_buttons_frame, text="Derive Formulas", command=self.on_derive_formulas)
        self.derive_button.pack(side=tk.LEFT, padx=5)

        self.calculate_button = ttk.Button(self.action_buttons_frame, text="Calculate Numerical Values", command=self.on_calculate_numerical)
        self.calculate_button.pack(side=tk.LEFT, padx=5)

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

            # --- 5. Derive and Display Example Formulas ---
            formulas_str = "Derived Symbolic Formulas (for first valid component):\n"
            first_comp_data = None
            for comp_data_dict in circuit_data: # circuit_data from _collect_circuit_data()
                if comp_data_dict.get('name') and comp_data_dict.get('n1'): # Basic check for a usable component
                    first_comp_data = comp_data_dict
                    break

            if first_comp_data:
                comp_name = first_comp_data['name']
                node1_name = first_comp_data['n1']

                # Attempt to get voltage at node1 of the first component (relative to ground '0')
                try:
                    v_expr = self.top_instance.v(node1_name, '0')
                    formulas_str += f"  Voltage at node '{node1_name}' (V({node1_name}, 0)): {sympy.pretty(v_expr)}\n"
                except Exception as e_v:
                    formulas_str += f"  Could not derive V({node1_name}): {type(e_v).__name__} - {e_v}\n"

                # Attempt to get current through the first component
                try:
                    # Ensure the element name for i() matches the SPICE prefix + GUI name if parser uses that.
                    # The _generate_spice_netlist prepends R, V, I to names.
                    # For now, assume self.top_instance.i() can find 'comp_name' if that's how it's stored.
                    # This might need adjustment if i() expects "R<comp_name>" etc.
                    # Based on how elements are added in scs_parser.add_element, the key is `name` (e.g. "R1")
                    # which is head (e.g. "R1"), not `comp['name']` ("1").
                    # The current _generate_spice_netlist uses prefix + comp['name'] e.g. "RR1".
                    # Let's assume for now the name in circuit_data is the one used in SPICE element line.
                    # The _generate_spice_netlist uses `prefix + comp['name']` for the element line.
                    # So if type is "Resistor" and name is "1", element is "R1".

                    # Determine the full SPICE element name
                    spice_el_name = ""
                    if first_comp_data['type'] == "Resistor": spice_el_name = "R" + comp_name
                    elif first_comp_data['type'] == "V_Source_DC": spice_el_name = "V" + comp_name
                    elif first_comp_data['type'] == "I_Source_DC": spice_el_name = "I" + comp_name
                    # Add more types if needed

                    if spice_el_name:
                        i_expr = self.top_instance.i(spice_el_name)
                        formulas_str += f"  Current through element '{spice_el_name}' (I({spice_el_name})): {sympy.pretty(i_expr)}\n"

                        # Attempt to get power in the first component
                        p_expr = self.top_instance.p(spice_el_name)
                        formulas_str += f"  Power in element '{spice_el_name}' (P({spice_el_name})): {sympy.pretty(p_expr)}\n"
                    else:
                        formulas_str += f"  Cannot determine SPICE name for element '{comp_name}' of type '{first_comp_data['type']}' to get I/P.\n"

                except Exception as e_ip: # Catch errors for I and P derivation
                    formulas_str += f"  Could not derive I/P for '{comp_name}': {type(e_ip).__name__} - {e_ip}\n"
            else:
                formulas_str += "  No valid components found to derive example formulas.\n"

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
        # This identifies which GUI-defined components correspond to free symbols in the solved model.
        self.active_symbols_info.clear()
        if self.top_instance and self.top_instance.paramsd:
            # These are the actual free symbols the circuit was solved in terms of.
            # e.g. {sympy.Symbol('R1_sym'): sympy.Symbol('R1_sym'), sympy.Symbol('VS_sym'): sympy.Symbol('VS_sym')}
            # The keys of paramsd are Symbol objects.
            defined_free_symbols = {str(s_obj) for s_obj in self.top_instance.paramsd if self.top_instance.paramsd[s_obj] == s_obj}

            current_gui_circuit_data = self._collect_circuit_data() # circuit_data from GUI state when "Derive" was clicked

            for comp_gui_dict in current_gui_circuit_data:
                gui_name = comp_gui_dict['name'] # This is the "number", e.g., "1" for R1
                val_str_from_gui = comp_gui_dict['value'] # This is the string from value field, e.g., "R1_sym"

                if val_str_from_gui in defined_free_symbols:
                    # This component's value is one of the free symbols in the solved circuit
                    prefix = 'X' # Default
                    if comp_gui_dict['type'] == "Resistor": prefix = 'R'
                    elif comp_gui_dict['type'] == "V_Source_DC": prefix = 'V'
                    elif comp_gui_dict['type'] == "I_Source_DC": prefix = 'I'
                    actual_spice_name = prefix + gui_name # e.g. R1, VS1

                    self.active_symbols_info[gui_name] = {
                        'symbol': sympy.Symbol(val_str_from_gui), # The actual sympy.Symbol object
                        'spice_name': actual_spice_name,
                        'n1': comp_gui_dict['n1'],
                        'n2': comp_gui_dict['n2'] if comp_gui_dict['n2'] else '0' # Default N2 to ground if empty
                    }
            self.display_message("Solver Status", f"Identified active symbolic inputs for numerical calculation: {list(self.active_symbols_info.keys())}")


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
        # Get current values from GUI entries FOR THE SYMBOLIC COMPONENTS
        # self.active_symbols_info maps GUI component name (e.g., "1" for R1) to its symbolic info

        current_gui_values_map = {item['name']: item['value'] for item in self._collect_circuit_data()}
        all_inputs_valid = True

        for gui_comp_name, info in self.active_symbols_info.items():
            symbol_obj = info['symbol'] # The sympy.Symbol object, e.g., Symbol('R1_sym')

            current_value_str = current_gui_values_map.get(gui_comp_name) # Get current text from GUI for this component

            if current_value_str is not None and current_value_str.strip() != "":
                try:
                    num_val = float(current_value_str)
                    numerical_substitutions[symbol_obj] = num_val
                except ValueError:
                    self.display_message("Input Error", f"Value '{current_value_str}' for component '{gui_comp_name}' (intended for symbol '{symbol_obj}') is not a valid number.")
                    all_inputs_valid = False
            else:
                self.display_message("Input Error", f"Missing numerical value for component '{gui_comp_name}' (symbol '{symbol_obj}').")
                all_inputs_valid = False # Require all identified symbols to get a value

        if not all_inputs_valid or not numerical_substitutions:
            self.display_message("Calculation Status", "Numerical calculation aborted due to input errors or no valid substitutions provided.")
            return

        self.display_message("Numerical Calculation", f"Attempting to substitute: { {str(k):v for k,v in numerical_substitutions.items()} }")

        results_str = "Numerical V, I, P Results:\n"

        for gui_comp_name, info in self.active_symbols_info.items():
            spice_name = info['spice_name']
            node1 = info['n1']
            node2 = info['n2'] # Already defaults to '0' if originally empty

            try:
                v_expr = self.top_instance.v(node1, node2)
                i_expr = self.top_instance.i(spice_name)
                p_expr = self.top_instance.p(spice_name)

                # Substitute numerical values into the symbolic expressions
                v_val_num_expr = v_expr.subs(numerical_substitutions)
                i_val_num_expr = i_expr.subs(numerical_substitutions)
                p_val_num_expr = p_expr.subs(numerical_substitutions)

                # Evaluate the substituted expressions to floats
                # Add error handling for evalf() if expression is not fully numeric after subs
                try:
                    v_val_num = float(v_val_num_expr.evalf())
                except (AttributeError, TypeError, sympy. SympifyError): # Catch if not an evaluable expression
                    v_val_num = "N/A (expr not fully numeric)"
                try:
                    i_val_num = float(i_val_num_expr.evalf())
                except (AttributeError, TypeError, sympy.SympifyError):
                    i_val_num = "N/A (expr not fully numeric)"
                try:
                    p_val_num = float(p_val_num_expr.evalf())
                except (AttributeError, TypeError, sympy.SympifyError):
                    p_val_num = "N/A (expr not fully numeric)"

                results_str += f"  For component '{gui_comp_name}' (as {spice_name}):\n"
                results_str += f"    Voltage ({node1}{'-'+node2 if node2 != '0' else ''}): {v_val_num if isinstance(v_val_num, str) else f'{v_val_num:.4f}'} V\n"
                results_str += f"    Current: {i_val_num if isinstance(i_val_num, str) else f'{i_val_num * 1000:.4f}'} mA\n"
                results_str += f"    Power:   {p_val_num if isinstance(p_val_num, str) else f'{p_val_num * 1000:.4f}'} mW\n"
            except Exception as e_calc:
                results_str += f"  Error calculating numerical V/I/P for '{gui_comp_name}' (SPICE: {spice_name}): {type(e_calc).__name__} - {e_calc}\n"

        if not self.active_symbols_info: # Should have been caught earlier, but as a fallback
            results_str += "  No components were identified as having symbolic values from the 'Derive Formulas' step.\n"

        self.display_message("Numerical Results", results_str)


if __name__ == '__main__':
    app = CircuitGUI()
    app.mainloop()
