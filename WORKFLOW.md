# Zolo Dev ↔ Prod Workflow (post alpha-1 lock-down)

One page. If a situation isn't covered here, the answer is probably
"work freely on dev; nothing reaches users until a deliberate publish."

## The three environments

| | What runs there | How it changes |
|---|---|---|
| **Dev (your Mac)** | `pip install -e` of the zOS repo; zGuard v1.0.7 binaries (or source — see toggle below); zCloud straight from its repo | Every file save. No builds, no bumps, no publishes. |
| **Golden alpha (frozen)** | `zolo-os==1.6.14` on PyPI, zGuard `1.0.7` wheels + folded binaries, `alpha-1` tag on zOS/zGuard/zCloud | Never. Immutable by construction. |
| **Prod box (zolo.media)** | Pinned published wheel + deployed zCloud checkout | Only by a deliberate upgrade/deploy (below). |

The prod box does NOT track main, PyPI "latest", or your working tree.
Nothing you do on dev can touch it by accident.

## The dev machine, concretely

- zOS: editable — `zolo`/`z` run straight from `~/Projects/zOS/core` (done 2026-07-14).
- zGuard: runs the fetched v1.0.7 binaries by default. To hack on zGuard
  source, uncomment `export ZGUARD_DEV_PATH="$HOME/Projects/zGuard"` in
  `~/.zshrc` (line ~117) — comment it back out to return to binaries.
- Back to a prod mirror at any time:
  `python3.12 -m pip install zolo-os==1.6.14` (kills the editable install).

## Daily development — the default mode

- Edit zOS / zGuard / zCloud freely. Run apps, run `python scripts/zos_baseline.py` locally when you want confidence.
- Commit and push to main as often as you like. Pushing code ≠ releasing code.
- Exception — `zguard_bin/` in this repo: `z patch` on every user machine
  fetches from that folder on main, so treat it as production. Only the
  refold flow (below) may change it.

## Releasing a zOS change (only when prod/users need it)

1. Bump the version in `core/version.py` + `pyproject.toml` (1.6.15, 1.6.16, …).
2. Push → wait for the **zOS baseline** gate to go green (all three legs).
3. Publish: `rm -rf dist && /tmp/pubenv/bin/python -m build && /tmp/pubenv/bin/twine upload -r zolo-os dist/*`
   (token lives in `~/.pypirc`; make a fresh venv with `build`+`twine` if `/tmp/pubenv` is gone).
4. Upgrade the box **explicitly**:
   `ssh box '/home/ubuntu/.zolo/venv/bin/pip install zolo-os==1.6.X && sudo systemctl restart zcloud'`
5. Smoke: `https://zolo.media` 200, `/app/zhello` → 302 → subdomain 200.

Rollback is always: `pip install zolo-os==1.6.14` (or last-good) + restart.

## Releasing a zGuard change

1. Bump `zguard/__init__.py` version, push, tag `vX.Y.Z` → CI builds wheels (~2 h).
2. `gh run download <run-id> -D /tmp/zguard_wheels` in the zGuard repo.
3. In zOS: `python scripts/refresh_zguard_bin.py /tmp/zguard_wheels`
   → `python scripts/verify_zguard_image.py` → commit `zguard_bin/` → push.
4. User machines pick it up via `z patch` (24 h trust window before they
   re-check; delete the cache under `~/Library/Application Support/zOS/zguard_bin`
   to force an immediate re-fetch).

## Deploying zCloud (app content — no versions involved)

zCloud is an app, not a package. Deploy = copy + restart:

    scp -i ~/.ssh/zcloud-prod.pem -r <changed files> ubuntu@51.84.210.107:/home/ubuntu/zCloud/
    ssh -i ~/.ssh/zcloud-prod.pem ubuntu@51.84.210.107 'sudo systemctl restart zcloud'

Box-only config (`zEnv.production.zolo`, Caddyfile, systemd unit) is
snapshotted in `zCloud/deploy/box/` — update the snapshot when you change it.

## Milestones

When a new state is worth freezing, tag all three repos `alpha-2`, `alpha-3`, …
at the commits that produced the published artifacts. Tags + PyPI versions
ARE the lock; nothing else is needed.

## Hard rules

- Never hot-patch site-packages on the prod box again (bootstrap-only; over).
- Never re-upload or mutate a published PyPI version — supersede with a bump.
- Anything risky ships behind an env flag, off by default (`ZHOST_INGRESS_DOMAIN` pattern).
- The baseline gate is the release gate. Red gate = no publish, no exceptions.
