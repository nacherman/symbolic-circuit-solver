* Inverting Amplifier for R2 Goal Seeking (Near-Ideal OpAmp)
.include opamp_lib.sp

.PARAM Vin_s = Vin_s         ; Symbolic input voltage
.PARAM R1_s = R1_s           ; Symbolic R1
.PARAM R2_s = R2_s           ; The unknown resistor (symbolic)
.PARAM Av_target_s = Av_target_s ; Symbolic target gain magnitude
.PARAM A_param_val = 1e-7    ; Fixed small value for A_param, so open-loop gain (1/A_param_val) is 10 Meg
.PARAM RL_val = 1e12         ; Large load resistance (effectively open circuit)
.PARAM Rout_opamp_val = 1e-3 ; Small opamp output resistance

V_in_source input_node 0 Vin_s
R1_element input_node inv_input_node R1_s
R2_element inv_input_node output_node R2_s
X_OpAmp 0 inv_input_node output_node 0 opamp gain='1/A_param_val' rout='Rout_opamp_val'
R_load output_node 0 RL_val

.end
