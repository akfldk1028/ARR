# External Research Code

Do not put third-party research repository checkouts in this ARR backend folder.

Research repositories are kept outside the ARR runtime tree at:

```text
/mnt/d/Data/25_ACE/clone/maas-aesthetic-texturing/
```

Reason:

- Avoid polluting ARR git status with external code.
- Avoid accidental imports from research repos.
- Avoid installing CUDA/diffusion dependencies into the Django backend venv.
- Keep adapters small and explicit under `design.maas.aesthetic`.

## Current External Checkouts

See:

```text
docs/ai-session-memory/maas-aesthetic-texturing/CODE_REPOS.md
```

Current external repo root:

```text
clone/maas-aesthetic-texturing/
```
