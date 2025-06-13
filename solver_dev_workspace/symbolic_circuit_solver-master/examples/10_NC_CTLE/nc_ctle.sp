*$
*$ Example 10 - Negative C CTLE
*$
*$
*$
.include 'examples\library\mos.sp'
.param Vin CL RL RX CX gm1 gm2 cgs gds2
.param gds1 = 0
Vp in 0 Vin
xm1 out in 0 mos_s gm='gm1' gds = 'gds1'
RL out 0 RL
CL out 0 CL
xm2 out nout x  mos_s gm='gm2' gds = 'gds2'
ex nout 0 out 0 -1
CX x 0 CX
.measure T0 'v(out)/Vin' gm2 = 0 CX = 0 cgs = 0 RX = 0
.measure T 'v(out)/Vin'
.ac T0 gm1=100m  RL = 1k gds1 = 0.1m gds2 = 0.1m CL = 10p cgs = 0 fstart = 1e2 fstop = 1e12 show_legend = yes hold = yes
.ac T gm1=100m gm2=50m RL = 1k gds1 = 0.1m gds2 = 0.02m CL = 10p CX = 10p cgs = 1p fstart = 1e2 fstop = 1e12 show_legend = yes
.ends