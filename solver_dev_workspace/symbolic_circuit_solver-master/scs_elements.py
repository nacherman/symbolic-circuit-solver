"""
Elements classes and their functions

Element
+-VoltageSource
| +-VoltageControlledVoltageSource
| +-CurrentControlledCurrentSource
|
+ -CurrentSource
| +-VoltageControlledCurrentSource
| +-CurrentControlledCurrentSource
|
+-PassiveElement
  +-Reistance
  +-Capacitance
  +-Inductance

Those elements are part of instance not circuit.
"""

import sympy
import sympy.abc
import scs_errors
import scs_parser

__author__ = "Tomasz Kniola"
__credits__ = ["Tomasz Kniola"]

__license__ = "LGPL"
__version__ = "0.0.1"
__email__ = "kniola.tomasz@gmail.com"
__status__ = "development"


class Element(object):
    """Object with instance of an element in circuit, just template for hierarchy of object
    """

    def __init__(self, names, nets, values):
        """ Initialize element

            names: list of names, first is element name

            nets: list of nets that element is connected to

            values: list of values for that element
        """
        self.names = names
        self.nets = nets
        self.values = values


class VoltageSource(Element):
    """Object with instance of voltage source of a circtuit
    """

    def __init__(self, name, element, evaluated_paramsd, parent):
        """ Initialize VoltageSource

            name: VoltageSource name

            element: element template from circuit, object from scs_circuit.Element

            evaluated_paramsd: dictionary of parameter value pair which can be used to evaluate value of voltage source

            parent: instance parent which can have defintion of needed parameters

            We evaluate the value of votage for voltage source and fill the structure of generic element.
        """
        if 'dc' in element.paramsd:
            vvalue_expresion = element.paramsd['dc']
        else:
            vvalue_expresion = element.paramsl[-1]
        if len(element.paramsl[:-1]) != 2:
            raise scs_errors.ScsElementError("Port list is too long or too short.")
        vvalue = scs_parser.evaluate_param('_v', {'_v': vvalue_expresion}, evaluated_paramsd, parent)
        self.names = [name]
        self.nets = element.paramsl[:-1]
        self.values = [sympy.sympify(vvalue,sympy.abc._clash)]


class VoltageControlledVoltageSource(VoltageSource):
    """Object with instance of voltage controlled voltage source of a circtuit
    """

    def __init__(self, name, element, evaluated_paramsd, parent):
        """ Initialize VoltageControlledVoltageSource

            name: element name

            element: element template from circuit, object from scs_circuit.Element

            evaluated_paramsd: dictionary of parameter value pair which can be used to evaluate value of voltage source

            parent: instance parent which can have defintion of needed parameters

            We evaluate the value of votage amplifictation for voltage controlled voltage source and fill the structure
            of generic element.
        """
        gain_expresion = element.paramsl[-1]
        gain_value = scs_parser.evaluate_param('_gain', {'_gain': gain_expresion}, evaluated_paramsd, parent)
        self.names = [name]
        self.nets = element.paramsl[:-1]
        self.values = [sympy.sympify(gain_value,sympy.abc._clash)]


class CurrentControlledVoltageSource(VoltageSource):
    """Object with instance of current controlled voltage source of a circtuit
    """

    def __init__(self, name, element, evaluated_paramsd, parent):
        """ Initialize CurrentControlledVoltageSource

            name: element name

            element: element template from circuit, object from scs_circuit.Element

            evaluated_paramsd: dictionary of parameter value pair which can be used to evaluate value of voltage source

            parent: instance parent which can have defintion of needed parameters

            We evaluate the value of transresistance for current controlled voltage source and fill the structure of
            generic element.
        """
        r_expresion = element.paramsl[-1]
        r_value = scs_parser.evaluate_param('_r', {'_r': r_expresion}, evaluated_paramsd, parent)
        self.names = [name, element.paramsl[-2]]
        self.nets = element.paramsl[:-2]
        self.values = [sympy.sympify(r_value,sympy.abc._clash)]


class CurrentSource(Element):
    """Object with instance of current source of a circtuit
    """

    def __init__(self, name, element, evaluated_paramsd, parent):
        """ Initialize CurrentSource

            name: element name

            element: element template from circuit, object from scs_circuit.Element

            evaluated_paramsd: dictionary of parameter value pair which can be used to evaluate value of voltage source

            parent: instance parent which can have defintion of needed parameters

            We evaluate the value of current for current source and fill the structure of generic element.
        """
        if 'dc' in element.paramsd:
            ivalue_expresion = element.paramsd['dc']
        else:
            ivalue_expresion = element.paramsl[-1]
        if len(element.paramsl[:-1]) != 2:
            raise scs_errors.ScsElementError("Port list is too long or too short.")
        ivalue = scs_parser.evaluate_param('_i', {'_i': ivalue_expresion}, evaluated_paramsd, parent)
        self.names = [name]
        self.nets = element.paramsl[:-1]
        self.values = [sympy.sympify(ivalue,sympy.abc._clash)]


class VoltageControlledCurrentSource(CurrentSource):
    """Object with instance of volatage controlled current source of a circtuit
    """

    def __init__(self, name, element, evaluated_paramsd, parent):
        """ Initialize VoltageControlledCurrentSource

            name: element name

            element: element template from circuit, object from scs_circuit.Element

            evaluated_paramsd: dictionary of parameter value pair which can be used to evaluate value of voltage source

            parent: instance parent which can have defintion of needed parameters

            We evaluate the value of transconductance for voltage controlled current source and fill the structure of
            generic element.
        """
        gm_expresion = element.paramsl[-1]
        gm_value = scs_parser.evaluate_param('_gm', {'_gm': gm_expresion}, evaluated_paramsd, parent)
        self.names = [name]
        self.nets = element.paramsl[:-1]
        self.values = [sympy.sympify(gm_value,sympy.abc._clash)]


class CurrentControlledCurrentSource(CurrentSource):
    """Object with instance of current controlled current source of a circtuit
    """

    def __init__(self, name, element, evaluated_paramsd, parent):
        """ Initialize CurrentControlledCurrentSource

            name: element name

            element: element template from circuit, object from scs_circuit.Element

            evaluated_paramsd: dictionary of parameter value pair which can be used to evaluate value of voltage source

            parent: instance parent which can have defintion of needed parameters

            We evaluate the value of current amplification for current controlled current source and fill the structure
            of generic element.
        """
        ai_expresion = element.paramsl[-1]
        ai_value = scs_parser.evaluate_param('_ai', {'_ai': ai_expresion}, evaluated_paramsd, parent)
        self.names = [name, element.paramsl[-2]]
        self.nets = element.paramsl[:-2]
        self.values = [sympy.sympify(ai_value,sympy.abc._clash)]


class PassiveElement(Element):
    """ Object with instance of a passive element of a circuit
    """
    None


class Resistance(PassiveElement):
    """Object with instance of a resitance of a circuit.
    """

    def __init__(self, name, element, evaluated_paramsd, parent):
        """ Initialize Resistance

            name: element name

            element: element template from circuit, object from scs_circuit.Element

            evaluated_paramsd: dictionary of parameter value pair which can be used to evaluate value of voltage source

            parent: instance parent which can have defintion of needed parameters

            We evaluate the value of resistance for resistor and fill the structure of generic element.
        """
        if 'r' in element.paramsd:
            rvalue_expresion = element.paramsd['r']
        elif 'R' in element.paramsd:
            rvalue_expresion = element.paramsd['R']
        else:
            rvalue_expresion = element.paramsl[-1]
        if len(element.paramsl[:-1]) != 2:
            raise scs_errors.ScsElementError("Port list is too long or too short.")
        rvalue = scs_parser.evaluate_param('_r', {'_r': rvalue_expresion}, evaluated_paramsd, parent)
        self.names = [name]
        self.nets = element.paramsl[:-1]
        self.values = [sympy.sympify(rvalue,sympy.abc._clash)]

    def conductance(self):
        """ Calculate the conductance of self
        """
        return 1.0 / self.values[0]


class Capacitance(PassiveElement):
    """Object with instance of a capacitance of a circuit.
    """

    def __init__(self, name, element, evaluated_paramsd, parent):
        """ Initialize Capacitance

            name: element name

            element: element template from circuit, object from scs_circuit.Element

            evaluated_paramsd: dictionary of parameter value pair which can be used to evaluate value of voltage source

            parent: instance parent which can have defintion of needed parameters

            We evaluate the value of capacitance for capacitor and fill the structure of generic element.
        """
        if 'c' in element.paramsd:
            cvalue_expresion = element.paramsd['c']
        elif 'C' in element.paramsd:
            cvalue_expresion = element.paramsd['C']
        else:
            cvalue_expresion = element.paramsl[-1]
        if len(element.paramsl[:-1]) != 2:
            raise scs_errors.ScsElementError("Port list is too long or too short.")
        cvalue = scs_parser.evaluate_param('_c', {'_c': cvalue_expresion}, evaluated_paramsd, parent)
        self.names = [name]
        self.nets = element.paramsl[:-1]
        self.values = [sympy.sympify(cvalue,sympy.abc._clash)]

    def conductance(self):
        """ Calculate the conductance of self
        """
        return sympy.symbols('s') * self.values[0]


class Inductance(PassiveElement):
    """Object with instance of a inductance of a circuit.
    """

    def __init__(self, name, element, evaluated_paramsd, parent):
        """ Initialize Inductace

            name: element name

            element: element template from circuit, object from scs_circuit.Element

            evaluated_paramsd: dictionary of parameter value pair which can be used to evaluate value of voltage source

            parent: instance parent which can have defintion of needed parameters

            We evaluate the value of inductance for inductor and fill the structure of generic element.
        """
        if 'l' in element.paramsd:
            lvalue_expresion = element.paramsd['l']
        elif 'L' in element.paramsd:
            lvalue_expresion = element.paramsd['L']
        else:
            lvalue_expresion = element.paramsl[-1]
        if len(element.paramsl[:-1]) != 2:
            raise scs_errors.ScsElementError("Port list is too long or too short.")
        lvalue = scs_parser.evaluate_param('_l', {'_l': lvalue_expresion}, evaluated_paramsd, parent)
        self.names = [name]
        self.nets = element.paramsl[:-1]
        self.values = [sympy.sympify(lvalue,sympy.abc._clash)]

    def conductance(self):
        """ Calculate the conductance of self
        """
        return 1.0 / (sympy.symbols('s') * self.values[0])


# Dictionary of 1st letter of a name with appriopriate element object
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
