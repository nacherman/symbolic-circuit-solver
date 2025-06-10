* Power Condition Test Circuit

.PARAM VS_val = 10
.PARAM R1_val = 5
.PARAM R2_val = R2_sym ; Symbolic value to solve for

VS N1 0 VS_val
R1 N1 N2 R1_val
R2 N2 0 R2_val

.PARAM R2_sym = R2_sym ; Explicitly declare R2_sym as a symbolic parameter for the solver

.end
