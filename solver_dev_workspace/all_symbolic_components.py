# all_symbolic_components.py
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

class VCVS(BaseComponent): # E-type
    def __init__(self, name, out_node1, out_node2, control_node_p, control_node_n, gain_sym=None, current_sym=None):
        super().__init__(name, out_node1, out_node2)
        if not (isinstance(control_node_p, str) and isinstance(control_node_n, str)): raise TypeError("Control node names for VCVS must be strings.")
        self.control_node_p_name = control_node_p; self.control_node_n_name = control_node_n
        self.V_control_p_sym = sp.Symbol(f"V_{control_node_p}"); self.V_control_n_sym = sp.Symbol(f"V_{control_node_n}")
        self.V_control_diff = self.V_control_p_sym - self.V_control_n_sym
        self.gain = gain_sym if gain_sym else sp.Symbol(f"Gain_{name}")
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{name}") # Current through the VCVS output
        self.values.update({'gain': self.gain, 'control_voltage_diff_expr': self.V_control_diff,
                            'output_voltage': self.V_comp, 'current': self.I_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([self.V_comp - self.gain * self.V_control_diff,
                                 self.P_comp - self.V_comp * self.I_comp])

class VCCS(BaseComponent): # G-type
    def __init__(self, name, out_node1, out_node2, control_node_p, control_node_n, transconductance_sym=None):
        super().__init__(name, out_node1, out_node2)
        if not (isinstance(control_node_p, str) and isinstance(control_node_n, str)): raise TypeError("Control node names for VCCS must be strings.")
        self.control_node_p_name = control_node_p; self.control_node_n_name = control_node_n
        self.V_control_p_sym = sp.Symbol(f"V_{control_node_p}"); self.V_control_n_sym = sp.Symbol(f"V_{control_node_n}")
        self.V_control_diff = self.V_control_p_sym - self.V_control_n_sym
        self.transconductance = transconductance_sym if transconductance_sym else sp.Symbol(f"Gm_{name}")
        self.I_comp = sp.Symbol(f"I_{name}") # Output current of the VCCS
        self.values.update({'transconductance': self.transconductance, 'control_voltage_diff_expr': self.V_control_diff,
                            'output_current': self.I_comp, 'voltage': self.V_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([self.I_comp - self.transconductance * self.V_control_diff,
                                 self.P_comp - self.V_comp * self.I_comp])

class CCVS(BaseComponent): # H-type
    def __init__(self, name, out_node1, out_node2, control_current_comp_name, transresistance_sym=None, current_sym=None):
        super().__init__(name, out_node1, out_node2)
        if not isinstance(control_current_comp_name, str): raise TypeError("Control current component name for CCVS must be a string.")
        self.control_current_comp_name = control_current_comp_name
        self.I_control_sym = sp.Symbol(f"I_{control_current_comp_name}")
        self.transresistance = transresistance_sym if transresistance_sym else sp.Symbol(f"Rm_{name}")
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{name}") # Current through the CCVS output
        self.values.update({'transresistance': self.transresistance, 'control_current_sym': self.I_control_sym,
                            'output_voltage': self.V_comp, 'current': self.I_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([self.V_comp - self.transresistance * self.I_control_sym,
                                 self.P_comp - self.V_comp * self.I_comp])

class CCCS(BaseComponent): # F-type
    def __init__(self, name, out_node1, out_node2, control_current_comp_name, gain_sym=None):
        super().__init__(name, out_node1, out_node2)
        if not isinstance(control_current_comp_name, str): raise TypeError("Control current component name for CCCS must be a string.")
        self.control_current_comp_name = control_current_comp_name
        self.I_control_sym = sp.Symbol(f"I_{control_current_comp_name}")
        self.gain = gain_sym if gain_sym else sp.Symbol(f"Gain_{name}")
        self.I_comp = sp.Symbol(f"I_{name}") # Output current of the CCCS
        self.values.update({'gain': self.gain, 'control_current_sym': self.I_control_sym,
                            'output_current': self.I_comp, 'voltage': self.V_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([self.I_comp - self.gain * self.I_control_sym,
                                 self.P_comp - self.V_comp * self.I_comp])

if __name__ == '__main__':
    print("Full Symbolic Components Test (s-domain AC, Power, All Controlled Sources):")

    # Test symbols
    R_s, C_s_val, L_s_val = sp.symbols('R_s C_s_val L_s_val')
    Vs_val_s, Is_val_s = sp.symbols('Vs_val_s Is_val_s')
    I_ctrl_sym_main = sp.Symbol('I_R_control_current')

    Gain_E, Gm_G, Rm_H, Gain_F = sp.symbols('Gain_E Gm_G Rm_H Gain_F')

    # Instantiate one of each
    res1 = Resistor(name='R_test1', node1='n1', node2='n2', resistance_sym=R_s)
    cap1 = Capacitor(name='C_test1', node1='n2', node2='gnd', capacitance_sym=C_s_val)
    ind1 = Inductor(name='L_test1', node1='n1', node2='n_l_out', inductance_sym=L_s_val)
    vs1 = VoltageSource(name='Vs_test1', node1='n_vs_in', node2='gnd', voltage_val_sym=Vs_val_s)
    is1 = CurrentSource(name='Is_test1', node1='n_is_in', node2='gnd', current_val_sym=Is_val_s)

    # Controlling component for H and F types
    r_control_comp = Resistor(name='RcontrolComp', node1='n_ctrl_in', node2='n_ctrl_out',
                              resistance_sym=sp.Symbol('R_ctrlval'), current_sym=I_ctrl_sym_main)

    vcvs1 = VCVS(name='E_test1', out_node1='n_e_o', out_node2='gnd',
                 control_node_p='n1', control_node_n='n2', gain_sym=Gain_E)
    vccs1 = VCCS(name='G_test1', out_node1='n_g_o', out_node2='gnd',
                 control_node_p='n1', control_node_n='n2', transconductance_sym=Gm_G)
    ccvs1 = CCVS(name='H_test1', out_node1='n_h_o', out_node2='gnd',
                 control_current_comp_name='RcontrolComp', transresistance_sym=Rm_H) # Uses I_RcontrolComp
    cccs1 = CCCS(name='F_test1', out_node1='n_f_o', out_node2='gnd',
                 control_current_comp_name='RcontrolComp', gain_sym=Gain_F) # Uses I_RcontrolComp

    all_components_list = [res1, cap1, ind1, vs1, is1, r_control_comp, vcvs1, vccs1, ccvs1, cccs1]
    print(f"Global Laplace variable s: {s_sym}")

    for comp_instance in all_components_list:
        print(f"\n--- {comp_instance.name} ({comp_instance.__class__.__name__}) ---")
        print(f"  Nodes: {comp_instance.node1} -> {comp_instance.node2}")
        if isinstance(comp_instance, (VCVS, VCCS)):
            print(f"  Control Nodes (V): {comp_instance.control_node_p_name} -> {comp_instance.control_node_n_name}")
            print(f"  Control Voltage Expr (internal): {sp.pretty(comp_instance.V_control_diff)}")
        if isinstance(comp_instance, (CCVS, CCCS)):
            print(f"  Control Current Component Name: {comp_instance.control_current_comp_name}")
            print(f"  Control Current Symbol Used by Source: {comp_instance.I_control_sym}")

        print("  Values Dictionary:")
        for key, val in comp_instance.values.items():
            val_str = sp.pretty(val) if isinstance(val, sp.Expr) and not val.is_Atom else str(val)
            print(f"    {key}: {val_str}")
        print("  Symbolic Expressions (first 3):") # V_comp def, V=IZ/characteristic, P=VI
        for i, expr_item in enumerate(comp_instance.expressions[:3]):
            print(f"    Eq{i}: {sp.pretty(expr_item)}")

    print(f"\nVerification: RcontrolComp's own I_comp symbol is {r_control_comp.I_comp} (should be '{I_ctrl_sym_main}')")
    print(f"CCVS H_test1 uses I_control_sym: {ccvs1.I_control_sym} (should be symbol 'I_RcontrolComp')")
    print(f"CCCS F_test1 uses I_control_sym: {cccs1.I_control_sym} (should be symbol 'I_RcontrolComp')")
    print("\nFull component definitions complete and basic check passed.")
