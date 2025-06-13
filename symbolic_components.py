# symbolic_components.py
import sympy as sp

# Global symbol for Laplace variable
s_sym = sp.Symbol('s')

class BaseComponent:
    def __init__(self, name, node1, node2):
        if not isinstance(name, str): raise TypeError("Component name must be a string.")
        if not isinstance(node1, str) or not isinstance(node2, str): raise TypeError("Node names must be strings.")
        self.name = name; self.node1 = node1; self.node2 = node2
        self.values = {}; self.expressions = []
        self.V_comp = sp.Symbol(f"V_{self.name}"); self.P_comp = sp.Symbol(f"P_{self.name}")
        self.V_node1 = sp.Symbol(f"V_{self.node1}"); self.V_node2 = sp.Symbol(f"V_{self.node2}")
        self.expressions.append(self.V_comp - (self.V_node1 - self.V_node2))
    def generate_expressions(self): raise NotImplementedError("Subclasses must implement generate_expressions")
    def __repr__(self): return f"{self.__class__.__name__}(name='{self.name}', node1='{self.node1}', node2='{self.node2}')"

class Resistor(BaseComponent):
    def __init__(self, name, node1, node2, resistance_sym=None, current_sym=None):
        super().__init__(name, node1, node2)
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{self.name}")
        self.R_val = resistance_sym if resistance_sym else sp.Symbol(f"R_{self.name}")
        self.values.update({
            'resistance': self.R_val,
            'impedance': self.R_val,
            'current': self.I_comp,
            'voltage': self.V_comp,
            'power': self.P_comp
        })
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([
            self.V_comp - self.I_comp * self.values['impedance'],
            self.P_comp - self.V_comp * self.I_comp
        ])

class Capacitor(BaseComponent):
    def __init__(self, name, node1, node2, capacitance_sym=None, current_sym=None):
        super().__init__(name, node1, node2)
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{self.name}")
        self.C_val = capacitance_sym if capacitance_sym else sp.Symbol(f"C_{self.name}")
        self.Z_C = 1 / (s_sym * self.C_val)
        self.values.update({
            'capacitance': self.C_val, 'impedance': self.Z_C,
            'current': self.I_comp, 'voltage': self.V_comp, 'power': self.P_comp
        })
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([
            self.V_comp - self.I_comp * self.values['impedance'],
            self.P_comp - self.V_comp * self.I_comp
        ])

class Inductor(BaseComponent):
    def __init__(self, name, node1, node2, inductance_sym=None, current_sym=None):
        super().__init__(name, node1, node2)
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{self.name}")
        self.L_val = inductance_sym if inductance_sym else sp.Symbol(f"L_{self.name}")
        self.Z_L = s_sym * self.L_val
        self.values.update({
            'inductance': self.L_val, 'impedance': self.Z_L,
            'current': self.I_comp, 'voltage': self.V_comp, 'power': self.P_comp
        })
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([
            self.V_comp - self.I_comp * self.values['impedance'],
            self.P_comp - self.V_comp * self.I_comp
        ])

class VoltageSource(BaseComponent):
    def __init__(self, name, node1, node2, voltage_val_sym=None, current_sym=None):
        super().__init__(name, node1, node2)
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{self.name}")
        self.V_source_val = voltage_val_sym if voltage_val_sym else sp.Symbol(f"Val_{self.name}")
        self.values.update({'voltage': self.V_source_val, 'current': self.I_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([self.V_comp - self.values['voltage'], self.P_comp - self.V_comp * self.I_comp])

class CurrentSource(BaseComponent):
    def __init__(self, name, node1, node2, current_val_sym=None):
        super().__init__(name, node1, node2)
        self.I_source_val = current_val_sym if current_val_sym else sp.Symbol(f"Val_{self.name}")
        self.I_comp = self.I_source_val
        self.values.update({'current': self.I_source_val, 'voltage': self.V_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.append(self.P_comp - self.V_comp * self.I_comp)

class VCVS(BaseComponent): # Voltage Controlled Voltage Source
    def __init__(self, name, out_node1, out_node2, control_node_p, control_node_n, gain_sym=None, current_sym=None):
        super().__init__(name, out_node1, out_node2)
        if not (isinstance(control_node_p, str) and isinstance(control_node_n, str)): raise TypeError("Control node names for VCVS must be strings.")
        self.control_node_p_name = control_node_p; self.control_node_n_name = control_node_n
        self.V_control_p_sym = sp.Symbol(f"V_{control_node_p}"); self.V_control_n_sym = sp.Symbol(f"V_{control_node_n}")
        self.V_control_diff = self.V_control_p_sym - self.V_control_n_sym
        self.gain = gain_sym if gain_sym else sp.Symbol(f"Gain_{name}")
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{name}") # Current flowing through the source
        self.values.update({'gain': self.gain, 'control_voltage_diff_expr': self.V_control_diff, 'output_voltage': self.V_comp, 'current': self.I_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([self.V_comp - self.gain * self.V_control_diff, self.P_comp - self.V_comp * self.I_comp])

class VCCS(BaseComponent): # Voltage Controlled Current Source
    def __init__(self, name, out_node1, out_node2, control_node_p, control_node_n, transconductance_sym=None):
        super().__init__(name, out_node1, out_node2)
        if not (isinstance(control_node_p, str) and isinstance(control_node_n, str)): raise TypeError("Control node names for VCCS must be strings.")
        self.control_node_p_name = control_node_p; self.control_node_n_name = control_node_n
        self.V_control_p_sym = sp.Symbol(f"V_{control_node_p}"); self.V_control_n_sym = sp.Symbol(f"V_{control_node_n}")
        self.V_control_diff = self.V_control_p_sym - self.V_control_n_sym
        self.transconductance = transconductance_sym if transconductance_sym else sp.Symbol(f"Gm_{name}")
        self.I_comp = sp.Symbol(f"I_{name}") # Output current of the VCCS
        self.values.update({'transconductance': self.transconductance, 'control_voltage_diff_expr': self.V_control_diff, 'output_current': self.I_comp, 'voltage': self.V_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([self.I_comp - self.transconductance * self.V_control_diff, self.P_comp - self.V_comp * self.I_comp])

class CCVS(BaseComponent): # Current Controlled Voltage Source
    def __init__(self, name, out_node1, out_node2, control_current_comp_name, transresistance_sym=None, current_sym=None):
        super().__init__(name, out_node1, out_node2)
        if not isinstance(control_current_comp_name, str): raise TypeError("Control current component name for CCVS must be a string.")
        self.control_current_comp_name = control_current_comp_name
        # The actual I_comp of the controlling component will be used by the solver.
        # This symbol is for defining the relationship.
        self.I_control_sym = sp.Symbol(f"I_{control_current_comp_name}")
        self.transresistance = transresistance_sym if transresistance_sym else sp.Symbol(f"Rm_{name}")
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{name}") # Current flowing through the source
        self.values.update({'transresistance': self.transresistance, 'control_current_sym': self.I_control_sym, 'output_voltage': self.V_comp, 'current': self.I_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([self.V_comp - self.transresistance * self.I_control_sym, self.P_comp - self.V_comp * self.I_comp])

class CCCS(BaseComponent): # Current Controlled Current Source
    def __init__(self, name, out_node1, out_node2, control_current_comp_name, gain_sym=None):
        super().__init__(name, out_node1, out_node2)
        if not isinstance(control_current_comp_name, str): raise TypeError("Control current component name for CCCS must be a string.")
        self.control_current_comp_name = control_current_comp_name
        self.I_control_sym = sp.Symbol(f"I_{control_current_comp_name}")
        self.gain = gain_sym if gain_sym else sp.Symbol(f"Gain_{name}")
        self.I_comp = sp.Symbol(f"I_{name}") # Output current of the CCCS
        self.values.update({'gain': self.gain, 'control_current_sym': self.I_control_sym, 'output_current': self.I_comp, 'voltage': self.V_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([self.I_comp - self.gain * self.I_control_sym, self.P_comp - self.V_comp * self.I_comp])

if __name__ == '__main__':
    print("Symbolic Components Test (s-domain AC, Power, All Controlled Sources):")

    # Test symbols
    R_s, C_s_val, L_s_val = sp.symbols('R_s C_s_val L_s_val')
    Vs_val_s, Is_val_s = sp.symbols('Vs_val_s Is_val_s')
    I_ctrl_sym_main = sp.Symbol('I_R_control_current') # Explicit symbol for controlling current

    Gain_E, Gm_G, Rm_H, Gain_F = sp.symbols('Gain_E Gm_G Rm_H Gain_F')

    # Basic passive components
    res1 = Resistor(name='R1', node1='n1', node2='n2', resistance_sym=R_s)
    cap1 = Capacitor(name='C1', node1='n2', node2='0', capacitance_sym=C_s_val)
    ind1 = Inductor(name='L1', node1='n1', node2='n_l_out', inductance_sym=L_s_val)

    # Independent sources
    volt_src1 = VoltageSource(name='Vs1', node1='n_vs_in', node2='0', voltage_val_sym=Vs_val_s)
    curr_src1 = CurrentSource(name='Is1', node1='n_is_in', node2='0', current_val_sym=Is_val_s)

    # Component providing a controlling current
    # For CCVS/CCCS, the solver will need to identify Rcontrol.I_comp as I_Rcontrol
    r_control = Resistor(name='Rcontrol', node1='n_vs_in', node2='n1', resistance_sym=sp.Symbol('R_ctrl_val'), current_sym=I_ctrl_sym_main)

    # Controlled sources
    vcvs1 = VCVS(name='E1', out_node1='n_e_o', out_node2='0', control_node_p='n1', control_node_n='n2', gain_sym=Gain_E)
    vccs1 = VCCS(name='G1', out_node1='n_g_o', out_node2='0', control_node_p='n1', control_node_n='n2', transconductance_sym=Gm_G)
    # For CCVS/CCCS, control_current_comp_name is 'Rcontrol'. The solver will need to map this to r_control.I_comp
    ccvs1 = CCVS(name='H1', out_node1='n_h_o', out_node2='0', control_current_comp_name='Rcontrol', transresistance_sym=Rm_H)
    cccs1 = CCCS(name='F1', out_node1='n_f_o', out_node2='0', control_current_comp_name='Rcontrol', gain_sym=Gain_F)

    all_my_components = [res1, cap1, ind1, volt_src1, curr_src1, r_control, vcvs1, vccs1, ccvs1, cccs1]
    print(f"Global Laplace variable s: {s_sym}")

    for comp in all_my_components:
        print(f"\n--- {comp.name} ({comp.__class__.__name__}) ---")
        print(f"  Output Nodes: {comp.node1} -> {comp.node2}")
        if isinstance(comp, (VCVS, VCCS)):
            print(f"  Control Nodes (V): {comp.control_node_p_name} -> {comp.control_node_n_name}")
            print(f"  Control Voltage Expr: {sp.pretty(comp.V_control_diff)}")
        if isinstance(comp, (CCVS, CCCS)):
            print(f"  Control Current Component Name: {comp.control_current_comp_name}")
            print(f"  Control Current Symbol Used by Source: {comp.I_control_sym}") # This is I_Rcontrol

        print("  Values:")
        for key, val in comp.values.items():
            # Pretty print if it's a Sympy expression and not just an Atom (like a single symbol)
            val_str = sp.pretty(val) if isinstance(val, sp.Expr) and not val.is_Atom else str(val)
            print(f"    {key}: {val_str}")
        print("  Expressions (first 3):") # Print up to 3 expressions
        for i, expr in enumerate(comp.expressions[:3]):
            print(f"    Eq{i}: {sp.pretty(expr)}")

    # Verification for CCVS/CCCS I_control_sym linkage
    # The I_control_sym in CCVS/CCCS (e.g., I_Rcontrol) should be the symbol for current
    # that the solver will identify as r_control.I_comp.
    print(f"\nVerification: Rcontrol's I_comp symbol is {r_control.I_comp} (this is {I_ctrl_sym_main})")
    print(f"CCVS H1 uses I_control_sym: {ccvs1.I_control_sym} (should match I_Rcontrol for solver linking)")
    print(f"CCCS F1 uses I_control_sym: {cccs1.I_control_sym} (should match I_Rcontrol for solver linking)")

    # Check that the I_control_sym created by CCVS/CCCS matches the I_comp of the named component
    # For this test, we manually provided I_ctrl_sym_main to Rcontrol.
    # So, I_Rcontrol (from CCVS/CCCS) should be different from I_ctrl_sym_main if not linked by solver.
    # The solver's job is to equate I_Rcontrol from the H/F source with the actual I_comp of Rcontrol.
    # The test here just confirms the symbol naming convention.
    assert ccvs1.I_control_sym == sp.Symbol(f"I_{ccvs1.control_current_comp_name}")
    assert cccs1.I_control_sym == sp.Symbol(f"I_{cccs1.control_current_comp_name}")
    # And that this is NOT the same object as r_control.I_comp unless it was passed in,
    # but it IS the same symbol name that the solver will look for.
    print("CCVS/CCCS I_control_sym naming convention is correct.")
    if ccvs1.I_control_sym == r_control.I_comp:
        print("Note: CCVS I_control_sym matches Rcontrol.I_comp directly because I_Rcontrol was used in test setup.")
    else:
        # This case would happen if Rcontrol auto-generated its current I_Rcontrol, and CCVS also auto-generated I_Rcontrol.
        # They would be different sp.Symbol objects but with the same string name.
        print(f"Note: CCVS I_control_sym ('{ccvs1.I_control_sym}') and Rcontrol.I_comp ('{r_control.I_comp}') are different objects but may have the same string representation. Solver handles the link.")

    # Test expression counts
    assert len(res1.expressions) == 3 # Vdef, V=IZ, P=VI
    assert len(cap1.expressions) == 3 # Vdef, V=IZ, P=VI
    assert len(ind1.expressions) == 3 # Vdef, V=IZ, P=VI
    assert len(volt_src1.expressions) == 3 # Vdef, V=Val, P=VI
    assert len(curr_src1.expressions) == 2 # Vdef, P=VI (I=Val is implicit in I_comp)
    assert len(vcvs1.expressions) == 3 # Vdef, Vout=Gain*Vin, P=VI
    assert len(vccs1.expressions) == 3 # Vdef, Iout=Gm*Vin, P=VI
    assert len(ccvs1.expressions) == 3 # Vdef, Vout=Rm*Iin, P=VI
    assert len(cccs1.expressions) == 3 # Vdef, Iout=Gain*Iin, P=VI
    print("Expression counts are correct.")

    # Test specific impedance/characteristic equations
    # The expression is already in the form f(variables) = 0, e.g., V_R1 - I_R1*R_s
    print(f"Resistor R1 impedance relation: {sp.pretty(res1.expressions[1])}")
    # Expected for C1: V_C1 - I_C1 * (1/(s*C_s_val))
    # Actual: V_C1 - I_C1 / (C_s_val*s)
    print(f"Capacitor C1 impedance relation: {sp.pretty(cap1.expressions[1])}")
    # Expected for L1: V_L1 - I_L1 * (s*L_s_val)
    print(f"Inductor L1 impedance relation: {sp.pretty(ind1.expressions[1])}")

    print("\nAll basic tests in __main__ passed.")
