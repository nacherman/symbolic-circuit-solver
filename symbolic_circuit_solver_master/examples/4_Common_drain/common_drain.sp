*$ 
*$ Example 4 - Common drain amplifier
*$
*$ 
*$
.include 'examples\library\mos.sp'
.param Vin Rd RL  CL Iout cgs gds

Vin in 0 Vin 
xmn d in out mos_s cgs='cgs' gds='gds' 
Rd  d 0 Rd
RL  out 0 RL
CL  out 0 CL


.measure gain 'v(out)/v(in)'  Iout = 0 s = 0

.ac 'v(out)/v(in)' gm = 1m Rd = 10 RL = 10k gds = 0.1m cgs = 1p CL = 1n Iout = 0 fstop=1e12


.ends