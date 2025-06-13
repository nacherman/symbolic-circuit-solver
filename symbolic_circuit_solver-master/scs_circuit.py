""" Circuit classes 
    
    Holds element of circuits after parsing the netlist. 
"""
import scs_errors
import scs_analysis

import time
import logging

__author__ = "Tomasz Kniola"
__credits__ = ["Tomasz Kniola"]

__license__ = "LGPL"
__version__ = "0.0.1"
__email__ = "kniola.tomasz@gmail.com"
__status__ = "development"


class Circuit(object):
    """Hold objects with descriptions to make instances of circuits. It's kind of a template of a circiuit.
       Need's to be instatciete with other functions. Hold elements, own parameters, can hold other subcircuits, 
       and information about it's parrent (if it's subcircuit of another circuit), and list of io ports
    """

    def __init__(self, name, parent, ports, params):
        """Initialize circuit.

            name: nmae of a circuit
            
            parent: parent circuit of that being created
        
            ports: list of nets being ports to connect to parent circuit
    
            params: dicitonary of default parameter names and expresionss, could be overwrite during instantiation

            Fill the structure with values and empty dictionaries.
        """
        self.name = name
        self.elementsd = {}  # Dictionary of element names with elements objects of circuit
        self.parametersd = {}  # Dictionary parameter names with expresion for them
        self.subcircuitsd = {}  # Dictionary of subcircuit names with circuit object
        self.parent = parent
        self.ports = ports
        if params:
            self.parametersd.update(params)

    def add_element(self, element_name, element):
        """ Adds an element to self elements dictionary

            element_name: name of an element being added

            element: element object being added to self.elementd dictionary

            if element with such names exist raise an error.
        """
        if element_name not in self.elementsd:
            self.elementsd.update({element_name: element})
        else:
            raise scs_errors.ScsParserError("Element %s already exists" % element_name)

    def add_subcircuit(self, subcircuit_name, subcircuit_ports, subcircuit_params):
        """ Adds a subcircuit to self subcircuit dictionary

            subcircuit_name: name of an subcircuit being added

            subcircuti: circuit object being added to self.subcircuitsd dictionary

            if subcircuit with such names exist raise an error.
        """
        if subcircuit_name in self.subcircuitsd:
            raise scs_errors.ScsParserError("Subcircuit %s defintion already exists" % subcircuit_name)
        new = Circuit(subcircuit_name, self, subcircuit_ports, subcircuit_params)
        self.subcircuitsd.update({subcircuit_name: new})


class TopCircuit(Circuit):
    """Circuit which doesn't have any parent (isn't subcircuit of any circuit). Holds also analysis that can be
       performed on whole circuit.
    """

    def __init__(self):
        """ Initialize TopCircuit
            
            Just passes name 'top' to parent Class and rest is empty.
        """
        Circuit.__init__(self, 'top', None, None, None)
        self.analysisl = []

    def perform_analysis(self, instance, file_prefix):
        """ Performs all analysis for self circuit.

            instance: solved instance for which we want to perform analysis
    
            file_prefix: prefix of a file where analysis are gonna print their answers
        """
        results_filename = "%s.results" % file_prefix

        created_print_file = False

        for analysis in self.analysisl:
            time1 = time.perf_counter()
            if not created_print_file:
                with open(results_filename, 'w'):
                    created_print_file = True
            try:
                scs_analysis.analysis_dict[analysis.type](analysis.paramsd, analysis.paramsl, instance, file_prefix)
                logging.info("Analysis: .%s '%s' performed in: %f s" %
                             (analysis.type, analysis.paramsl[0], time.perf_counter() - time1))
            except (scs_errors.ScsInstanceError, scs_errors.ScsParameterError, scs_errors.ScsAnalysisError) as e:
                logging.warning(e)
                logging.warning("Analysis: %s %s not performed" % (analysis.type, analysis.paramsl[0]))

                # TODO: add exception handling here


class Element(object):
    """Element object, which are being hold in circuits dictionaries
    """

    def __init__(self, paramsl, paramsd):
        """ Initialize Element
            
            paramsl: positional parameters list

            paramsd: parameters dictionary with parameters name, parameters expresions pairs.

            Fills those structures.
        """
        self.paramsl = paramsl
        self.paramsd = paramsd


class Analysis(object):
    """Analysiss object with definitions on how to perform analysis of the circuit.
    """

    def __init__(self, typ, paramsl, paramsd):
        """ Initialize Element
            
            paramsl: positional parameters list

            paramsd: parameters dictionary with parameters name, parameters expresions pairs.

            Fills those structures.
        """
        self.type = typ
        self.paramsl = paramsl
        self.paramsd = paramsd
