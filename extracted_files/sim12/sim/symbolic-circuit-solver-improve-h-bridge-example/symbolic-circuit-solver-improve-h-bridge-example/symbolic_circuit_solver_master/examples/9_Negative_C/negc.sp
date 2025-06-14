*$
*$ Example 8 - Negative C
*$
*$
*$
.include 'examples\library\mos.sp'
.param Vin CL RL CX  gds

Vin inp inm Vin


xmp inp inm x1  mos_s gds='gds'
xmm inm inp x2  mos_s gds='gds'
CX x1 x2 CX



CL1 inp 0 CL
CL2 inm 0 CL

.measure Zout '-Vin/i(Vin)' gds=0

.ac Zout CL=10n CX=1000n gm=100m gds=0.01m fstart=1e3 fstop=1e7
.ac Zout CL=10n CX=1000n gm=100m gds=0.01m fstart=1e3 fstop=1e7 type=phase yscale='linear'
.ends