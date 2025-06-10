*$ 
*$ Operatiol amplifier library
*$
*$ 
*$ Simple models, can be extended by defining parameters which are 0 for default
*$ 
*$ 
*$ 


.subckt inp inm out ref opamp gain='gain' rout = 'rout' pole='1/0'

eota1 x ref inp inm gain
Rpole x y 1
Cpole y ref '1/pole'
eota2 outr ref y ref 1
rout out outr rout

.ends

.ends