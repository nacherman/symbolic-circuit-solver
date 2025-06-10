import sys
print(f'Python version: {sys.version}')
print(f'Sys path: {sys.path}')
try:
    print('Attempting to import symbolic_circuit_solver_master.scs_elements...')
    from symbolic_circuit_solver_master import scs_elements
    print('Successfully imported symbolic_circuit_solver_master.scs_elements')
    print(f'Resistor class from elements: {scs_elements.Resistor}')
except Exception as e:
    print(f'An error occurred: {type(e).__name__}: {e}')
    import traceback
    print(traceback.format_exc())
