# R&D Operating Model

## 1. R&D is an enterprise organ, not a document folder

In Cyber-Lion, `writeups` is the long-term **R&D / evidence corpus** of the AI-Native enterprise. It stores research questions, falsification reports, architecture hypotheses, security studies, OSINT, simulations, experiments and publications.

Its role is not to directly configure production systems. Its role is to create **candidate knowledge** that can be promoted into executable specifications only after explicit validation.

```text
WORLD / INCIDENT / MARKET / EXPERIMENT
                ↓
            R&D OBSERVATION
                ↓
             HYPOTHESIS
                ↓
       FALSIFICATION / TEST
                ↓
       REPRODUCIBLE EVIDENCE
                ↓
         ENGINEERING RULE
                ↓
          SPEC CANDIDATE
                ↓
       SHADOW / SIMULATION
                ↓
             GATE
                ↓
       NORMATIVE RUNTIME SPEC
```

Core invariant:

```text
RESEARCH CLAIM != RUNTIME AUTHORITY
```

---

## 2. Research object

Every important research result should eventually be representable as:

```text
ResearchRecord = {
  research_id,
  title,
  question,
  hypothesis,
  scope,
  sources,
  evidence_for,
  evidence_against,
  methods,
  simulations,
  assumptions,
  falsifiers,
  limitations,
  epistemic_status,
  confidence,
  artifacts,
  related_findings,
  candidate_rules,
  supersedes,
  superseded_by
}
```

`writeups` remains the human-readable corpus; a future machine-readable index will expose these fields to the platform.

---

## 3. Epistemic states

Use a strict ladder:

```text
QUESTION
→ HYPOTHESIS
→ OBSERVED
→ REPRODUCED
→ ENGINEERING_CANDIDATE
→ SHADOW_VALIDATED
→ NORMATIVE
→ SUPERSEDED
```

This ladder is different from confidence. A highly plausible hypothesis remains a hypothesis until it has the required evidence and validation path.

For quantitative material, preserve the existing distinction:

```text
OBSERVED
DERIVED
CALIBRATED
ASSUMED
HYPOTHESIS
SPECULATION
STRESS_PARAMETER
```

Monte Carlo convergence reduces sampling noise **inside a model**. It does not automatically promote a calibrated assumption into an observed real-world frequency.

---

## 4. Research cells

R&D work is performed by temporary research mosaics rather than one monolithic research agent.

Example:

```text
R&D Cell
├── Source / Evidence Agent
├── Hypothesis Agent
├── Falsification Agent
├── Simulation Agent
├── Security/Methodology Auditor
└── Human Research Owner
```

For lower-risk exploratory work, fewer roles may be combined. For high-impact policy or security research, hypothesis generation and falsification SHOULD be separated across independent agents/providers.

---

## 5. Research event chain

```text
ResearchQuestionCreated
→ ObservationAttached
→ HypothesisGenerated
→ EvidenceAttached
→ HypothesisUpdated
→ SimulationRequested
→ SimulationCompleted
→ FalsificationResult
→ EngineeringRuleProposed
→ SpecCandidateCreated
→ ShadowValidationCompleted
→ GateApplied
→ SpecPromoted
```

All steps should share correlation/provenance IDs through Cyber-Lion `EventEnvelope`.

---

## 6. Promotion classes

### Class R0 — narrative / exploratory

Examples:

- essays,
- analogies,
- conceptual sketches,
- speculative architectures.

May inform hypothesis generation. Cannot become runtime control directly.

### Class R1 — formal hypothesis

Must include:

- explicit proposition,
- falsifiers,
- alternative explanations,
- evidence status.

### Class R2 — reproduced experiment / analysis

Must include:

- reproducible inputs or clear source references,
- method,
- outputs,
- limitations,
- negative results where relevant.

### Class R3 — engineering candidate

A research result is translated into a candidate invariant, policy, schema, algorithm or test.

Requires:

- explicit mapping from evidence → rule,
- failure modes,
- rollback,
- proposed metrics.

### Class R4 — shadow validated

The candidate runs without authority over real consequences and is compared with existing behavior.

### Class R5 — normative

May influence production execution after independent gate/approval and versioned release.

---

## 7. Security research promotion

Security findings use the strongest promotion path:

```text
finding
→ reproduction
→ exploitability/impact classification
→ missing invariant
→ generalized rule
→ regression family
→ GlitchLab/SAST integration
→ shadow validation
→ policy/enforcement candidate
→ gate
→ runtime control
```

A single payload or CVE-specific patch is not the final product. The preferred result is a generalized class-level invariant.

---

## 8. Writeups ↔ ai_platform contract

Target future interface:

```text
writeups ResearchRecord
        ↓
R&D index adapter
        ↓
Cyber-Lion Evidence / Hypothesis registry
        ↓
engineering candidate
        ↓
Agent Foundry / Policy / Simulation / GlitchLab
```

The adapter must preserve original document path, commit SHA, cited sources and epistemic status.

---

## 9. Hypotheses repository ↔ R&D

`hipotezy_nadawcze_LLM` remains a dedicated small laboratory for narrow model/channel hypotheses.

Its records should be linkable into `writeups` by ID, not copied and silently changed.

Target:

```text
HypothesisSpec
→ ExperimentSpec
→ Result
→ ResearchRecord
```

---

## 10. Simulation role

Simulation is a falsification amplifier, not evidence replacement.

A simulation request includes:

```text
model_id
model_version
scenario
parameter distribution
seed strategy
assumptions
requested metrics
stress conditions
```

Output includes:

```text
result
convergence diagnostics
sensitivity
failure region
model-risk notes
```

The system MUST preserve the distinction:

```text
SIMULATED
!=
OBSERVED
```

---

## 11. Research memory

Committed R&D memory should store:

```text
what was known
when it was known
source/evidence
which hypotheses were rejected
which assumptions were used
which rule version was derived
what later superseded it
```

This prevents the organization from repeatedly rediscovering the same problem or silently resurrecting invalidated assumptions.

---

## 12. R&D observability

Measure more than publication count.

Useful metrics:

```text
time question → falsifiable hypothesis
time hypothesis → experiment
reproduction rate
negative-result retention
research → engineering-candidate conversion
candidate → normative conversion
supersession frequency
research lineage completeness
model-risk disclosure completeness
```

The objective is learning velocity with epistemic integrity.

---

## 13. Human role in R&D

Humans remain owners of:

- strategic research questions,
- interpretation of ambiguous real-world evidence,
- ethical/legal scope,
- high-impact promotion decisions,
- deciding whether a useful engineering rule is aligned with enterprise goals.

Agents accelerate collection, formalization, simulation, falsification and synthesis.

---

## 14. Definition of done for a promoted research result

A research result becomes eligible for normative use only when:

```text
1. original evidence is reconstructable
2. epistemic state is explicit
3. falsifiers were defined
4. contrary evidence is retained
5. engineering rule is separately specified
6. tests/regressions exist
7. model/simulation risk is disclosed
8. shadow behavior was observed where applicable
9. authority/security impact is reviewed
10. versioned promotion event exists
11. rollback/supersession path exists
```
