# solver_dev_workspace/symbolic_circuit_solver-master/scs_analysis.py
import sympy as sp
# import sympy.abc # Not typically used if using 'sp'
import warnings
import numpy as np
import matplotlib.pyplot as plt # Capital 'P' is conventional for pyplot
import logging # Ensure logging is imported

# scs_parser and scs_errors are in the same directory (symbolic_circuit_solver-master)
import scs_parser
import scs_errors

# Robust import for root-level all_symbolic_components.py (now one level up)
import sys
import os
current_script_dir_analysis = os.path.dirname(os.path.abspath(__file__))
# project_workspace_root is the parent directory of symbolic_circuit_solver-master, which is solver_dev_workspace
project_workspace_root = os.path.dirname(current_script_dir_analysis)
if project_workspace_root not in sys.path:
    sys.path.insert(0, project_workspace_root)

try:
    from all_symbolic_components import s_sym as s_sym_global
    print(f"DEBUG scs_analysis: Successfully imported s_sym_global: {s_sym_global} (id: {id(s_sym_global)}) from all_symbolic_components.py")
    logging.info(f"DEBUG scs_analysis: Successfully imported s_sym_global: {s_sym_global} (id: {id(s_sym_global)}) from all_symbolic_components.py") # Added logging
except ImportError as e:
    print(f"CRITICAL ERROR in scs_analysis.py: Failed to import s_sym_global from all_symbolic_components: {e}")
    logging.critical(f"CRITICAL ERROR in scs_analysis.py: Failed to import s_sym_global from all_symbolic_components: {e}") # Added logging
    s_sym_global = sp.Symbol('s_fallback_analysis_critical_s_sym') # Fallback

# Local sympify context if scs_analysis.py does direct sympification not through scs_parser.evaluate_expresion
LOCAL_SYMPYFY_CONTEXT_ANALYSIS = {
    's': s_sym_global, 'I': sp.I, 'exp': sp.exp, 'sin': sp.sin, 'cos': sp.cos,
    'tan': sp.tan, 'pi': sp.pi, 'sqrt': sp.sqrt, 'log': sp.log,
    'MAG': sp.Abs, 'ABS': sp.Abs, 'ARG': sp.arg, 'PHASE': sp.arg,
    'DEG': lambda x_arg: sp.deg(x_arg) if hasattr(x_arg, 'is_complex') or (hasattr(x_arg, 'is_number') and x_arg.is_number) else x_arg,
    'RE': sp.re, 'IM': sp.im
}

# Polyfill for _ensure_sympy_expr_from_str IF scs_parser.py doesn't have it
if not hasattr(scs_parser, '_ensure_sympy_expr_from_str'):
    logging.warning("DEBUG scs_analysis: scs_parser._ensure_sympy_expr_from_str not found. Defining temporary fallback.") # Changed print to logging
    def _temp_ensure_from_str_for_analysis(val_str, context_params, parent_context_params, temp_param_prefix="_temp_analysis_param"):
        if isinstance(val_str, (sp.Expr, int, float, complex)): return sp.sympify(val_str)
        try:
            return sp.sympify(val_str, locals=LOCAL_SYMPYFY_CONTEXT_ANALYSIS)
        except (sp.SympifyError, TypeError):
            if context_params and val_str in context_params: return sp.sympify(context_params[val_str], locals=LOCAL_SYMPYFY_CONTEXT_ANALYSIS) # Sympify context param too
            if parent_context_params and val_str in parent_context_params: return sp.sympify(parent_context_params[val_str], locals=LOCAL_SYMPYFY_CONTEXT_ANALYSIS)
            logging.warning(f"Warning (scs_analysis): Could not fully evaluate '{val_str}' as expression or param. Treating as symbol.")
            return sp.Symbol(val_str)
    scs_parser._ensure_sympy_expr_from_str = _temp_ensure_from_str_for_analysis


def measure_analysis(param_d, param_l, instance, file_sufix):
    filename = "%s.results" % file_sufix
    logging.info(f"Executing .MEASURE. Name: {param_l[0]} Expressions: {param_l[1:]}, Params: {param_d}")
    out_lines = []; measure_name = param_l[0]
    out_lines.append(f"{measure_name}:")
    measure_subs = {}
    if hasattr(instance, 'paramsd'):
        for key, val_str in param_d.items():
            try:
                measure_subs[sp.Symbol(key)] = scs_parser._ensure_sympy_expr_from_str(val_str, instance.paramsd, instance.parent.paramsd if instance.parent else {}, f"_meas_{key}")
            except Exception as e: logging.warning(f"Warning: could not eval .MEASURE param {key}={val_str}: {e}")

    for expr_str_to_measure in param_l[1:]:
        out_lines.append(f"  Expression: {expr_str_to_measure}")
        symbolic_expr_from_eval = scs_parser.evaluate_expresion(expr_str_to_measure, instance)
        value_after_measure_subs = symbolic_expr_from_eval.subs(measure_subs) if measure_subs and hasattr(symbolic_expr_from_eval,'subs') else symbolic_expr_from_eval
        final_value_for_measure = value_after_measure_subs

        omega_val_from_ac_line = None
        if hasattr(instance, 'paramsd'):
            omega_val_from_ac_line = instance.paramsd.get(sp.Symbol('OMEGA'), instance.paramsd.get('OMEGA'))

        if hasattr(value_after_measure_subs, 'free_symbols') and s_sym_global in value_after_measure_subs.free_symbols and \
           omega_val_from_ac_line is not None:
            try:
                num_omega_test = sp.sympify(omega_val_from_ac_line)
                if num_omega_test.is_number: # Check if it's a number before evalf
                    num_omega = num_omega_test.evalf()
                    s_replacement = sp.I * num_omega
                    final_value_for_measure = value_after_measure_subs.subs({s_sym_global: s_replacement})
                    out_lines.append(f"  Substituted s={s_replacement.evalf(chop=True)} (omega={num_omega}) for AC measure.")
                else:
                    logging.warning(f"OMEGA value '{omega_val_from_ac_line}' is not numeric, cannot substitute s in .MEASURE.")
            except Exception as e:
                logging.warning(f"Could not substitute s for omega='{omega_val_from_ac_line}' in .MEASURE for '{expr_str_to_measure}': {e}")

        out_lines.append(f"  Symbolic Value: {sp.pretty(final_value_for_measure)}")
        try: num_val = final_value_for_measure.evalf(chop=True); out_lines.append(f"  Numerical Value: {num_val}")
        except Exception as e: out_lines.append(f"  Numerical Value: Could not eval to float for '{expr_str_to_measure}' ({e})")
        out_lines.append("---------------------")
    with open(filename, 'a') as fil: fil.write("\n".join(out_lines) + "\n\n")

class PlotNumber:
    plot_num = 0
    def __init__(self):
        pass

def dc_analysis(param_d, param_l, instance, file_sufix):
    config = {'sweep': None,'xstart': 1,'xstop': 10,'xscale': 'linear','npoints': 10,'yscale': 'linear',
              'hold': 'no','title': None,'show_legend': 'no','xkcd': 'no'}
    for k in list(param_d.keys()):
        if k in config: config[k] = param_d.pop(k)
    if not config['sweep']: raise scs_errors.ScsAnalysisError("No sweep parameter for .dc")
    try: xsym = sp.Symbol(config['sweep'])
    except ValueError: raise scs_errors.ScsAnalysisError(f"Bad sweep parameter: {config['sweep']}")
    fixed_param_subs = []
    if hasattr(instance, 'paramsd'):
        for sym_str, val_str in param_d.items():
             try: fixed_param_subs.append((sp.Symbol(sym_str), scs_parser._ensure_sympy_expr_from_str(val_str, instance.paramsd, instance.parent.paramsd if instance.parent else {}, f"_dc_{sym_str}")))
             except Exception as e: logging.warning(f"Cannot process .DC line substitution {sym_str}={val_str}: {e}")
    if config['xscale'] == 'log': xs = np.logspace(np.log10(float(config['xstart'])), np.log10(float(config['xstop'])), int(config['npoints']))
    elif config['xscale'] == 'linear': xs = np.linspace(float(config['xstart']), float(config['xstop']), int(config['npoints']))
    else: raise scs_errors.ScsAnalysisError(f"Invalid xscale: {config['xscale']}")
    if config['yscale'] not in ['log', 'linear']: raise scs_errors.ScsAnalysisError(f"Invalid yscale: {config['yscale']}")
    if config['xkcd'] == 'yes': plt.xkcd()
    fig, current_axes = plt.subplots() # Use subplots for better figure management
    current_axes.set_title(fr'$%s$' % config['title'] if config['title'] else 'DC Sweep Analysis')
    for expression_str in param_l:
        value_expr_sym = scs_parser.evaluate_expresion(expression_str, instance)
        value_at_dc = value_expr_sym.subs({s_sym_global: 0}) if hasattr(value_expr_sym,'subs') else value_expr_sym # Use s_sym_global
        value_for_sweep = value_at_dc.subs(fixed_param_subs) if fixed_param_subs and hasattr(value_at_dc,'subs') else value_at_dc
        logging.debug(f"DC Analysis: Expr '{expression_str}', for sweep: {value_for_sweep}, free: {value_for_sweep.free_symbols if hasattr(value_for_sweep,'free_symbols') else 'N/A'}")
        if not hasattr(value_for_sweep,'free_symbols') or not value_for_sweep.free_symbols or value_for_sweep.free_symbols == {xsym}:
            yf = sp.lambdify(xsym, value_for_sweep, modules=['numpy', 'sympy'])
            try: ys = np.array([yf(x_val) for x_val in xs], dtype=np.float64); current_axes.plot(xs, ys, label=expression_str)
            except Exception as e: logging.warning(f"Warning: Could not plot DC for {expression_str}. Error: {e}. Value: {value_for_sweep}")
        else: logging.warning(f"Warning: DC Expr {expression_str} has too many free symbols: {value_for_sweep.free_symbols}. Expected only {xsym}.")
    current_axes.set_xscale(config['xscale']); current_axes.set_yscale(config['yscale']); current_axes.set_xlabel(fr'$%s$' % str(xsym)); current_axes.set_ylabel('Values')
    if config['show_legend'] == 'yes': current_axes.legend()
    if config['hold'] == 'no': plt.savefig(f'%s_dc_{PlotNumber.plot_num}.png' % file_sufix); PlotNumber.plot_num += 1
    plt.close(fig) # Close figure after saving if not holding


def ac_analysis(param_d, param_l, instance, file_sufix):
    warnings.filterwarnings('ignore', category=UserWarning)
    f_sym_for_lambdify = sp.Symbol('f_freq_sweep_var', real=True, positive=True)
    config = {'fstart': 1, 'fstop': 1e6, 'fscale': 'log', 'npoints': 100, 'yscale': 'log',
              'type': 'amp', 'hold': 'no', 'show_poles': 'yes', 'show_zeros': 'yes',
              'title': None, 'show_legend': 'no', 'xkcd': 'no'}
    for k in list(param_d.keys()):
        if k in config: config[k] = param_d.pop(k)
    fixed_param_subs_for_ac = []
    if hasattr(instance, 'paramsd'):
        for sym_str, val_str in param_d.items():
            try: fixed_param_subs_for_ac.append((sp.Symbol(sym_str), scs_parser._ensure_sympy_expr_from_str(val_str, instance.paramsd, instance.parent.paramsd if instance.parent else {}, f"_ac_{sym_str}")))
            except Exception as e: logging.warning(f"Cannot process .AC line substitution {sym_str}={val_str}: {e}")
    if config['fscale'] == 'log': fs_sweep_values = np.logspace(np.log10(float(config['fstart'])), np.log10(float(config['fstop'])), int(config['npoints']))
    elif config['fscale'] == 'linear': fs_sweep_values = np.linspace(float(config['fstart']), float(config['fstop']), int(config['npoints']))
    else: raise scs_errors.ScsAnalysisError(f"Invalid fscale: {config['fscale']}")
    if config['yscale'] not in ['log', 'linear']: raise scs_errors.ScsAnalysisError(f"Invalid yscale: {config['yscale']}")
    filename_results_text = "%s.results" % file_sufix
    with open(filename_results_text, 'a') as fil:
        if config['xkcd'] == 'yes': plt.xkcd()
        fig, current_axes = plt.subplots() # Use subplots for better figure management
        current_axes.set_title(fr'$%s$' % config['title'] if config['title'] else 'AC Analysis', y=1.05) # y for title padding
        for expression_str_to_plot in param_l:
            fil.write(f"AC analysis of: {expression_str_to_plot} \n---------------------\n")
            symbolic_expr_s_domain = scs_parser.evaluate_expresion(expression_str_to_plot, instance)
            expr_after_fixed_params = symbolic_expr_s_domain.subs(fixed_param_subs_for_ac) if fixed_param_subs_for_ac and hasattr(symbolic_expr_s_domain,'subs') else symbolic_expr_s_domain
            s_replacement_expr = sp.I * 2 * sp.pi * f_sym_for_lambdify
            value_expr_for_lambdify = expr_after_fixed_params.subs({s_sym_global: s_replacement_expr}) if hasattr(expr_after_fixed_params,'subs') else expr_after_fixed_params # Use s_sym_global
            logging.debug(f"AC Analysis: Expr '{expression_str_to_plot}' for lambdify: {value_expr_for_lambdify}")
            fil.write(f"  Expression for lambdify (terms of f): {sp.pretty(value_expr_for_lambdify)}\n")
            logging.debug(f"AC Analysis: Free symbols before lambdify: {value_expr_for_lambdify.free_symbols if hasattr(value_expr_for_lambdify,'free_symbols') else 'N/A'}")
            plot_expr_for_lambdify_final = None; ylabel = ""
            if config['type'] == 'amp':
                plot_expr_for_lambdify_final = sp.Abs(value_expr_for_lambdify); ylabel = f'|{expression_str_to_plot}|'
            elif config['type'] == 'phase':
                plot_expr_for_lambdify_final = (sp.arg(value_expr_for_lambdify) * 180 / sp.pi); ylabel = f'Phase({expression_str_to_plot}) [deg]'
            else: raise scs_errors.ScsAnalysisError(f"Invalid AC plot type: {config['type']}")
            logging.debug(f"AC Analysis: Plot expression for lambdify: {plot_expr_for_lambdify_final}")
            logging.debug(f"AC Analysis: Free symbols in plot_expr: {plot_expr_for_lambdify_final.free_symbols if hasattr(plot_expr_for_lambdify_final,'free_symbols') else 'N/A'}")
            if not hasattr(plot_expr_for_lambdify_final,'free_symbols') or not plot_expr_for_lambdify_final.free_symbols or plot_expr_for_lambdify_final.free_symbols == {f_sym_for_lambdify}:
                lambdify_modules = [{'Abs': np.abs, 'arg': np.angle}, 'numpy']
                lambdified_func = sp.lambdify(f_sym_for_lambdify, plot_expr_for_lambdify_final, modules=lambdify_modules)
                try:
                    ys_plot_values = np.array([lambdified_func(f_val) for f_val in fs_sweep_values], dtype=np.float64)
                    current_axes.plot(fs_sweep_values, ys_plot_values, label=expression_str_to_plot)
                except Exception as e: logging.warning(f"ERROR during AC lambdify/plotting for '{expression_str_to_plot}': {e}") # Changed to warning
            else: logging.warning(f"Warning: AC Expr '{expression_str_to_plot}' has unexpected free symbols: {plot_expr_for_lambdify_final.free_symbols}")

            try:
                s_domain_expr_for_pz = expr_after_fixed_params
                if hasattr(s_domain_expr_for_pz, 'as_numer_denom'):
                    num, den = s_domain_expr_for_pz.as_numer_denom()
                    if hasattr(num,'is_polynomial') and num.is_polynomial(s_sym_global) and \
                       hasattr(den,'is_polynomial') and den.is_polynomial(s_sym_global):
                        poles = sp.solve(den, s_sym_global); zeros = sp.solve(num, s_sym_global)
                        fil.write(f"  Poles (rad/s): {poles}\n  Zeros (rad/s): {zeros}\n")
            except Exception as e_pz: logging.warning(f"Could not calculate poles/zeros for {expression_str_to_plot}: {e_pz}")
            fil.write('\n\n')
        current_axes.set_xscale(config['fscale']); current_axes.set_yscale(config['yscale']); current_axes.set_xlabel('Frequency [Hz]'); current_axes.set_ylabel(ylabel)
        if config['show_legend'] == 'yes': current_axes.legend()
        if config['hold'] == 'no': plt.savefig(f'%s_ac_{PlotNumber.plot_num}.png' % file_sufix); PlotNumber.plot_num += 1
        plt.close(fig) # Close figure after saving if not holding

analysis_dict = {'measure': measure_analysis, 'ac': ac_analysis, 'dc': dc_analysis}

# Final check and log for the polyfill status (from prompt)
if hasattr(scs_parser, '_ensure_sympy_expr_from_str') and scs_parser._ensure_sympy_expr_from_str.__name__ == '_temp_ensure_from_str_for_analysis':
    logging.info("scs_analysis.py is using its temporary polyfill for scs_parser._ensure_sympy_expr_from_str for .AC/.DC line parameter evaluation.")
elif not hasattr(scs_parser, '_ensure_sympy_expr_from_str'):
     logging.error("CRITICAL: scs_parser._ensure_sympy_expr_from_str is MISSING and polyfill FAILED to set.")
else:
    logging.info("scs_analysis.py: scs_parser._ensure_sympy_expr_from_str seems to be present from scs_parser itself.")
