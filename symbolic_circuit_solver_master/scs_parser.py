"""
Parsing functions

Here are all functions with deal with any kind of parsing the input data,
the most importing one being parseFile which reads the file and makes top circuit.
There are also function which deals with convering expresions for paramters and so on.
 
"""
import re
import sympy
import sympy.abc
import logging

# Defer import of scs_circuit to break potential import cycle
# from . import scs_circuit
from . import scs_errors

__author__ = "Tomasz Kniola"
__credits__ = ["Tomasz Kniola"]

__license__ = "LGPL"
__version__ = "0.0.1"
__email__ = "kniola.tomasz@gmail.com"
__status__ = "development"

# Matches line with comment at the end like: foo $ bar OR foo ; bar
reg_comment = re.compile('(?P<not_comment>.*?)(?P<comment>[\$;].*$)')
# Matches whole line with parameter definition at the end like: foo bar = 'spam spam spam'
reg_param_with_rest = re.compile('(?P<rest>.*)(?P<param>(\s.+?=\s*?\'.*?\'$)|(\s.+?=\s*?\".*?\"$))')
# Matches just the parameter: foo = 'spam spam spam'
reg_param = re.compile('(?P<name>.*?)=.*?(\'|\")(?P<value>.*)(\'|\")')
# Matches whole line with paramter, but that one definition is without apostophes like: foo = bar
reg_param_wo_brackets = re.compile('(?P<rest>.*)\s(?P<name>.+?)=\s*?(?P<value>.+?)$')
# Matches line with last item being a posiotional parameter like: spam spam spam 'foo'
reg_unnamed_param_with_rest = re.compile('(?P<rest>.*)(?P<param>(\'.*?\'$)|(\".*?\"$))')
# Matches just positional parameter: 'foo'
reg_unnamed_param = re.compile('(\'|\")(?P<value>.*)(\'|\")')
# Matches a line with simple positional parameter like: spam spam spam foo
reg_simple_param = re.compile('(?P<rest>.*)\s(?P<param>.*?$)')
# Matches numeric values: 1, 1.01, 1e1, 1.0e+1, 1e-1 etc. could be more charachters after
reg_numeric = re.compile('(?P<token>^\d+\.?(\d*?)((e|E)(\+|\-)?\d+?)?)(.*)')
# Matches engineer format numbers: 1k, 1.01n etc. could be more charachters after
reg_numeric_eng = re.compile('(?P<token>^\d+\.?(\d*?)(meg|Meg|MEg|MEG|a|A|f|F|p|P|n|N|u|U|m|M|k|K|x|X|g|G|t|T))(.*)')
# Matches engineer format numbers: 1k, 1.01n etc. no more charachters after
reg_only_numeric_eng = re.compile(
    '^(?P<number>\d+\.?\d*)?(?P<suffix>meg|Meg|MEg|MEG|a|A|f|F|p|P|n|N|u|U|m|M|k|K|x|X|g|G|t|T)$')
# Matches mathematical operators: *, **, +, -, / could be more charachters after
reg_operator = re.compile('(?P<token>^((\*\*?)|\+|\-|/))(.*)')
# Matches alphanumeric name of parameter, could be more charachters after
reg_symbols = re.compile('(?P<token>^[a-zA-Z]+[\w_\{\}]*)(.*)')
# Matches alphanumeric name of parameter, no more charachters after
reg_only_symbol = re.compile('(?P<symbol>^[a-zA-Z]+[\w_\{\}]*)$')
# Matches the inside of beginig brackets like: (foo) bar
reg_brackets = re.compile('(^\((?P<token>.*)\))(.*)')
# Matches funcion expresion, more characters could be after: foo(bar) spam spam spam
reg_function = re.compile('(?P<token>^[a-zA-z]?[\w_\{\}]*?\(.*?\))(.*)')
# Matches just function expresion: foo(bar)
reg_only_function = re.compile('(?P<function>^[a-zA-z]?[\w_\{\}]*?)\((?P<argument>.*?)\)$')

# Engineer sufixes for numbers
suffixd = {'meg': 1e6, 'Meg': 1e6, 'MEg': 1e6, 'MEG': 1e6,
           'a': 1e-18, 'A': 1e-18, 'f': 1e-15, 'F': 1e-15,
           'p': 1e-12, 'P': 1e-12, 'n': 1e-9, 'N': 1e-9,
           'u': 1e-6, 'U': 1e-6, 'm': 1e-3, 'M': 1e-3,
           'k': 1e3, 'K': 1e3, # Corrected 'k' from 1e6 to 1e3
           'x': 1e6, 'X': 1e6, # Note: 'x' and 'X' are often not standard SPICE, but present here. Assuming Mega.
           'g': 1e9, 'G': 1e9, 't': 1e12, 'T': 1e12}


def evaluate_param(param, paramsd, evaluated_paramsd, parent=None, params_called_list=None):
    """ Evaluates param value and puts it into dictionary for later use

        param: name of the parameter which values needs to be evaluated
        
        paramsd: dictionary of params which values may be yet to evaluated whith their expresions inside, param SHOUD be
        inside

        evaluated_paramsd: dictionary of already evaluated params, could be numerical value or symbols expresion (sympy)
    
        parent: parrent circuit of circuit which made the call, its for while we can't find definition in own
        dictionaries we can look for it in parents ones

        params_called_list: a list of params which we are already in process of evaluating so we don't call to evaluate
        them again, its for catching a circulary reference

        This funciotn expands the expresion for a parameter to its grammatic tokens and look for their value or calls to
        evaluate their values if they are on the list
        of paramters to be evaluated and weren't called for yet. When it completes to get all the needed values it
        calculates the expresion for that value, and puts it in the evaluated_paramsd. Raises an exception if
        definitions aren't found. Also raises exception if expresion is ill-formed.
    """

    def expand(_tokens):
        """ Expands glues together tokens into one expresion
            
            tokens: gramatical tokens to be expanded into one expresion            

            Take tokens and expand into expresion string, take all the tokens which are params to their value
            It's inner function of evaluate_param so it uses its variables.
            Output string should be able to simpyfy.
        """
        expr = ''
        for token in _tokens:
            if isinstance(token, list):
                expr += '(%s)' % expand(token)
            else:
                if reg_only_symbol.match(token):  # symbol token
                    if token not in evaluated_paramsd:
                        # Check if that parameter is on the list to be evaluated
                        if token in paramsd:
                            if token not in params_called_list:
                                tmp = evaluate_param(token, paramsd, evaluated_paramsd, parent,
                                                     params_called_list + [token])
                                if tmp:
                                    evaluated_paramsd.update({token: sympy.sympify(tmp,sympy.abc._clash)})
                            else:
                                raise scs_errors.ScsParameterError("Circulary refence for %s" % token)
                        else:
                            tmp = get_parent_evaluated_param(token, parent)
                            if not tmp:
                                raise scs_errors.ScsParameterError("Can't find definition for parameter: %s" % token)

                            expr += tmp
                            continue
                    if token in evaluated_paramsd:
                        expr += str(evaluated_paramsd[token])
                    else:
                        raise scs_errors.ScsParameterError("Can't find definition for parameter: %s" % token)
                elif reg_only_numeric_eng.match(token):
                    m = reg_only_numeric_eng.search(token)
                    expr += m.group('number') + "*" + str(suffixd[m.group('suffix')])
                else:
                    expr += token
        return expr

    if params_called_list is None:
        params_called_list = []

    if paramsd[param] == param:  # symbol definition
        return sympy.symbols(param)
    else:
        tokens = parse_param_expresion(paramsd[param])
        return expand(tokens)


def evaluate_params(paramsd, parent=None):
    """ Evaluate parameters expresion to their values or symbols expresions
        
        paramsd: dictionary of parameters to be evaluated
        
        parent: a parent circuit to the caller, where we might look for defintions of paramters in the expresions
        
        Function takes the dictionary and try to evaluate each parameter one by one. Returns dictionary of evaluated
        parameters.

    """
    evaluated_paramsd = {}
    for param, param_str in paramsd.items(): #iteritems -> items
        if param not in evaluated_paramsd:
            tmp = evaluate_param(param, paramsd, evaluated_paramsd, parent, [param])
            if tmp:
                evaluated_paramsd.update({param: sympy.sympify(tmp,sympy.abc._clash)})
    return evaluated_paramsd


def evaluate_passed_params(paramsd, inst, evaluated_paramsd=None):
    """ Evaluate parameters expresion passed to subinstance to their values or symbols expresions
        
        paramsd: dictionary of parameters to be evaluated (name expresion strings pairs)

        inst: instance which instatiates new subciruit or some of its parents
        
        evaluated_paramsd: allready evaluated parameters (name value pairs)
        
        Function takes the dictionary and try to evaluate each parameter one by one. Returns dictionary of evaluated
        parameters.

    """
    if evaluated_paramsd is None:
        evaluated_paramsd = {}

    for param, param_str in paramsd.items(): #iteritems -> items
        if param not in evaluated_paramsd:
            tmp = evaluate_expresion(param_str, inst.paramsd)
            if tmp:
                evaluated_paramsd.update({param: sympy.sympify(tmp,sympy.abc._clash)})
            elif inst.parent:
                evaluate_passed_params({param: paramsd}, inst.parent, evaluated_paramsd)
    return evaluated_paramsd


def parse_analysis_expresion(expresion):
    """ Parses expresion for analysis
        
        expresion: string to be parsed

        Function parses the expresion. Expresion should be mathematical construct. Could contain variable names, numbers
        and operators, round brackets and functions from the set of v(),i(),isub(). Function returns grammatical tokens
        for this expresion.
    """
    expresion0 = expresion
    expresion.strip()
    tokens = []
    while expresion:
        m = reg_numeric_eng.search(expresion)
        if not m:
            m = reg_numeric.search(expresion)
        if not m:
            m = reg_operator.search(expresion)
        if not m:
            m = reg_function.search(expresion)
        if not m:
            m = reg_symbols.search(expresion)
        if m:
            tokens.append(m.group('token'))
        else:
            m = reg_brackets.search(expresion)
            if m:
                try:
                    tokens.append(parse_analysis_expresion(m.group('token')))
                except scs_errors.ScsParameterError:
                    raise scs_errors.ScsParameterError("Can't parse expresion: %s" % expresion0)
        if not m:
            raise scs_errors.ScsParameterError("Can't parse expresion: %s" % expresion0)
        else:
            expresion = m.group(m.lastindex)  # rest of the expression

    return tokens


def parse_param_expresion(expresion):
    """ Parses expresion for parameters
        
        expresion: string to be parsed

        Function parses the expresion. Expresion should be mathematical construct. Could contain variable names, numbers
        and operators, round brackets. Function returns grammatical tokens for this expresion.
    """
    expresion.strip()
    tokens = []
    while expresion:
        m = reg_numeric_eng.search(expresion)
        if not m:
            m = reg_numeric.search(expresion)
        if not m:
            m = reg_operator.search(expresion)
        if not m:
            m = reg_symbols.search(expresion)
        if m:
            tokens.append(m.group('token'))
        else:
            m = reg_brackets.search(expresion)
            if m:
                tokens.append(parse_param_expresion(m.group('token')))
        if not m:
            raise scs_errors.ScsParameterError("Can't parse expresion: %s" % expresion)
        else:
            expresion = m.group(m.lastindex)  # rest of the expression

    return tokens


def get_parent_evaluated_param(param, parent):
    """ Functions get value of paramer or parent of a parent circuit
        
        param: name of a paramter which value we would like to get
        parent: parent of circuit where we are looking for parameter value

        If param definition is not find in parent, we call this function again for its parent of a parent. 
        If no defintion is present and there is no parent to be called, empty string is returned.
    """
    if parent:
        if param in parent.paramsd:
            return str(parent.paramsd[param])
        return get_parent_evaluated_param(param, parent.parent)
    return ''


def results2values(tokens, instance):
    """ Translates tokens to their values and makes a single expresion out of them.

        tokens: gramatical tokens
      
        instance: instance object which should hold value of parametrs or which could be called for function of it's
        solution (like v() etc.)

        It translate tokens list into one expresion. Single token could also be a list in which way it would be
        translated in whole expresion inside the bracket.
    """
    ret_str = ''
    for token in tokens:
        if isinstance(token, list):
            ret_str += '(' + results2values(token, instance) + ')'
        else:
            if reg_only_function.match(token):
                m = reg_only_function.search(token)
                if m.group('function') == 'v':
                    arguments = m.group('argument').split(',')
                    ret_str += '(' + str(instance.v(*tuple(arguments))) + ')'
                elif m.group('function') == 'i':
                    ret_str += '(' + str(instance.i(m.group('argument'))) + ')'
                elif m.group('function') == 'isub':
                    ret_str += '(' + str(instance.isub(m.group('argument'))) + ')'
                elif m.group('function') == 'p':
                    ret_str += '(' + str(instance.p(m.group('argument'))) + ')'
                else:
                    raise scs_errors.ScsInstanceError("Can't find function: %s" % token)
            elif reg_only_symbol.match(token):  # symbol token
                if token in instance.paramsd:
                    ret_str += str(instance.paramsd[token])
                else:
                    raise scs_errors.ScsInstanceError("Can't find definition for parameter: %s" % token)
            elif reg_only_numeric_eng.match(token):
                m = reg_only_numeric_eng.search(token)
                ret_str += m.group('number') + "*" + str(suffixd[m.group('suffix')])
            else:
                ret_str += token
    return ret_str


def params2values(tokens, valuesd):
    """ Translates tokens to their values and makes a single expresion out of them.

        tokens: gramatical tokens
        
        valuesd: dictionary of parametr:value pairs

        It translate tokens list into one expresion. Single token could also be a list in which way it would be
        translated in whole expresion inside the bracket.
    """
    ret_str = ''
    for token in tokens:
        if isinstance(token, list):
            ret_str += '(' + params2values(token, valuesd) + ')'
        else:
            if reg_only_symbol.match(token):  # symbol token
                if token in valuesd:
                    ret_str += str(valuesd[token])
                else:
                    raise scs_errors.ScsInstanceError("Can't find definition for parameter: %s" % token)
            elif reg_only_numeric_eng.match(token):
                m = reg_only_numeric_eng.search(token)
                ret_str += m.group('number') + "*" + str(suffixd[m.group('suffix')])
            else:
                ret_str += token
    return ret_str


def evaluate_expresion(expresion, valuesd):
    """ Evaluates expresion into a value

        expresion: string to be evaluated 
        
        valuesd: dictionary of parametr:value pairs

        Evaluate expresion into tokens and than change it to a single value or symbolic expresion
    """
    tokens = parse_param_expresion(expresion)
    return sympy.sympify(params2values(tokens, valuesd),sympy.abc._clash)


def strip_comment(in_str):
    """ Strip comments from a string

        str: string to be striped of comments
        
        Return string with tailing comments ($ comment) striped"""
    m = reg_comment.search(in_str)
    return m.group('not_comment') if m else in_str


def get_unnamed_params(in_str):
    """ Gets list of unnamed parameters from string 

        str: string where we look for parameters

        The string is changed in place, so when we find a parameter on string we trim it from string.
        String could be something like this
        .foo bar1 'bar2' bar3
        where return would be [bar1, bar2, bar3]
        and str would be: .foo
    """
    in_str = in_str.strip()
    param_l = []
    while in_str:
        in_str.strip()
        m = reg_unnamed_param_with_rest.search(in_str)
        if m:
            in_str = m.group('rest').strip()
            m2 = reg_unnamed_param.search(m.group('param'))
            param_l.append(m2.group('value'))
            continue
        m = reg_simple_param.search(in_str)
        if m:
            in_str = m.group('rest').strip()
            param_l.append(m.group('param'))
        else:
            param_l.append(in_str)
            break
    return list(reversed(param_l))


def get_params(in_str):
    """ Get dictionary of parameters from the end of string.

        str: string where we look for parameters

        Get dictionary of params from end of string and modyfies str in place to just hold rest of the string not being
        named parameters. So string like .foo bar1 bar2 bar3 = spam1 bar4 = 'spam2' would return
         {bar3: spam1, bar4: spam2} and str would be: .foo bar1 bar2
    """
    in_str = in_str.strip()
    param_d = {}

    while True:
        m = reg_param_with_rest.search(in_str)
        if m:
            in_str = m.group('rest').strip()
            m2 = reg_param.search(m.group('param'))
            param_d.update({m2.group('name').strip(): m2.group('value').strip()})
        else:
            m = reg_param_wo_brackets.search(in_str)
            if m:
                in_str = m.group('rest').strip()
                param_d.update({m.group('name').strip(): m.group('value').strip()})
        if not m:
            break

    return param_d, in_str


def add_element(param_d, param_l, name, circuit):
    """ Adds element to circuit
        
        param_d: Named parametrs dictionary for element

        param_l: positional parameters list for element

        name: name of an element to add
        
        circuit: circuit where we are adding an element

        Function is on the list of function for getNameFunctionFromHead. It adds a element to circuit and returns this
        circuit.
    """
    from . import scs_circuit # Local import
    circuit.add_element(name, scs_circuit.Element(param_l, param_d))
    return circuit


def add_subcircuit(param_d, param_l, name, circuit):
    """ Adds subcircuit to circuit
        
        param_d: Named parametrs dictionary for element

        param_l: positional parameters list for element

        name: name of an element to add
        
        circuit: circuit where we are adding an element

        Function is on the list of function for getNameFunctionFromHead. It adds a element to circuit and returns this
        circuit.
    """

    name = param_l.pop()
    circuit.add_subcircuit(name, param_l, param_d)
    return circuit.subcircuitsd[name]


def include_file(param_d, param_l, name, circuit):
    """ Includes contents of another file into currentling parsing file.
        
        param_d: dummy - ignored

        param_l: on first position of the list should be name of included file, rest is ignored

        name: dummy - ignored
        
        circuit: cirtuit which we are gonna parse contents of the included file

        Function is on the list of function for getNameFunctionFromHead. It includes contents of another file into
        parsing process. It just start parsing this file. Returns circuit (could be modified while parsing include file)
    """
    parse_file(param_l[0], circuit)
    return circuit


def add_param(param_d, param_l, name, circuit):
    """ Adds parameter defintion to circuit
        
        param_d: Named parametrs dictionarionary

        param_l: positional parameters list, will be translated into symbols

        name: dummy - ignored
        
        circuit: circuit where we are adding an parameter definition

        Function is on the list of function for getNameFunctionFromHead. It adds a parameter definition to circuit and
        returns this circuit. Should be either one element dictionary or one element parameter list, else it doesn't
        add any defition
    """
    for param in param_l:
        circuit.parametersd.update({param: param})
    circuit.parametersd.update(param_d)
    return circuit


def add_analysis(param_d, param_l, name, circuit):
    """ Adds element to top circuit
        
        param_d: Named parametrs dictionary for analysis

        param_l: positional parameters list for analysis

        name: name of an analysis to add
        
        circuit: circuit where we are adding an analysis

        Function is on the list of function for getNameFunctionFromHead. It adds an analysis to circuit and returns this
        circuit.
    """
    from . import scs_circuit # Local import
    if not circuit.parent:  # Check if top circuit
        circuit.analysisl.append(scs_circuit.Analysis(name, param_l, param_d))
    return circuit


def change_to_parent_circuit(param_d, param_l, name, circuit):
    """ Change working circuit to parent circuit
        
        param_d: dummy - ignored

        param_l: dummy - ignored

        name: dummy - ignored
        
        circuit: its parent will be returned

        Function is on the list of function for getNameFunctionFromHead. When .ends will be encountered in file this
        function will be executed. It will change the working circuit while parsing to parent of current circuit.

    """
    return circuit.parent


def get_name_function_from_head(head):
    """ Return appropriate function depending on head string

        head: string with header of a line, depending on it appropriate funcition to deal with rest of the line will be
        returned

        Depending if a line which header is provided as input is a control sentence (.foo) or element defintion
        (Xname etc.) will return appriopriate function to deal with rest of the line.
    """
    name, funct = head[1:], None
    function_dict = {'param': add_param,
                     'include': include_file,
                     'subckt': add_subcircuit,
                     'measure': add_analysis,
                     'ac': add_analysis,
                     'dc': add_analysis,
                      'end': change_to_parent_circuit} # Changed 'ends' to 'end'
    if head[0] == '.':
        # Make lookup case-insensitive for control keywords like .param, .PARAM, .subckt, etc.
        lower_name = name.lower() # name is head[1:]
        if lower_name in function_dict:
            funct = function_dict[lower_name]
        else:
            raise scs_errors.ScsParserError("Unknown control sentence: %s" % head)
    elif head[0] in \
            ('R', 'r', 'L', 'l', 'C', 'c', 'V', 'v', 'I', 'i', 'E', 'e', 'H', 'h', 'G', 'g', 'F', 'f', 'X', 'x'):
        name, funct = head, add_element
    elif head[0] == '*':  # Comment
        pass
    else:
        raise scs_errors.ScsParserError("Unknown element: %s" % head)
    return name, funct


def parseline(line, circuit):
    """ Parses a single line of input file

        line: string from a file to be parsed

        circuit: circuit for whihc parsing is performed

        Take line (string) and circuit performs action depending on the head of the line.
        Returns circuit - could be parrent,same or child of what was on the input.        
    """
    line = strip_comment(line)
    param_d, line = get_params(line)
    param_l = get_unnamed_params(line)

    head = None
    funct = None
    name = None
    if param_l:
        head = param_l.pop(0)
    if head:
        name, funct = get_name_function_from_head(head.strip())
    if funct:
        return funct(param_d, param_l, name, circuit)
    return circuit


def parse_file(filename, circuit):
    """ Parses input file into a circuit

        filename - path to a file to be parsed

        circuit - a circuit which will parse a file into
    
        Takes filename, tries to open the file, read the file line by line, creating circuit on the go from it. 
        Returns circuit. Will return None if any problems occured.
    """
    # current_cir is the initial TopCircuit object, which should already be an instance of scs_circuit.TopCircuit
    # No need to import scs_circuit just for type checking current_cir here if parse_file
    # is always called with a pre-existing circuit object (which it is from SymbolicCircuitProblemSolver).
    current_cir = circuit
    line_number = 1
    try:
        with open(filename, 'r') as fil:
            next_line = fil.readline()
            for line in fil:
                current_line = next_line
                next_line = line
                while next_line and next_line[0] == '+':
                    current_line += next_line[1:]
                    next_line = fil.readline()
                circuit = parseline(current_line, circuit)
                line_number += 1
                if circuit is None:
                    break
        if next_line and circuit:
            circuit = parseline(next_line, circuit)
        if circuit is current_cir:
            logging.error("No .end statement on the end of file!")
        return current_cir
    except scs_errors.ScsParserError as e:
        logging.error("Syntax error in file: %s on line: %d \n %s" % (filename, line_number, e))
        return None
    except IOError as e:
        logging.error(e)
        return None


__all__ = [add_analysis, add_element, add_param, add_subcircuit, change_to_parent_circuit,
           get_name_function_from_head, get_parent_evaluated_param, get_params, get_unnamed_params,
           evaluate_expresion, evaluate_param, evaluate_params, include_file, params2values, parse_analysis_expresion,
           parse_param_expresion, parse_file, parseline, strip_comment]
