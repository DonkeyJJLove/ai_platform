# Human–AI – Tryb dialogu (architektura hybrydowa)

W hybrydzie rejestr **Human–AI‡** rozszerza się o sposób translacji między różnymi reprezentacjami (AST, mozaika, obrazy).  
`mode` może określać, czy system używa języka naturalnego, kodu pseudo-zapytaniowego, czy wizualizacji.  
`proposal_limit` dzieli się na limity lokalne (dla jednego modułu) i globalne (cała sieć).  
`require_confirmation` może mieć wartość `threshold`, co oznacza, że dopiero zmiany powyżej ustalonego progu wymagają zgody człowieka.