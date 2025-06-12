* Schaltungsanalyse zur Bestimmung von R3 und I
* Basierend auf den Schaltplänen (Bild 2, Bild 3) und den berechneten Werten

* Definition der Spannungsquellen
V1 n1 0 1
V2 n2 0 0.1

* Definition der Widerstände
R1 n1 n2_r1 180
R2 n2_r1 n3 100
R3 n3 0 56.18  $ R3 wurde zuvor zu 56.18 Ohm berechnet
R4 n2_r1 n4 22
R5 n4 0 39
R6 n2 0 39   $ R6 ist 39 Ohm

* Dummy-Spannungsquelle zur Messung des Stroms 'I'
VI n3 n4 0

* Attempt to get the current I(VI) using the simpler .measure syntax
.measure current_I I(VI)

* Using .ends as it was mentioned the parser handles this for subcircuits.
.ends
