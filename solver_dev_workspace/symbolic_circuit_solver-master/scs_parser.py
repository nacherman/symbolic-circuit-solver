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

import scs_circuit
import scs_errors

# Adjust sys.path to allow importing from root project directory
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# from symbolic_components import s_sym as s_laplace_sym_global # Old import
try:
    from all_symbolic_components import s_sym as s_laplace_sym_global
    print(f"DEBUG scs_parser: Successfully imported s_laplace_sym_global: {s_laplace_sym_global} (id: {id(s_laplace_sym_global)}) from all_symbolic_components.py")
except ImportError as e_parser_s_sym:
    print(f"CRITICAL ERROR in scs_parser.py: Failed to import s_laplace_sym_global from all_symbolic_components: {e_parser_s_sym}")
    s_laplace_sym_global = sympy.Symbol('s_fallback_parser_critical') # Fallback

__author__ = "Tomasz Kniola"
__credits__ = ["Tomasz Kniola"]

__license__ = "LGPL"
__version__ = "0.0.1"
__email__ = "kniola.tomasz@gmail.com"
__status__ = "development"

# Regexes
reg_comment = re.compile('(?P<not_comment>.*?)(?P<comment>[\$;].*$)') # Handles $ and ; comments
reg_param_with_rest = re.compile('(?P<rest>.*)(?P<param>(\s.+?=\s*?\'.*?\'$)|(\s.+?=\s*?\".*?\"$))')
reg_param = re.compile('(?P<name>.*?)=.*?(\'|\")(?P<value>.*)(\'|\")')
reg_param_wo_brackets = re.compile('(?P<rest>.*)\s(?P<name>.+?)=\s*?(?P<value>.+?)$')
reg_unnamed_param_with_rest = re.compile('(?P<rest>.*)(?P<param>(\'.*?\'$)|(\".*?\"$))')
reg_unnamed_param = re.compile('(\'|\")(?P<value>.*)(\'|\")')
reg_simple_param = re.compile('(?P<rest>.*)\s(?P<param>.*?$)')
reg_numeric = re.compile('(?P<token>^\d+\.?(\d*?)((e|E)(\+|\-)?\d+?)?)(.*)')
reg_numeric_eng = re.compile('(?P<token>^\d+\.?(\d*?)(meg|Meg|MEg|MEG|a|A|f|F|p|P|n|N|u|U|m|M|k|K|x|X|g|G|t|T))(.*)')
reg_only_numeric_eng = re.compile(
    '^(?P<number>\d+\.?\d*)?(?P<suffix>meg|Meg|MEg|MEG|a|A|f|F|p|P|n|N|u|U|m|M|k|K|x|X|g|G|t|T)$')
reg_operator = re.compile('(?P<token>^((\*\*?)|\+|\-|/))(.*)')
reg_symbols = re.compile('(?P<token>^[a-zA-Z]+[\w_\{\}]*)(.*)')
reg_only_symbol = re.compile('(?P<symbol>^[a-zA-Z]+[\w_\{\}]*)$')
reg_brackets = re.compile('(^\((?P<token>.*)\))(.*)')
reg_function = re.compile('(?P<token>^[a-zA-z]?[\w_\{\}]*?\(.*?\))(.*)')
reg_only_function = re.compile('(?P<function>^[a_zA-z]?[\w_\{\}]*?)\((?P<argument>.*?)\)$')

suffixd = {'meg': 1e6, 'Meg': 1e6, 'MEg': 1e6, 'MEG': 1e6,
           'a': 1e-18, 'A': 1e-18, 'f': 1e-15, 'F': 1e-15,
           'p': 1e-12, 'P': 1e-12, 'n': 1e-9, 'N': 1e-9,
           'u': 1e-6, 'U': 1e-6, 'm': 1e-3, 'M': 1e-3,
           'k': 1e3, 'K': 1e3, 'x': 1e6, 'X': 1e6,
           'g': 1e9, 'G': 1e9, 't': 1e12, 'T': 1e12}

SYMPYFY_LOCALS_BASE = {
    "I": sympy.I, "pi": sympy.pi, "exp": sympy.exp,
    "sin": sympy.sin, "cos": sympy.cos, "tan": sympy.tan,
    "asin": sympy.asin, "acos": sympy.acos, "atan": sympy.atan,
    "sqrt": sympy.sqrt, "log": sympy.log, "ln": sympy.log,
    "s": s_laplace_sym_global,
    "omega": s_laplace_sym_global
}

# Moved parse_param_expresion and parse_analysis_expresion before evaluate_param
def parse_param_expresion(expresion):
    expresion = expresion.strip()
    tokens = []
    while expresion:
        m = reg_numeric_eng.search(expresion)
        if not m: m = reg_numeric.search(expresion)
        if not m: m = reg_operator.search(expresion)
        if not m: m = reg_symbols.search(expresion)
        if m: tokens.append(m.group('token'))
        else:
            m = reg_brackets.search(expresion)
            if m: tokens.append(parse_param_expresion(m.group('token')))
        if not m: raise scs_errors.ScsParameterError("Can't parse expresion: %s" % expresion)
        else: expresion = m.group(m.lastindex).strip()
    return tokens

def parse_analysis_expresion(expresion):
    expresion0 = expresion
    expresion = expresion.strip()
    tokens = []
    while expresion:
        m = reg_numeric_eng.search(expresion)
        if not m: m = reg_numeric.search(expresion)
        if not m: m = reg_operator.search(expresion)
        if not m: m = reg_function.search(expresion)
        if not m: m = reg_symbols.search(expresion)
        if m: tokens.append(m.group('token'))
        else:
            m = reg_brackets.search(expresion)
            if m:
                try: tokens.append(parse_analysis_expresion(m.group('token')))
                except scs_errors.ScsParameterError: raise scs_errors.ScsParameterError("Can't parse expresion: %s" % expresion0)
        if not m: raise scs_errors.ScsParameterError("Can't parse expresion: %s" % expresion0)
        else: expresion = m.group(m.lastindex).strip()
    return tokens


def get_parent_evaluated_param(param, parent_instance, params_called_list=None, instance_context=None):
    if params_called_list is None: params_called_list = []
    if parent_instance:
        if param in parent_instance.paramsd:
            val = parent_instance.paramsd[param]
            return str(val)
        return get_parent_evaluated_param(param, parent_instance.parent, params_called_list=params_called_list, instance_context=parent_instance)
    return ''

def evaluate_param(param, paramsd, evaluated_paramsd, parent=None, params_called_list=None, instance_context=None):
    def expand(_tokens):
        expr = ''
        for token in _tokens:
            if isinstance(token, list):
                expr += '(%s)' % expand(token)
            else:
                # Pre-strip units from token before further processing
                processed_token = token
                units_to_strip = ["FARAD", "FD", "F", "HENRY", "H", "OHMS", "OHM", "HZ", "V", "A", "SEC", "S"] # Added S for seconds, common units
                units_to_strip.sort(key=len, reverse=True) # Sort by length for longest match

                # Store original token case for symbol matching if no unit is stripped.
                # Symbol matching should be case-sensitive if possible, or consistently cased.
                # For now, scs_parser tends to uppercase lines then lowercase for some keywords.
                # Parameters are often case-sensitive in SPICE. Let's assume processed_token maintains original case from tokenizer.

                original_processed_token_for_symbol_lookup = processed_token

                for unit_upper in units_to_strip:
                    # Check if current processed_token ends with a unit (case-insensitive)
                    if processed_token.upper().endswith(unit_upper):
                        val_part = processed_token[:-len(unit_upper)]
                        # Only strip unit if remaining part is numeric, eng notation, or empty
                        # This prevents stripping 'F' from a symbol like 'OFFSET'
                        if reg_only_numeric_eng.match(val_part) or \
                           reg_numeric.match(val_part) or \
                           not val_part: # Allows token to be just a unit like "F"
                            processed_token = val_part
                            break # Stripped one unit, that's enough

                # Now, use 'processed_token' for numeric/symbol checks
                # If processed_token became empty (e.g. original token was just "F"), it won't match symbol/numeric

                if not processed_token: # If token was purely a unit that got stripped
                    pass # Effectively ignore the unit token, add nothing to expr
                elif reg_only_symbol.match(processed_token):
                    # Use original_processed_token_for_symbol_lookup if needed for case sensitivity,
                    # but current parameter handling seems to work with whatever case comes.
                    # Sticking to processed_token for now.
                    active_token_for_symbol = processed_token
                    if active_token_for_symbol not in evaluated_paramsd:
                        if active_token_for_symbol in paramsd:
                            if active_token_for_symbol not in params_called_list:
                                tmp = evaluate_param(active_token_for_symbol, paramsd, evaluated_paramsd, parent,
                                                     params_called_list + [active_token_for_symbol], instance_context=instance_context)
                                if tmp is not None:
                                    try:
                                        basic_sympify_locals = {k: SYMPYFY_LOCALS_BASE[k] for k in ['I','pi','exp','s','omega'] if k in SYMPYFY_LOCALS_BASE}
                                        evaluated_paramsd.update({active_token_for_symbol: sympy.sympify(tmp, locals=basic_sympify_locals)})
                                    except (sympy.SympifyError, TypeError):
                                        evaluated_paramsd.update({active_token_for_symbol: tmp})
                            else:
                                raise scs_errors.ScsParameterError("Circulary refence for %s" % active_token_for_symbol)
                        elif instance_context and active_token_for_symbol in instance_context.paramsd:
                            expr += str(instance_context.paramsd[active_token_for_symbol])
                            continue
                        else:
                            tmp = get_parent_evaluated_param(active_token_for_symbol, parent, instance_context=instance_context, params_called_list=params_called_list)
                            if not tmp:
                                if active_token_for_symbol == str(s_laplace_sym_global) or active_token_for_symbol.lower() == 's': expr += str(s_laplace_sym_global); continue
                                if active_token_for_symbol.lower() == 'omega': expr += str(s_laplace_sym_global); continue
                                # If after stripping units, the remaining symbol is not found, it's an error.
                                raise scs_errors.ScsParameterError("Can't find definition for parameter: %s (processed from %s)" % (active_token_for_symbol, token))
                            expr += tmp
                            continue
                    if active_token_for_symbol in evaluated_paramsd:
                        expr += str(evaluated_paramsd[active_token_for_symbol])
                    else: # Should not be reached if logic above is correct
                        if active_token_for_symbol == str(s_laplace_sym_global) or active_token_for_symbol.lower() == 's': expr += str(s_laplace_sym_global); continue
                        if active_token_for_symbol.lower() == 'omega': expr += str(s_laplace_sym_global); continue
                        raise scs_errors.ScsParameterError("Parameter %s (processed from %s) evaluated to None or still not found." % (active_token_for_symbol, token))
                elif reg_only_numeric_eng.match(processed_token):
                    m = reg_only_numeric_eng.search(processed_token)
                    num_part = m.group('number') if m.group('number') else "1" # If only suffix like "k", treat as "1k"
                    suffix_val = suffixd.get(m.group('suffix'))
                    if suffix_val is not None:
                        expr += num_part + "*" + str(suffix_val)
                    else: # Should not happen if reg_only_numeric_eng matched with a valid suffix from its list
                        logging.warning(f"Unknown suffix {m.group('suffix')} in token '{processed_token}' (from '{token}'). Using token as is.")
                        expr += processed_token
                elif reg_numeric.match(processed_token): # Plain number, no suffix
                    expr += processed_token
                else: # Fallback for anything else (e.g. operators, or if token was an unhandled mix)
                    expr += processed_token # Original token, not processed_token, if stripping made it invalid? Or error?
                                          # Sticking with processed_token. If it's an operator, it's fine.
                                          # If it's a malformed remnant, sympify will catch it later.
        return expr

    if params_called_list is None: params_called_list = []
    param_value_str = paramsd.get(param, str(param))

    if isinstance(param_value_str, str) and param_value_str.startswith('{') and param_value_str.endswith('}'):
        param_value_str = param_value_str[1:-1]

    if param_value_str == param and param not in paramsd:
        return sympy.symbols(param)
    else:
        tokens = parse_param_expresion(param_value_str) # This call is now valid
        return expand(tokens)

def evaluate_params(paramsd, parent=None, instance_context=None):
    evaluated_paramsd = {}
    # Build initial context by copying parent's evaluated params, then instance's (passed on X-line)
    # This establishes hierarchy: instance > parent > grandparent etc.
    # Local .PARAM definitions (in paramsd argument) will then be evaluated using this context.

    # Start with an empty context for the current level's .PARAM definitions
    # Hierarchical lookup will be handled by evaluate_param -> expand -> get_parent_evaluated_param

    # If instance_context is provided (it's the 'inst' object being built),
    # its paramsd might already have X-line evaluated parameters. These should be available.
    # And parent.paramsd are from .PARAM of parent subcircuit definitions.

    # The context for sympifying the final expression string for a parameter
    # should include already evaluated parameters at the current level.

    sympify_context = {**SYMPYFY_LOCALS_BASE}
    if instance_context and instance_context.paramsd: # Parameters from X-line, already Sympy objects
        for k,v in instance_context.paramsd.items(): # k is Symbol, v is Sympy obj
            sympify_context[str(k.name if hasattr(k,'name') else k)] = v

    # 'parent' here is parent_evaluated_param_dict from scs_instance_hier.py (parent_instance.paramsd or {})
    if parent: # parent is a dict of already evaluated parameters from the parent instance's scope
         for k_str, v_sympy in parent.items(): # k_str should be string, v_sympy is Sympy obj
            if k_str not in sympify_context : # Don't override X-line params if names clash
                sympify_context[k_str] = v_sympy

    for param, param_str in paramsd.items(): # paramsd is circuit_template.parametersd (str:str)
        # Only evaluate if not already in evaluated_paramsd from a higher scope (e.g. X-line parameters)
        # This 'evaluated_paramsd' is local to this function call for this level's .PARAMs
        if param not in evaluated_paramsd :
            # evaluate_param needs the actual parent *instance* for hierarchical lookups,
            # which is instance_context.parent.
            # paramsd to evaluate_param is the current level's definitions.
            # evaluated_paramsd to evaluate_param is the dict being built at this level.
            tmp_expr_str = evaluate_param(
                param, paramsd, evaluated_paramsd,
                instance_context.parent if instance_context else None, # Actual parent Instance object
                [param], instance_context=instance_context
            )
            if tmp_expr_str is not None:
                try:
                    # Build specific locals for this sympify, including already evaluated params from this level
                    current_level_sympify_locals = {**sympify_context, **evaluated_paramsd}
                    # Ensure keys are strings
                    final_locals = {k_s: v_val for k_s, v_val in current_level_sympify_locals.items() if isinstance(k_s, str)}
                    for k_sym_loc, v_val_loc in current_level_sympify_locals.items():
                        if hasattr(k_sym_loc, 'name') and k_sym_loc.name not in final_locals:
                            final_locals[k_sym_loc.name] = v_val_loc

                    evaluated_paramsd[param] = sympy.sympify(tmp_expr_str, locals=final_locals)
                except (sympy.SympifyError, TypeError) as e_sympify:
                    if isinstance(tmp_expr_str, sympy.Expr): evaluated_paramsd[param] = tmp_expr_str
                    else:
                        logging.warning(f"Could not sympify parameter {param} from expr '{tmp_expr_str}'. Err: {e_sympify}")
                        evaluated_paramsd[param] = tmp_expr_str
    return evaluated_paramsd

def evaluate_passed_params(paramsd_on_x_line, inst_calling_subcircuit):
    evaluated_passed_params = {}
    for param_name, raw_expr_str in paramsd_on_x_line.items():
        try:
            # evaluate_expresion expects (expression_str, current_instance_object)
            # inst_calling_subcircuit is the instance object that contains the X-line.
            rhs_sympy_expr = evaluate_expresion(
                raw_expr_str,
                inst_calling_subcircuit
            )
            evaluated_passed_params[param_name] = rhs_sympy_expr
        except Exception as e:
            logging.error(f"Error evaluating passed parameter {param_name}='{raw_expr_str}' for subcircuit. {e}")
            evaluated_passed_params[param_name] = sympy.Symbol(param_name + "_passed_eval_error")
    return evaluated_passed_params

def evaluate_expresion(expresion_str, current_instance_object): # Changed signature
    if isinstance(expresion_str, sympy.Expr): return expresion_str
    if not isinstance(expresion_str, str): expresion_str = str(expresion_str)
    original_expresion_str_for_fallback = expresion_str

    if expresion_str.startswith('{') and expresion_str.endswith('}'):
        expresion_str = expresion_str[1:-1]

    # Use parse_analysis_expresion as it handles functions like V(), I() better
    tokens = parse_analysis_expresion(expresion_str)

    # SYMPYFY_LOCALS_BASE already contains common math functions and s, I, pi etc.
    # We need to add MAG, DEG, ARG if not already handled by sympy.
    # For now, assume they might be sympy functions or need to be custom.
    # Let's define them for our sympify context if they are not standard.
    custom_math_functions = {
        "MAG": lambda x: sympy.Abs(x),
        "ABS": lambda x: sympy.Abs(x),
        "ARG": lambda x: sympy.arg(x), # Returns radians
        "PHASE": lambda x: sympy.arg(x), # Alias for ARG
        "DEG": lambda x: x * 180 / sympy.pi, # Converts radians to degrees
        "DB": lambda x: 20 * sympy.log(sympy.Abs(x), 10), # Decibels
        # POWER(R1) might be special, not a simple function.
        # For now, focus on V() and I() which are instance methods.
    }
    # Merge with SYMPYFY_LOCALS_BASE and parameters from instance
    eval_context = {**SYMPYFY_LOCALS_BASE, **custom_math_functions}
    if current_instance_object and current_instance_object.paramsd:
        for k,v_loc in current_instance_object.paramsd.items():
            key_str = str(k.name if hasattr(k, 'name') else k)
            eval_context[key_str] = v_loc


    def expand_tokens_with_instance_methods(_tokens, instance_obj):
        # This function will now try to call instance.v() and instance.i()
        # if it encounters V(net) or I(element) tokens.
        # For other functions like MAG(V(net)), it constructs a string expression
        # that sympy.sympify can evaluate using the eval_context.

        expr_parts = []
        for token in _tokens:
            if isinstance(token, list): # A nested expression (e.g. arguments to a function)
                expr_parts.append(f"({expand_tokens_with_instance_methods(token, instance_obj)})")
            else:
                # Check if token is a V(net) or I(element) style function call
                m_func = reg_only_function.match(token)
                if m_func:
                    func_name = m_func.group('function').upper()
                    func_arg_str = m_func.group('argument')
                    if func_name == 'V':
                        # Argument to V() can be one node "N1" or two "N1,N2"
                        arg_parts = [a.strip() for a in func_arg_str.split(',')]
                        if len(arg_parts) == 1:
                            val = instance_obj.v(arg_parts[0])
                        elif len(arg_parts) == 2:
                            val = instance_obj.v(arg_parts[0], arg_parts[1])
                        else:
                            raise scs_errors.ScsParameterError(f"Function V() expects 1 or 2 arguments, got: {func_arg_str}")
                        # We need to return a string that sympify can use, or directly the Sympy object.
                        # If instance.v() returns a Sympy object, we can't just append it to expr_parts if other parts are strings.
                        # This expansion needs to build a list of Sympy objects and strings, then combine.
                        # For now, assume instance.v() returns a Sympy object, and this is the only part of the expression.
                        # This is a simplification. A full expression evaluator is more complex.
                        # Let's try to make evaluate_expression return the direct Sympy object from v() or i()
                        # if the expression IS v(...) or i(...)
                        if len(_tokens) == 1: return val # Special case: if expression is *just* V(...) or I(...)
                        expr_parts.append(str(val)) # Else, stringify for larger expression

                    elif func_name == 'I':
                        val = instance_obj.i(func_arg_str)
                        if len(_tokens) == 1: return val
                        expr_parts.append(str(val))
                    elif func_name == 'POWER': # POWER(R1)
                        # This would need: P_R1 symbol from solved_dict.
                        # P_R1 = instance_obj.solved_dict.get(sp.Symbol(f"P_{func_arg_str.upper()}"))
                        # For now, let POWER(X) become a symbol P_X to be resolved by sympify context
                        # if P_X is in instance_obj.paramsd (populated from solved_dict)
                        expr_parts.append(f"P_{func_arg_str.upper()}")
                    else: # Other functions like MAG, DEG, ARG, or user-defined: keep as string for sympify
                        expr_parts.append(token)
                elif reg_only_symbol.match(token):
                    # Parameters or s, omega etc.
                    # These will be resolved by sympy.sympify using the 'eval_context'
                    expr_parts.append(token)
                elif reg_only_numeric_eng.match(token): # Numeric with engineering suffix
                    m = reg_only_numeric_eng.search(token)
                    num_part = m.group('number') if m.group('number') else "1"
                    expr_parts.append(num_part + "*" + str(suffixd[m.group('suffix')]))
                else: # Plain numbers, operators
                    expr_parts.append(token)
        return "".join(expr_parts)

    # Handle the simple V(X) or I(X) case first
    if len(tokens) == 1 and isinstance(tokens[0], str):
        m_func_direct = reg_only_function.match(tokens[0])
        if m_func_direct:
            func_name = m_func_direct.group('function').upper()
            func_arg_str = m_func_direct.group('argument')
            if func_name == 'V':
                arg_parts = [a.strip() for a in func_arg_str.split(',')]
                if len(arg_parts) == 1: return current_instance_object.v(arg_parts[0])
                if len(arg_parts) == 2: return current_instance_object.v(arg_parts[0], arg_parts[1])
            elif func_name == 'I':
                return current_instance_object.i(func_arg_str)
            # POWER(X) could be handled here if desired, by looking up P_X in solved_dict/paramsd

    # For more complex expressions like MAG(V(N1)) or V(N1)-V(N2)
    final_expr_str = expand_tokens_with_instance_methods(tokens, current_instance_object)
    try:
        # The eval_context now includes parameters from instance.paramsd (which has solved values)
        # and custom functions like MAG, DEG.
        return sympy.sympify(final_expr_str, locals=eval_context)
    except Exception as e:
        logging.warning(f"Failed to sympify complex expr '{final_expr_str}' from '{expresion_str}'. Error: {e}")
        # Fallback to trying to sympify the original string if our expansion failed badly.
        try:
            return sympy.sympify(original_expresion_str_for_fallback, locals=eval_context)
        except Exception as e2:
            logging.error(f"Double fail to sympify: 1) '{final_expr_str}' 2) '{original_expresion_str_for_fallback}'. Errors: {e}, {e2}. Returning as symbol.")
            return sympy.Symbol(original_expresion_str_for_fallback)


def strip_comment(in_str):
    if in_str.startswith('$'): return ""
    m = reg_comment.search(in_str)
    if in_str.startswith('$') or in_str.startswith(';'): return "" # Whole line is comment
    m = reg_comment.search(in_str)
    return m.group('not_comment').strip() if m else in_str.strip()

def get_unnamed_params(in_str):
    in_str = in_str.strip()
    param_l = []
    while in_str:
        in_str = in_str.strip()
        m = reg_unnamed_param_with_rest.search(in_str)
        if m:
            in_str = m.group('rest').strip(); m2 = reg_unnamed_param.search(m.group('param'))
            param_l.append(m2.group('value'))
            continue
        m = reg_simple_param.search(in_str)
        if m:
            in_str = m.group('rest').strip(); param_l.append(m.group('param'))
        else:
            param_l.append(in_str); break
    return list(reversed(param_l))

def get_params(in_str):
    in_str = in_str.strip()
    param_d = {}
    while True:
        m = reg_param_with_rest.search(in_str)
        if m:
            in_str = m.group('rest').strip(); m2 = reg_param.search(m.group('param'))
            param_d.update({m2.group('name').strip(): m2.group('value').strip()})
        else:
            m = reg_param_wo_brackets.search(in_str)
            if m:
                in_str = m.group('rest').strip(); param_d.update({m.group('name').strip(): m.group('value').strip()})
        if not m: break
    return param_d, in_str

def add_element(param_d, param_l, name, circuit):
    circuit.add_element(name, scs_circuit.Element(param_l, param_d))
    return circuit

def add_subcircuit(param_d_from_line, param_l_from_line, name_keyword, circuit_obj): # name_keyword is "subckt"
    subckt_name = param_l_from_line.pop(0) # e.g. "MY_RC_FILTER"

    ports = []
    subckt_params_dict = {} # For params defined with PARAM keyword on .SUBCKT line

    param_keyword_found = False
    # Iterate through the rest of param_l_from_line to find ports and PARAM keyword
    idx = 0
    while idx < len(param_l_from_line):
        item_val = param_l_from_line[idx]
        if item_val.upper() == 'PARAM':
            param_keyword_found = True
            # The items after PARAM are parameter assignments
            param_defs_list = param_l_from_line[idx+1:]
            # Use similar logic as add_param for parsing "name=value" pairs
            # This assumes params are like "R_SUBCKT=1k", "C_SUBCKT=1u"
            current_param_idx = 0
            while current_param_idx < len(param_defs_list):
                param_item_str = param_defs_list[current_param_idx].strip()
                if '=' in param_item_str:
                    p_name, p_val = param_item_str.split('=',1)
                    subckt_params_dict[p_name.strip()] = p_val.strip()
                else:
                    logging.warning(f"Parameter definition '{param_item_str}' on .SUBCKT line for {subckt_name} is malformed. Expected 'name=value'.")
                current_param_idx += 1
            break # All items after PARAM keyword are processed as params
        else:
            ports.append(item_val) # This is a port name
        idx += 1

    # param_d_from_line usually contains parameters defined with key=value syntax on the .SUBCKT line itself,
    # which is not standard for SPICE .SUBCKT parameters (they use PARAM keyword).
    # However, if any were parsed into param_d_from_line, merge them.
    # For now, only parameters after PARAM keyword are put into subckt_params_dict.
    if param_d_from_line:
        logging.warning(f"Parameters found in key=value form on .SUBCKT line for {subckt_name}: {param_d_from_line}. These are not standard and might not be handled as expected. Use PARAM keyword.")
        # Example: .SUBCKT MYSUB N1 N2 RVAL=1K ; RVAL=1K would be in param_d_from_line
        # Merge them if necessary, but standard is PARAM keyword.
        # subckt_params_dict.update(param_d_from_line) # Or prioritize one over other if conflicts

    circuit_obj.add_subcircuit(subckt_name, ports, subckt_params_dict)
    return circuit_obj.subcircuitsd[subckt_name]

def include_file(param_d, param_l, name, circuit):
    if not param_l : raise scs_errors.ScsParserError(".include statement needs a filename.")
    parse_file(param_l[0], circuit)
    return circuit

def add_param(param_d, param_l, name, circuit):
    circuit.parametersd.update(param_d)
    i = 0
    while i < len(param_l):
        param_item = param_l[i].strip()
        if '=' in param_item:
            p_name, p_val = param_item.split('=',1)
            circuit.parametersd.update({p_name.strip(): p_val.strip()})
            i += 1
        elif i + 1 < len(param_l) and not any(op in param_l[i+1] for op in ['=','{','(']):
            circuit.parametersd.update({param_item: param_l[i+1].strip()})
            i += 2
        else:
             circuit.parametersd.update({param_item: param_item})
             i += 1
    return circuit

def add_analysis(param_d, param_l, name, circuit):
    current_c = circuit
    while current_c.parent is not None: current_c = current_c.parent
    if isinstance(current_c, scs_circuit.TopCircuit):
        current_c.analysisl.append(scs_circuit.Analysis(name, param_l, param_d))
    else: logging.warning(f"Analysis line '.{name}' found outside of top-level circuit. Ignored.")
    return circuit

def change_to_parent_circuit(param_d, param_l, name, circuit):
    if circuit.parent is None and name.lower() == 'end':
        return None
    if circuit.parent is None and name.lower() == 'ends':
        logging.warning(".ENDS called on top-level circuit. No parent to return to.")
        return circuit
    return circuit.parent if circuit.parent is not None else circuit

def get_name_function_from_head(head):
    name_key = head[1:].lower()
    funct = None
    function_dict = {'param': add_param, 'include': include_file, 'subckt': add_subcircuit,
                     'measure': add_analysis, 'ac': add_analysis, 'dc': add_analysis, 'tran': add_analysis,
                     'ends': change_to_parent_circuit, 'options':add_param, 'model':add_param, 'end': change_to_parent_circuit}
    if head.startswith('.'):
        if name_key in function_dict: funct = function_dict[name_key]
        else: logging.warning(f"Unknown control sentence: {head}"); return head, None
        return name_key, funct
    elif head[0].upper() in ('R','L','C','V','I','E','H','G','F','X'):
        return head, add_element
    elif head.startswith('*') or head.startswith('$'):
        return head, None
    else:
        logging.warning(f"Unknown element or line type: {head}"); return head, None

def parseline(line, circuit):
    original_line_for_err_report = line
    line = strip_comment(line)
    if not line: return circuit
    param_d, line_after_named_params = get_params(line)
    param_l = get_unnamed_params(line_after_named_params)
    head = None
    if param_l: head = param_l.pop(0).strip()
    if head:
        name_from_map, funct = get_name_function_from_head(head)
        if funct: return funct(param_d, param_l, name_from_map, circuit)
        elif head and not (head.startswith('*') or head.startswith('$')):
            logging.warning(f"No function to handle line starting with '{head}' in: {original_line_for_err_report}")
    return circuit

def parse_file(filename, circuit=None):
    if circuit is None:
        top_circuit_obj = scs_circuit.TopCircuit()
        top_circuit_obj.name = os.path.splitext(os.path.basename(filename))[0]
        circuit = top_circuit_obj
    current_parsing_circuit = circuit
    line_number = 0
    try:
        with open(filename, 'r') as fil: content_lines = fil.readlines()
        idx = 0
        while idx < len(content_lines):
            current_line_segment = content_lines[idx]
            line_number = idx + 1; idx += 1
            full_line_for_parsing = current_line_segment.rstrip('\n\r')
            while idx < len(content_lines) and content_lines[idx].strip().startswith('+'):
                full_line_for_parsing += content_lines[idx].strip()[1:]
                idx += 1
            clean_line = full_line_for_parsing.strip()
            if not clean_line or clean_line.startswith('*') or clean_line.startswith('$'): continue
            new_context_circuit = parseline(clean_line, current_parsing_circuit)
            if new_context_circuit is None:
                 if current_parsing_circuit.parent is None and clean_line.strip().upper() == '.END':
                     logging.info(f"Reached .END for top-level circuit {current_parsing_circuit.name}. End of parsing.")
                     break
                 else:
                     logging.error(f"Critical error: parseline returned None at line {line_number}: {clean_line}.")
                     return circuit
            current_parsing_circuit = new_context_circuit
            if current_parsing_circuit is None: break
        if current_parsing_circuit is not circuit and circuit.parent is None : # Check if still in a subcircuit
            if hasattr(current_parsing_circuit, 'name'):
                 logging.warning(f"Parsing finished, but context is still in subcircuit '{current_parsing_circuit.name}'. Missing '.ENDS'?")
        return circuit
    except scs_errors.ScsParserError as e:
        logging.error(f"Parser error in file '{filename}' near line {line_number}: {e}")
        return None
    except IOError as e:
        logging.error(f"IOError accessing file '{filename}': {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error parsing file '{filename}' near line {line_number}: {e}")
        return None

__all__ = [
    'add_analysis', 'add_element', 'add_param', 'add_subcircuit',
    'change_to_parent_circuit', 'get_name_function_from_head',
    'get_parent_evaluated_param', 'get_params', 'get_unnamed_params',
    'evaluate_expresion', 'evaluate_param', 'evaluate_params', 'evaluate_passed_params',
    'include_file', 'parse_analysis_expresion',
    'parse_param_expresion', 'parse_file', 'parseline', 'strip_comment'
]
