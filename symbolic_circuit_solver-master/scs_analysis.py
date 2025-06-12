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
    for symbol, value in param_d.items():
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

    for config_name in list(config.keys()): # Changed to list(config.keys()) for Python 3
        if config_name in param_d:
            config.update({config_name: param_d[config_name]})
            param_d.pop(config_name)

    if not config['sweep']:
        raise scs_errors.ScsAnalysisError("No specified sweep parameter for .dc analysis")

    try:
        xsym = sympy.symbols(config['sweep'])
    except ValueError: # Removed ", e" as e is not used
        raise scs_errors.ScsAnalysisError("Bad sweep parameter for .dc analysis: %s" % config['sweep'])

    subst = []
    for symbol, value in param_d.items():
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
        raise scs_errors.ScsAnalysisError(("Option %s for xscale invalid!" % config['yscale']))

    if config['yscale'] != 'log' and config['yscale'] != 'linear':
        raise scs_errors.ScsAnalysisError(("Option %s for yscale invalid!" % config['fscale'])) # Should be yscale

    if config['xkcd'] == 'yes':
        plt.xkcd()
    plt.title(r'$%s$' % config['title'] if config['title'] else ' ')
    # plt.hold(True) # plt.hold is deprecated

    for expresion in param_l:
        tokens = scs_parser.parse_analysis_expresion(expresion)
        value0 = sympy.sympify(scs_parser.results2values(tokens, instance),sympy.abc._clash).subs(s, 0).simplify()
        value = value0.subs(subst)
        yf = sympy.lambdify(xsym, value)
        try:
            ys = [float(yf(x)) for x in xs]
        except (ValueError, TypeError):
            raise scs_errors.ScsAnalysisError(
                "Numeric error while evaluating expresions: %s. Not all values where subsituted?" % value)

        plt.plot(xs, ys, label=expresion)
        try:
            plt.xscale(config['xscale'])
            plt.yscale(config['yscale'])
        except ValueError as e:
            raise scs_errors.ScsAnalysisError(e)

        plt.xlabel(r'$%s$' % str(xsym))

    if config['show_legend'] == 'yes':
        plt.legend()
    if config['hold'] == 'no':
        plt.savefig('%s_%d.png' % (file_sufix, PlotNumber.plot_num))
        PlotNumber.plot_num += 1
        # plt.hold(False) # plt.hold is deprecated
        plt.clf() # Clear figure for next plot


def ac_analysis(param_d, param_l, instance, file_sufix):
    """ Performs ac analysis

        param_d: substitutions for symbols, or named parameters for plot
        
        param_l: expresions to plot

        format is:
        .ac expresion0 [expresion1 expresion2 ...] sweep = parameter_to_sweep [symmbol_or_option0 = value0
        symmbol_or_option1 = value1 ...]
        
        expresions are on positiona parameters list can hold expresions containing parameters or functions of nodal
        voltages [v(node)] and element and port currents [i(element) isub(port)]

        named parameters (param_d) can contain options for analysis or substitutions for symbols, substituions will be
        done as they are without any parsing, be aware of symbol and option names clashes.

        Config options:
        fstart:         first value of frequency for AC analysis [float]
        fstop:          last value of frequency for AC analysis [float]
        fscale:         scale for frequency points [linear | log]
        npoints:        numbers of points for ac analysis [integer]
        yscale:         scale for y-axis to being displayed on [linear or log]
        hold:           hold plot for next analysis and don't save it to file [yes | no]
        show_poles:     show poles of function on plot [yes | no]
        show_zeroes:    show zeros of function on plot [yes | no]
        title:          display title above ac plot [string]
        show_legend:    show legend on plot [yes | no]
        xkcd:           style plot to be xkcd like scetch
    """
    warnings.filterwarnings('ignore')  # Just getting rid of those fake casting from complex warnings
    s, w = sympy.symbols(('s', 'w'))
    config = {'fstart': 1,
              'fstop': 1e6,
              'fscale': 'log',
              'npoints': 100,
              'yscale': 'log',
              'type': 'amp',
              'hold': 'no',
              'show_poles': 'yes',
              'show_zeros': 'yes',
              'title': None,
              'show_legend': 'no',
              'xkcd': 'no'}

    for config_name in list(config.keys()): # Changed to list(config.keys()) for Python 3
        if config_name in param_d:
            config.update({config_name: param_d[config_name]})
            param_d.pop(config_name)

    subst = []
    for symbol, value in param_d.items():
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
        raise scs_errors.ScsAnalysisError(("Option %s for fscale invalid!" % config['yscale'])) # Should be fscale

    if config['yscale'] != 'log' and config['yscale'] != 'linear':
        raise scs_errors.ScsAnalysisError(("Option %s for yscale invalid!" % config['fscale'])) # Should be yscale

    filename = "%s.results" % file_sufix

    with open(filename, 'a') as fil:
        if config['xkcd'] == 'yes':
            plt.xkcd()
        # plt.hold(True) # plt.hold is deprecated

        for expresion in param_l:
            fil.write("%s: %s \n---------------------\n" % ('AC analysis of', expresion))
            tokens = scs_parser.parse_analysis_expresion(expresion)
            value0 = sympy.factor(sympy.sympify(scs_parser.results2values(tokens, instance),sympy.abc._clash), s).simplify()
            fil.write("%s = %s \n\n" % (expresion, str(value0)))
            denominator = sympy.denom(value0)
            numerator = sympy.numer(value0)
            poles = sympy.solve(denominator, s)
            zeros = sympy.solve(numerator, s)
            poles_r = sympy.roots(denominator, s)
            zeros_r = sympy.roots(numerator, s)
            gdc = str(value0.subs(s, 0).simplify())
            fil.write('G_DC = %s\n\n' % gdc)

            p = 0
            titled = 1
            for pole, degree in poles_r.items():
                if pole == 0:
                    titled *= s ** degree
                else:
                    titled *= (s / sympy.symbols("\\omega_p%d" % p) + 1)
                p += 1
            z = 0
            titlen = 1
            for zero, degree in zeros_r.items():
                if zero == 0:
                    titlen *= s ** degree
                else:
                    titlen *= (s / sympy.symbols("\\omega_z%d" % z) + 1)
                z += 1
            # title = sympy.symbols("G_DC") * (titlen / titled)
            value = value0.subs(subst)
            f = sympy.symbols('f', real=True)
            value = value.subs(s, sympy.sympify('2*pi*I').evalf() * f)
            tf = sympy.lambdify(f, abs(sympy.numer(value)) / abs(sympy.denom(value)))
            phf = sympy.lambdify(f, sympy.arg(value))

            if config['type'] == 'amp':
                zf = tf
                ylabel = '|T(f)|'
            elif config['type'] == 'phase':
                zf = phf
                ylabel = 'ph(T(f))'
            else:
                raise scs_errors.ScsAnalysisError("Option %s for type invalid!" % config['type'])

            try:
                ys = [float(zf(f_val)) for f_val in fs] # Renamed f to f_val
            except (ValueError, TypeError):
                raise scs_errors.ScsAnalysisError(
                    "Numeric error while evaluating expresions: %s. Not all values where subsituted?" % value0)

            plt.plot(fs, ys, label=expresion)

            plt.title(r'$%s$' % config['title'] if config['title'] else ' ', y=1.05)
            try:
                plt.xscale(config['fscale'])
                plt.yscale(config['yscale'])
            except ValueError as e:
                raise scs_errors.ScsAnalysisError(e)

            plt.xlabel('f [Hz]')
            plt.ylabel(ylabel)

            if len(poles):
                fil.write('Poles: \n')

            p = 0
            for pole in poles:

                try:
                    pole_value = pole.subs(subst)
                    pole_value_f = abs(np.float64(-abs(pole_value) / sympy.sympify('2*pi').evalf()))
                    pole_s = (-pole).simplify()
                    polestr = str(pole_s)
                    fil.write('wp_%d = %s\n\n' % (p, polestr))

                    p += 1
                    if pole_value_f > float(config['fstop']) \
                            or pole_value_f < float(config['fstart']) \
                            or np.isnan(zf(pole_value_f)):
                        continue
                    if config['show_poles'] == 'yes':
                        pole_label = r'$\omega_{p%d} $' % (p - 1)
                        plt.plot(pole_value_f, zf(pole_value_f), 'o', label=pole_label)
                        plt.text(pole_value_f, zf(pole_value_f), pole_label)
                        plt.axvline(pole_value_f, linestyle='dashed')
                except: # Bare except
                    pass

            z = 0
            for zero in zeros:
                try:
                    zero_value = zero.subs(subst)
                    zero_value_f = abs(np.float64(-abs(zero_value) / sympy.sympify('2*pi').evalf()))
                    zero_s = (-zero).simplify()
                    zerostr = str(zero_s)
                    fil.write('wz_%d = %s\n\n' % (z, zerostr))
                    z += 1
                    if zero_value_f > float(config['fstop']) \
                            or zero_value_f < float(config['fstart']) \
                            or np.isnan(zf(zero_value_f)):
                        continue
                    if config['show_zeros'] == 'yes':
                        zero_label = r'$\omega_{z%d} $' % (z - 1)
                        plt.plot(zero_value_f, zf(zero_value_f), '*', label=zero_label)
                        plt.axvline(zero_value_f, linestyle='dashed')
                        plt.text(zero_value_f, zf(zero_value_f), zero_label)
                except: # Bare except
                    pass
            if config['show_legend'] == 'yes':
                plt.legend()
            if config['hold'] == 'no':
                # plt.hold(False) # plt.hold is deprecated
                plt.savefig('%s_%d.png' % (file_sufix, PlotNumber.plot_num))
                plt.clf() # Clear figure for next plot
                PlotNumber.plot_num += 1
# Dictionary of analysis name with appropriate functions
analysis_dict = {'measure': measure_analysis,
                 'ac': ac_analysis,
                 'dc': dc_analysis}
