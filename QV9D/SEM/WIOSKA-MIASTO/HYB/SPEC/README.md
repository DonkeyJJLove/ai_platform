# Wioska–Miasto – Skala społeczna (architektura hybrydowa)

W hybrydzie `Wioska–Miasto` wpływa na to, ile kafelków mozaiki i ile węzłów AST podlega wspólnemu zarządzaniu.  
`scope=local` oznacza skupienie na pojedynczym procesie/kaflu; `scope=global` – optymalizację całej sieci połączeń między domenami.  
Parametr `aggregation` może definiować, w jaki sposób scalać metryki z różnych modułów (np. średnia ważona według udziału semantycznego).  
`fanout_limit` decyduje o tym, do ilu komponentów hybrydowy agent rozsyła stan.