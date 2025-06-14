*$
*$ Example 8 - CTLE
*$
*$
*$
.include 'examples\library\mos.sp'
.param RL CL RX CX Vin Rt gds

Vp inp 0 'Vin/2'


xmp outp inp  tp   mos_s gds='gds'


RX tp 0 RX
CX tp 0 CX

RLP outp 0 RL
CLP outp 0 CL

CL out 0 CL
.measure T 'v(outp)/v(inp)' gds=0
.ac T RL = 1000 RX=100 CL=0.1n CX=50n gm=10m gds=0.01m fstart=1 fstop=1e8 cgs=10p  cds=1p cgd=10p show_legend='yes'
.ends