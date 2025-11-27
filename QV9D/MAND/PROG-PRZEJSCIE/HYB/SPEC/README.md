# Próg–Przejście – Warunek commitu (architektura hybrydowa)

W hybrydzie rejestr **Próg–Przejście** dotyczy zarówno kodu AST, jak i mozaiki kafelków.  
`deltaJ_threshold` mierzy spadek globalnej funkcji celu, która może obejmować zarówno kryteria strukturalne (`ΔS`), semantyczne (`ΔH`), jak i zmiany poziomu (`ΔZ`).  
`confirm_iterations` oznacza liczbę cykli, w których stan musi się utrzymać, aby uznać zmianę za stabilną.  
Parametr `rollback_enabled` informuje, czy w przypadku pogorszenia metryk system automatycznie powróci do poprzedniego planu.