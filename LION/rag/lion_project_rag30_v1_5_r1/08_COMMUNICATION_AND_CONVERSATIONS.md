# LION RAG 1.5 — COMMUNICATION AND CONVERSATIONS

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Identyfikatory mają różne czasy życia

Conversation, mission, external SaaS thread, provider session, lane, message/request, invocation, phase, attempt, generation i lease/fence nie są zamiennymi nazwami. Conversation plane używa między innymi conversations, conversation_lineage, conversation_bindings, conversation_provider_lanes, conversation_threads, conversation_messages, conversation_delivery_events oraz external bridges. Pełne definicje sprawdź w aktualnym conversation_schema/domain/chat.

Powiązanie lub odłączenie misji musi respektować semantykę następcy i zamrożonego poprzednika. Nie przypisuj starej odpowiedzi do nowej epoki dlatego, że tekst jest podobny. DUAL jest sposobem organizacji odrębnych provider legs, nie trzecim modelem ani zgodą na scalenie ich pochodzenia.

## Rzeczywisty consumer SaaS

W badanym canonical-conversation-consumer.cjs używany jest CHATGPT_SENTINELX_MCP i system CHATGPT_SAAS. Consumer waliduje broker request, command_id, parent_event_id, profil CONTROL_PLANE, authority_effect, transport oraz osadzone conversation/binding/lane/message/correlation/causation/context identities. Nie usuwaj tych kontroli, by przepchnąć źle związane żądanie misji.

Nowa rozmowa przechodzi przez createProjectConversationWithPrompt, a powiązanie jest utrwalane w durable bridge. Istniejąca rozmowa jest wybierana z jawnego zapisu bridge'a, nie aktywnej karty. SUPERSESSION zapisuje się w provenance; poprzednia tożsamość nie jest przepisywana. Stan SEND_UNKNOWN nie uprawnia do ślepego ponowienia niejednoznacznie wysłanej wiadomości.

## Miejsce instrukcji cold-start

Dołączenie instrukcji z pliku 01 należy zaprojektować w istniejącej gałęzi tworzenia nowej rozmowy i w kontrakcie kontekstu. Treść powinna być związana z wersją pakietu i requestem; dowód dołączenia nie oznacza dowodu przestrzegania. Nie kopiuj całego RAG do każdej wiadomości i nie zmieniaj zamrożonych identities po stworzeniu ich digestów.

Przy istniejącym wątku badaj jawne odświeżenie wiedzy, nie bezwarunkowe ponowne wykonanie bootstrapu. Brak możliwości odczytu źródeł powinien wrócić jako określony stan do właściwej rozmowy i misji, a nie jako fałszywy wynik zakończenia.

## Źródła i dalszy odczyt

- `DonkeyJJLove/ai_platform:browser_broker/src/canonical-conversation-consumer.cjs`
- `DonkeyJJLove/ai_platform:cyber_lion/app_coordination/conversation_schema.py`
- `DonkeyJJLove/ai_platform:LION/architecture/v1_4/R24_CONVERSATION_IDENTITY_CONTRACT.md`
