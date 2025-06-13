* Simple AC Test for Integrated Solver (Series RC)
VSAC N_IN 0 AC 10 0 ; 10V peak, 0 phase
R1AC N_IN N_OUT 1k
C1AC N_OUT 0 1uF    ; ZC = 1/(j*1k*1u) = 1/(j*1m) = -j1k @ omega=1k.

.AC OMEGA 1000 ; Test at omega = 1000 rad/s
* For omega=1000: ZC = -j1000. Z_total = 1k - j1k.
* |Z_total| = sqrt(1k^2 + (-1k)^2) = 1k*sqrt(2) approx 1414 Ohms
* I_total = 10 / (1k - j1k) = 10*(1k+j1k)/(1k^2+1k^2) = 10*(1k+j1k)/(2*1M) = (1+j)/(200) A = 5mA + j5mA
* V_OUT (across C1AC) = I_total * ZC = ( (1+j)/200 ) * (-j1k) = (-j1000 -j^2*1000)/200 = (-j1000 + 1000)/200 = 5 - j5 V
* Mag(V_OUT) = sqrt(5^2+(-5)^2) = sqrt(50) approx 7.07V. Phase = -45 deg.

.MEASURE AC V_OUT_MAG MAG(V(N_OUT))
.MEASURE AC V_OUT_PHASE_DEG DEG(ARG(V(N_OUT)))
.MEASURE AC I_TOTAL_MAG MAG(I(VSAC))
.MEASURE AC I_TOTAL_PHASE_DEG DEG(ARG(I(VSAC)))
.END
