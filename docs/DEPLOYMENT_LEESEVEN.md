# Leeseven deployment branch

This fork keeps deployment-specific integration separate from upstream `main`.

## Branches and remotes

- `upstream/main`: read-only mirror of `myfanhua/turb-gpt-free-register`.
- `origin/main`: GitHub fork default branch; kept aligned with upstream.
- `origin/deploy/leeseven`: production branch deployed at `/opt/turb-gpt-free-register`.
- The local `upstream` push URL is intentionally disabled.

## Local integrations

- CloakBrowser Selenium compatibility fixes.
- Email Butler mail source and pool view.
- Host-level WARP egress configuration is managed outside Git by systemd and is
  documented in the service catalog.

## Updating from upstream

Review upstream changes before merging them into production:

```bash
git fetch upstream origin
git switch main
git merge --ff-only upstream/main
git push origin main
git switch deploy/leeseven
git merge main
python -m unittest discover -v tests
```

Resolve integration conflicts only on `deploy/leeseven`, then perform the live
smoke checks before pushing the deployment branch.
