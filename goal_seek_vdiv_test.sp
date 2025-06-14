* Voltage Divider for R2 Goal Seeking Test

.PARAM Vin_s = 5.0
.PARAM R1_s = 1000.0
.PARAM R2_sym = R2_sym ; The unknown resistor value we want to find

VS V_in_node 0 Vin_s
R1 V_in_node N_out R1_s
R2_element N_out 0 R2_sym ; Element using the symbolic R2_sym

.end
