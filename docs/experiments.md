# Declarative Veyra experiments

Veyra supports a versioned YAML form of `.veyra` alongside the original brace-format test DSL.
The declarative form is intended for reproducible execution, inspection, and structured export.

```yaml
name: projectile-runtime-reference
version: 1
parameters:
  velocity:
    value: 42
    unit: m/s
  angle:
    value: 38
    unit: deg
  gravity:
    value: 9.80665
    unit: m/s^2
simulation:
  engine: mechanics.projectile
  solver: analytic
outputs:
  - range
  - max_height
  - flight_time
assert:
  - expression: range > 0
```

Run the complete validation before execution:

```bash
veyra validate experiment.veyra
veyra graph experiment.veyra
veyra run experiment.veyra
```

## Schema v1

- `name` — required experiment identifier.
- `version` — schema version; currently `1`.
- `parameters` — named values with an optional Pint-compatible `unit` and `uncertainty`.
- `simulation.engine` — `mechanics.projectile`, `mathematics.symbolic`, or a Veyra catalog model.
- `simulation` — optional `solver`, `rtol`, and `atol`; tolerances remain visible in the artifact.
- `outputs` — requested kernel metrics. Projectile aliases are `range`, `max_height`, and `flight_time`.
- `assert` — assertions over actual output metrics; a failed assertion makes the run fail.
- `monte_carlo` — `samples` and an explicit deterministic `seed`.
- `resources` and `references` — recorded execution intent and citations; resource limits are metadata in v1, not an OS sandbox.

The parser accepts the documented indentation-based YAML subset: mappings, scalar lists, quoted
or unquoted scalar values, and comments. It deliberately rejects YAML tags, anchors, aliases,
and unrecognised fields instead of interpreting executable content.

## Results

Every persisted run writes a JSON `.veyr` artifact under `.veyra/results/`. It records the run,
experiment definition, graph, selected outputs, runtime/platform metadata, deterministic hash,
and random seed. The runtime cache is stored separately in `.veyra/cache/` and only used after
validation succeeds.

Veyra does not claim a result from a cached record is freshly computed: the graph marks its
execution, output, and assertion nodes as `cached` and includes `cache_hit: true` in the
reproducibility metadata.
