* Voltage Divider for Goal Seeking Test
.PARAM Vin_s = Vin_s
.PARAM R1_s = R1_s
.PARAM R2_s = R2_s
.PARAM I_R1_target = I_R1_target

Vin N_in 0 Vin_s
R1 N_in N_out R1_s
R2 N_out 0 R2_s
.end
