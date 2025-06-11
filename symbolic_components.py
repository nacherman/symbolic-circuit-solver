import sympy as sp

class BaseComponent:
    def __init__(self, name, node1, node2):
        if not isinstance(name, str):
            raise TypeError("Component name must be a string.")
        if not isinstance(node1, str) or not isinstance(node2, str):
            raise TypeError("Node names must be strings.")

        self.name = name
        self.node1 = node1
        self.node2 = node2
        self.values = {}  # To store symbolic values like R, V, I
        self.expressions = []  # To store symbolic equations

        # Define generic voltage and current symbols for the component itself
        # V_comp = V_node1 - V_node2
        # I_comp is current flowing from node1 to node2 through the component
        self.V_comp = sp.Symbol(f"V_{self.name}") # Voltage across the component
        # Individual components will define how I_comp relates to their specific current symbol

        # Placeholder for node voltage symbols - these will be resolved by the solver
        self.V_node1 = sp.Symbol(f"V_{self.node1}")
        self.V_node2 = sp.Symbol(f"V_{self.node2}")

        # Expression relating component voltage to node voltages
        # This is a fundamental definition: V_comp = V_node1 - V_node2
        # However, we must be careful if one of the nodes is ground (0V)
        # The solver will handle ground node substitution.
        self.expressions.append(self.V_comp - (self.V_node1 - self.V_node2))

    def generate_expressions(self):
        # This method should be overridden by subclasses
        # to add their specific characteristic equations.
        raise NotImplementedError("Subclasses must implement generate_expressions")

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}', node1='{self.node1}', node2='{self.node2}')"

class Resistor(BaseComponent):
    def __init__(self, name, node1, node2, resistance_sym=None, current_sym=None):
        super().__init__(name, node1, node2)

        # If symbols aren't provided, create them.
        # Current flows from node1 to node2
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{self.name}")
        self.R_val = resistance_sym if resistance_sym else sp.Symbol(f"R_{self.name}")

        self.values['resistance'] = self.R_val
        self.values['current'] = self.I_comp # This is I_R for the resistor
        self.values['voltage'] = self.V_comp # This is V_R for the resistor

        self.generate_expressions()

    def generate_expressions(self):
        # Ohm's Law: V_comp = I_comp * R_val
        # (V_node1 - V_node2) = I_R * R
        self.expressions.append(self.V_comp - self.I_comp * self.values['resistance'])

class VoltageSource(BaseComponent):
    def __init__(self, name, node1, node2, voltage_val_sym=None, current_sym=None):
        super().__init__(name, node1, node2) # node1 is positive, node2 is negative

        # If symbols aren't provided, create them.
        # current_sym is the current flowing out of the positive terminal (node1)
        # and into the negative terminal (node2)
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{self.name}")
        self.V_source_val = voltage_val_sym if voltage_val_sym else sp.Symbol(f"Val_{self.name}")

        self.values['voltage'] = self.V_source_val # The defined source voltage
        self.values['current'] = self.I_comp # Current supplied by the source
        # self.V_comp is the actual voltage across its terminals, which is constrained by V_source_val

        self.generate_expressions()

    def generate_expressions(self):
        # V_comp = V_source_val
        # (V_node1 - V_node2) = V_source_val
        self.expressions.append(self.V_comp - self.values['voltage'])
        # Note: The current I_comp for a voltage source is an unknown to be solved by the circuit context (KCL).

class CurrentSource(BaseComponent):
    def __init__(self, name, node1, node2, current_val_sym=None):
        super().__init__(name, node1, node2) # Current flows from node1 to node2

        # If symbol isn't provided, create it.
        self.I_source_val = current_val_sym if current_val_sym else sp.Symbol(f"Val_{self.name}")

        # For a current source, its characteristic current *is* I_comp
        self.I_comp = self.I_source_val

        self.values['current'] = self.I_source_val # The defined source current
        self.values['voltage'] = self.V_comp # Voltage across the source (unknown, solved by circuit context)

        self.generate_expressions()

    def generate_expressions(self):
        # The current source defines its current.
        # This means the I_comp (current from node1 to node2) is fixed to I_source_val.
        # This will be used in KCL equations.
        # No specific equation like V=IR, but its current is fixed.
        # The expression relating I_comp to I_source_val is implicitly handled
        # by setting self.I_comp = self.I_source_val.
        # The solver will use self.I_comp in KCL.
        pass # No additional equation needed here beyond V_comp = V_node1 - V_node2

if __name__ == '__main__':
    # Example Usage and Test
    print("Symbolic Components Test:")

    # Define some symbols for testing
    R1_sym, R2_sym = sp.symbols('R1 R2')
    I1_sym, I2_sym = sp.symbols('I1 I2')
    V1_sym = sp.Symbol('V1_val')
    Is_sym = sp.Symbol('Is_val')

    # Create components
    resistor1 = Resistor(name='R1', node1='n1', node2='n2', resistance_sym=R1_sym, current_sym=I1_sym)
    voltage_source1 = VoltageSource(name='VS1', node1='n1', node2='GND', voltage_val_sym=V1_sym)
    current_source1 = CurrentSource(name='CS1', node1='n2', node2='GND', current_val_sym=Is_sym)
    resistor2 = Resistor(name='R2', node1='n2', node2='GND', resistance_sym=R2_sym) # Auto-generate current symbol

    components = [resistor1, voltage_source1, current_source1, resistor2]

    for comp in components:
        print(f"\n--- {comp.name} ({comp.__class__.__name__}) ---")
        print(f"  Nodes: {comp.node1} -> {comp.node2}")
        print(f"  V_comp symbol: {comp.V_comp}")
        print(f"  I_comp symbol: {comp.I_comp if hasattr(comp, 'I_comp') else 'N/A (CS defines it directly)'}")
        print(f"  Node1 Voltage Symbol: {comp.V_node1}")
        print(f"  Node2 Voltage Symbol: {comp.V_node2}")
        print("  Values:")
        for key, val_sym in comp.values.items():
            print(f"    {key}: {val_sym}")
        print("  Expressions:")
        for expr in comp.expressions:
            print(f"    {sp.pretty(expr)}")

    print("\nExpected V_R2 symbol:", resistor2.values['current']) # Should be I_R2
    print("Expected R_R2 symbol:", resistor2.values['resistance']) # Should be R_R2

    # Test V_comp = V_node1 - V_node2 expressions
    print("\nChecking V_comp definitions:")
    # For R1: V_R1 - (V_n1 - V_n2) = 0
    # For VS1: V_VS1 - (V_n1 - V_GND) = 0
    # For CS1: V_CS1 - (V_n2 - V_GND) = 0
    # For R2: V_R2 - (V_n2 - V_GND) = 0
    for comp in components:
        print(f"  {comp.name}: {sp.pretty(comp.expressions[0])}")

    print("\nChecking specific component equations:")
    # For R1: V_R1 - I_R1*R1 = 0
    print(f"  {resistor1.name}: {sp.pretty(resistor1.expressions[1])}")
    # For VS1: V_VS1 - V1_val = 0
    print(f"  {voltage_source1.name}: {sp.pretty(voltage_source1.expressions[1])}")
    # For CS1: (no specific equation other than V_CS1 = V_n2 - V_GND and its current being Is_val)
    print(f"  {current_source1.name} expressions count: {len(current_source1.expressions)}") # Should be 1
    # For R2: V_R2 - I_R2*R_R2 = 0
    print(f"  {resistor2.name}: {sp.pretty(resistor2.expressions[1])}")
