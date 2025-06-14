* Voltage Divider for R2 Goal Seeking Test (Symbolic Target)

.PARAM Vin_s = Vin_s     ; Symbolic input voltage
.PARAM R1_s = R1_s       ; Symbolic R1
.PARAM R2_sym = R2_sym   ; The unknown resistor value we want to find (symbolic)
.PARAM K_div_s = K_div_s ; Symbolic division factor for the target output voltage

VS V_in_node 0 Vin_s
R1 V_in_node N_out R1_s
R2_element N_out 0 R2_sym

.end
