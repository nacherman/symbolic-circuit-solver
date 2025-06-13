#!/depot/Python-2.7.2/bin/python -E

""" Main script.

    Script gets arguments of input file and output file suffix (default is same as input).
    Starts parsing input netlist. If parse goes without error it instanciate and solve it.
    If all goes without error (each warning and error is logged into output.log), it perform
    each analysis which was declared in input files writing to output.results and dumping eventual
    plots in output_plot_name.png . And quit. If -v option flag was put all warnings and errors go
    also to standard output.
"""
import argparse
import sys
import os
import logging
import time

import scs_instance_hier
import scs_circuit
import scs_parser

__author__ = "Tomasz Kniola"
__credits__ = ["Tomasz Kniola"]

__license__ = "LGPL"
__version__ = "0.0.1"
__email__ = "kniola.tomasz@gmail.com"
__status__ = "development"

__description__ = """
    Symbolic circuit solver - solves circuit from a netlist file with similar to spice syntax

"""


def main():
    """Main function.

        Look at description of this file.
    """
    parser = argparse.ArgumentParser(description=__description__, prog='scs')
    parser.add_argument('-i', help='input file', required=True)
    parser.add_argument('-o',
                        help='output files name, on default name from input file before prefix will be used')
    parser.add_argument('-v', action='store_true',
                        help='verbose mode - displays output warning and errors onto standard output')
    args = parser.parse_args(sys.argv[1:])

    input_file_name = args.i
    output_file_prefix = args.o if args.o else os.path.splitext(input_file_name)[0]
    logging_file_name = '%s.log' % output_file_prefix

    # Remove old log file with same name
    try:
        os.remove(logging_file_name)
    except:
        None  # ignore errorss don't care if file already exists

    # Setup the logger
    logformat = '%(levelname)s: %(message)s'
    logging.basicConfig(format=logformat, filename=logging_file_name, level=logging.INFO)
    logging.basicConfig(level=logging.WARNING)
    logging.basicConfig(level=logging.ERROR)
    # If the verbose option is on make additional stream for logging data as standard output
    if args.v:
        stderrlogger = logging.StreamHandler()
        stderrlogger.setFormatter(logging.Formatter(logformat))
        logging.getLogger().addHandler(stderrlogger)

    # Greeting message
    logging.info(
        """
    Symbolic system solver %s
    Author: %s
    Runtime: %s
    """ % (__version__, __author__, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))

    # Create top circtuit by parsing input file
    time1 = time.perf_counter()
    top_cir = scs_parser.parse_file(input_file_name, scs_circuit.TopCircuit())
    if not top_cir:
        logging.error("Failed to parse a circuit.")
        exit()
    logging.info('Input file parsed in: %f s' % (time.perf_counter() - time1))

    # Instantiate circuit
    time1 = time.perf_counter()
    top_instance = scs_instance_hier.make_top_instance(top_cir)
    if not top_instance:
        logging.error("Failed to instanace a circuit.")
        exit()
    logging.info('Instantiated circuit in: %f s' % (time.perf_counter() - time1))

    # Check if circuit is "well-formed"
    if not top_instance.check_path_to_gnd(): exit()
    if not top_instance.check_voltage_loop(): exit()

    time1 = time.perf_counter()
    try:
        top_instance.solve()
    except:
        exit()
    logging.info('Solved circuit in: %f s' % (time.perf_counter() - time1))

    top_cir.perform_analysis(top_instance, output_file_prefix)


if __name__ == "__main__":
    main()
