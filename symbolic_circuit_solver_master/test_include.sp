
.subckt d g s pmos gm = 'gm' cgs = 'cgs' gds='gds'

gm d s s g gm
rds d s '1/gds'
cgs g s cgs

.ends pmos 

.ends