# symbolic_circuit_solver-master/scs_analysis.py
import sympy as sp # Changed from sympy to sp
import sympy.abc
import warnings
import numpy as np
import matplotlib.pyplot as plt
import logging # Added for logging

import scs_parser
import scs_errors

# Attempt to import s_sym from the definitive source (root symbolic_components.py)
import sys
import os
current_script_dir_analysis = os.path.dirname(os.path.abspath(__file__))
project_root_dir_analysis = os.path.dirname(current_script_dir_analysis)
if project_root_dir_analysis not in sys.path:
    sys.path.insert(0, project_root_dir_analysis)

try:
    from symbolic_components import s_sym as s_sym_global # Use a distinct name
    print(f"DEBUG scs_analysis: Imported s_sym_global: {s_sym_global} (id: {id(s_sym_global)})")
except ImportError as e:
    print(f"DEBUG scs_analysis: Failed to import s_sym_global from symbolic_components: {e}")
    s_sym_global = sp.Symbol('s_fallback_analysis') # Fallback if import fails


# Helper to ensure a string value is properly converted to a Sympy numeric/symbolic expression
# Needed for .MEASURE and .DC/.AC line parameter substitutions
def _ensure_sympy_expr_from_str_for_analysis(val_str, inst_paramsd_context, parent_paramsd_context, prefix_for_temp_eval_param):
    # This is a simplified version of _ensure_sympy_expr in scs_instance_hier.py
    # It assumes val_str is an expression that needs to be evaluated using scs_parser.evaluate_param
    # if it's not directly sympifiable.
    # For robustness, this should ideally call the main _ensure_sympy_expr if available,
    # or scs_parser.evaluate_expresion if val_str can be complex.
    # For now, direct sympify with SYMPYFY_LOCALS_BASE from scs_parser.
    try:
        # Try direct sympification with a basic set of locals
        return sp.sympify(val_str, locals=scs_parser.SYMPYFY_LOCALS_BASE)
    except (sp.SympifyError, TypeError):
        # If direct sympify fails, it might be a parameter that needs evaluation.
        # This part is tricky as evaluate_param needs a dict of params to evaluate.
        # This helper is a placeholder for a more robust solution if needed.
        logging.warning(f"Could not directly sympify '{val_str}' in analysis substitution. Attempting as raw symbol or keeping as string for later stages if applicable.")
        # Fallback: treat as a symbol or let higher level handle it.
        # For now, let's rely on evaluate_expresion to handle it if it's part of a larger expression.
        # If it's a direct value for substitution, it must be parseable.
        # This indicates that parameters on .AC/.DC/.MEASURE lines must be numbers or simple expressions.
        # For this version, we'll stick to the original code's direct sympify for such params where it was used.
        # The main expressions (V(N1) etc.) go through evaluate_expresion.
        # The original code for .DC/.AC substitutions:
        # value = float(sympy.sympify(scs_parser.params2values(tokens, instance.paramsd),sympy.abc._clash))
        # This implies params2values (which is now evaluate_expresion) should return something floatable.
        # Let's assume for now that .MEASURE/.DC/.AC substitutions are simple numeric strings.
        return sp.sympify(val_str) # Retry without locals if SYMPYFY_LOCALS_BASE was too restrictive


def measure_analysis(param_d, param_l, instance, file_sufix):
    filename = "%s.results" % file_sufix
    logging.info(f"Executing .MEASURE. Params: {param_l}, Dict: {param_d}")
    out_lines = []

    measure_type = param_l[0].upper()
    measure_name = param_l[1]
    out_lines.append(f"{measure_name}:")

    # Prepare substitutions from param_d (e.g., from .MEASURE line itself like FREQ=1k)
    measure_subs = {}
    for key, val_str in param_d.items():
        try:
            # These values in param_d are strings and need evaluation.
            # Using a simplified sympify here, assuming they are numbers or simple math.
            measure_subs[sp.Symbol(key)] = sp.sympify(val_str, locals=scs_parser.SYMPYFY_LOCALS_BASE)
        except Exception as e:
            logging.warning(f"Cannot sympify .MEASURE parameter {key}={val_str}: {e}")

    for expr_str_to_measure in param_l[2:]:
        out_lines.append(f"  Expression: {expr_str_to_measure}")
        logging.info(f"  Measuring: {expr_str_to_measure}")
        try:
            symbolic_expr_from_eval = scs_parser.evaluate_expresion(expr_str_to_measure, instance)
            logging.debug(f"    Raw symbolic from eval: {symbolic_expr_from_eval}, free: {symbolic_expr_from_eval.free_symbols if hasattr(symbolic_expr_from_eval,'free_symbols') else 'N/A'}")

            value_after_measure_subs = symbolic_expr_from_eval.subs(measure_subs) if measure_subs and hasattr(symbolic_expr_from_eval,'subs') else symbolic_expr_from_eval
            logging.debug(f"    After measure subs: {value_after_measure_subs}, free: {value_after_measure_subs.free_symbols if hasattr(value_after_measure_subs,'free_symbols') else 'N/A'}")

            final_value = value_after_measure_subs
            if measure_type == 'AC':
                # OMEGA comes from .AC line, stored in instance.paramsd by scs_parser.add_analysis -> Analysis object
                # then passed to ac_analysis, but measure_analysis needs it too.
                # Let's assume 'omega' or 'OMEGA' is in instance.paramsd if set by .AC OMEGA
                omega_val = instance.paramsd.get(sp.Symbol('omega'), instance.paramsd.get(sp.Symbol('OMEGA')))
                if omega_val is not None:
                    s_replacement = sp.I * omega_val
                    if hasattr(final_value, 'subs') and s_sym_global in final_value.free_symbols:
                        final_value = final_value.subs({s_sym_global: s_replacement})
                        logging.debug(f"    Substituted s={s_replacement} for AC measure: {final_value}")
                else:
                    logging.warning(f"    AC Measure, but no OMEGA found in instance.paramsd. Result for '{expr_str_to_measure}' might be symbolic in s.")

            if hasattr(final_value, 'simplify'): final_value = final_value.simplify()
            out_lines.append(f"  Symbolic Value: {sp.pretty(final_value)}")
            num_val_str = "Could not evalf"
            if hasattr(final_value, 'evalf'):
                try: num_val_str = str(final_value.evalf(chop=True))
                except Exception as e_evalf: logging.warning(f"Could not evalf {final_value}: {e_evalf}")
            out_lines.append(f"  Numerical Value: {num_val_str}")

        except Exception as e:
            logging.error(f"Error evaluating .MEASURE expression '{expr_str_to_measure}': {e}", exc_info=True)
            out_lines.append(f"  ERROR: Could not evaluate - {e}")
        out_lines.append("---------------------")

    with open(filename, 'a') as fil: fil.write("\n".join(out_lines) + "\n\n")


class PlotNumber:
    plot_num = 0
    def __init__(self): pass

def dc_analysis(param_d, param_l, instance, file_sufix):
    config = {'sweep': None,'xstart': 1,'xstop': 10,'xscale': 'linear','npoints': 10,'yscale': 'linear',
              'hold': 'no','title': None,'show_legend': 'no','xkcd': 'no'}
    for config_name in list(config.keys()): # Use list for Py3
        if config_name in param_d: config.update({config_name: param_d.pop(config_name)}) # Pop consumed keys
    if not config['sweep']: raise scs_errors.ScsAnalysisError("No specified sweep parameter for .dc analysis")
    try: xsym = sp.Symbol(config['sweep'])
    except ValueError: raise scs_errors.ScsAnalysisError(f"Bad sweep parameter for .dc analysis: {config['sweep']}")

    subst_dc_line = [] # Substitutions from .DC line itself (e.g., V2=5)
    for symbol_str, value_str in param_d.items(): # Remaining items in param_d are fixed substitutions
        try:
            # These values should be numbers or simple expressions evaluatable now
            subst_dc_line.append((sp.Symbol(symbol_str), sp.sympify(value_str, locals=scs_parser.SYMPYFY_LOCALS_BASE)))
        except Exception as e: logging.warning(f"Cannot process DC line substitution {symbol_str}={value_str}: {e}")

    if config['xscale'] == 'log': xs_sweep_vals = np.logspace(np.log10(float(config['xstart'])), np.log10(float(config['xstop'])), int(config['npoints']))
    elif config['xscale'] == 'linear': xs_sweep_vals = np.linspace(float(config['xstart']), float(config['xstop']), int(config['npoints']))
    else: raise scs_errors.ScsAnalysisError(f"Option {config['xscale']} for xscale invalid!")
    if config['yscale'] not in ['log', 'linear']: raise scs_errors.ScsAnalysisError(f"Option {config['yscale']} for yscale invalid!")

    if config['xkcd'] == 'yes': plt.xkcd()
    fig, current_axes = plt.subplots() # Create new figure and axes for each .DC plot call
    current_axes.set_title(fr'$%s$' % config['title'] if config['title'] else 'DC Sweep Analysis')

    for expression_str_to_plot in param_l:
        symbolic_expr_from_eval = scs_parser.evaluate_expresion(expression_str_to_plot, instance)
        # For DC, s_sym_global (if present) is effectively 0.
        # Components should already reflect DC behavior if s_sym_global=0 was used in their value derivation (e.g. L=0, C=inf impedance)
        # Or, more directly, substitute s_sym_global=0 into the obtained expression.
        expr_at_dc = symbolic_expr_from_eval.subs({s_sym_global: 0}) if hasattr(symbolic_expr_from_eval, 'subs') else symbolic_expr_from_eval
        expr_for_sweep = expr_at_dc.subs(subst_dc_line) if subst_dc_line and hasattr(expr_at_dc,'subs') else expr_at_dc
        
        logging.debug(f"DC plot: Expr '{expression_str_to_plot}', for sweep var '{xsym}': {expr_for_sweep}, free: {expr_for_sweep.free_symbols if hasattr(expr_for_sweep,'free_symbols') else 'N/A'}")
        
        if not hasattr(expr_for_sweep, 'free_symbols') or expr_for_sweep.free_symbols == {xsym} or not expr_for_sweep.free_symbols:
            # Expression is constant or only depends on the sweep variable
            lambdified_func = sp.lambdify(xsym, expr_for_sweep, modules=['numpy', 'sympy'])
            try:
                ys_plot_values = np.array([lambdified_func(x_val) for x_val in xs_sweep_vals], dtype=np.float64)
                current_axes.plot(xs_sweep_vals, ys_plot_values, label=expression_str_to_plot)
            except Exception as e: logging.error(f"Error plotting DC for {expression_str_to_plot}: {e}. Value: {expr_for_sweep}", exc_info=True)
        else: logging.warning(f"DC Expr {expression_str_to_plot} has too many free symbols for sweep: {expr_for_sweep.free_symbols}. Expected only {xsym} or none.")

    current_axes.set_xscale(config['xscale']); current_axes.set_yscale(config['yscale'])
    current_axes.set_xlabel(fr'$%s$' % str(xsym)); current_axes.set_ylabel('Values')
    if config['show_legend'] == 'yes': current_axes.legend()
    if config['hold'] == 'no':
        plt.savefig(f'%s_dc_{PlotNumber.plot_num}.png' % file_sufix); PlotNumber.plot_num += 1
    plt.close(fig) # Close figure to free memory


def ac_analysis(param_d, param_l, instance, file_sufix):
    warnings.filterwarnings('ignore', category=UserWarning)
    f_sym_for_lambdify = sp.Symbol('f_freq_sweep_var', real=True, positive=True)

    config = {'fstart': 1, 'fstop': 1e6, 'fscale': 'log', 'npoints': 100, 'yscale': 'log',
              'type': 'amp', 'hold': 'no', 'show_poles': 'yes', 'show_zeros': 'yes',
              'title': None, 'show_legend': 'no', 'xkcd': 'no'}
    for config_name in list(config.keys()): # Use list for Py3
        if config_name in param_d: config.update({config_name: param_d.pop(config_name)})

    fixed_param_subs_for_ac = []
    if hasattr(instance, 'paramsd'):
        for symbol_str, value_str in param_d.items():
            try: fixed_param_subs_for_ac.append((sp.Symbol(symbol_str), _ensure_sympy_expr_from_str_for_analysis(value_str, instance.paramsd, instance.parent.paramsd if instance.parent else {}, "_ac_param")))
            except Exception as e: logging.warning(f"Cannot process AC line substitution {symbol_str}={value_str}: {e}")

    if config['fscale'] == 'log': fs_sweep_values = np.logspace(np.log10(float(config['fstart'])), np.log10(float(config['fstop'])), int(config['npoints']))
    elif config['fscale'] == 'linear': fs_sweep_values = np.linspace(float(config['fstart']), float(config['fstop']), int(config['npoints']))
    else: raise scs_errors.ScsAnalysisError(f"Option {config['fscale']} for fscale invalid!")
    if config['yscale'] not in ['log', 'linear']: raise scs_errors.ScsAnalysisError(f"Option {config['yscale']} for yscale invalid!")

    filename_results_text = "%s.results" % file_sufix
    with open(filename_results_text, 'a') as fil:
        if config['xkcd'] == 'yes': plt.xkcd()
        fig, current_axes = plt.subplots() # New figure for each .AC call.
        current_axes.set_title(fr'$%s$' % config['title'] if config['title'] else 'AC Analysis', y=1.05)

        for expression_str_to_plot in param_l:
            fil.write(f"AC analysis of: {expression_str_to_plot} \n---------------------\n")
            symbolic_expr_s_domain = scs_parser.evaluate_expresion(expression_str_to_plot, instance)
            fil.write(f"  Symbolic Expression (s-domain): {sp.pretty(symbolic_expr_s_domain)}\n")

            expr_after_fixed_params = symbolic_expr_s_domain.subs(fixed_param_subs_for_ac) if fixed_param_subs_for_ac and hasattr(symbolic_expr_s_domain,'subs') else symbolic_expr_s_domain
            logging.debug(f"AC plot: Expr '{expression_str_to_plot}', after fixed params: {expr_after_fixed_params}, free: {expr_after_fixed_params.free_symbols if hasattr(expr_after_fixed_params,'free_symbols') else 'N/A'}")
            fil.write(f"  After fixed params sub: {sp.pretty(expr_after_fixed_params)}\n")

            s_replacement_expr = sp.I * 2 * sp.pi * f_sym_for_lambdify
            value_expr_for_lambdify = expr_after_fixed_params.subs({s_sym_global: s_replacement_expr})
            logging.debug(f"AC plot: Expr for lambdify (terms of f_sweep_var '{f_sym_for_lambdify}'): {value_expr_for_lambdify}")
            fil.write(f"  Expression for lambdify (terms of f): {sp.pretty(value_expr_for_lambdify)}\n")
            logging.debug(f"AC plot: Free symbols before lambdify: {value_expr_for_lambdify.free_symbols if hasattr(value_expr_for_lambdify,'free_symbols') else 'N/A'}")

            plot_expr_for_lambdify_final = None
            ylabel = ""
            if config['type'] == 'amp':
                plot_expr_for_lambdify_final = sp.Abs(value_expr_for_lambdify)
                ylabel = f'|{expression_str_to_plot}|'
            elif config['type'] == 'phase':
                # Phase in degrees for plotting
                plot_expr_for_lambdify_final = (sp.arg(value_expr_for_lambdify) * 180 / sp.pi)
                ylabel = f'Phase({expression_str_to_plot}) [deg]'
            else: raise scs_errors.ScsAnalysisError(f"Option {config['type']} for AC plot type invalid!")

            logging.debug(f"AC plot: Plot expression for lambdify: {plot_expr_for_lambdify_final}, free_symbols: {plot_expr_for_lambdify_final.free_symbols if hasattr(plot_expr_for_lambdify_final,'free_symbols') else 'N/A'}")

            if not hasattr(plot_expr_for_lambdify_final, 'free_symbols') or \
               plot_expr_for_lambdify_final.free_symbols == {f_sym_for_lambdify} or \
               not plot_expr_for_lambdify_final.free_symbols :

                lambdified_func = sp.lambdify(f_sym_for_lambdify, plot_expr_for_lambdify_final, modules=['numpy', {"Abs": np.abs, "arg": np.angle}]) # More explicit mapping
                try:
                    ys_plot_values = np.array([lambdified_func(f_val) for f_val in fs_sweep_values], dtype=np.float64)
                    current_axes.plot(fs_sweep_values, ys_plot_values, label=expression_str_to_plot)
                except Exception as e:
                    logging.error(f"Error during AC lambdify/plotting for '{expression_str_to_plot}': {e}", exc_info=True)
            else:
                logging.warning(f"AC Expr '{expression_str_to_plot}' (plot form: {plot_expr_for_lambdify_final}) has unexpected free symbols for sweep: {plot_expr_for_lambdify_final.free_symbols}. Expected only '{f_sym_for_lambdify}'.")

            # Pole-zero text output (simplified)
            try:
                s_domain_expr_for_pz = expr_after_fixed_params # Use expression before s->jwf substitution
                if hasattr(s_domain_expr_for_pz, 'as_numer_denom'):
                    num, den = s_domain_expr_for_pz.as_numer_denom()
                    if num.is_polynomial(s_sym_global) and den.is_polynomial(s_sym_global):
                        poles = sp.solve(den, s_sym_global); zeros = sp.solve(num, s_sym_global)
                        fil.write(f"  Poles (rad/s): {poles}\n  Zeros (rad/s): {zeros}\n")
            except Exception as e_pz: logging.warning(f"Could not calculate poles/zeros for {expression_str_to_plot}: {e_pz}")
            fil.write('\n\n')

        current_axes.set_xscale(config['fscale']); current_axes.set_yscale(config['yscale'])
        current_axes.set_xlabel('Frequency [Hz]'); current_axes.set_ylabel(ylabel)
        if config['show_legend'] == 'yes': current_axes.legend()
        if config['hold'] == 'no':
            plt.savefig(f'%s_ac_{PlotNumber.plot_num}.png' % file_sufix); PlotNumber.plot_num += 1
        plt.close(fig) # Close figure to free memory

analysis_dict = {'measure': measure_analysis, 'ac': ac_analysis, 'dc': dc_analysis}

if not hasattr(scs_parser, '_ensure_sympy_expr_from_str'):
    logging.info("DEBUG scs_analysis: scs_parser._ensure_sympy_expr_from_str polyfill used.")
    def _temp_ensure_from_str(val_str, current_inst_paramsd, parent_inst_paramsd, prefix_hint):
        # This is a simplified placeholder. Proper evaluation should use scs_parser.evaluate_param
        # or a robust version of _ensure_sympy_expr from scs_instance_hier.
        # For now, try direct sympify with basic locals.
        return sp.sympify(val_str, locals=scs_parser.SYMPYFY_LOCALS_BASE)
    scs_parser._ensure_sympy_expr_from_str = _temp_ensure_from_str
