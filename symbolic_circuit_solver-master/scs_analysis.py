"""
    Module holding functions for performing analysis on solved instances of circuits.
"""
import sympy
import sympy.abc
import warnings
import numpy as np
import matplotlib.pyplot as plt

import scs_parser
import scs_errors

__author__ = "Tomasz Kniola"
__credits__ = ["Tomasz Kniola"]

__license__ = "LGPL"
__version__ = "0.0.1"
__email__ = "kniola.tomasz@gmail.com"
__status__ = "development"


def measure_analysis(param_d, param_l, instance, file_sufix):
    """ Performs measure analysis
        
        param_d: substitutions for symbols, should evaluate to numeric values
        
        param_l: expresions to print

        filename: filename for output of print analysis

        Measure analisis format is:
        .measure measure_name expresion1 [expresion2 ...]  [symbol0 = value0 symbol1 = value1 ...]    
        
        expresion are on param_l - poistional parameters list, which can hold expresion using parameters,
        and/or function of nodal voltages [v(node)] and element and port currents [i(element) isub(port)] 
        and symbols subsitutions are on param_d - dictionary of params, substitutions will be done as they are, 
        without any parsing

        value of a measue will be saved on instance.paramsd dictionary with measute_name which allows it to be used
        in next analysis. This feature can be abused to show parametric plots of ac and dc.
    """
    filename = "%s.results" % file_sufix
    subst = []
    for symbol, value in param_d.items(): #iteritems() -> items()
        # tokens = scs_parser.parse_param_expresion(value)
        # try:
        #    value =  float(sympy.sympify(scs_parser.params2values(tokens,instance.paramsd)))
        # except ValueError:
        #    logging.error("Passed subsitution for %s is not a number, aborting analysis")
        #    return
        subst.append((symbol, value))

    print_name = param_l[0]

    for expresion in param_l[1:]:
        tokens = scs_parser.parse_analysis_expresion(expresion)
        value = sympy.factor(sympy.sympify(scs_parser.results2values(tokens, instance),sympy.abc._clash), sympy.symbols('s'))
        # value =  sympy.sympify(scs_parser.results2values(tokens,instance)).simplify()
        value = value.subs(subst).simplify()
        instance.paramsd.update({print_name: value})
        with open(filename, 'a') as fil:
            fil.write("%s: %s \n---------------------\n" % (print_name, expresion))
            fil.write(str(value))
            fil.write("\n\n")


class PlotNumber:
    """ Just to keep track of how many files were saved to a file not to overwrite them
    """
    plot_num = 0

    def __init__(self):
        pass


def dc_analysis(param_d, param_l, instance, file_sufix):
    """ Performs dc analysis

        param_d: substitutions for symbols, or named parameters for plot
        
        param_l: expresions to plot

        format is:
        .dc expresion0 [expresion1 expresion2 ...] sweep = parameter_to_sweep [symmbol_or_option0 = value0
        symmbol_or_option1 = value1 ...]
        
        expresions are on positiona parameters list can hold expresions containing parameters or functions of nodal
        voltages [v(node)] and element and port currents [i(element) isub(port)]

        named parameters (param_d) can contain options for analysis or substitutions for symbols, substituions
        will be done as they are without any parsing, be aware of symbol and option names clashes.

        Config options:
        sweep:          name of symbol for which values dc analysis will be performed for each point
        xstart:         first value of sweep [float]
        xstop:          last value of sweep [float]
        xscale:         scale for x points (sweep values) [linear | log]
        npoints:        numbers of points for dc sweep [integer]
        yscale:         scale for y-axis to being displayed on [linear or log]
        hold:           hold plot for next analysis and don't save it to file [yes | no]
        title:          display title above dc plot [string]
        show_legend:    show legend on plot [yes | no]
        xkcd:           style plot to be xkcd like scetch
    """
    config = {'sweep': None,  # Name of the variable to be an x - parameter, must be filled!
              'xstart': 1,
              'xstop': 10,
              'xscale': 'linear',
              'npoints': 10,
              'yscale': 'linear',
              'hold': 'no',
              'title': None,
              'show_legend': 'no',
              'xkcd': 'no'}

    for config_name in list(config.keys()): # Use list(config.keys()) for Py3 if modifying dict
        if config_name in param_d:
            config.update({config_name: param_d[config_name]})
            param_d.pop(config_name)

    if not config['sweep']:
        raise scs_errors.ScsAnalysisError("No specified sweep parameter for .dc analysis")

    try:
        xsym = sympy.symbols(config['sweep'])
    except ValueError: # No 'as e' needed if not using e
        raise scs_errors.ScsAnalysisError("Bad sweep parameter for .dc analysis: %s" % config['sweep'])

    subst = []
    for symbol, value in param_d.items(): # iteritems() -> items()
        tokens = scs_parser.parse_param_expresion(value)
        try:
            value = float(sympy.sympify(scs_parser.params2values(tokens, instance.paramsd),sympy.abc._clash))
        except ValueError:
            raise scs_errors.ScsAnalysisError("Passed subsitution for %s is not a number")
        subst.append((symbol, value))

    s = sympy.symbols('s')

    if config['xscale'] == 'log':
        xs = np.logspace(np.log10(float(config['xstart'])),
                         np.log10(float(config['xstop'])),
                         int(config['npoints']))
    elif config['xscale'] == 'linear':
        xs = np.linspace(float(config['xstart']), float(config['xstop']), int(config['npoints']))
    else:
        raise scs_errors.ScsAnalysisError(("Option %s for xscale invalid!" % config['yscale'])) # Should be config['xscale']

    if config['yscale'] != 'log' and config['yscale'] != 'linear':
        raise scs_errors.ScsAnalysisError(("Option %s for yscale invalid!" % config['fscale'])) # Should be config['yscale']

    if config['xkcd'] == 'yes':
        plt.xkcd()

    fig, ax = plt.subplots() # Create figure and axes for holding
    if config['title']:
        ax.set_title(r'$%s$' % config['title'])
    # plt.hold(True) is deprecated. Plotting on 'ax' handles this.

    for expresion in param_l:
        tokens = scs_parser.parse_analysis_expresion(expresion)
        value0 = sympy.sympify(scs_parser.results2values(tokens, instance),sympy.abc._clash).subs(s, 0).simplify()
        value = value0.subs(subst)
        yf = sympy.lambdify(xsym, value, modules=['numpy', 'sympy']) # Add modules for lambdify
        try:
            ys = [float(yf(x)) for x in xs] # Ensure yf returns float-able
        except (ValueError, TypeError) as e: # Corrected Syntax
            raise scs_errors.ScsAnalysisError(
                "Numeric error while evaluating expresions: %s. Not all values where subsituted? Error: %s" % (value, e))

        ax.plot(xs, ys, label=expresion)
        try:
            ax.set_xscale(config['xscale'])
            ax.set_yscale(config['yscale'])
        except ValueError as e: # Corrected Syntax
            raise scs_errors.ScsAnalysisError(str(e)) # Use str(e)

        ax.set_xlabel(r'$%s$' % str(xsym))

    if config['show_legend'] == 'yes':
        ax.legend()
    if config['hold'] == 'no':
        plt.savefig('%s_%d.png' % (file_sufix, PlotNumber.plot_num))
        PlotNumber.plot_num += 1
        plt.close(fig) # Close the figure to free memory if not holding
    # else: figure 'fig' is kept for further plots if hold is 'yes'


def ac_analysis(param_d, param_l, instance, file_sufix):
    warnings.filterwarnings('ignore')
    s, w = sympy.symbols(('s', 'w'))
    config = {'fstart': 1, 'fstop': 1e6, 'fscale': 'log', 'npoints': 100,
              'yscale': 'log', 'type': 'amp', 'hold': 'no', 'show_poles': 'yes',
              'show_zeros': 'yes', 'title': None, 'show_legend': 'no', 'xkcd': 'no'}

    for config_name in list(config.keys()): # Use list for Py3
        if config_name in param_d:
            config.update({config_name: param_d[config_name]})
            param_d.pop(config_name)

    subst = []
    for symbol, value in param_d.items(): # iteritems() -> items()
        tokens = scs_parser.parse_param_expresion(value)
        try:
            value = float(sympy.sympify(scs_parser.params2values(tokens, instance.paramsd),sympy.abc._clash))
        except ValueError:
            raise scs_errors.ScsAnalysisError("Passed subsitution for %s is not a number")
        subst.append((symbol, value))

    if config['fscale'] == 'log':
        fs = np.logspace(np.log10(float(config['fstart'])), np.log10(float(config['fstop'])), int(config['npoints']))
    elif config['fscale'] == 'linear':
        fs = np.linspace(float(config['fstart']), float(config['fstop']), int(config['npoints']))
    else:
        raise scs_errors.ScsAnalysisError(("Option %s for fscale invalid!" % config['fscale']))

    if config['yscale'] != 'log' and config['yscale'] != 'linear':
        raise scs_errors.ScsAnalysisError(("Option %s for yscale invalid!" % config['yscale']))

    filename = "%s.results" % file_sufix

    with open(filename, 'a') as fil:
        if config['xkcd'] == 'yes': plt.xkcd()

        fig, ax = plt.subplots() # Create figure and axes
        if config['title']: ax.set_title(r'$%s$' % config['title'], y=1.05)
        # plt.hold(True) is deprecated

        for expresion in param_l:
            fil.write("%s: %s \n---------------------\n" % ('AC analysis of', expresion))
            tokens = scs_parser.parse_analysis_expresion(expresion)
            value0 = sympy.factor(sympy.sympify(scs_parser.results2values(tokens, instance),sympy.abc._clash), s).simplify()
            fil.write("%s = %s \n\n" % (expresion, str(value0)))

            # Pole/Zero calculation can be complex and error-prone if value0 is not a simple rational function in s
            try:
                denominator = sympy.denom(value0)
                numerator = sympy.numer(value0)
                poles = sympy.solve(denominator, s)
                zeros = sympy.solve(numerator, s)
                # poles_r = sympy.roots(denominator, s) # roots() may not work for complex symbolic
                # zeros_r = sympy.roots(numerator, s)
            except Exception as e:
                logging.warning(f"Could not reliably find poles/zeros for {expresion}: {e}")
                poles, zeros = [],[]

            gdc = str(value0.subs(s, 0).simplify()) # DC gain if s=0 is valid
            fil.write('G_DC = %s\n\n' % gdc)

            value = value0.subs(subst)
            f_sym = sympy.symbols('f_freq', real=True) # Use a different symbol for frequency to avoid clash
            value_at_f = value.subs(s, sympy.sympify('2*pi*I').evalf() * f_sym)

            # Lambdify for magnitude and phase
            # It's often better to lambdify the complex function and compute abs/arg in numpy
            complex_tf_func = sympy.lambdify(f_sym, value_at_f, modules=['numpy', 'sympy'])

            ys_mag = np.abs(complex_tf_func(fs))
            ys_phase = np.angle(complex_tf_func(fs), deg=True) # angle in degrees

            if config['type'] == 'amp':
                ys_to_plot = ys_mag
                ylabel = '|T(f)|'
            elif config['type'] == 'phase':
                ys_to_plot = ys_phase
                ylabel = 'ph(T(f)) [deg]'
            else: # Default to amplitude or raise error
                ys_to_plot = ys_mag
                ylabel = '|T(f)|'
                # raise scs_errors.ScsAnalysisError("Option %s for type invalid!" % config['type'])


            ax.plot(fs, ys_to_plot, label=expresion)
            ax.set_xscale(config['fscale'])
            ax.set_yscale(config['yscale'])
            ax.set_xlabel('f [Hz]')
            ax.set_ylabel(ylabel)

            if len(poles): fil.write('Poles (s-domain): \n')
            for p_idx, pole_val in enumerate(poles):
                try:
                    pole_subst = pole_val.subs(subst)
                    fil.write('  p_%d = %s\n' % (p_idx, str(pole_subst.evalf(chop=True))))
                    # Plotting poles/zeros on frequency response needs conversion from s to f
                    # This is simplified, assumes s = jw = j2pif => f = s/(j2pi)
                    # Only plot if real part is near zero for AC response poles.
                    if abs(sympy.re(pole_subst).evalf(chop=True)) < 1e-9: # Effectively on jw-axis
                        pole_freq = abs(sympy.im(pole_subst).evalf(chop=True) / (2*sympy.pi))
                        if float(config['fstart']) <= pole_freq <= float(config['fstop']) and config['show_poles'] == 'yes':
                            ax.axvline(pole_freq, linestyle='dashed', color='r')
                except Exception: pass

            if len(zeros): fil.write('Zeros (s-domain): \n')
            for z_idx, zero_val in enumerate(zeros):
                try:
                    zero_subst = zero_val.subs(subst)
                    fil.write('  z_%d = %s\n' % (z_idx, str(zero_subst.evalf(chop=True))))
                    if abs(sympy.re(zero_subst).evalf(chop=True)) < 1e-9 and config['show_zeros'] == 'yes':
                        zero_freq = abs(sympy.im(zero_subst).evalf(chop=True) / (2*sympy.pi))
                        if float(config['fstart']) <= zero_freq <= float(config['fstop']):
                             ax.axvline(zero_freq, linestyle='dotted', color='g')
                except Exception: pass
            fil.write('\n\n')


        if config['show_legend'] == 'yes': ax.legend()
        if config['hold'] == 'no':
            # plt.hold(False) # Deprecated
            plt.savefig('%s_ac_%d.png' % (file_sufix, PlotNumber.plot_num))
            plt.clf() # Clear figure for next plot if any
            PlotNumber.plot_num += 1
        plt.close(fig) # Close figure associated with ax

# Dictionary of analysis name with appropriate functions
analysis_dict = {'measure': measure_analysis,
                 'ac': ac_analysis,
                 'dc': dc_analysis}
