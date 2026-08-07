# qlibx Product Requirements Document

## Document status

| Field | Value |
|---|---|
| Version | 2.0 draft |
| Target | qlibx research core v1 |
| Updated | 2026-08-08 |
| Status | Proposed replacement PRD |
| Historical predecessor | docs/qlibx-prd.md |
| Reference evidence | KOSPI 200 low-P/B first cycle |

The historical PRD remains preserved. This document is a proposed replacement
that incorporates evidence from the first completed research cycle.

Normative language:

- **MUST** — required for v1.
- **SHOULD** — expected unless a documented constraint prevents it.
- **MAY** — optional.

---

## 1. Product thesis

### 1.1 Definition

qlibx is an agent-facing financial research control plane.

It helps people and AI coding agents turn financial hypotheses and
project-owned data into reproducible, reviewable evidence. It coordinates:

- Data inspection and registration.
- Point-in-time research inputs.
- Frozen study definitions.
- Eligibility and integrity audits.
- Deterministic evaluation.
- Evidence classification.
- Provenance, reuse, and reporting.

Qlib is a compatible research backend. In v1, qlibx primarily uses Qlib as a
standard financial-data interface. Qlib execution and account simulation are
future capabilities, not prerequisites for useful research.

### 1.2 Problem

Agent-generated financial research can become unreliable when:

- Source headers or financial meanings are guessed.
- Dated data is assumed to have been available historically.
- Index membership and security identity changes are ignored.
- Missing prices or corporate actions are silently repaired.
- Rules are changed after results are seen.
- Equivalent operations are implemented differently by different agents.
- Successful computation is confused with valid evidence.
- Results lack enough lineage to reproduce later.

qlibx makes these failure modes explicit and controllable.

### 1.3 Core value

The primary output is not a backtest number. It is an evidence package whose
inputs, rules, limitations, integrity, and decision boundary are inspectable.

A completed study classified as invalid can be a successful qlibx outcome when
the system correctly prevents unreliable evidence from becoming an investment
claim.

### 1.4 v1 outcome

For daily equity research, a user or agent can:

1. Register unfamiliar local financial data without modifying it.
2. Resolve ambiguous semantics explicitly.
3. Build a versioned Qlib-compatible research provider.
4. Freeze a study before viewing its performance.
5. Audit whether its evidence is usable.
6. Execute deterministic comparisons and diagnostics.
7. Separate operational completion from evidence validity.
8. Preserve and reproduce the complete evidence package.
9. Start a separate follow-up study without rewriting history.

---

## 2. Scope and maturity

### 2.1 v1 scope

v1 covers:

- Daily listed-equity research.
- Fundamental and market-derived cross-sectional signals.
- CSV, Parquet, and DuckDB sources.
- Explicit source-to-canonical column mappings.
- Dataset profiling, hashing, registration, and versioning.
- Dynamic point-in-time universes.
- Qlib-compatible daily research profiles.
- Frozen study specifications.
- Eligibility, availability, and integrity audits.
- Deterministic portfolio comparisons.
- Discovery and confirmation segments.
- Risk, turnover, exposure, regime, and concentration diagnostics.
- Immutable artifacts and append-only operation history.
- Minimal queryable research history.
- Markdown and HTML evidence reports.
- Agent-facing CLI, schemas, errors, examples, and skills.

The initial reference study is monthly fundamental equity research. Public
contracts MUST NOT hardcode P/B, KOSPI 200, quintiles, or one portfolio design.

### 2.2 v1 non-goals

v1 does not provide:

- Live orders or broker integration.
- Investment approval or guaranteed profitability.
- Native or synthetic short execution.
- Borrow, margin, locate, recall, or forced buy-in models.
- Full market-microstructure simulation.
- General portfolio optimization or alpha ensembles.
- Enhanced-index or ETF look-through construction.
- Futures, options, bonds, or derivative lifecycles.
- Embedded AI investment-decision strategies.
- Organization-wide compliance or fund-governance workflows.

Future work may address these subjects through separate requirements.

### 2.3 Capability maturity

| Capability | State | v1 treatment |
|---|---|---|
| Source inspection and mapping | First-cycle validated | Core |
| CSV, Parquet, DuckDB registration | First-cycle validated | Core |
| Immutable registrations | First-cycle validated | Core |
| Qlib daily research provider | First-cycle validated | Core |
| Frozen study and audit | First-cycle validated | Core |
| Deterministic evaluation | Study-specific implementation | Generalize |
| Artifact hashes and reproduction | First-cycle validated | Core |
| Append-only action journal | First-cycle validated | Core |
| Instrument successor mapping | Missing; blocked first cycle | Add |
| Revision-aware fundamentals | Provenance unknown | Add contract |
| Research catalog | Filesystem only | Add minimal catalog |
| Transaction costs and execution | Deferred | Later |
| Signed alpha and short compatibility | Design only | RFC |
| StrategyAgent and ensembles | Design only | Future |
| Multi-asset research | Vision only | Future |

---

## 3. Users and jobs

### 3.1 Primary users

- Researchers proposing or reviewing investment hypotheses.
- Coding agents working for those researchers.
- Data reviewers validating meaning and information timing.
- Independent reviewers checking evidence and limitations.
- Maintainers extending qlibx through public contracts.

One person or agent may perform several roles. A permanent persona selection is
not required.

### 3.2 Core jobs

#### Register data safely

Make a local dataset available without modifying the source or inventing its
financial meaning.

#### Define a bounded study

Freeze the hypothesis, timing, comparison, statistics, and invalidating
conditions before evaluating performance.

#### Decide whether evidence is usable

Allow data quality, look-ahead risk, corporate actions, and missing observations
to affect the evidence classification.

#### Reproduce and review

Identify exactly which source, mapping, implementation, runtime, and config
produced every result.

#### Continue from prior evidence

Use supported, challenged, inconclusive, failed, and invalid studies to guide
the next distinct study.

---

## 4. Product principles

1. **Evidence before performance.** Evidence integrity is evaluated before
   performance is presented as a conclusion.
2. **Public contracts for agents.** Supported work does not require reading
   private package source.
3. **Raw data remains project-owned.** Inspection and registration are
   read-only.
4. **Ambiguity is explicit.** Unsafe semantic guesses return a structured
   blocked result.
5. **Time semantics are declared.** Observation date is not proof of historical
   availability.
6. **Runs use frozen inputs.** Later edits do not alter existing results.
7. **Invalid work remains valuable.** Failed and invalid work stays queryable.
8. **Artifacts connect components.** Public boundaries use documented,
   serializable results.
9. **Qlib integration is modular.** Research remains useful without execution.
10. **Requirements precede implementation.** Storage, locking, classes, and Git
    topology are architecture decisions unless they affect public behavior.

---

## 5. System structure and lifecycle

### 5.1 Components

#### Agent interface

Commands, schemas, documentation, stable errors, and task skills.

#### Data control

Source inspection, semantic mapping, profiling, registration, identity,
materialization, and validation.

#### Research control

Frozen study definitions, eligibility audits, deterministic execution, and
diagnostics.

#### Evidence control

Integrity and evidence classification, artifacts, reports, prior-research
queries, and follow-up decisions.

#### Governance

Operation history, immutable identities, warnings, limitations, and safe
publication across all components.

### 5.2 Lifecycle

~~~text
question
→ inspect source
→ confirm mapping
→ register immutable data
→ materialize target profile
→ freeze study
→ audit eligibility and integrity
→ execute deterministically
→ classify integrity and evidence
→ publish artifacts and report
→ define a separate next action
~~~

### 5.3 Stage gates

| Gate | Exit condition |
|---|---|
| Registration | Confirmed semantics, valid keys, immutable identity |
| Profile | Valid provider with declared capabilities and exclusions |
| Study | Frozen timing, comparisons, statistics, and invalidation policy |
| Audit | Structured pass, warning, or failure result |
| Execution | Complete artifacts or structured failure |
| Evidence | Integrity, outcome, and next action recorded separately |
| Publication | Atomic output, verified hashes, completed journal lifecycle |

An audit failure MAY allow descriptive calculations if the frozen study permits
them. Such calculations remain non-evidentiary.

---

## 6. Domain and status model

### 6.1 Core objects

| Object | Responsibility |
|---|---|
| Project | Owns data, config, generated state, extensions, and evidence |
| Dataset registration | Binds one source snapshot to canonical semantics |
| Dataset snapshot | Immutable registered source content |
| Target profile | Standard calendar, universe, feature, and storage contract |
| Study specification | Frozen research and decision policy |
| Audit result | Checks, coverage, warnings, failures, and affected observations |
| Research run | Execution of one effective study against immutable inputs |
| Evidence artifact | Portable holdings, returns, metrics, diagnostics, or report |
| Evidence decision | Integrity, evidence outcome, and next research action |
| Action event | Append-only record of a public operation |
| Catalog record | Queryable reference to canonical project evidence |

### 6.2 Identity

Identity is content based.

A changed source, mapping, semantic interpretation, profile, study rule,
implementation, runtime compatibility boundary, or declared seed MUST change
the dependent identity.

Timestamps and storage paths MUST NOT be the sole identity of canonical
content.

### 6.3 Status dimensions

#### Operation phase

- requested
- started
- blocked
- succeeded
- failed

#### Run completion

- complete
- failed
- incomplete

#### Study integrity

- valid
- invalid
- not_assessed

#### Evidence outcome

- supported
- challenged
- inconclusive
- not_evaluated

#### Research action

- stop
- revise
- follow_up
- retain_diagnostic
- reject
- promote_research
- supersede

These dimensions MUST remain separate.

A complete run can have invalid integrity. Invalid integrity normally requires
not_evaluated evidence. promote_research means another research stage, not live
investment approval.

### 6.4 First-cycle representation

| Dimension | Value |
|---|---|
| Operation | succeeded |
| Run completion | complete |
| Study integrity | invalid |
| Evidence outcome | not_evaluated |
| Research action | revise |

Descriptive performance may be preserved without contradicting these states.

---

## 7. Functional requirements

### 7.1 Project and runtime

- **PRJ-001** — qlibx MUST discover a selected project without requiring one
  fixed directory layout.
- **PRJ-002** — Public operations MUST use project-relative paths and keep
  generated state distinct from raw sources.
- **PRJ-003** — Run manifests MUST record qlibx, Python, relevant dependency,
  Qlib adapter, and Qlib runtime identity.
- **PRJ-004** — Unsupported runtime combinations MUST fail with a stable error
  and recovery guidance.
- **PRJ-005** — Initialization SHOULD recommend safe ignore rules without
  silently replacing user-authored rules.

Acceptance: a public status command explains the active project, data roots,
generated roots, package version, and runtime compatibility.

### 7.2 Source inspection and registration

- **DATA-001** — Inspection and registration MUST NOT modify source files.
- **DATA-002** — CSV, Parquet, and DuckDB sources MUST be supported.
- **DATA-003** — Registrations MUST declare canonical fields, explicit mappings,
  keys, frequency, time semantics, and limitations.
- **DATA-004** — Automatic mapping MAY resolve only unambiguous aliases; missing
  or conflicting candidates MUST return mapping_confirmation_required.
- **DATA-005** — User judgment MUST be explicitly confirmed before publication.
- **DATA-006** — Profiling MUST report rows, date coverage, required nulls, key
  uniqueness, and schema-relevant invalid values.
- **DATA-007** — Registration identity MUST include complete source content,
  mapping, semantics, schema, limitations, and producer implementation.
- **DATA-008** — Identical registration is idempotent; conflicting reuse of a
  dataset version fails.
- **DATA-009** — Registration records MUST avoid secrets, raw rows, and
  unbounded samples.

Acceptance: the same confirmed bundle returns the same ID without rewriting the
registry, while an ambiguous fixture publishes nothing.

### 7.3 Information-time contract

- **TIME-001** — Schemas MUST distinguish observation time from decision-time
  availability.
- **TIME-002** — Where relevant, data SHOULD declare observed_at, available_at,
  effective_from, effective_to, and revision or vintage identity.
- **TIME-003** — Unknown availability or revision semantics MUST remain a
  structured limitation rather than being inferred from the date.
- **TIME-004** — Each study MUST declare whether an unknown time semantic warns,
  blocks execution, or invalidates evidence.
- **TIME-005** — Data access MUST not expose information beyond the declared
  decision boundary; historical membership uses the relevant effective date.
- **TIME-006** — Study windows MUST distinguish warm-up, discovery,
  confirmation, reserved, and closeout dependency periods.
- **TIME-007** — Closeout-only data MUST NOT create another evaluated holding
  period.

Acceptance: future membership and later data revisions cannot affect an earlier
test decision.

### 7.4 Instrument identity and corporate actions

- **INST-001** — v1 MUST define canonical instrument identity separately from a
  mutable listing code or display name.
- **INST-002** — A security master MUST represent listing dates, predecessors,
  successors, and conversion relationships.
- **INST-003** — Supplied corporate-action data MUST distinguish split-like
  quantity adjustments, reference-price adjustments, cash distributions,
  mergers, conversions, and delistings.
- **INST-004** — Adjustment-factor semantics MUST be declared; event-day factors
  MUST NOT be silently treated as cumulative Qlib factors.
- **INST-005** — Equivalent return formulas SHOULD be cross-checked when the
  source supplies all required fields.
- **INST-006** — qlibx MUST NOT invent successor mappings or silently drop,
  replace, or fill affected selected securities.
- **INST-007** — Unresolved successor events MUST follow the study's frozen
  invalidation policy; changing treatment after results requires a new study.

Acceptance: an A000030-style fixture remains invalid until an explicit,
registered continuity policy is supplied.

### 7.5 Target profiles and materialization

- **PROF-001** — Profiles MUST have stable versioned IDs and declare calendar,
  universe, features, dtype, missing behavior, capabilities, and exclusions.
- **PROF-002** — Raw headers belong to registration; profiles use canonical
  feature names.
- **PROF-003** — Preflight MUST validate schema, paths, fields, transforms, and
  compatibility without a full data scan.
- **PROF-004** — Materialization MUST be deterministic and publish atomically
  from a temporary build.
- **PROF-005** — Conflicting existing output MUST fail rather than overwrite.
- **PROF-006** — Structural validation MUST cover calendar, universe intervals,
  feature bounds, binary shape, and required coverage.
- **PROF-007** — Supported Qlib adapters MUST include public-API smoke testing,
  not only direct binary checks.
- **PROF-008** — Identity MUST include profile, config, registrations, sources,
  producer, and runtime compatibility.

Acceptance: repeated builds return one verified identity and sampled Qlib API
values equal direct expected values.

### 7.6 Frozen study specification

- **STUDY-001** — Studies MUST have stable versioned IDs, a question, and a
  proposed mechanism.
- **STUDY-002** — Studies MUST reference immutable registrations and profiles.
- **STUDY-003** — Universe, eligibility, signal, observation, entry, exit,
  holding horizon, and rebalancing MUST be explicit.
- **STUDY-004** — Portfolio construction, weighting, ties, missing inputs,
  missing returns, and cash behavior MUST be explicit.
- **STUDY-005** — Study periods, comparisons, metrics, uncertainty method, and
  evidence rules MUST be explicit.
- **STUDY-006** — Search limits, stopping rules, invalidating conditions, and
  accepted limitations MUST be explicit.
- **STUDY-007** — Preregistered comparisons MUST be distinguishable from
  exploratory analysis added after results.
- **STUDY-008** — Amendments MUST be dated and frozen before affected results;
  later changes create a new study version.
- **STUDY-009** — Evaluator contracts MUST be task agnostic and MUST NOT require
  P/B-specific implementation.

Acceptance: changing any frozen rule, period, limitation policy, or seed changes
the effective study identity.

### 7.7 Eligibility and integrity audit

- **AUDIT-001** — Audit MUST use the same frozen inputs as execution.
- **AUDIT-002** — It MUST evaluate universe coverage, signal eligibility, entry
  availability, holding-return completeness, and time boundaries.
- **AUDIT-003** — It MUST report dynamic-universe additions and removals and
  identify affected instruments, dates, and portfolios.
- **AUDIT-004** — It MUST run declared corporate-action and return-construction
  checks.
- **AUDIT-005** — Rules and thresholds MUST be part of the study identity.
- **AUDIT-006** — Results MUST distinguish passes, warnings, accepted
  limitations, and failures.
- **AUDIT-007** — Failure behavior follows frozen policy and cannot be weakened
  after observing performance.
- **AUDIT-008** — Descriptive output after a blocking failure MUST be labeled
  non-evidentiary.

Acceptance: deterministic fixtures produce structured pass, warning, and failure
states that control integrity classification.

### 7.8 Research execution

- **RUN-001** — Execution MUST resolve an immutable effective config first.
- **RUN-002** — Manifests MUST record study, data, profile, implementation,
  runtime, and seed identities.
- **RUN-003** — Stable ordering and declared seeds MUST make deterministic
  operations reproducible.
- **RUN-004** — Holdings and weights at every decision point MUST be preserved.
- **RUN-005** — Entry, holding, exit, and rebalance calculations MUST follow the
  study clock exactly.
- **RUN-006** — Missing values follow declared policy; silent zero filling or
  replacement is forbidden.
- **RUN-007** — Turnover, metrics, annualization, and statistical resampling MUST
  declare their exact semantics.
- **RUN-008** — Exposure and regime results are diagnostics unless the frozen
  study explicitly uses them in decision logic.
- **RUN-009** — Failed or incomplete execution MUST not appear as a verified
  complete run.
- **RUN-010** — Re-execution MUST compare every canonical artifact hash and
  report reproduced true or a conflict.

Acceptance: the reference study executes twice with identical canonical
artifact bytes and without rewriting its first publication.

### 7.9 Evidence decisions

- **EVID-001** — Operation, completion, integrity, evidence outcome, and
  research action MUST be separate fields.
- **EVID-002** — Complete execution MUST NOT imply supported evidence.
- **EVID-003** — Invalid integrity requires not_evaluated evidence unless a
  separate valid subset was preregistered.
- **EVID-004** — Rationale MUST reference supporting or failing artifacts.
- **EVID-005** — Invalid performance MAY be preserved only as descriptive
  diagnostics with limitations and warnings.
- **EVID-006** — Follow-up recommendations are separate from retroactive changes.
- **EVID-007** — Research promotion MUST NOT be described as live investment
  approval.

Acceptance: the first cycle is represented as complete and invalid without
implying support or challenge for low P/B.

### 7.10 Artifacts and lineage

- **ART-001** — Canonical artifacts MUST record type, schema, content hash,
  producer, parents, and input references.
- **ART-002** — Metadata MUST declare relevant time range, axis, units, currency,
  timezone, and semantics.
- **ART-003** — Artifacts MUST be portable and readable without live strategy
  objects.
- **ART-004** — Publication MUST be atomic; incomplete output cannot appear
  verified.
- **ART-005** — Same identity with different bytes MUST raise a provenance
  conflict.
- **ART-006** — Reporting MUST reuse artifacts without rerunning research.
- **ART-007** — Source data is referenced by identity, not copied into evidence
  by default.
- **ART-008** — Public verification MUST detect changed artifact bytes.

Acceptance: changing one published artifact fails verification without changing
its manifest or prior evidence.

### 7.11 Journal and catalog

- **GOV-001** — Every public operation MUST emit append-only lifecycle events.
- **GOV-002** — Events MUST record actor, context, action, phase, read-only
  status, bounded inputs, outputs, warnings, and changed paths.
- **GOV-003** — Events MUST redact secrets and avoid raw or unbounded data.
- **GOV-004** — Blocked, failed, no-op, and succeeded operations remain
  queryable; journal records remain separate from research evidence.
- **GOV-005** — v1 MUST provide a minimal project-local catalog indexing data,
  studies, runs, integrity, evidence outcomes, decisions, and artifacts.
- **GOV-006** — Agents MUST be able to find prior failed and invalid studies
  before proposing similar work.
- **GOV-007** — Concurrent publication MUST not overwrite another operation,
  regardless of Git topology.

Acceptance: the first invalid run is discoverable by study, dataset, instrument
issue, or integrity status.

### 7.12 Reporting

- **REPORT-001** — Report calculations MUST come from stored artifacts rather
  than reimplementing research logic in rendering code.
- **REPORT-002** — Standard reports MUST show the question, statuses, primary
  comparisons, diagnostics, limitations, and next action.
- **REPORT-003** — Invalid evidence MUST be visibly labeled; descriptive
  performance cannot be presented as a conclusion.
- **REPORT-004** — Markdown, HTML, notebook, image, or document renderers MAY use
  the same evidence without creating a new research run.

Acceptance: one stored run can produce the first-cycle Markdown report and HTML
presentation with unchanged evidence identity.

### 7.13 Agent-facing experience

- **AGENT-001** — Public help MUST expose supported workflows and side effects.
- **AGENT-002** — Schemas and examples MUST be discoverable without private
  imports.
- **AGENT-003** — Errors MUST have stable codes, safe messages, and suggested
  next actions.
- **AGENT-004** — Instructions and skills MUST require inspection before writes
  and human clarification for unresolved semantics.
- **AGENT-005** — Skills MUST be versioned, validated, and explain source
  immutability, confirmation, validation, and idempotence.
- **AGENT-006** — Agents MUST report changed files, artifacts, limitations, and
  validation outcomes.
- **AGENT-007** — Agents MUST inspect prior failed and invalid evidence before
  repeating a related study.

Acceptance: an agent using only public help and skills can register an
unambiguous fixture and correctly block an ambiguous one.

### 7.14 Extensions

- **EXT-001** — v1 SHOULD define minimal public contracts for evaluators,
  diagnostics, and report sections.
- **EXT-002** — Extensions MUST declare artifact schemas, time boundaries,
  side effects, and validation.
- **EXT-003** — Invalid extension output MUST fail before verified publication.
- **EXT-004** — Extensions MUST NOT require modification of qlibx, Qlib, or
  site-packages.

Discovery mechanisms and class structures are architecture decisions.

---

## 8. Non-functional requirements

### 8.1 Determinism and reliability

- **NFR-DET-001** — Unordered inputs MUST use stable ordering.
- **NFR-DET-002** — Randomized methods MUST use declared seeds.
- **NFR-REL-001** — Publication is atomic or detectably incomplete.
- **NFR-REL-002** — Idempotent retries do not duplicate canonical content.
- **NFR-REL-003** — Crashes cannot corrupt previously verified artifacts.

### 8.2 Performance

- **NFR-PERF-001** — Header inspection and preflight avoid full scans.
- **NFR-PERF-002** — Full profiling and materialization SHOULD stream or batch
  rather than require memory proportional to the entire source.
- **NFR-PERF-003** — Long operations SHOULD expose bounded progress.
- **NFR-PERF-004** — Benchmarks include multi-million-row first-cycle-scale
  inputs.

### 8.3 Security and privacy

- **NFR-SEC-001** — Paths remain within the selected project unless an explicit
  external-source policy permits otherwise.
- **NFR-SEC-002** — Logs and errors redact credentials and sensitive values.
- **NFR-SEC-003** — qlibx does not commit, upload, or copy raw data without
  explicit user action.

### 8.4 Compatibility

- **NFR-COMP-001** — Public schemas are versioned.
- **NFR-COMP-002** — Breaking changes provide migration or explicit failure.
- **NFR-COMP-003** — Qlib adapters declare supported Qlib and Python versions.
- **NFR-COMP-004** — Human and machine-readable output represent the same facts.

---

## 9. Public capability groups

v1 MUST expose public operations for:

- Project and runtime inspection.
- Profile discovery.
- Source inspection, mapping validation, and registration.
- Materialization preflight, build, and validation.
- Study validation, audit, execution, and reproduction.
- Artifact verification and inspection.
- Journal and research-catalog queries.
- Evidence-decision inspection.
- Report rendering.

Exact command names MAY evolve. Schemas, observable behavior, and stable error
families are the compatibility contract.

Initial error families include:

- mapping confirmation required
- source changed
- dataset version conflict
- unresolved time semantics
- profile incompatibility
- validation failed
- unresolved instrument successor
- frozen config conflict
- artifact provenance conflict
- unsupported runtime
- incomplete publication

---

## 10. v1 acceptance plan

### 10.1 Registration

Using CSV, Parquet, and DuckDB fixtures:

- Unambiguous mappings register.
- Ambiguous mappings block without publication.
- Invalid dates, nulls, and duplicate keys are reported.
- Source hashes remain unchanged.
- Repetition is idempotent.
- Changed content requires a new registration version.

### 10.2 Point-in-time behavior

Using future-membership, revised-value, and delayed-availability fixtures:

- Earlier decisions cannot see later information.
- Unknown provenance remains a limitation.
- Frozen policy determines whether it warns or invalidates.
- Closeout dates do not create an extra evaluation month.

### 10.3 Corporate actions

Using split, conversion, delisting, and missing-successor fixtures:

- Declared adjustment formulas are checked.
- Event-day and cumulative factors remain distinct.
- Registered successors follow frozen policy.
- Unresolved selected holdings invalidate when policy requires.

### 10.4 Qlib provider

- Calendar and dynamic universe intervals validate.
- Required feature binaries validate.
- Public Qlib APIs load representative data.
- Sample values match direct expected values.
- Repeated materialization returns the same identity.

### 10.5 Study execution

Using a valid synthetic study:

- Timing and portfolio rules are exact.
- Ties and missing values are deterministic.
- Holdings, returns, turnover, metrics, and diagnostics are preserved.
- Repetition reproduces every canonical artifact.

Using the A000030-style reference:

- The run may complete descriptively.
- Integrity is invalid.
- Evidence is not_evaluated.
- The report makes no support or challenge claim.
- Any fix requires a separate study version.

### 10.6 Governance and agent use

- All operation phases are queryable.
- Failed, incomplete, and invalid studies are queryable.
- Catalog traversal connects study, run, artifact, and decision.
- Concurrent publications do not overwrite each other.
- An agent can complete the workflow using public documentation and skills.

---

## 11. Success measures

v1 success is reliability and clarity, not discovery of profitable alphas.

Required measures:

- Zero raw-source modification in supported workflows.
- Complete identity reuse for unchanged registration and materialization.
- Complete artifact-hash equality for repeated deterministic runs.
- No invalid study classified as supported or challenged.
- Every run references immutable inputs and producer identity.
- Every state-changing operation has a complete or recoverable journal
  lifecycle.
- Every v1 requirement maps to a test, fixture, or inspectable artifact.

Usability outcomes:

- A new teammate can explain qlibx v1 after reading sections 1–5.
- An agent can find task instructions without loading this entire PRD.
- A reviewer can identify why a study was invalid from its decision and audit.
- A follow-up can reuse prior data without altering the original study.

---

## 12. Risks and decisions

### 12.1 Revised fundamental data

Risk: historical ratios may include later revisions.

Decision: v1 models availability and revision semantics. Unknown provenance is
not silently treated as point-in-time safe.

### 12.2 Instrument continuity

Risk: mergers, conversions, delistings, and identifier changes can break holding
returns.

Decision: security identity and successor data are v1 priorities and can block
strong evidence claims.

### 12.3 Qlib compatibility

Risk: Qlib and qlibx may require different Python environments.

Decision: adapters record exact runtime identity and use public-API smoke tests.
Unsupported combinations fail explicitly.

### 12.4 Overfitting the reference study

Risk: current code may encode P/B and monthly-quintile assumptions.

Decision: retain the first study as a conformance fixture while extracting
task-agnostic registration, audit, evaluator, diagnostics, and artifact
contracts.

### 12.5 Premature platform scope

Risk: short workarounds, optimization, and execution can dominate work before
research evidence is reliable.

Decision: these features require later PRDs or approved RFCs.

---

## 13. Delivery roadmap

### 13.1 Completed foundation

The first cycle established:

- Confirmed data-registration bundles.
- Immutable source and implementation identity.
- Qlib daily provider materialization.
- Frozen study logic and integrity audit.
- Deterministic metrics and reproduction.
- Append-only action journaling.
- Evidence artifacts and reporting.
- An honest invalid decision.

### 13.2 Milestone A — Contract consolidation

- Adopt this domain and status model.
- Version current public schemas.
- Add project/runtime and artifact inspection.
- Align CLI terminology with this PRD.

### 13.3 Milestone B — Time and instrument integrity

- Register security-master and successor data.
- Add corporate-action schemas.
- Add availability and revision metadata.
- Add time-boundary conformance fixtures.

### 13.4 Milestone C — General research core

- Extract P/B-specific behavior into a reference study.
- Define task-agnostic evaluator contracts.
- Generalize eligibility and missing-data policies.
- Preserve the first cycle as a golden invalid fixture.
- Add a valid conformance study.

### 13.5 Milestone D — Evidence reuse

- Add the minimal research catalog.
- Query prior failed and invalid evidence.
- Render reports from stored artifacts.
- Validate concurrent publication.
- Complete end-to-end agent acceptance.

### 13.6 Later

- Transaction costs, taxes, spreads, and market impact.
- Sector, size, momentum, and beta controls.
- Portfolio constraints and optimization.
- Robustness-study orchestration.
- Stored-alpha combinations.

### 13.7 Future or separate RFC

- Qlib execution adapters.
- Signed alpha and short compatibility.
- ETF and index look-through.
- Futures and options.
- Adaptive or nested StrategyAgent behavior.
- AI-backed local strategies.

---

## 14. Design documents outside this PRD

The following belong in Architecture Decision Records or RFCs:

- Qlib binary layout.
- Catalog storage engine.
- Atomic publication and locking mechanism.
- Python extension discovery.
- General StrategyAgent class design.
- Nested research.
- Matched-capitalization accounting.
- Enhanced-index optimization.
- ETF look-through.
- Multi-asset lifecycles.
- Embedded AI strategy runtimes.

These designs may change while preserving the behavior required here.

---

## 15. First-cycle traceability

Reference study:

| Field | Value |
|---|---|
| Study | k200-low-pbr/v1 |
| Discovery | 2018–2022 |
| Confirmation | 2023–2025 |
| Comparisons | Low P/B vs eligible baseline and high P/B |
| Completion | complete |
| Integrity | invalid |
| Evidence | not_evaluated |
| Blocking issue | Missing A000030 successor and holding returns |

Validated requirement areas:

- Registration: DATA.
- Provider materialization: PROF.
- Frozen study: STUDY.
- Eligibility and integrity: AUDIT.
- Deterministic execution: RUN.
- Evidence separation: EVID.
- Artifacts and journal: ART and GOV.
- Reporting: REPORT.

Requirements discovered through the cycle:

- Revision-aware data: TIME.
- Explicit closeout windows: TIME-006 and TIME-007.
- Security continuity: INST.
- Runtime manifests: PRJ-003 and PRJ-004.
- Separate evidence states: EVID.
- Minimal research catalog: GOV-005 and GOV-006.

The first-cycle performance remains descriptive. It does not validate a low-P/B
alpha, demonstrate investability, or authorize trading.

---

## 16. Glossary

| Term | Meaning |
|---|---|
| Alpha | A return hypothesis or signal; not a claim of proven profitability |
| Availability time | Earliest time a decision may use an observation |
| Canonical artifact | Immutable, versioned, hash-verified research output |
| Closeout period | Data needed only to exit the last evaluated holding |
| Corporate action | Event changing price, quantity, cash flow, or identity |
| Decision time | Time at which permitted information determines an action |
| Descriptive result | Diagnostic calculation not treated as valid evidence |
| Effective config | Fully resolved immutable configuration for one operation |
| Evidence outcome | Supported, challenged, inconclusive, or not_evaluated |
| Instrument | Canonical security identity, separate from a mutable code |
| Integrity | Whether data, timing, and construction satisfy study rules |
| Logical dataset | Financial-data contract independent of raw storage syntax |
| Observation time | Time or period to which a recorded value refers |
| Point-in-time safe | Reflects information available at the historical decision |
| Research catalog | Queryable index of studies, evidence, and decisions |
| Research run | Execution of a frozen study against immutable inputs |
| Study | Preregistered question and complete evaluation policy |
| Successor mapping | Registered continuity across a conversion or reorganization |
| Target profile | Standard calendar, universe, feature, and storage contract |

---

## 17. Adoption criteria

Before adoption, the team should confirm:

1. v1 centers daily equity research rather than execution.
2. Qlib provider compatibility is core; Qlib execution is deferred.
3. The five status dimensions are accepted.
4. Instrument identity and corporate actions are v1 priorities.
5. Revision-aware time semantics are required.
6. The catalog begins as a minimal project-local capability.
7. StrategyAgent, ensemble, and signed execution move to separate RFCs.
8. Every v1 requirement receives a test, fixture, or inspectable artifact.

After adoption, this PRD changes only when product behavior or scope changes.
Implementation choices are recorded separately.
