# Protokół scaffoldingu

Scaffolding to pre-deterministic probabilistic semantic relational geometric language space służąca odkrywaniu struktury. Nie klasyfikuj jej automatycznie jako losowego szumu ani jako empirycznego dowodu.

DO_NOT_NORMALIZE_BY_DEFAULT. PRESERVE_GLITCH, PRESERVE_SPACING, PRESERVE_ORDER, PRESERVE_NUMBERS, PRESERVE_SYMBOLS, PRESERVE_AMBIGUITY. POTENTIALLY_SEMANTIC_NOT_PROVEN_SEMANTIC.

Gdy wejście jest oznaczone SCAFFOLDING, zachowaj jego literalną kopię. Bez jawnego żądania edycji nie poprawiaj gramatyki, słów, interpunkcji, odstępów, powtórzeń, kolejności, języka, glitchy, liczb ani pozornych nonwords. Interpretacje i transformacje zapisuj oddzielnie od źródła. Zgoda na analizę nie jest zgodą na korektę; zgoda na redakcję dotyczy wskazanej kopii/zakresu, nie archiwalnych payloadów RAG.

Potencjalnie semantyczne cechy: token_order, word_shape, sound_shape, rhythm, repetition, punctuation, white_space, line_breaks, numbers, symbols, brackets, mirroring, sequences, near_duplicates, semantic_glitches, language_switches, entity_collisions, positional_relations. Potencjalna semantyka nie jest udowodnioną semantyką.

## Przebieg

1. Zachowaj literalne wejście; zanotuj identyfikator i zakres, a dla pliku hash jego oryginalnych bajtów.
2. Wyodrębnij candidate entities i candidate relations.
3. Zbuduj kilka możliwych grafów; zachowaj niejednoznaczność.
4. Zastosuj TIGER Geometry; szukaj inwariantów, symetrii/asymetrii, sekwencji i możliwych granic.
5. Zapisz wiele hipotez i kontrhipotez. Scoring, jeśli użyty, pozostaje heurystyką.
6. Nie redukuj przedwcześnie do jednej interpretacji. Zmaterializuj testowalne twierdzenia i falsyfikuj tam, gdzie istnieje rozstrzygający test.

Przykład literalny (dwie spacje mają pozostać dwiema):

```text
beam  beaM ↔ 13  31
gl!tch   [ ] [ ]
```

Możliwe odczyty obejmują odbicie, różnicę wielkości liter lub przypadkową zbieżność. Żaden nie jest stwierdzony przez samo podobieństwo. Raport powinien oddzielać surowy tekst, obserwowane cechy, hipotezy, testy i UNKNOWN. Dla pytania o rzeczywisty system potrzebny jest dowód spoza tego grafu.
