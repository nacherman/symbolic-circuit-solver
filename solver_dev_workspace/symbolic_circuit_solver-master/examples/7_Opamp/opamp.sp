*$
*$ Example 7 - Simple operational amplifier
*$
*$
*$
.include 'examples\library\mos.sp'
.param gmn gmp gdsp gdsn CL Vin cgs

Vp inp 0 'Vin/2'
Vm inm 0 '-Vin/2'

xmnp bias inp  tail   mos_s gds = 'gdsn' gm='gmn'
xmnm out  inm  tail   mos_s gds = 'gdsn' gm='gmn'
xmpp out  bias 0      mos_s gds = 'gdsp' gm='gmp'  cgs='cgs'
xmpm out  out  out    mos_s gds = 'gdsp' gm='gmp' cgs='cgs'

CL out 0 CL
.measure T 'v(out)/v(inp,inm)'
.ac T gmn=1m gmp=1m gdsp=0.1m gdsn=0.1m CL = 10n  cgs=1p fstop=1e12
.ends