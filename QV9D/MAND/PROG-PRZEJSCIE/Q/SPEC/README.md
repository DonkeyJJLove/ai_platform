# Próg–Przejście – Warunek commitu (architektura kwantowa)

W wersji kwantowej `Próg–Przejście` definiuje kryteria akceptacji nowych konfiguracji obwodów.  
`deltaJ_threshold` może być interpretowany jako minimalne obniżenie energii w algorytmach variational (VQE) lub spadek kosztu w QAOA.  
`confirm_iterations` wskazuje, ile prób pomiarowych musi wykazać spadek, zanim obwód zostanie zatwierdzony.  
`rollback_enabled` zezwala na powrót do poprzedniej konfiguracji, jeśli wyniki pomiarów przestaną spełniać kryteria.