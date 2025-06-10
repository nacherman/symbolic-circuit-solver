* Voltage Divider for Formula Derivation

* Declare all components as symbolic parameters
.PARAM US_val = US_sym
.PARAM R1_val = R1_sym
.PARAM R2_val = R2_sym

* Define the symbols themselves so the parser knows they are intended to be symbolic
.PARAM US_sym = US_sym
.PARAM R1_sym = R1_sym
.PARAM R2_sym = R2_sym

VS N_source 0 US_val
R1 N_source N_out R1_val
R2 N_out 0 R2_val

.end
