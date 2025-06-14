* User Bridge Circuit Test
.PARAM U1_val = U1_val
.PARAM U2_val = U2_val
.PARAM R1_val = R1_val
.PARAM R2_val = R2_val
.PARAM R4_val = R4_val
.PARAM R5_val = R5_val
.PARAM R6_val = R6_val
.PARAM R3_sym = R3_sym ; This is the symbol we want to determine

Vs1 s1 0 U1_val
R1 s1 N2 R1_val
Vs2 N2 0 U2_val
R6 N2 0 R6_val
R2 N2 N3 R2_val
R3_element N3 0 R3_sym
R4 N2 N4 R4_val
R5 N4 0 R5_val
VdummyI34 N3 N4 0 ; Dummy 0V source to measure current between N3 and N4

.end
