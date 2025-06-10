* H-Bridge Circuit for Symbolic R3 and U_source Calculation

.PARAM U_sym = U_sym
.PARAM R3_sym = R3_sym
.PARAM U_source_val = U_sym
.PARAM R1_val = 180
.PARAM R2_val = 100
.PARAM R3_val = R3_sym
.PARAM R4_val = 22
.PARAM R5_val = 39
.PARAM R6_val = 39

* Main Voltage Source
VU N_TOP 0 U_source_val

* Left Arm
R1 N_TOP N1 R1_val
R2 N1 N2 R2_val
R3 N2 0 R3_val

* Right Arm
R5 N_TOP N3 R5_val
R6 N3 0 R6_val

* Bridge Resistor
R4 N2 N3 R4_val

* Analysis (optional, can be added later if needed for direct solver use)
* .measure V_N3 v(N3)
* .measure I_R4 i(R4)
.measure P_R3 p(R3)

.end
