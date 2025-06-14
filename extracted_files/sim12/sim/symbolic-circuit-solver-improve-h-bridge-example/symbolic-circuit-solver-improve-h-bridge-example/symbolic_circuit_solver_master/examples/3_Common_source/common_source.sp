*$
*$ Example 3 - Common source amplifier
*$
*$
*$
.include 'examples\library\mos.sp'
.param Vin Rs RL  CL Iout gds cgs

Vin in 0 Vin
xmn out in s mos_s gds = 'gds' cgs = 'cgs'
Rs  s 0 Rs
RL  out 0 RL
CL  out 0 CL

.measure gain 'v(out)/v(in)'  Iout = 0 s = 0
.ac 'v(out)/v(in)' gm = 1m Rs = 10 RL = 10k gds = 0.1m cgs = 100p CL = 1n Iout = 0 fstop=1e10


.ends