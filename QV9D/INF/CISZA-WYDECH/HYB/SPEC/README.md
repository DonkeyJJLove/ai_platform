# Cisza–Wydech – Rejestr resetu (architektura hybrydowa)

W trybie hybrydowym Cisza–Wydech działa tak, jak w architekturze klasycznej, ale obejmuje dodatkowo synchronizację między drzewem AST a mozaiką kafelków.  
Reset „oddechu” usuwa lokalne fluktuacje, przywraca kafelki mozaiki do stanu bazowego i rekonfiguruje mosty 9D.  
Poziom resetu decyduje także o tym, czy i kiedy hybrydowy agent może uruchomić nowe zadania w QPU.

**Pola konfiguracyjne** pozostają takie same jak w wersji klasycznej (`frequency`, `mode`, `threshold`), ale w hybrydzie dopuszcza się dodatkowe wartości trybu (`sync_reset`), które odświeżają zależności między AST a mozaiką.