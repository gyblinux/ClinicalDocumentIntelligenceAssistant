# Repository Instructions

## Spec-Driven Development

- Read `.specify/memory/constitution.md` before changing user-visible behavior.
- Start new work with `$speckit-specify` or update the relevant file under `specs/`.
- Use `$speckit-plan` and `$speckit-tasks` before implementing a new feature.
- Keep requirements, plans, tasks, tests, and changelog entries traceable.
- Advance only after explicit user approval between specification, planning,
  task generation, and implementation.
- Keep ingestion, question answering, and evaluation independently controllable
  in specifications, plans, and tasks.
- Treat `.specify/templates/` as upstream Spec Kit assets; customize project
  behavior through `.specify/memory/constitution.md` and installed presets.

## Changelog

- Maintain `CHANGELOG.md` with a concise entry for every push.
- Add the entry before pushing and include it in the same commit as the related change.
- Group entries under `Added`, `Changed`, `Fixed`, or `Security`.
- Keep bullets focused on user-visible or operationally important changes.
