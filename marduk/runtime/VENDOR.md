# Vendored runtime

The Python files in this directory are **vendored copies** of the PLAN runtime
maintained in the Gallowglass repo. They are treated as read-only inside
Marduk; do not edit them in place. Re-sync via `scripts/sync_runtime.sh` (or
hand-copy and update this file's SHA block).

## Source

- **Repo:** `git@github.com:sigilante/gallowglass.git`
- **Branch:** `main`
- **Commit:** `48519f7e2d7286ffca91fd3b768c747a02ad3401`
- **Sync date:** 2026-05-07
- **Sync method:** manual (initial vendor)

## Files

| Vendored path                       | Source path (in gallowglass)     | Source blob SHA                            |
|-------------------------------------|----------------------------------|--------------------------------------------|
| `marduk/runtime/plan.py`            | `dev/harness/plan.py`            | `215bd00dceab5c3f9631741119d8b70045e524eb` |
| `marduk/runtime/bplan.py`           | `dev/harness/bplan.py`           | `6be8416118afb7096a3ac465705562f3f0b474ea` |
| `marduk/runtime/bplan_deps.py`      | `bootstrap/bplan_deps.py`        | `86c90ab20f97dcf6caf110dc2c3519ef8d2c1223` |

(Blob SHAs are `git hash-object` of the upstream file at the sync commit. They
are *not* the post-rewrite SHAs of the vendored copy — they pin upstream
content so drift is detectable even if the vendored copy is locally edited.)

## Import-rewrite delta

The only divergence from upstream is import paths in `bplan.py`:

- `from dev.harness.plan import …` → `from .plan import …`

This appears twice — once at module top, once inside `_bexec` (lazy import).
`plan.py` and `bplan_deps.py` vendor without modification.

## Drift policy

`tests/test_runtime_smoke.py` is the canary: if it fails after a sync, the
upstream runtime has changed shape underneath us. Investigate before
re-syncing — do not "fix" the vendored copies in place. Either land the
fix upstream and re-sync, or pin to an older Gallowglass commit here.

The Gallowglass-side equivalent canary (`tests/sanity/test_bplan_deps.py`)
greps `vendor/reaver/src/hs/Plan.hs` to confirm the BPLAN op set in
`bplan_deps.py` still matches Reaver. If that test starts failing in
Gallowglass, do not re-sync into Marduk until it is resolved.
