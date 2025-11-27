# Ostrze–Cierpliwość – Agresja zmian (architektura hybrydowa)

W hybrydowej wersji rejestr **Ostrze–Cierpliwość** steruje zarówno tempem aktualizacji kodu AST, jak i tempem modyfikacji mozaiki.  
`step_size` przekłada się na liczbę i wielkość wkładek (insertion calculus) w AST, a `memory` – na długość okna, z którego zbierane są delty z kafelków.  
Parametr `hysteresis` tłumi fluktuacje miar takich jak PSNR/SSIM, aby uniknąć chaotycznego przełączania się między filtrami.