.subckt inp inm out ref opamp gain='gain' rout = 'rout' pole='1/0'
eota1 x ref inp inm gain
Rpole x y 1
Cpole y ref '1/pole'
eota2 outr ref y ref 1
rout_element out outr rout
.ENDS opamp
