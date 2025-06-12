# utils.py
import sympy as sp
from sympy import simplify, Abs, arg, im, re, deg, N # Explicit imports

def format_symbolic_expression(expr):
    if expr is None: return "None"
    try:
        # Using simplify with rational=True can sometimes make expressions more standard
        # For pretty printing, the default simplify might be fine.
        return sp.pretty(simplify(expr))
    except Exception:
        return sp.pretty(expr)

def print_solutions(solution_list, title="Solution"):
    print(f"\n--- {title} ---")
    if not solution_list:
        print("  No solution found or an error occurred in the solver.")
        return
    if isinstance(solution_list, list) and not any(s for s in solution_list if s):
        print("  No specific solution values found.")
        return
    if not isinstance(solution_list, list):
        print(f"  Unexpected solution format: {solution_list}")
        return

    for i, sol_dict in enumerate(solution_list):
        if not sol_dict:
            print(f"  Solution Set {i+1} is empty.")
            continue
        print(f"  Solution Set {i+1}:")
        try:
            # Sort items by symbol name (converted to string) for consistent output
            sorted_items = sorted(sol_dict.items(), key=lambda item: str(item[0]))
        except Exception: # Fallback if sorting fails
            sorted_items = sol_dict.items()

        for sym, val in sorted_items:
            val_str = ""
            is_multiline_for_print = False
            rest_lines_for_print = []

            processed_as_numerical = False
            # Handle Python native numbers first
            if isinstance(val, (int, float)):
                if abs(val - round(val)) < 1e-9 and isinstance(val, float):
                    val_str = f"{int(round(val))}"
                elif isinstance(val, int):
                     val_str = f"{val}"
                else:
                    val_str = f"{val:.6g}" # Use .6g for general float formatting
                processed_as_numerical = True
            elif hasattr(val, 'evalf'): # For Sympy objects
                try:
                    num_val_evalf = val.evalf(n=15, chop=True)

                    if not num_val_evalf.free_symbols: # Check if it's a concrete numerical expression
                        real_part_val = re(num_val_evalf)
                        imag_part_val = im(num_val_evalf)

                        real_check_tolerance = 1e-12
                        imag_part_as_float = float(imag_part_val.evalf(n=15))

                        if abs(imag_part_as_float) < real_check_tolerance:
                            f_val = float(real_part_val)
                            if abs(f_val - round(f_val)) < 1e-9:
                                val_str = f"{int(round(f_val))}"
                            else:
                                val_str = f"{f_val:.6g}"
                            processed_as_numerical = True
                        else:
                            rp_str = f"{float(real_part_val):.4g}" # Use .4g for parts of complex num
                            ip_val_float = float(imag_part_val)

                            if ip_val_float >= 0:
                                val_str = f"{rp_str} + {ip_val_float:.4g}j"
                            else:
                                val_str = f"{rp_str} - {abs(ip_val_float):.4g}j"

                            magnitude = Abs(num_val_evalf)
                            phase_deg_val = deg(arg(num_val_evalf))
                            val_str += f"  (Polar: {float(magnitude):.4g} ∠ {float(phase_deg_val):.2f}°)"
                            processed_as_numerical = True
                except Exception:
                    processed_as_numerical = False

            if not processed_as_numerical:
                pretty_expr = format_symbolic_expression(val)
                lines = pretty_expr.split('\n')
                val_str = lines[0]
                if len(lines) > 1:
                    is_multiline_for_print = True
                    rest_lines_for_print = lines[1:]

            # Use a consistent padding for the symbol string part
            symbol_str_padded = f"{str(sym):<28}" # Increased padding
            print(f"    {symbol_str_padded} = {val_str}")
            if is_multiline_for_print:
                for line_content in rest_lines_for_print:
                    print(f"    {'':<28}   {line_content}") # Ensure alignment


# --- New Node Map Utility ---
def generate_node_map_text(components_list):
    """
    Generates a text-based node map showing component connections.
    Args:
        components_list: A list of component instances.
    Returns:
        A string representing the formatted node map.
    """
    if not components_list:
        return "Node Map:\n  No components provided."

    node_connections = {}
    all_nodes = set()

    for comp in components_list:
        if not (hasattr(comp, 'name') and hasattr(comp, 'node1') and hasattr(comp, 'node2') and hasattr(comp, '__class__')):
            print(f"Warning: Skipping component {comp} as it lacks required attributes (name, node1, node2, __class__).")
            continue

        all_nodes.add(comp.node1)
        all_nodes.add(comp.node2)

        # Connection to node1
        if comp.node1 not in node_connections:
            node_connections[comp.node1] = []
        node_connections[comp.node1].append(f"{comp.name} ({comp.__class__.__name__}) -- {comp.node2}")

        # Connection to node2 (avoid duplicating for self-loops immediately)
        if comp.node1 != comp.node2 : # Avoid double listing for self-loops here
            if comp.node2 not in node_connections:
                node_connections[comp.node2] = []
            node_connections[comp.node2].append(f"{comp.name} ({comp.__class__.__name__}) -- {comp.node1}")
        elif comp.node1 == comp.node2 and f"{comp.name} ({comp.__class__.__name__}) -- {comp.node1}" not in node_connections[comp.node1]:
            # For self-loops, ensure it's listed once under the node
             node_connections[comp.node1].append(f"{comp.name} ({comp.__class__.__name__}) -- {comp.node1} (self-loop)")


    output_lines = ["Node Map:"]
    if not all_nodes:
        output_lines.append("  No nodes found in components.")
        return "\n".join(output_lines)

    # Sort nodes: GND first (if present), then numerically/alphanumerically
    # Ensure node names are strings for sorting, especially if they are numbers like '0'
    sorted_nodes = sorted(list(all_nodes), key=lambda x: (str(x).upper() != 'GND', str(x).lower()))


    for node_name in sorted_nodes:
        output_lines.append(f"Node '{node_name}':") # Add quotes for clarity, esp for node '0'
        if node_name in node_connections and node_connections[node_name]:
            # Sort connections for consistency under each node
            for connection_info in sorted(node_connections[node_name]):
                output_lines.append(f"  - {connection_info}")
        else:
            # This case should ideally not be hit if all_nodes is derived from components with connections
            output_lines.append("  - (No connections listed in map; node might be isolated or only in self-loops if not listed above)")

    return "\n".join(output_lines)


if __name__ == '__main__':
    # Existing tests for print_solutions (condensed for brevity)
    s_x, s_y, s_z, s_c1, s_c2 = sp.symbols('s_x s_y s_z s_c1 s_c2')
    print("Testing print_solutions (summary):")
    example_sol_ac = [{ s_c1: 3 + 4*sp.I, sp.Symbol('formula'): (s_x**2-1)/(s_x-1) + s_y*(s_z+1)-s_y*s_z }]
    print_solutions(example_sol_ac, title="AC & Symbolic Test")
    example_sol_real = [{s_x: 10, s_y: sp.Rational(1,2), sp.Symbol('almost_real'): 1.0 + 1e-15*sp.I}]
    print_solutions(example_sol_real, title="Real & Near-Real Test")


    print("\n--- Testing generate_node_map_text ---")

    # Mock components for testing node map
    class MockComponentUtil: # Renamed to avoid conflict if symbolic_components.BaseComponent is imported
        def __init__(self, name, node1, node2, class_name_str="MockComp"):
            self.name = name
            self.node1 = node1
            self.node2 = node2
            self._class_name_str = class_name_str # Store the desired class name

        @property
        def __class__(self):
            # Mock the __class__ attribute to return an object that has a __name__
            class MockClass:
                pass
            MockClass.__name__ = self._class_name_str
            return MockClass

    mock_r1 = MockComponentUtil("R1", "N1", "N2", "Resistor")
    mock_vs = MockComponentUtil("VS1", "N1", "GND", "VoltageSource")
    mock_c1 = MockComponentUtil("C1", "N2", "GND", "Capacitor")
    # Test a component connecting to numeric node '0' which is different from 'GND'
    mock_l1 = MockComponentUtil("L1", "N2", "0", "Inductor")
    mock_r2 = MockComponentUtil("R2", "N1", "N2", "Resistor") # Another R1||R2 like component

    test_components = [mock_r1, mock_vs, mock_c1, mock_l1, mock_r2]
    node_map_output = generate_node_map_text(test_components)
    print(node_map_output)

    print("\nTest with empty component list:")
    print(generate_node_map_text([]))

    print("\nTest with component connecting a node to itself (self-loop):")
    mock_loop = MockComponentUtil("Loop1", "N_Loop", "N_Loop", "Looper")
    print(generate_node_map_text([mock_loop]))

    print("\nTest with disconnected components:")
    mock_d1 = MockComponentUtil("D1", "nA", "nB", "Diode")
    mock_d2 = MockComponentUtil("D2", "nC", "nD", "Diode")
    print(generate_node_map_text([mock_d1, mock_d2]))
