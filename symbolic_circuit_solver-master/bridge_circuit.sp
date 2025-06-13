* Bridge Circuit Example
* Voltage Sources
V1 n1 0 1
V2 n2 0 0.1

.param R3_sym = R3_sym
* Resistors
R1 n1 n2 180
R2 n2 n3 100
R3 n3 0 R3_sym  $ R3 is symbolic
R4 n2 n4 22
R5 n4 0 39
R6 n2 0 39      $ Parallel to V2

* Analyses
.measure TARGET_CURRENT i(R3) R3_sym=56.18
.measure SYMBOLIC_CURRENT_R3 i(R3)
.measure SYMBOLIC_VOLTAGE_N3 v(n3)
.measure SYMBOLIC_VOLTAGE_N4 v(n4)
