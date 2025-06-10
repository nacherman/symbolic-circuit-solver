# symbolic_circuit_solver
Symbolic circuit solver - tool for solving circuits sybolicly (unlike spice which does it numericly) but using similar to spice netlist files.

Syntax of netlist is very similar to spice netlists but it doesn't have all set of functions and some of them are vastly different in behaviour. For full overview of netlist syntax check the wiki pages.

Script relies heavly on sympy module. Depending on the size of network, solving circuit can take long times. Avoid creating circuits with nodes count above 10 (sic!), or try it to divide in subinstances. Number of inner nodes (nets not being port nets) is the number of linear equations (size of the matrix containning information about the system), and hance inverting large matrices symbolicly can take up a long time. Number of symbols is striclty connected with times that analysis of solution takes, because mainly what is done is fractioning and simplifying solutions into most readable form. Restrict models to most simple forms at first and then try to introduce more parameters, and check if readability of answer is not compromised. All models must be linear, as answers here provided are just small signal linear models answer or dc sweeps. For transient analysis only spice simulations do their job correctly.

The sole function of this script is to determine how different parameters of network affect the output in the analyticly manner. 

