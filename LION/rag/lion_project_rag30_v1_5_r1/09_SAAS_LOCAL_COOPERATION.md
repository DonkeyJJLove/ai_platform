# LION RAG 1.5 — SAAS LOCAL COOPERATION

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Wspólna semantyka, nie wymienność wszystkich funkcji

SaaS i model lokalny mają współpracować na tej samej źródłowo związanej intencji oraz kontekście, z odrębnymi projekcjami, sesjami i wywołaniami. Rola buildera, krytyka, badacza czy koordynatora wynika z zadania i rzeczywiście dostępnych capabilities. Nie zakładaj, że lokalność oznacza zaufanie, a większy model oznacza authority.

CognitiveSessionBinding wiąże scope, misję lub wątek, endpoint, session_ref, binding_epoch, model_release_ref i input_context_digest. CognitiveInvocation wiąże request, message, rzeczywisty payload, binding, provider leg, route policy i deadline. ModelCallV2 i ModelRelease zachowują tożsamość bez przejmowania transportu, schedulera i polityki.

Oddziel wspólny digest kontekstu, digest projekcji i digest wysłanych bajtów. Zmiana providera nie zmienia authority; nie wolno za jej pomocą ominąć scope ani zgody operatora. Potwierdź, że oba legs mają odrębne tożsamości i mogą zwrócić różne wyniki bez nadpisania drugiego.

## Odpowiedzi i rozbieżności

Zachowaj output obu providerów z ich identyfikatorami, czasem, błędami, stop reason i provenance. Uzgodnienie dotyczy twierdzeń i dowodów, nie konkursu popularności. Gdy jeden model cytuje drugi albo oba korzystają z jednego źródła, wspólny korzeń jest jawny. Nie zamieniaj teacher output w ground truth dla EvidenceBoundLearningEpisode.

Brak modelu, niedostępna sesja, niewspierany transport, timeout, wygasły binding i błędny context hash to różne problemy. Nie zastępuj SaaS produktem API bez decyzji obejmującej trwałość sesji, narzędzia, koszty i transport. Ścieżka /mnt/data w SaaS nie istnieje automatycznie na MOON; artefakt wymaga transferu bajtów lub osiągalnej, zakresowanej referencji.

## Konkretna luka do zbadania

`lion_context_provider.py` pobiera release z bootstrapu, lecz buduje tekst zawierający ARCHITECTURE_EPOCH=1.4, MATERIAL_EPOCH=R10, stałą nazwę gpt-oss-20b-MXFP4 i stałe liczniki. To odczytany kod, nie poświadczenie rzeczywiście uruchomionego modelu. Misja rozwojowa ma ustalić jego konsumentów i zastąpić nieprawdziwe bieżące deklaracje właściwym source/session bindingiem lub UNKNOWN, zachowując historyczne fakty i kontrakty autoryzacji.

## Źródła i dalszy odczyt

- `DonkeyJJLove/ai_platform:cyber_lion/contracts/cognitive_invocation.py`
- `DonkeyJJLove/ai_platform:cyber_lion/contracts/model_call_v2.py`
- `DonkeyJJLove/ai_platform:cyber_lion/contracts/model_release.py`
- `DonkeyJJLove/ai_platform:cyber_lion/app_coordination/lion_context_provider.py`
