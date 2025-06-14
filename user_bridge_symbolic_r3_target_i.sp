* User Bridge Circuit Test for Symbolic R3 Formula

.PARAM U1_s = U1_s
.PARAM U2_s = U2_s
.PARAM R1_s = R1_s
.PARAM R2_s = R2_s
.PARAM R3_s = R3_s       ; The unknown resistor value (symbolic)
.PARAM R4_s = R4_s
.PARAM R5_s = R5_s
.PARAM R6_s = R6_s
.PARAM I_target_s = I_target_s ; Symbolic target current I(N3,N4)

Vs1 s1 0 U1_s
R1_elem s1 N2 R1_s  ; Changed name
Vs2 N2 0 U2_s
R6_elem N2 0 R6_s   ; Changed name
R2_elem N2 N3 R2_s  ; Changed name
R3_elem N3 0 R3_s   ; Changed name
R4_elem N2 N4 R4_s  ; Changed name
R5_elem N4 0 R5_s   ; Changed name
VdummyI34 N3 N4 0     ; Dummy 0V source to measure current between N3 and N4

.end
