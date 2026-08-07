# Agent Action Journal Contract

Status: initial design contract  
Schema: `qlibx.agent_action_event/v1`

## Purpose

The action journal provides a consistent, queryable record of meaningful qlibx
operations performed by agents, humans, and the system. It answers what was
attempted, which frozen inputs were used, what changed, what was produced, and
whether the operation succeeded.

The journal is operational provenance. It does not replace the research catalog,
which stores hypotheses, evidence conclusions, and research decisions.

## Recording boundary

Every public qlibx operation must emit journal events automatically. Skills and
agents must not be responsible for manually creating complete audit records.

Record:

- Public command or tool calls
- Validation, materialization, execution, publication, and decision operations
- Input and output artifact references
- Project-state changes
- Warnings, accepted limitations, failures, and blocked operations
- User approvals or answers that authorize an otherwise ambiguous operation

Do not record:

- Private model reasoning or hidden chain of thought
- Credentials, tokens, secrets, or authentication material
- Full prompts when a bounded action summary is sufficient
- Raw dataset contents or large artifacts that can be referenced by identity

## Event envelope

Each event is an immutable record with the following shape:

```yaml
schema: qlibx.agent_action_event/v1
event_id: <globally unique id>
operation_id: <id shared by all phases of one operation>
occurred_at: <UTC timestamp>
sequence: <monotonic sequence within the operation>

actor:
  type: agent | human | system
  id: <stable actor id when available>

context:
  project_id: <project identity>
  session_id: <agent or human session>
  run_id: <optional research run>
  parent_event_id: <optional causal parent>
  correlation_id: <optional cross-operation workflow id>

action: data.mapping.validate
phase: requested | started | blocked | succeeded | failed
read_only: true

inputs:
  artifacts: []
  effective_config_id: <optional frozen config>
  parameters: <bounded, redacted action parameters>

outputs:
  artifacts: []
  result_summary: <bounded structured summary>

side_effects:
  changed_paths: []
  created_artifacts: []

warnings: []
accepted_limitations: []

error:
  code: <stable machine-readable code>
  message: <safe human-readable description>
  retryable: false
```

Fields that do not apply may be omitted, but identity, time, actor, context,
action, phase, and read-only status are required.

## Operation lifecycle

An operation uses one `operation_id` and emits separate append-only events for
its lifecycle transitions. A typical successful operation emits `requested`,
`started`, and `succeeded`; a rejected ambiguity emits `requested` and
`blocked`; an execution error emits `requested`, `started`, and `failed`.

Later events do not overwrite earlier events. Retrying an operation creates a
new `operation_id` and references the failed operation through
`parent_event_id` or `correlation_id`.

## Stable action names

Action names use a version-independent dotted namespace. Initial names include:

- `data.inspect`
- `data.mapping.validate`
- `data.registration.create`
- `data.materialize.preflight`
- `data.materialize.qlib`
- `data.validate`
- `profile.list`
- `profile.show`
- `research.proposal.create`
- `research.run.execute`
- `artifact.publish`
- `research.decision.record`

New actions may be added without changing the event schema. Renaming an action
requires an explicit compatibility alias.

## Reliability rules

- Events are append-only, schema-validated, and durably ordered per operation.
- Artifact and config references use immutable content or effective-config IDs.
- A state-changing operation must not begin when its required `started` event
  cannot be recorded.
- Successful state publication and its `succeeded` event must be recoverable as
  one operation; interrupted publication must be detectable and reconcilable.
- Failed, blocked, invalid, and no-op operations remain queryable.
- Concurrent sessions must not overwrite or reorder each other's events within
  an operation.
- Event producers redact sensitive values before persistence.

## Query surface

The public surface must support bounded queries by:

- Event or operation ID
- Time range
- Actor and session
- Action and phase
- Input or output artifact
- Research run or correlation ID
- Changed path
- Failure or warning code

The storage engine and physical file layout remain implementation decisions.
Consumers depend on the event schema and query behavior, not storage internals.
