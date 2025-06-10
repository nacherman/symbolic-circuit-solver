*$ 
*$ Example 13 - High Pass Active Filter
*$
*$ 
*$
.include 'examples\library\opamp.sp'
.param Vin R1 R2 C1 C2
.param A 


Vp in 0 Vin
C1 in x C1
C2 x p C2
R1 x out R1
R2 p 0 R2
XOTA p out out 0 opamp gain='1/A'


.measure T 'v(out)/Vin' rout=0 A=0
.ac T R1 = 1 R2 =1 C1=220n C2 = 220n fstart = 1e-3 fstop=1e12 show_legend = yes title = 'T'
.ends