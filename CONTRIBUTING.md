# Contributing to Junk Cleaner

Thanks for helping. This guide covers setup, the code layout, and the rules every change must follow.

## Development setup

Requires Python 3.10 or newer. Supported platforms: Windows and Linux.

```
python -m venv .venv
.venv\Scripts\activate            (Linux: source .venv/bin/activate)
pip install -r requirements.txt
python -m junkcleaner --no-elevate
```

`--no-elevate` stops a source run on Windows from asking for administrator rights. Run elevated only when
you need to test admin-only paths. `python junkclean.py` is an equivalent launcher.

## Tests

```
python -m unittest tests.test_core
```

The tests do not need a display.

## Project layout

Dependencies point inward only; see the docstring in `junkcleaner/__init__.py`.

| Path | Purpose |
| ---- | ------- |
| `junkcleaner/domain.py` | Model and rules (pure, no I/O) |
| `junkcleaner/platform_os.py` | Windows and Linux specifics |
| `junkcleaner/scanner.py` | Read-only discovery |
| `junkcleaner/cleaner.py` | Deletes or quarantines confirmed items |
| `junkcleaner/quarantine.py` | Restorable store and its history |
| `junkcleaner/history.py` | Activity log |
| `junkcleaner/security.py` | Windows security checks |
| `junkcleaner/ui/` | PySide6 pages and theme |
| `tests/` | Unit tests |

## Rules

- Use only the standard library and PySide6. Do not add a dependency without discussing it in an issue first.
- The scanner is read-only. It must never delete, move or write files.
- Every destructive action needs explicit confirmation in the UI, with No as the default.
- New logic needs a unit test in `tests/`.

## Branches and pull requests

1. Fork the repository, or create a branch if you have write access.
2. Keep each pull request to one change.
3. Run the tests before you push.
4. Fill in the pull request template. Attach screenshots for UI changes.
5. Open the pull request against `main`.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): summary`, for example
`fix(security): handle empty winget output`. Common types: `feat`, `fix`, `docs`, `test`, `refactor`,
`chore`, `ci`.

## Sign-off (DCO)

Every commit needs a `Signed-off-by` line. Add it with `git commit -s`. The sign-off certifies the
Developer Certificate of Origin for that commit.

## License

The project is licensed under the Apache License 2.0 (see `LICENSE`). Contributions are accepted under the
same license (inbound = outbound): by submitting a change, you agree that it is licensed under Apache-2.0.

## Conduct and security

Participation is governed by `CODE_OF_CONDUCT.md`. Report security problems privately as described in
`SECURITY.md`, not in public issues.

## What happens after you open a pull request

- `main` is protected by a ruleset: nobody pushes to it directly. Work on a branch (or a fork) and open a PR.
- Required checks must pass: tests (Windows and Ubuntu), Bandit, pip-audit, gitleaks, and the ClamAV and binary
  check. On the public repo, CodeQL and dependency review also run. Pull requests may not add executables or
  archives (`.exe`, `.dll`, `.msi`, `.zip`…). Binary media is allowed only under `assets/`, `docs/images/`,
  `docs/media/` and `marketing/shots/`.
- A bot review comments on security, data safety, bugs and missing tests. Treat it as a second opinion. A
  maintainer still has to approve.
- On a first-time contributor's PR, workflows wait until a maintainer approves running them.
- Once approved, a maintainer adds the `automerge` label, and GitHub squash-merges when everything is green.
- Every merge to `main` builds the MSI, virus-scans it and keeps it as a build artifact. Bumping
  `junkcleaner/__init__.py` `__version__` publishes a GitHub Release.

Run the checks locally before pushing:
```bash
python -m unittest tests.test_core
pip install bandit pip-audit
bandit -r junkcleaner marketing tests -ll -ii
pip-audit -r requirements.txt
```
