# Protokół generowania i ewolucji

## 1. Cel

Cyber-Lion musi wspierać ciągłe generowanie agentów, kodu, polityk, schematów, eksperymentów i topologii rojów bez dopuszczenia do dryfu ekosystemu w kierunku nieśledzalnego zbioru artefaktów generowanych przez modele.

Reguła podstawowa:

> **Generuj swobodnie w przestrzeni proposal; zmieniaj rzeczywistość wyłącznie przez typowane delty, deterministyczne gates i obserwowalne execution.**

Protokół ma zastosowanie do:

```text
source code
AgentSpec
SwarmSpec
Mosaic topology
policy
schema
memory contract
repository manifest
research-to-runtime rule
CI configuration
execution provider
```

---

## 2. Change Proposal

Każda wygenerowana lub ręcznie zaproponowana zmiana przedsiębiorstwa jest opakowywana jako:

```text
ChangeProposal = {
  change_id,
  proposer_identity,
  target_entities,
  target_artifacts,
  evidence_refs,
  rationale,
  expected_outcome,
  proposed_delta,
  changed_contracts,
  authority_effect,
  observability_effect,
  security_effect,
  migration_plan,
  tests_required,
  adversarial_tests_required,
  rollback_plan,
  expiry / review window
}
```

Proposal bez evidence może nadal istnieć jako hipoteza, ale nie może być przedstawiany jako wiedza implementacyjna podparta evidence.

---

## 3. Uniwersalny pipeline zmiany

```text
OBSERVE
↓
STRUCTURE
↓
HYPOTHESISE
↓
PROPOSE CHANGE
↓
NORMALIZE DELTA
↓
GLITCHLAB / STRUCTURAL ANALYSIS
↓
CONTRACT COMPATIBILITY
↓
SECURITY / AUTHORITY ANALYSIS
↓
SIMULATION / FALSIFICATION if required
↓
TEST
↓
GATE
↓
BOUNDED EXECUTION
↓
EXECUTION RECEIPT
↓
OUTCOME OBSERVED
↓
MEMORY / SPEC CANDIDATE
↓
PROMOTE / REJECT / SUPERSEDE
```

Żaden etap nie jest pomijany tylko dlatego, że LLM wygenerował tekst o wysokim confidence.

---

## 4. Ewolucja przedsiębiorstwa delta-first

Zasada Δ-first z GlitchLab jest uogólniana poza source code.

Platforma powinna normalizować każdą zmianę do tokenów takich jak:

```text
ADD_AGENT
REMOVE_AGENT
MODIFY_AGENT_MISSION
MODIFY_AGENT_AUTHORITY
ADD_CAPABILITY
REMOVE_CAPABILITY
MODIFY_CAPABILITY_CONTRACT
ADD_SWARM_EDGE
REMOVE_SWARM_EDGE
CHANGE_SWARM_TOPOLOGY
ADD_POLICY
MODIFY_POLICY
ADD_MEMORY_RULE
MODIFY_SCHEMA
ADD_REPOSITORY_PROVIDER
MODIFY_EXECUTION_DOMAIN
```

Każdy token jest związany z:

```text
entity
location/artifact
before state
after state
provenance
risk class
```

Docelowa integracja z GlitchLab:

```text
EnterpriseDelta
→ GlitchLab normalized tokens
→ fingerprint
→ structural projection
→ invariants
→ decision artifact
```

---

## 5. Inwarianty przedsiębiorstwa

Istniejące inwarianty GlitchLab pozostają użyteczne, ale przedsiębiorstwo wprowadza szerszą rodzinę inwariantów.

### E1 — Ciągłość tożsamości

Zmiana nie może po cichu zmieniać tożsamości encji.

```text
same entity_id
⇒ compatible identity semantics
```

Zmiana nazwy/migracja wymaga rekordów alias/supersession.

### E2 — Kompatybilność kontraktów

Publiczne interfejsy capability/event/schema/agent nie mogą być łamane po cichu.

Zmiany breaking wymagają:

```text
new version
adapter or migration
consumer impact list
rollback
```

### E3 — Brak eskalacji authority

Wygenerowana zmiana nie może po cichu zwiększać effective authority.

```text
Authority_after > Authority_before
⇒ explicit consequential gate
```

### E4 — Kompletność provenance

Consequential changes wymagają rekonstruowalnego evidence i lineage proposal.

### E5 — Zachowanie obserwowalności

Zmiana nie może zmniejszać wymaganej obserwowalności przy zachowaniu authority bez odpowiedniej degradacji.

```text
Observability_after < required
⇒ Authority_after < Authority_before
```

### E6 — Replayability

System musi potrafić zrekonstruować na podstawie events/artifacts, dlaczego nastąpiło przejście stanu.

### E7 — Ograniczenie blast radius

Zmiany muszą deklarować i testować zakres awarii.

### E8 — Poprawność epistemiczna

Twierdzenia są oznaczane jako:

```text
OBSERVED
DERIVED
CALIBRATED
HYPOTHESIS
EXPERIMENTAL
SPECULATIVE
```

`HYPOTHESIS` nie może po cichu stać się normatywną regułą produkcyjną.

### E9 — Rozdzielenie pamięci

Working context i wygenerowane notatki nie stają się automatycznie committed organizational memory.

### E10 — Integralność strukturalna polimorfizmu

Dynamiczne zmiany topologii muszą zachować pokrycie capabilities misji i ograniczenia authority.

---

## 6. Model integracji GlitchLab

Długoterminowo GlitchLab staje się kompilatorem enterprise deltas.

Adaptery wejściowe:

```text
source-code adapter
AgentSpec adapter
SwarmSpec adapter
policy adapter
JSON Schema adapter
repository-manifest adapter
memory-contract adapter
```

Output:

```json
{
  "change_id": "...",
  "delta_tokens": [],
  "fingerprint": "...",
  "contracts": [],
  "violations": [],
  "security_findings": [],
  "observability_delta": {},
  "authority_delta": {},
  "decision": "ACCEPT|REVIEW|BLOCK",
  "evidence": []
}
```

Decyzja GlitchLab jest wejściem do polityki Cyber-Lion. Sama nie przyznaje praw production execution.

---

## 7. Reguły generowania dla agentów AI

Agent generujący artefakt **MUSI** otrzymać:

```text
mission
current state
allowed scope
relevant contracts
required invariants
available capabilities
evidence/context refs
output schema
non-goals
authority ceiling
```

**NIE MOŻE** wywodzić brakującego authority z prose.

Wygenerowany output **POWINIEN** zawierać:

```text
artifact
rationale
delta summary
assumptions
uncertainties
tests
security notes
rollback/migration implications
```

---

## 8. Jedna pętla → jeden ograniczony artefakt

Zasada GlitchLab jest przyjmowana globalnie:

```text
one generation loop
→ one primary artifact or one coherent contract change
```

Przykłady:

```text
one Python module
one AgentSpec
one SwarmSpec
one policy file
one schema
one migration adapter
one research promotion record
```

Duże zmiany są dekomponowane do sekwencji audytowalnych delt.

Zmniejsza to:

- hidden coupling,
- złożoność review,
- niepewność rollbacku,
- przeciążenie kontekstu modelu.

---

## 9. Pipeline wygenerowanego kodu

```text
SoftwareBuildSpec
→ code proposal
→ static structure extraction
→ dependency/provenance registration
→ tests generated/updated
→ SAST-Bridge
→ GlitchLab invariants
→ bounded local build
→ BuildReceipt
→ optional isolated execution provider
→ gate for external/deploy effects
```

Dowolny kod modelu nigdy nie jest uznawany za zaufany tylko dlatego, że się skompilował.

---

## 10. Pipeline generowania agenta

```text
MissionSpec
→ required capabilities
→ AgentTemplate selection
→ AgentSpec candidate
→ validate identity/authority/memory/observability
→ simulation or dry-run
→ register AgentSpec version
→ issue AgentInstance identity
→ admit to execution domain
```

Agent template nie może zawierać wielokrotnego użytku production credentials.

---

## 11. Pipeline generowania roju

```text
MissionSpec
→ capability gap
→ candidate agents
→ set-cover / topology planning
→ SwarmSpec candidate
→ risk topology rules
→ authority ceiling validation
→ observability quorum validation
→ simulation / adversarial topology test
→ gate if consequential
→ activate swarm
```

Każdy dynamiczny spawn/reconfiguration emituje `MosaicDelta`.

---

## 12. Aktualizacja reguł i progów

Same reguły również ewoluują. Dlatego wymagane jest rozróżnienie:

```text
runtime data
rule candidate
calibrated threshold candidate
normative rule
```

Przykład ewolucji progu w stylu GlitchLab:

```text
observed metric history
→ EWMA/MAD/quantiles
→ threshold candidate
→ drift check
→ shadow evaluation
→ review/gate
→ spec version update
```

Automatyczna adaptacja **MUSI** mieć granice. System nie może stopniowo normalizować coraz bardziej niebezpiecznego zachowania przez ciągłe przesuwanie progów.

Stosuj:

```text
freeze-on-drift
max-change-per-version
minimum evidence window
manual or independent-agent review for security-critical thresholds
```

---

## 13. Utrzymanie polimorficznego repozytorium

Przedsiębiorstwo jest celowo multi-repository. Zmiany cross-repository wymagają więc `ChangeSet`:

```text
ChangeSet = {
  changeset_id,
  mission_id,
  repository_deltas[],
  dependency_order,
  compatibility_window,
  rollout_order,
  rollback_order,
  expected cross-repo invariants
}
```

Zalecany rollout:

```text
1. contract/schema
2. compatibility adapter
3. provider implementation
4. consumer integration
5. dual-read/dual-write period
6. observability validation
7. remove deprecated path
```

Nigdy nie modyfikuj wszystkich repozytoriów jednocześnie bez pośrednich stanów kompatybilności.

---

## 14. Polityka wygenerowanych artefaktów repozytorium

Repozytoria źródłowe **POWINNY** rozdzielać:

```text
SOURCE
SPEC
GENERATED EPHEMERAL
GENERATED REVIEWABLE
RUNTIME STATE
RESEARCH ARTIFACT
```

Reguły:

- virtualenv/IDE/runtime state nie są source,
- generated source musi mieć provenance,
- duże wyniki symulacji nie powinny po cichu stawać się canonical input,
- artefakty derived zawierają refs source/config/seed,
- secrets nigdy nie są przechowywane jako wygenerowane przykłady z rzeczywistymi wartościami.

---

## 15. Reguły generowania związane z bezpieczeństwem

Każda wygenerowana zmiana dotycząca:

```text
authentication
authorization
credentials
network egress
subprocess/exec
deserialization
file extraction
policy/gate logic
memory write
model/tool delegation
```

**MUSI** uruchamiać security review/testy adversarialne.

Minimalne testy negatywne obejmują:

```text
invalid identity
missing provenance
stale capability
unauthorized delegation
path traversal
shell injection
policy bypass
observability loss
replay corruption
authority escalation
malformed provider output
```

---

## 16. Reguły obserwowalności

Każda consequential enterprise mutation musi emitować wystarczające informacje do rekonstrukcji:

```text
source evidence
proposer
change proposal
policy decision
capability used
execution identity
actual effect
result/outcome
follow-up state
```

Obserwowalność jest częścią permission model, a nie pasywną funkcją monitoringu.

---

## 17. Rollback i supersession

Usunięcie nie jest jedynym sposobem ewolucji.

Artefakty/agenci/polityki mogą mieć stany:

```text
ACTIVE
DEPRECATED
SUPERSEDED
REVOKED
ARCHIVED
```

Supersession zachowuje lineage:

```text
v1 → superseded_by → v2
```

Rollback musi określać, czy przywraca:

- kod,
- kontrakt,
- schema danych,
- stan authority,
- topologię agentów,
- stan pamięci.

---

## 18. Budżet autonomicznych aktualizacji

Nie każda zmiana wymaga human review. Autonomia jest podzielona na lane'y.

### GREEN

Agent może autonomicznie aktualizować:

- read-only indexes,
- derived documentation,
- lokalne test fixtures,
- non-consequential experiment scaffolds,
- wewnętrzne artefakty analityczne.

### AMBER

Wymaga deterministycznego gate i/lub niezależnego verifiera:

- source code change,
- AgentSpec change,
- memory candidate promotion,
- komunikacja zewnętrzna,
- dependency update,
- swarm reconfiguration.

### RED

Wymaga high-assurance approval/enforcement:

- production deployment,
- authority expansion,
- zmiany dostępu do secrets,
- zobowiązania finansowe,
- infrastruktura krytyczna,
- nieodwracalne mutacje danych.

---

## 19. Ciągła regresja przedsiębiorstwa

Skuteczna zmiana tworzy rodzinę regresji.

```text
finding
→ generalized missing invariant
→ deterministic rule where possible
→ regression test
→ adversarial variant set
→ continuous retest
```

Celem nie jest nauczenie modelu jednej odpowiedzi. Celem jest uczynienie niebezpiecznej klasy strukturalnie nieosiągalną albo jawnie bramkowaną.
