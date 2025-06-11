Symbolic Circuit Solver Project

This project implements a symbolic circuit solver using Python and the Sympy library.
It can derive formulas for unknown circuit parameters (voltages, currents, resistances)
given a set of known values and circuit topology.

**File Structure:**

/symbolic_solver_project/
│
├── symbolic_components.py      # Core component classes (Resistor, VoltageSource, CurrentSource, BaseComponent)
├── symbolic_solver.py          # Contains the main `solve_circuit` function.
├── symbolic_tester.py          # Example script demonstrating solver usage, including an H-bridge like circuit.
├── utils.py                    # Optional helper functions, e.g., for formatting output.
└── README.txt                  # This file.

**Core Concepts:**

- **`symbolic_components.py`**: Defines electrical components as classes. Each component
  knows its connection nodes (`node1`, `node2`), its symbolic values (e.g., resistance `R`,
  current `I`), and generates its characteristic symbolic equations (e.g., Ohm's Law: `V - I*R = 0`).

- **`symbolic_solver.py`**: The `solve_circuit` function takes a list of component instances,
  a list of symbols to solve for, a dictionary of known substitutions, optional additional
  constraint equations, and a ground node name. It automatically:
    1. Collects all component equations.
    2. Generates Kirchhoff's Current Law (KCL) equations for all non-ground nodes.
    3. Substitutes known values and applies constraints.
    4. Uses `sympy.solve()` to solve the system of equations for the desired unknowns
       as well as internal circuit variables (other node voltages, component currents/voltages).

- **`symbolic_tester.py`**: Provides concrete examples of how to define symbols, instantiate
  components for a circuit, set up knowns and desired unknowns, and call the solver.
  It includes scenarios for both direct solving and "reverse" solving (e.g., finding a
  source voltage needed to achieve a specific voltage across a load).

**Requirements:**

- Python 3.x
- Sympy library: Install using `pip install sympy`

**How to Run:**

1. Ensure you have Python and Sympy installed.
2. Navigate to the `symbolic_solver_project` directory in your terminal.
3. Run the example tester script:
   ```bash
   python symbolic_tester.py
   ```
4. Examine the output, which will show the component definitions, the equations being solved (if debug prints are enabled in `symbolic_solver.py`), and the symbolic or numerical solutions for the unknowns.

**Key Features Demonstrated:**

- Symbolic representation of circuit components and their physics.
- Automatic generation of KCL equations.
- Solution of linear and non-linear algebraic equations (via Sympy).
- Ability to solve for component values, currents, or voltages.
- Handling of mixed symbolic and numerical knowns.
- Application of arbitrary symbolic constraint equations.
- "Goal-seeking" or "reverse solving": determining input parameters based on desired output conditions.
