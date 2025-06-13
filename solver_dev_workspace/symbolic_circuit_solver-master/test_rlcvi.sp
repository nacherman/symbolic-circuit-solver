* Test for RLCVI instantiation with my_components
.PARAM RVAL_PARAM = 100
.PARAM LVAL_PARAM = {2*1m}
.PARAM CVAL_PARAM = {0.1u + 0.1u}
.PARAM VSIN_AMP = 2
.PARAM VSIN_PHASE_DEG = 45

R1 N1 N2 1K
R2 N2 0 {RVAL_PARAM}
L1 N3 N4 {LVAL_PARAM}
C1 N4 0 {CVAL_PARAM}

VDC N_VDC 0 DC 10
VAC N_VAC 0 AC 5 30 ; 5V peak, 30 degrees phase
VSIN N_VSIN 0 SIN(1 {VSIN_AMP} 1K 0 0 {VSIN_PHASE_DEG}) ; offset 1V, amp from param, freq 1kHz, phase from param

IDC N_IDC 0 DC 2M
IAC N_IAC 0 AC 100U 0
ISIN N_ISIN 0 SIN(0.5m 1m 2K) ; offset 0.5mA, amp 1mA, freq 2kHz

.AC OMEGA 1000
.END
