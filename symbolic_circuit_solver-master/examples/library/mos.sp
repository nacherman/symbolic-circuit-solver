*$ 
*$ Library of nmos's and pmos's with different level of complexity in the model
*$
*$ mos_[s|t|c]
*$ s - saturation
*$ t - triode
*$ c - cut-off
*$ Can serve both as pmos or nmos - same model - need just to connect appriopriatly


.subckt d g s mos_s gm = 'gm' gds = 0 cgs = 0 cgd = 0 cds = 0 m = 1
gm s d g s 'm*gm'
rds d s '1/(m*gds)'
cgs g s 'm*cgs'
cgd g d 'm*cgd'
cds d s 'm*cds'
.ends

.ends