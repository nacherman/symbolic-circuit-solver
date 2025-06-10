*$ 
*$ Example 5 - Active load
*$
*$ 
*$
.include 'examples\library\mos.sp'
.param Vin Vbias gdsn gdsp gmn gmp cgsp CL

Vin in 0 Vin
CL out 0 CL
xmn out in 0 mos_s gds='gdsn' gm='gmn'
xmp out out 0 mos_s gds='gdsp' gm='gmp' 


.measure gain 'v(out)/v(in)'  s = 0 
.measure vout 'v(out)' 
.measure T 'v(out)/v(in)' Vbias=0
.ac T gdsn=0.1m gdsp=0.01m gmn=1m gmp=0.1m CL=1n cgs=0.1n

.ends