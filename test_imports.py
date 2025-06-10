import sys
print(f'Python version: {sys.version}')
print(f'Sys path: {sys.path}')
try:
    print('Attempting to import symbolic_circuit_solver_master.scs_elements...')
    from symbolic_circuit_solver_master import scs_elements
    print(f"SUCCESS: scs_elements module imported: {scs_elements}")
    # Note: The class is named Resistance in the source file
    print(f"SUCCESS: scs_elements.Resistance class: {scs_elements.Resistance}")
    print(f"SUCCESS: scs_elements.elementd dictionary: {scs_elements.elementd}")
    print(f"SUCCESS: All basic checks passed for scs_elements.")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    print(traceback.format_exc())
