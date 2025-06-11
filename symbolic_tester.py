import sympy as sp
from symbolic_components import Resistor, VoltageSource, CurrentSource
from symbolic_solver import solve_circuit
from utils import print_solutions # Import the new utility

# Define all symbolic variables
# Source Voltages
V1_sym = sp.Symbol('V_source1')
V2_sym = sp.Symbol('V_source2')

# Resistances
R1_sym = sp.Symbol('R1_val')
R2_sym = sp.Symbol('R2_val')
R3_sym = sp.Symbol('R3_val')
R4_sym = sp.Symbol('R4_val')

# Currents through components
I_V1_sym = sp.Symbol('I_V1')
I_R1_sym = sp.Symbol('I_R1')
I_R2_sym = sp.Symbol('I_R2')
I_V2_sym = sp.Symbol('I_V2')
I_R3_sym = sp.Symbol('I_R3')
I_R4_sym = sp.Symbol('I_R4')
I_CS5_sym = sp.Symbol('I_CS5')

V_R2_actual_comp_sym = None

components = [
    VoltageSource(name='V1', node1='n1', node2='GND', voltage_val_sym=V1_sym, current_sym=I_V1_sym),
    Resistor(name='R1', node1='n1', node2='n2', resistance_sym=R1_sym, current_sym=I_R1_sym),
    Resistor(name='R2', node1='n2', node2='n3', resistance_sym=R2_sym, current_sym=I_R2_sym),
    VoltageSource(name='V2', node1='n3', node2='GND', voltage_val_sym=V2_sym, current_sym=I_V2_sym),
    Resistor(name='R3', node1='n2', node2='n4', resistance_sym=R3_sym, current_sym=I_R3_sym),
    Resistor(name='R4', node1='n4', node2='GND', resistance_sym=R4_sym, current_sym=I_R4_sym),
    CurrentSource(name='CS5', node1='n4', node2='n3', current_val_sym=I_CS5_sym)
]

for comp in components:
    if comp.name == 'R2':
        V_R2_actual_comp_sym = comp.V_comp
        break

if V_R2_actual_comp_sym is None:
    print("Error: Could not find V_comp symbol for R2 (load resistor).")
    exit()

print("--- H-Bridge Reverse Scenario Test (using print_solutions) ---")
print("Goal: Given all R values, V2, CS5, and a target voltage V_R2 (load)=0.1V, find required V_source1 and its current I_V1.")

known_values = {
    R1_sym: 180,
    R2_sym: 39,
    R3_sym: 50,
    R4_sym: 22,
    V2_sym: 0.5,
    I_CS5_sym: 0.01
}

constraints = [
    V_R2_actual_comp_sym - 0.1
]

unknowns_to_solve = [
    V1_sym,
    I_V1_sym
]

print(f"\nAttempting to solve for: {unknowns_to_solve}")
print(f"With known values: {known_values}")
print(f"And constraint equations (target zero):")
for con_eq in constraints:
    print(f"  {sp.pretty(con_eq)} = 0")

solution = solve_circuit(
    components,
    unknowns_to_solve,
    known_substitutions=known_values,
    additional_equations=constraints,
    ground_node='GND'
)

# Use the new print_solutions utility
print_solutions(solution, title="H-Bridge Reverse Scenario Solution")


# Original Scenario Test (solving for R3_sym, I_V1_sym, R1_sym)
# This was the state from the previous symbolic_tester.py for step 4.
# We can include it here as well to ensure print_solutions works for it.

V_R1_actual_comp_sym_orig = None
# V_R2_actual_comp_sym is already fetched and is the same for R2 component
for comp in components: # Re-fetch R1's V_comp for clarity in this section
    if comp.name == 'R1':
        V_R1_actual_comp_sym_orig = comp.V_comp

if V_R1_actual_comp_sym_orig is None: # V_R2_actual_comp_sym checked earlier
    print("Error: Could not find V_comp symbols for R1 for original scenario.")
    exit()

print("\n--- Original H-Bridge Style Test Scenario (from step 4, using print_solutions) ---")
print("Goal: Given V_source1=1V, V_drop_R1=0.9V, V_n2=0.1V, and other R values, find R3_val, I_V1, R1_val.")

known_values_orig = {
    V1_sym: 1.0,
    # R1_sym: 180,      # R1_sym is unknown here
    R2_sym: 39,
    R4_sym: 22,
    V2_sym: 0.5,
    I_CS5_sym: 0.01
}

# The constraints were V_R1 = 0.9 and V_n2 = 0.1
# V_n1 is V1_sym due to the V1 source. So V_R1 = V1_sym - V_n2_sym
# V_R1 = 1.0 - V_n2_sym = 0.9  => V_n2_sym = 0.1
# So the constraints are:
# V_R1_actual_comp_sym - 0.9 = 0
# sp.Symbol('V_n2') - 0.1 = 0  (This was the successful constraint from subtask report for step 4)

constraints_orig = [
    V_R1_actual_comp_sym_orig - 0.9,
    sp.Symbol('V_n2') - 0.1
]

unknowns_to_solve_orig = [
    R3_sym,
    I_V1_sym,
    R1_sym
]

print(f"\nAttempting to solve for: {unknowns_to_solve_orig}")
print(f"With known values: {known_values_orig}")
print(f"And constraint equations (target zero):")
for con_eq in constraints_orig:
    print(f"  {sp.pretty(con_eq)} = 0")

solution_orig = solve_circuit(
    components,
    unknowns_to_solve_orig,
    known_substitutions=known_values_orig,
    additional_equations=constraints_orig,
    ground_node='GND'
)

print_solutions(solution_orig, title="Original H-Bridge Scenario Solution (R3, I_V1, R1 unknown)")


print("\n--- Component Definitions (for reference, printed once) ---")
for comp in components:
    print(f"• {comp.name} [{comp.__class__.__name__}] connecting {comp.node1} to {comp.node2}")
    # print(f"  Values: {comp.values}") # Values are part of the solution output now
