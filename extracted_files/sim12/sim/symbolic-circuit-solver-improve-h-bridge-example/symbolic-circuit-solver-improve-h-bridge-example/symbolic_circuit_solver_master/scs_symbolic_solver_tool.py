import sympy
from . import scs_parser
from . import scs_instance_hier
from . import scs_circuit
from . import scs_errors # Import scs_errors

class SymbolicCircuitProblemSolver:
    def __init__(self, netlist_path):
        self.netlist_path = netlist_path
        self.top_circuit = None
        self.top_instance = None
        self.solved_symbolic_vars = {}

    def _parse_and_solve_base_circuit(self):
        '''Parses the netlist, creates instance, and solves it symbolically.'''
        if not self.top_instance: # Avoid re-parsing and re-solving if already done
            self.top_circuit = scs_parser.parse_file(self.netlist_path, scs_circuit.TopCircuit())
            if not self.top_circuit:
                raise scs_errors.ScsParserError(f"Failed to parse the netlist: {self.netlist_path}")

            self.top_instance = scs_instance_hier.make_top_instance(self.top_circuit)
            if not self.top_instance:
                raise scs_errors.ScsInstanceError("Failed to instantiate the circuit.")

            # Perform basic checks
            if not self.top_instance.check_path_to_gnd():
                 raise scs_errors.ScsInstanceError("Circuit check failed: No path to ground for some nets.")
            if not self.top_instance.check_voltage_loop():
                 raise scs_errors.ScsInstanceError("Circuit check failed: Voltage loop detected.")

            self.top_instance.solve()

    def solve_for_unknowns(self, known_conditions, params_to_solve_names):
        '''
        Solves for the specified unknown parameters given the known conditions.

        Args:
            known_conditions (list): A list of dictionaries, e.g.,
                [{'type': 'voltage', 'node1': 'N3', 'node2': '0', 'value': 0.1},
                 {'type': 'current', 'element': 'R4', 'value': 559e-6}]
            params_to_solve_names (list): A list of strings, names of the parameters
                                          (as defined in .PARAM) to solve for.

        Returns:
            dict: A dictionary containing the solutions for the specified parameters.
        '''
        self._parse_and_solve_base_circuit()

        equations = []

        # Create Sympy symbols for the parameters we want to solve for
        symbols_to_solve = [sympy.symbols(name) for name in params_to_solve_names]

        subs_dict = {}
        if self.top_instance.paramsd:
            for param_name, param_value in self.top_instance.paramsd.items():
                # param_name here is a sympy.Symbol object, param_value is its expression
                is_target_symbol = False
                for sym_to_solve in symbols_to_solve: # symbols_to_solve contains sympy.Symbol objects
                    if sym_to_solve == param_name:
                        is_target_symbol = True
                        break
                if not is_target_symbol:
                    subs_dict[param_name] = param_value # param_name is already a symbol


        for condition in known_conditions:
            eq = None
            if condition['type'] == 'voltage':
                node1 = condition['node1']
                node2 = condition.get('node2', '0') # Default to ground if not specified
                val = condition['value']
                # Ensure val is a Sympy expression if it's symbolic, or a number
                sym_val = sympy.sympify(val)

                expr_v = self.top_instance.v(node1, node2)
                eq = sympy.Eq(expr_v, sym_val)

            elif condition['type'] == 'current':
                element = condition['element']
                val = condition['value']
                sym_val = sympy.sympify(val)

                expr_i = self.top_instance.i(element)
                eq = sympy.Eq(expr_i, sym_val)

            elif condition['type'] == 'power':
                element_name = condition['element']
                val = condition['value']
                sym_val = sympy.sympify(val)

                # Get element object. For now, assumes non-hierarchical or full path for hierarchical.
                # self.top_instance.elements contains element objects keyed by their name.
                el_obj = self.top_instance.elements.get(element_name)
                if not el_obj:
                    # A more robust solution would be to search recursively in sub-instances
                    # or expect users to provide full hierarchical names like "X1.R1".
                    # The current Element.name does not store hierarchical path.
                    # For now, we rely on direct lookup or that scs_instance_hier flattens names for top_instance.elements
                    raise scs_errors.ScsToolError(f"Element '{element_name}' not found in the circuit instance. Hierarchical elements might require full path if not automatically resolved.")

                if len(el_obj.nets) < 2:
                    raise scs_errors.ScsToolError(f"Element '{element_name}' does not have at least two terminals for power calculation.")

                node1_name = el_obj.nets[0] # Name of the first net connected to the element
                node2_name = el_obj.nets[1] # Name of the second net connected to the element

                # Voltage across the element (node1 to node2)
                # The direction of current from i() method is from node1 to node2 for passive elements if defined that way.
                expr_v_el = self.top_instance.v(node1_name, node2_name)
                expr_i_el = self.top_instance.i(element_name) # Current through the element

                # Power = V * I. This assumes passive sign convention for P_absorbed.
                # If current from i() is defined from node1 to node2, and v() is v(node1,node2)
                # then P = v * i is power absorbed by the element.
                expr_p_el = expr_v_el * expr_i_el
                eq = sympy.Eq(expr_p_el, sym_val)

            else:
                raise ValueError(f"Unknown condition type: {condition['type']}")

            if eq is not None:
                # Substitute known fixed parameters into this equation before adding
                eq_substituted = eq.subs(subs_dict)
                equations.append(eq_substituted)

        if not equations:
            raise ValueError("No equations were formulated from the known conditions.")

        # Solve the system
        # sympy.solve returns a list of solutions or a dictionary
        solution = sympy.solve(equations, symbols_to_solve, dict=True)

        if solution:
             # If solution is a list of dicts, take the first one.
             # This happens when there are multiple solution sets.
            self.solved_symbolic_vars = solution[0] if isinstance(solution, list) else solution
            return self.solved_symbolic_vars
        else:
            # Try to solve by simplifying equations first if direct solve fails
            simplified_equations = [sympy.simplify(eq) for eq in equations]
            solution = sympy.solve(simplified_equations, symbols_to_solve, dict=True)
            if solution:
                self.solved_symbolic_vars = solution[0] if isinstance(solution, list) else solution
                return self.solved_symbolic_vars
            else:
                raise ValueError(f"Could not solve the system of equations: {equations} for {symbols_to_solve}")

    def get_element_power(self, element_name):
        '''
        Calculates the symbolic power dissipated or generated by a specified element.
        Assumes passive sign convention (power absorbed).

        Args:
            element_name (str): The name of the element.

        Returns:
            sympy.Expr: The symbolic expression for the power of the element.
                        This expression will have any solved variables (from previous calls
                        to solve_for_unknowns) substituted.
        '''
        self._parse_and_solve_base_circuit() # Ensure circuit is loaded and base solution exists

        el_obj = self.top_instance.elements.get(element_name)
        if not el_obj:
            raise scs_errors.ScsToolError(f"Element '{element_name}' not found in the circuit instance.")

        if len(el_obj.nets) < 2:
            raise scs_errors.ScsToolError(f"Element '{element_name}' does not have at least two terminals for power calculation.")

        node1_name = el_obj.nets[0]
        node2_name = el_obj.nets[1]

        expr_v_el = self.top_instance.v(node1_name, node2_name)
        expr_i_el = self.top_instance.i(element_name)

        power_expr = expr_v_el * expr_i_el

        # Substitute parameter definitions (e.g. R1_val -> 180, U_source_val -> U_sym)
        # self.top_instance.paramsd maps symbols like Symbol('R1_val') to their values (180 or Symbol('U_sym'))
        # The expressions from v() and i() are in terms of the keys of paramsd.
        # This step resolves defined parameters to their actual values or further symbols.
        if self.top_instance.paramsd:
             power_expr = power_expr.subs(self.top_instance.paramsd)

        # After the above, power_expr might be in terms of base symbols like U_sym, R3_sym.
        # Now, substitute the solved values for these symbols (if any).
        # self.solved_symbolic_vars maps Symbol('U_sym') or Symbol('R3_sym') to their solved numerical values.
        if self.solved_symbolic_vars:
            power_expr = power_expr.subs(self.solved_symbolic_vars)

        return power_expr

# Example Usage (for testing within this file, can be removed or commented out later)
if __name__ == '__main__':
    # This example assumes you have 'h_bridge.sp' in a relative path like '../examples/H_Bridge/h_bridge.sp'
    # Adjust the path as necessary for your test environment.
    # Create a dummy h_bridge.sp for testing if it doesn't exist or is not accessible here.
    # For the subtask, only the class definition is required.

    # solver_tool = SymbolicCircuitProblemSolver(netlist_path='examples/H_Bridge/h_bridge.sp') # Adjust path
    # known_conditions_example = [
    #    {'type': 'voltage', 'node1': 'N3', 'node2': '0', 'value': 0.1},
    #    {'type': 'current', 'element': 'R4', 'value': 559e-6} # Assuming R4 defined N2-N3, current N2->N3
    # ]
    # params_to_solve_example = ['R3_sym', 'U_sym']
    #
    # try:
    #    solution = solver_tool.solve_for_unknowns(known_conditions_example, params_to_solve_example)
    #    print("Solution:", solution)
    # except Exception as e:
    #    print("An error occurred:", e)
    pass
