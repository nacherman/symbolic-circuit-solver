* Simple DC Test for Integrated Solver
VS1 N1 0 DC 10V
R1 N1 N2 2k
R2 N2 0 3k
R3 N1 0 10k ; Parallel to VS1, for I(VS1) check

* Analysis to perform (using .MEASURE as .PRINT might not be fully supported by scs_analysis.py)
.MEASURE DC V_N1 V(N1) ; Voltage at Node N1
.MEASURE DC V_N2 V(N2) ; Voltage at Node N2
.MEASURE DC I_VS1 I(VS1) ; Current from VS1
.MEASURE DC I_R1 I(R1)   ; Current through R1
.MEASURE DC P_R2 POWER(R2) ; Placeholder if power measure is supported, else ignore
.END
