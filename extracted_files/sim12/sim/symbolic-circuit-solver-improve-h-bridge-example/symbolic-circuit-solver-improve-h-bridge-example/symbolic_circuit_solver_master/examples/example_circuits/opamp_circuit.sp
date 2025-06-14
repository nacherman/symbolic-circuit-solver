* Complex Test Circuit: Inverting Op-Amp with Symbolic Params
.PARAM V_source_sym = V_source_sym
.PARAM R1_sym = R1_sym
.PARAM R2_val = 10k          ; Fixed R2 - can be overridden by user_param_override_values in verification tasks
.PARAM Aol_sym = Aol_sym

Vin N_in 0 V_source_sym
R1 N_in N_minus R1_sym
R2 N_minus N_out R2_val
E_opamp N_out 0 0 N_minus Aol_sym
.end
