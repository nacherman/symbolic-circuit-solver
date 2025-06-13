* Test Netlist for All Linear Symbolic Components
* Based on spice_parser.py sample

.PARAM Rval_param = 1k Cval_param = {10u/2} Lval_param='{Rval_param/1000}'

R1 N1 N2 1K
R2 N2 0 {Rval_param} ; Resistor with unit and parameter
C1 N2 N3 10uF
L1 N3 0 {Lval_param} ; Using parameter
VS1 N1 0 DC 10 AC 5 0
VS2 N4 0 20V
IS1 0 N3 AC 2MA 90 ; Current source, current flows N3 to 0 (standard I is N1->N2)
IS2 N5 0 1A
E1 N_EOUT 0 N2 N3 2.5
G1 N_GOUT 0 N2 N3 0.1
H1 N_HOUT 0 R2 100 ; CCVS, R2 is name of component for control current I(R2)
F1 N_FOUT 0 R2 50  ; CCCS, R2 is name of component for control current I(R2)
RX N_SYM N_SYM_GND MyResistanceSymbol
VY N_V_SYM 0 MyVoltageSymbol
VSIN N_SIN 0 SIN(0 5 1K 0 0 0)
VSIN2 N_SIN2 0 SIN(1 2 500 0 0 30DEG) ; Phase with unit
VLAP N_LAP 0 {10/(s+100)} ; Source with s-domain expression

.AC OMEGA 1000
.END
