; G-code generated for Cyl
; Generated directly from CAD shape by AdaptiveCAD G-code Generator
; Date: 2025-06-15 01:08:12
; ------------------------------------------
G21       ; Set units to mm
G28       ; Home all axes
; ------------------------------------------
; Simple milling operation for Cyl
; Tool diameter: 6.0mm
G0 Z15.000  ; Move to safe height
G0 X0.000 Y0.000   ; Move to start position
; Begin cutting operation
G1 Z-2.000 F100.0 ; Move to cutting depth
G1 X50.000 F200.0 ; Cut along X
G1 Y50.000        ; Cut along Y
G1 X0.000         ; Cut back along X
G1 Y0.000         ; Cut back along Y
G0 Z15.000  ; Move to safe height
; ------------------------------------------
; End of program
G28       ; Return to home position
; Program Cyl completed