*$
*$ Example 11 - Inverting amplifier setup
*$
*$
*$
.include 'examples\library\opamp.sp'
.param Vin R1 R2 x RL A

Vp in 0 Vin
R1 in x R1
R2 x out R2
XOTA 0 x out 0 opamp gain='1/A'
RL out 0 RL

.measure gain 'v(out)/Vin' rout=0 A=0

.ends