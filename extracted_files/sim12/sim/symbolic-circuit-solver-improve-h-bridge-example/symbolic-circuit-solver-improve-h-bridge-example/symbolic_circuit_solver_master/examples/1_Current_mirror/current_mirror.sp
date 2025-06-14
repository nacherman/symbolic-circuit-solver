*$
*$ Example 1 - Current mirror
*$
*$
*$
.include 'examples\library\mos.sp'
.param i_0 VL n gds
i0   b   0   i_0
xmn0 b   b 0 mos_s gds = 'gds' m = 1
xmn1 out b 0 mos_s gds = 'gds' m = n
VL out 0 VL
.measure vb v(b)
.measure iout 'i(VL)'
.measure multiplication 'i(VL)/i(i0)' VL='i0/(gds + gm)'
.measure output_resistance '-VL/i(VL)' i_0=0

.ends