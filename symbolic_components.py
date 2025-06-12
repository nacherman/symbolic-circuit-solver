# symbolic_components.py
import sympy as sp

# Global symbol for angular frequency
omega = sp.Symbol('omega', real=True, positive=True)

class BaseComponent:
    def __init__(self, name, node1, node2):
        if not isinstance(name, str): raise TypeError("Component name must be a string.")
        if not isinstance(node1, str) or not isinstance(node2, str): raise TypeError("Node names must be strings.")
        self.name = name; self.node1 = node1; self.node2 = node2
        self.values = {}; self.expressions = []
        self.V_comp = sp.Symbol(f"V_{self.name}"); self.P_comp = sp.Symbol(f"P_{self.name}") # P_comp can be complex power S for AC
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
            'impedance': self.R_val, # Z_R = R
            'current': self.I_comp,
            'voltage': self.V_comp,
            'power': self.P_comp
        })
        self.generate_expressions()
    def generate_expressions(self):
        # V = I * Z (where Z=R for resistor)
        self.expressions.extend([
            self.V_comp - self.I_comp * self.values['impedance'],
            self.P_comp - self.V_comp * self.I_comp # S = V * I (can be complex if V/I are complex)
        ])

# --- New AC Components ---
class Capacitor(BaseComponent):
    def __init__(self, name, node1, node2, capacitance_sym=None, current_sym=None):
        super().__init__(name, node1, node2)
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{self.name}")
        self.C_val = capacitance_sym if capacitance_sym else sp.Symbol(f"C_{self.name}")

        self.Z_C = 1 / (sp.I * omega * self.C_val)

        self.values.update({
            'capacitance': self.C_val,
            'impedance': self.Z_C,
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

class Inductor(BaseComponent):
    def __init__(self, name, node1, node2, inductance_sym=None, current_sym=None):
        super().__init__(name, node1, node2)
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{self.name}")
        self.L_val = inductance_sym if inductance_sym else sp.Symbol(f"L_{self.name}")
        self.Z_L = sp.I * omega * self.L_val

        self.values.update({
            'inductance': self.L_val,
            'impedance': self.Z_L,
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

# --- Existing Source Components (can now handle complex values for AC) ---
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
    def generate_expressions(self): # P_comp - V*I = 0
        self.expressions.append(self.P_comp - self.V_comp * self.I_comp)

# --- Existing Controlled Sources (can now handle complex values/gains for AC) ---
class VCVS(BaseComponent):
    def __init__(self, name, out_node1, out_node2, control_node_p, control_node_n, gain_sym=None, current_sym=None):
        super().__init__(name, out_node1, out_node2)
        if not (isinstance(control_node_p, str) and isinstance(control_node_n, str)): raise TypeError("Control node names for VCVS must be strings.")
        self.control_node_p_name = control_node_p; self.control_node_n_name = control_node_n
        self.V_control_p_sym = sp.Symbol(f"V_{control_node_p}"); self.V_control_n_sym = sp.Symbol(f"V_{control_node_n}")
        self.V_control_diff = self.V_control_p_sym - self.V_control_n_sym
        self.gain = gain_sym if gain_sym else sp.Symbol(f"Gain_{self.name}")
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{self.name}")
        self.values.update({'gain': self.gain, 'control_voltage_diff_expr': self.V_control_diff, 'output_voltage': self.V_comp, 'current': self.I_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([self.V_comp - self.gain * self.V_control_diff, self.P_comp - self.V_comp * self.I_comp])

class VCCS(BaseComponent):
    def __init__(self, name, out_node1, out_node2, control_node_p, control_node_n, transconductance_sym=None):
        super().__init__(name, out_node1, out_node2)
        if not (isinstance(control_node_p, str) and isinstance(control_node_n, str)): raise TypeError("Control node names for VCCS must be strings.")
        self.control_node_p_name = control_node_p; self.control_node_n_name = control_node_n
        self.V_control_p_sym = sp.Symbol(f"V_{control_node_p}"); self.V_control_n_sym = sp.Symbol(f"V_{control_node_n}")
        self.V_control_diff = self.V_control_p_sym - self.V_control_n_sym
        self.transconductance = transconductance_sym if transconductance_sym else sp.Symbol(f"Gm_{self.name}")
        self.I_comp = sp.Symbol(f"I_{self.name}")
        self.values.update({'transconductance': self.transconductance, 'control_voltage_diff_expr': self.V_control_diff, 'output_current': self.I_comp, 'voltage': self.V_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([self.I_comp - self.transconductance * self.V_control_diff, self.P_comp - self.V_comp * self.I_comp])

class CCVS(BaseComponent):
    def __init__(self, name, out_node1, out_node2, control_current_comp_name, transresistance_sym=None, current_sym=None):
        super().__init__(name, out_node1, out_node2)
        if not isinstance(control_current_comp_name, str): raise TypeError("Control current component name for CCVS must be a string.")
        self.control_current_comp_name = control_current_comp_name
        self.I_control_sym = sp.Symbol(f"I_{control_current_comp_name}")
        self.transresistance = transresistance_sym if transresistance_sym else sp.Symbol(f"Rm_{self.name}")
        self.I_comp = current_sym if current_sym else sp.Symbol(f"I_{self.name}")
        self.values.update({'transresistance': self.transresistance, 'control_current_sym': self.I_control_sym, 'output_voltage': self.V_comp, 'current': self.I_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([self.V_comp - self.transresistance * self.I_control_sym, self.P_comp - self.V_comp * self.I_comp])

class CCCS(BaseComponent):
    def __init__(self, name, out_node1, out_node2, control_current_comp_name, gain_sym=None):
        super().__init__(name, out_node1, out_node2)
        if not isinstance(control_current_comp_name, str): raise TypeError("Control current component name for CCCS must be a string.")
        self.control_current_comp_name = control_current_comp_name
        self.I_control_sym = sp.Symbol(f"I_{control_current_comp_name}")
        self.gain = gain_sym if gain_sym else sp.Symbol(f"Gain_{self.name}")
        self.I_comp = sp.Symbol(f"I_{self.name}")
        self.values.update({'gain': self.gain, 'control_current_sym': self.I_control_sym, 'output_current': self.I_comp, 'voltage': self.V_comp, 'power': self.P_comp})
        self.generate_expressions()
    def generate_expressions(self):
        self.expressions.extend([self.I_comp - self.gain * self.I_control_sym, self.P_comp - self.V_comp * self.I_comp])


if __name__ == '__main__':
    print("Symbolic Components Test (including AC components):")

    C_val_s, L_val_s = sp.symbols('C_val_s L_val_s')
    R_ac_s = sp.Symbol('R_ac_s')

    cap = Capacitor(name='C1', node1='n_ac1', node2='n_ac2', capacitance_sym=C_val_s)
    ind = Inductor(name='L1', node1='n_ac2', node2='n_ac_gnd', inductance_sym=L_val_s)
    res_ac = Resistor(name='Rac1', node1='n_ac1', node2='n_ac_gnd', resistance_sym=R_ac_s)

    ac_components = [cap, ind, res_ac]

    for comp in ac_components:
        print(f"\n--- {comp.name} ({comp.__class__.__name__}) ---")
        print(f"  Nodes: {comp.node1} -> {comp.node2}")
        print("  Values:")
        for key, val_sym in comp.values.items():
            # For impedance and other expressions, pretty print
            if key == 'impedance' or (hasattr(val_sym, 'free_symbols') and not isinstance(val_sym, sp.Symbol)):
                 print(f"    {key}: {sp.pretty(val_sym)}")
            else:
                print(f"    {key}: {val_sym}")
        print("  Expressions:")
        # Eq0: V_comp def; Eq1: V-IZ; Eq2: Power
        expected_descs = ["(V_comp def)", "(V-IZ eq)", "(Power eq)"]
        for i, expr in enumerate(comp.expressions):
            desc = expected_descs[i] if i < len(expected_descs) else ""
            print(f"    Eq{i} {desc}: {sp.pretty(expr)}")

    print(f"\nOmega symbol: {omega} (type: {type(omega)})")
    print(f"Imaginary unit I: {sp.I} (type: {type(sp.I)})")

    print(f"\n  Capacitor {cap.name} impedance Z_C (direct access): {sp.pretty(cap.values['impedance'])}")
    print(f"  Inductor {ind.name} impedance Z_L (direct access): {sp.pretty(ind.values['impedance'])}")
    print(f"  Resistor {res_ac.name} impedance Z_R (direct access): {sp.pretty(res_ac.values['impedance'])}")

    # --- Minimal test for existing components to ensure no breakage ---
    # print("\n--- Brief check of DC/Controlled components ---")
    # R_s, I_s_val_ctrl, Vs_val_s  = sp.symbols('R_s I_s_val_ctrl Vs_val_s')
    # Gain_F = sp.Symbol('Gain_F')
    # vs_main = VoltageSource(name='Vs_main_check', node1='n_vs_p_c', node2='GND', voltage_val_sym=Vs_val_s)
    # r_control_cccs = Resistor(name='Rctrl_check', node1='n_load_mid_c', node2='GND', current_sym=I_s_val_ctrl)
    # cccs1_check = CCCS(name='F1_check', out_node1='n_f_out_c', out_node2='GND', control_current_comp_name='Rctrl_check', gain_sym=Gain_F)
    # print(f"  {vs_main.name} V_comp: {vs_main.V_comp}, P_comp: {vs_main.P_comp}, Num Expr: {len(vs_main.expressions)}")
    # print(f"  {r_control_cccs.name} V_comp: {r_control_cccs.V_comp}, P_comp: {r_control_cccs.P_comp}, Num Expr: {len(r_control_cccs.expressions)}")
    # print(f"  {cccs1_check.name} V_comp: {cccs1_check.V_comp}, P_comp: {cccs1_check.P_comp}, Num Expr: {len(cccs1_check.expressions)}")
    # print(f"    CCCS control current symbol: {cccs1_check.I_control_sym}")
    # print(f"    CCCS output current symbol: {cccs1_check.I_comp}")
    # print(f"    CCCS gain value: {cccs1_check.values['gain']}")
    # print(f"    CCCS characteristic eq: {sp.pretty(cccs1_check.expressions[1])}")
