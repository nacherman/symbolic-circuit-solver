"""
Elements classes and their functions
"""

import sympy
import sympy.abc
from . import scs_errors
# No 'from . import scs_parser' due to dependency injection

__author__ = "Tomasz Kniola"
__credits__ = ["Tomasz Kniola"]
__license__ = "LGPL"
__version__ = "0.0.1"
__email__ = "kniola.tomasz@gmail.com"
__status__ = "development"


class Element(object):
    def __init__(self, names, nets, values, evaluate_param_func=None):
        self.names = names
        self.nets = nets
        self.values = values
        # Store the passed function if needed by base or for consistency, though children will use it directly.
        if evaluate_param_func:
            self.evaluate_param = evaluate_param_func

    def get_numerical_dc_value(self, param_values: dict):
        raise NotImplementedError(
            f"get_numerical_dc_value() is not implemented for {type(self).__name__}"
        )

class VoltageSource(Element):
    def __init__(self, name, element, evaluated_paramsd, parent, evaluate_param_func):
        voltage_source_nets = element.paramsl[:-1]
        if len(voltage_source_nets) != 2:
            raise scs_errors.ScsElementError("Port list is too long or too short for VoltageSource.")
        super().__init__([name], voltage_source_nets, [], evaluate_param_func=evaluate_param_func)

        if evaluate_param_func is None:
            raise ValueError("evaluate_param_func must be provided to VoltageSource constructor")

        if 'dc' in element.paramsd: vvalue_expresion = element.paramsd['dc']
        else: vvalue_expresion = element.paramsl[-1]

        vvalue = evaluate_param_func('_v', {'_v': vvalue_expresion}, evaluated_paramsd, parent)
        self.values = [sympy.sympify(vvalue, sympy.abc._clash)]

    @staticmethod
    def get_symbolic_equations(V_n_plus: sympy.Symbol, V_n_minus: sympy.Symbol, V_source_sym: sympy.Symbol) -> list:
        """
        Returns the symbolic equation for an independent voltage source.

        The equation defines the voltage difference between the positive and
        negative terminals of the source.

        Args:
            V_n_plus (sympy.Symbol): Symbol for the voltage at the positive node.
            V_n_minus (sympy.Symbol): Symbol for the voltage at the negative node.
            V_source_sym (sympy.Symbol): Symbol for the voltage value of the source.

        Returns:
            list: A list containing one Sympy Eq: V_n_plus - V_n_minus = V_source_sym.
        """
        return [sympy.Eq(V_n_plus - V_n_minus, V_source_sym)]

    def get_numerical_dc_value(self, param_values: dict) -> float | object:
        expr = self.values[0]
        try:
            substituted_expr = expr.subs(param_values) if hasattr(expr, 'subs') else expr
            return float(substituted_expr)
        except (TypeError, AttributeError, ValueError) as e:
            print(f"Warning: Could not convert DC value of {self.names[0]} ('{expr}') to float. Error: {e}. Returning substituted expression: {substituted_expr}")
            return substituted_expr

class VoltageControlledVoltageSource(VoltageSource): # Inherits get_numerical_dc_value from VoltageSource
    def __init__(self, name, element, evaluated_paramsd, parent, evaluate_param_func):
        # VCVS specific net extraction: n+, n-, nc+, nc-
        # element.paramsl for VCVS: [n_plus, n_minus, n_control_plus, n_control_minus, gain_expr]
        actual_nets = element.paramsl[:-1]
        if len(actual_nets) != 4:
            raise scs_errors.ScsElementError("Net list is incorrect for VoltageControlledVoltageSource. Expected 4 control/output nets.")

        Element.__init__(self, [name], actual_nets, [], evaluate_param_func=evaluate_param_func)

        if evaluate_param_func is None:
            raise ValueError("evaluate_param_func must be provided to VCVS constructor")

        gain_expresion = element.paramsl[-1]
        gain_value = evaluate_param_func('_gain', {'_gain': gain_expresion}, evaluated_paramsd, parent)
        self.values = [sympy.sympify(gain_value, sympy.abc._clash)]

    @staticmethod
    def get_symbolic_equations(V_out_plus: sympy.Symbol, V_out_minus: sympy.Symbol,
                               V_in_plus: sympy.Symbol, V_in_minus: sympy.Symbol,
                               gain_sym: sympy.Symbol) -> list:
        """
        Returns the symbolic equation for a Voltage-Controlled Voltage Source (VCVS).

        Equation: V_out_plus - V_out_minus = gain_sym * (V_in_plus - V_in_minus)

        Args:
            V_out_plus (sympy.Symbol): Symbol for the output positive node voltage.
            V_out_minus (sympy.Symbol): Symbol for the output negative node voltage.
            V_in_plus (sympy.Symbol): Symbol for the input positive control node voltage.
            V_in_minus (sympy.Symbol): Symbol for the input negative control node voltage.
            gain_sym (sympy.Symbol): Symbol for the voltage gain of the source.

        Returns:
            list: A list containing one Sympy Eq representing the VCVS behavior.
        """
        return [sympy.Eq(V_out_plus - V_out_minus, gain_sym * (V_in_plus - V_in_minus))]
    # get_numerical_dc_value is inherited from VoltageSource

class CurrentControlledVoltageSource(VoltageSource):
    def __init__(self, name, element, evaluated_paramsd, parent, evaluate_param_func):
        output_nets = element.paramsl[:-2]
        Element.__init__(self, [name, element.paramsl[-2]], output_nets, [], evaluate_param_func=evaluate_param_func)

        if evaluate_param_func is None:
            raise ValueError("evaluate_param_func must be provided to CCVS constructor")
        r_expresion = element.paramsl[-1]
        r_value = evaluate_param_func('_r', {'_r': r_expresion}, evaluated_paramsd, parent)
        self.values = [sympy.sympify(r_value, sympy.abc._clash)]

    @staticmethod
    def get_symbolic_equations(V_out_plus: sympy.Symbol, V_out_minus: sympy.Symbol,
                               I_control_sym: sympy.Symbol, r_trans_sym: sympy.Symbol) -> list:
        """
        Returns the symbolic equation for a Current-Controlled Voltage Source (CCVS).

        Equation: V_out_plus - V_out_minus = r_trans_sym * I_control_sym

        Args:
            V_out_plus (sympy.Symbol): Symbol for the output positive node voltage.
            V_out_minus (sympy.Symbol): Symbol for the output negative node voltage.
            I_control_sym (sympy.Symbol): Symbol for the controlling current.
            r_trans_sym (sympy.Symbol): Symbol for the transresistance of the source.

        Returns:
            list: A list containing one Sympy Eq representing the CCVS behavior.
        """
        return [sympy.Eq(V_out_plus - V_out_minus, r_trans_sym * I_control_sym)]
    # get_numerical_dc_value is inherited

class CurrentSource(Element):
    def __init__(self, name, element, evaluated_paramsd, parent, evaluate_param_func):
        current_source_nets = element.paramsl[:-1]
        if len(current_source_nets) != 2:
            raise scs_errors.ScsElementError("Port list is too long or too short for CurrentSource.")
        super().__init__([name], current_source_nets, [], evaluate_param_func=evaluate_param_func)

        if evaluate_param_func is None:
            raise ValueError("evaluate_param_func must be provided to CurrentSource constructor")

        if 'dc' in element.paramsd: ivalue_expresion = element.paramsd['dc']
        else: ivalue_expresion = element.paramsl[-1]

        ivalue = evaluate_param_func('_i', {'_i': ivalue_expresion}, evaluated_paramsd, parent)
        self.values = [sympy.sympify(ivalue, sympy.abc._clash)]

    @staticmethod
    def get_symbolic_equations(I_element: sympy.Symbol, I_source_sym: sympy.Symbol) -> list:
        """
        Returns the symbolic equation for an independent current source.

        The equation defines that the current through the element is equal
        to the source's specified current value.

        Args:
            I_element (sympy.Symbol): Symbol for the current flowing through the source.
            I_source_sym (sympy.Symbol): Symbol for the current value of the source.

        Returns:
            list: A list containing one Sympy Eq: I_element = I_source_sym.
        """
        return [sympy.Eq(I_element, I_source_sym)]

    def get_numerical_dc_value(self, param_values: dict) -> float | object:
        expr = self.values[0]
        try:
            substituted_expr = expr.subs(param_values) if hasattr(expr, 'subs') else expr
            return float(substituted_expr)
        except (TypeError, AttributeError, ValueError) as e:
            print(f"Warning: Could not convert DC value of {self.names[0]} ('{expr}') to float. Error: {e}. Returning substituted expression: {substituted_expr}")
            return substituted_expr

class VoltageControlledCurrentSource(CurrentSource): # Inherits get_numerical_dc_value from CurrentSource
    def __init__(self, name, element, evaluated_paramsd, parent, evaluate_param_func):
        actual_nets = element.paramsl[:-1]
        if len(actual_nets) != 4:
            raise scs_errors.ScsElementError("Net list is incorrect for VoltageControlledCurrentSource. Expected 4 control/output nets.")

        Element.__init__(self, [name], actual_nets, [], evaluate_param_func=evaluate_param_func)

        if evaluate_param_func is None:
            raise ValueError("evaluate_param_func must be provided to VCCS constructor")

        gm_expresion = element.paramsl[-1]
        gm_value = evaluate_param_func('_gm', {'_gm': gm_expresion}, evaluated_paramsd, parent)
        self.values = [sympy.sympify(gm_value, sympy.abc._clash)]

    @staticmethod
    def get_symbolic_equations(I_element: sympy.Symbol, V_in_plus: sympy.Symbol,
                               V_in_minus: sympy.Symbol, gm_sym: sympy.Symbol) -> list:
        """
        Returns the symbolic equation for a Voltage-Controlled Current Source (VCCS).

        Equation: I_element = gm_sym * (V_in_plus - V_in_minus)

        Args:
            I_element (sympy.Symbol): Symbol for the output current of the source.
            V_in_plus (sympy.Symbol): Symbol for the input positive control node voltage.
            V_in_minus (sympy.Symbol): Symbol for the input negative control node voltage.
            gm_sym (sympy.Symbol): Symbol for the transconductance of the source.

        Returns:
            list: A list containing one Sympy Eq representing the VCCS behavior.
        """
        return [sympy.Eq(I_element, gm_sym * (V_in_plus - V_in_minus))]
    # get_numerical_dc_value is inherited from CurrentSource

class CurrentControlledCurrentSource(CurrentSource):
    def __init__(self, name, element, evaluated_paramsd, parent, evaluate_param_func):
        output_nets = element.paramsl[:-2]
        Element.__init__(self, [name, element.paramsl[-2]], output_nets, [], evaluate_param_func=evaluate_param_func)

        if evaluate_param_func is None:
            raise ValueError("evaluate_param_func must be provided to CCCS constructor")
        ai_expresion = element.paramsl[-1] # Current gain
        ai_value = evaluate_param_func('_ai', {'_ai': ai_expresion}, evaluated_paramsd, parent)
        self.values = [sympy.sympify(ai_value, sympy.abc._clash)]

    @staticmethod
    def get_symbolic_equations(I_element: sympy.Symbol, I_control_sym: sympy.Symbol,
                               gain_sym: sympy.Symbol) -> list:
        """
        Returns the symbolic equation for a Current-Controlled Current Source (CCCS).

        Equation: I_element = gain_sym * I_control_sym

        Args:
            I_element (sympy.Symbol): Symbol for the output current of the source.
            I_control_sym (sympy.Symbol): Symbol for the controlling current.
            gain_sym (sympy.Symbol): Symbol for the current gain of the source.

        Returns:
            list: A list containing one Sympy Eq representing the CCCS behavior.
        """
        return [sympy.Eq(I_element, gain_sym * I_control_sym)]
    # get_numerical_dc_value is inherited

class PassiveElement(Element):
    def __init__(self, name, element, evaluated_paramsd, parent, evaluate_param_func=None):
        _names = [name] if name else []
        _nets = []
        if hasattr(element, 'paramsl'):
             _nets = element.paramsl[:-1]
        super().__init__(_names, _nets, [], evaluate_param_func=evaluate_param_func)

class Resistance(PassiveElement):
    def __init__(self, name, element, evaluated_paramsd, parent, evaluate_param_func):
        super().__init__(name, element, evaluated_paramsd, parent, evaluate_param_func=evaluate_param_func)
        if evaluate_param_func is None:
            raise ValueError("evaluate_param_func must be provided to Resistance constructor")

        if 'r' in element.paramsd: rvalue_expresion = element.paramsd['r']
        elif 'R' in element.paramsd: rvalue_expresion = element.paramsd['R']
        else: rvalue_expresion = element.paramsl[-1]

        current_nets = element.paramsl[:-1]
        if len(current_nets) != 2:
            raise scs_errors.ScsElementError("Port list is too long or too short for Resistance.")

        rvalue = evaluate_param_func('_r', {'_r': rvalue_expresion}, evaluated_paramsd, parent)
        self.names = [name]
        self.nets = current_nets
        self.values = [sympy.sympify(rvalue, sympy.abc._clash)]

    @staticmethod
    def get_symbolic_equations(V_n_plus: sympy.Symbol, V_n_minus: sympy.Symbol, I_element: sympy.Symbol, R_sym: sympy.Symbol) -> list:
        """
        Returns the symbolic equation for a resistor based on Ohm's Law.

        Args:
            V_n_plus (sympy.Symbol): Symbol for the voltage at the positive node.
            V_n_minus (sympy.Symbol): Symbol for the voltage at the negative node.
            I_element (sympy.Symbol): Symbol for the current flowing through the resistor
                                     (from V_n_plus to V_n_minus).
            R_sym (sympy.Symbol): Symbol for the resistance value.

        Returns:
            list: A list containing one Sympy Eq: V_n_plus - V_n_minus = I_element * R_sym.
        """
        return [sympy.Eq(V_n_plus - V_n_minus, I_element * R_sym)]

    def conductance(self):
        return 1.0 / self.values[0]

    def get_numerical_dc_value(self, param_values: dict) -> float | object:
        expr = self.values[0]
        try:
            substituted_expr = expr.subs(param_values) if hasattr(expr, 'subs') else expr
            return float(substituted_expr)
        except (TypeError, AttributeError, ValueError) as e:
            print(f"Warning: Could not convert resistance of {self.names[0]} ('{expr}') to float. Error: {e}. Returning substituted expression: {substituted_expr}")
            return substituted_expr

class Capacitance(PassiveElement):
    def __init__(self, name, element, evaluated_paramsd, parent, evaluate_param_func):
        super().__init__(name, element, evaluated_paramsd, parent, evaluate_param_func=evaluate_param_func)
        if evaluate_param_func is None:
            raise ValueError("evaluate_param_func must be provided to Capacitance constructor")

        if 'c' in element.paramsd: cvalue_expresion = element.paramsd['c']
        elif 'C' in element.paramsd: cvalue_expresion = element.paramsd['C']
        else: cvalue_expresion = element.paramsl[-1]

        current_nets = element.paramsl[:-1]
        if len(current_nets) != 2:
            raise scs_errors.ScsElementError("Port list is too long or too short for Capacitance.")

        cvalue = evaluate_param_func('_c', {'_c': cvalue_expresion}, evaluated_paramsd, parent)
        self.names = [name]
        self.nets = current_nets
        self.values = [sympy.sympify(cvalue, sympy.abc._clash)]

    def conductance(self):
        return sympy.symbols('s') * self.values[0]

    def get_numerical_dc_value(self, param_values: dict) -> float:
        return float('inf')

class Inductance(PassiveElement):
    def __init__(self, name, element, evaluated_paramsd, parent, evaluate_param_func):
        super().__init__(name, element, evaluated_paramsd, parent, evaluate_param_func=evaluate_param_func)
        if evaluate_param_func is None:
            raise ValueError("evaluate_param_func must be provided to Inductance constructor")

        if 'l' in element.paramsd: lvalue_expresion = element.paramsd['l']
        elif 'L' in element.paramsd: lvalue_expresion = element.paramsd['L']
        else: lvalue_expresion = element.paramsl[-1]

        current_nets = element.paramsl[:-1]
        if len(current_nets) != 2:
            raise scs_errors.ScsElementError("Port list is too long or too short for Inductance.")

        lvalue = evaluate_param_func('_l', {'_l': lvalue_expresion}, evaluated_paramsd, parent)
        self.names = [name]
        self.nets = current_nets
        self.values = [sympy.sympify(lvalue, sympy.abc._clash)]

    def conductance(self):
        return 1.0 / (sympy.symbols('s') * self.values[0])

    def get_numerical_dc_value(self, param_values: dict) -> float:
        return 0.0

elementd = {'r': Resistance, 'R': Resistance,
            'c': Capacitance, 'C': Capacitance,
            'l': Inductance, 'L': Inductance,
            'v': VoltageSource, 'V': VoltageSource,
            'i': CurrentSource, 'I': CurrentSource,
            'e': VoltageControlledVoltageSource, 'E': VoltageControlledVoltageSource,
            'g': VoltageControlledCurrentSource, 'G': VoltageControlledCurrentSource,
            'f': CurrentControlledCurrentSource, 'F': CurrentControlledCurrentSource,
            'h': CurrentControlledVoltageSource, 'H': CurrentControlledVoltageSource
            }
