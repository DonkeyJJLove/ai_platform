# Plan–Pauza – Planowanie vs wykonanie (architektura kwantowa)

W architekturze kwantowej Plan–Pauza steruje liczbą wywołań obwodu kwantowego w stosunku do tradycyjnych iteracji planowania.  
`plan_ratio` określa procent czasu przeznaczony na klasyczne symulacje, a `exec_ratio` – na przygotowanie i wykonanie obwodów QPU.  
`window` może być interpretowane jako maksymalna głębokość obwodu (`QDEPTH`) dopuszczalna w danym planie.  

Zmiana tych parametrów powinna być zatwierdzona przez człowieka, szczególnie w przypadku zwiększania `QDEPTH` lub liczby kubitów.