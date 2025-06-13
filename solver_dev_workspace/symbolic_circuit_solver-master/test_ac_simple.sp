* Simple AC Test for Integrated Solver (Series RC)
VSAC N_IN 0 AC 10 0 ; 10V peak, 0 phase
R1AC N_IN N_OUT 1k
C1AC N_OUT 0 1uF

.AC OMEGA 1000 ; Test at omega = 1000 rad/s
* For omega=1000 rad/s: Z_R1AC = 1k, Z_C1AC = -j/(1000 * 1e-6) = -j/0.001 = -j1k
* Z_total = 1k - j1k Ohms
* I_total_peak = 10 / (1k - j1k) = 10 * (1k + j1k) / (1k^2 + 1k^2) = 10 * (1000 + j1000) / 2000000
*            = (10000 + j10000) / 2000000 = 0.005 + j0.005 A
* V_OUT (across C1AC) = I_total_peak * Z_C1AC = (0.005 + j0.005) * (-j1000)
*                     = (-j0.005*1000) + (-j*j*0.005*1000) = -j5 + 5 = 5 - j5 V

.MEASURE AC V_OUT_RECT V(N_OUT)                 ; Expect 5 - j5 V
.MEASURE AC V_OUT_MAG MAG(V(N_OUT))             ; Expect sqrt(5^2 + (-5)^2) = sqrt(50) = 7.071 V
.MEASURE AC V_OUT_PHASE_DEG DEG(ARG(V(N_OUT)))  ; Expect atan(-5/5) = atan(-1) = -45 degrees
.MEASURE AC I_VSAC_RECT I(VSAC)                ; If I(VSAC) is current OUT of N_IN (like I_comp): 0.005 + j0.005 A
                                               ; If I(VSAC) is current INTO N_IN (SPICE convention): -(0.005 + j0.005) A
.MEASURE AC I_VSAC_MAG MAG(I(VSAC))           ; Expect sqrt(0.005^2 + 0.005^2) = sqrt(50e-6) = 0.007071 A
.MEASURE AC I_VSAC_PHASE_DEG DEG(ARG(I(VSAC))) ; Expect 45 deg (for I_comp) or -135 deg (for SPICE convention)
.END
