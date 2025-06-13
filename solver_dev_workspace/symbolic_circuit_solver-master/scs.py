#!/depot/Python-2.7.2/bin/python -E

""" Main script.
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
__description__ = "Symbolic circuit solver"


def main():
    parser = argparse.ArgumentParser(description=__description__, prog='scs')
    parser.add_argument('-i', help='input file', required=True)
    parser.add_argument('-o', help='output files name')
    parser.add_argument('-v', action='store_true', help='verbose mode')
    args = parser.parse_args(sys.argv[1:])

    input_file_name = args.i
    output_file_prefix = args.o if args.o else os.path.splitext(input_file_name)[0]
    logging_file_name = '%s.log' % output_file_prefix

    try:
        os.remove(logging_file_name)
    except OSError:
        pass

    logformat = '%(levelname)s: %(filename)s:%(lineno)d: %(message)s' # Added filename and lineno

    # Configure root logger to write to file
    logging.basicConfig(format=logformat, filename=logging_file_name, level=logging.DEBUG) # Set file to DEBUG

    # If verbose, also add a console handler printing INFO and above (or DEBUG for more verbosity)
    if args.v:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(logging.Formatter(logformat))
        console_handler.setLevel(logging.DEBUG) # Print DEBUG and above to console if -v
        logging.getLogger().addHandler(console_handler)

    # Ensure logging is not disabled globally if it was set to a higher level by default
    logging.getLogger().setLevel(logging.DEBUG)


    logging.info(f"Starting SCS v{__version__}. Input: {input_file_name}, Output Prefix: {output_file_prefix}")
    logging.info(f"Runtime: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")

    print("SCS: Parsing input file...") # Direct print
    time1 = time.perf_counter()
    top_cir_obj = scs_circuit.TopCircuit()
    top_cir_obj.name = os.path.splitext(os.path.basename(input_file_name))[0] # Set name explicitly
    top_cir = scs_parser.parse_file(input_file_name, top_cir_obj)

    if not top_cir:
        print("SCS: ERROR - Failed to parse the circuit. Check log for details.") # Direct print
        logging.error("Failed to parse a circuit.")
        sys.exit(1) # Use sys.exit for clearer exit status
    parsing_time = time.perf_counter() - time1
    print(f"SCS: Input file parsed in: {parsing_time:.4f} s") # Direct print
    logging.info(f'Input file parsed in: {parsing_time:.4f} s')

    print("SCS: Instantiating circuit...") # Direct print
    time1 = time.perf_counter()
    top_instance = scs_instance_hier.make_top_instance(top_cir)

    if not top_instance:
        print("SCS: ERROR - Failed to instantiate the circuit. Check log for details.") # Direct print
        logging.error("Failed to instantiate a circuit.")
        sys.exit(1)
    instantiation_time = time.perf_counter() - time1
    print(f"SCS: Circuit instantiated in: {instantiation_time:.4f} s") # Direct print
    logging.info(f'Instantiated circuit in: {instantiation_time:.4f} s')

    print("SCS: Checking circuit integrity (placeholders)...") # Direct print
    if not top_instance.check_path_to_gnd():
        logging.error("Circuit check: Path to ground failed.")
    if not top_instance.check_voltage_loop():
        logging.error("Circuit check: Voltage loop check failed.")

    print("SCS: Calling placeholder solve()...") # Direct print
    time1 = time.perf_counter()
    try:
        solve_status = top_instance.solve()
        if not solve_status : print("SCS: Placeholder solve() reported an issue.") # Direct print
    except Exception as e:
        print(f"SCS: ERROR during placeholder circuit solution: {e}") # Direct print
        logging.error(f"Error during (placeholder) circuit solution: {e}", exc_info=True)
        sys.exit(1)
    solve_time = time.perf_counter() - time1
    print(f"SCS: Placeholder solve() called, duration: {solve_time:.4f} s") # Direct print
    logging.info(f'Placeholder solve() called, duration: {solve_time:.4f} s')

    print("SCS: Performing analysis (if any)...") # Direct print
    top_cir.perform_analysis(top_instance, output_file_prefix)
    print("SCS: Analysis phase complete.") # Direct print
    print(f"SCS: Log file generated at: {logging_file_name}")


if __name__ == "__main__":
    main()
