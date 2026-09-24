# Contributing

Thanks for helping improve hermes-odd. Issues and pull requests are welcome.

## Scope

hermes-odd brings the Organic Driven Development (ODD) and receipt-driven
development (RDD) workflows to Hermes Agent. It does **not** ship SDD: no SDD
agents, chains, skills, preflight, prompts, or `gentle-sdd-*` commands.
Pull requests that add SDD content are declined. Pi-only aesthetics (themes,
banners, TUI widgets) and Pi runtime plumbing are out of scope too.

## Development setup

The plugin uses the Python standard library only, so the Hermes venv
interpreter is enough to run the tests:

```bash
git clone https://github.com/goldenSniperOS/hermes-odd.git
cd hermes-odd
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests -v
```

Linting uses [ruff](https://docs.astral.sh/ruff/) (line length 100, Python
3.11 target). Do not install it into the Hermes venv; use any standalone
runner:

```bash
ruff check . && ruff format --check .      # or: uvx ruff ... / pipx run ruff ...
```

CI runs the same checks plus `pytest -q` and `python -m build` on Python 3.11
and 3.12. To reproduce CI in a separate virtualenv:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]" build
ruff check . && ruff format --check . && pytest -q && python -m build
```

End-to-end smoke against your local Hermes install (throwaway `HERMES_HOME`,
never touches `~/.hermes`, no network, no model calls):

```bash
~/.hermes/hermes-agent/venv/bin/python scripts/smoke_e2e.py
```

## Workflow

1. Open or pick an issue. Upstream changes use the **Upstream port request**
   template; problems seen on a real agent use **Field report**.
2. Branch from `main`: `git switch -c feat/my-change main`.
3. Commit in **work units**: each commit is one reviewable, self-contained
   change with its tests and docs, and leaves the suite green.
4. Write commit messages with
   [Conventional Commits](https://www.conventionalcommits.org/)
   (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`); mark
   breaking changes with `!`.
5. Add a line under `## [Unreleased]` in `CHANGELOG.md`.
6. Open a pull request against `main` and fill in the template. CI must pass.

## Attribution rule

hermes-odd adapts MIT-licensed text from
[gentle-ai](https://github.com/Gentleman-Programming/gentle-ai) and
[gentle-shell](https://github.com/Gentleman-Programming/gentle-shell). Any
text you derive from an upstream project must:

1. carry a marker in the derived file naming the upstream repository, the
   pinned 40-character commit and the upstream source path, in the form
   `<!-- derived-from: <upstream>@<commit> <path> -->` (inside a docstring
   or comment for Python files);
2. be listed under that upstream in `THIRD_PARTY_NOTICES.md`;
3. have its upstream source path indexed, with the SHA-256 at the pinned
   commit, under its component in `upstream/upstream.lock.json`.

Upstream versions are supported by pinned commit. Syncing to a newer
upstream follows the procedure in
[`upstream/SUPPORTED.md`](upstream/SUPPORTED.md): triage every upstream
change into its triage log (ported, not portable and why, or pending), then
update the derived files, markers, notices, canonical render and lock
together. `tests/test_upstream_lock.py` cross-checks them.

`tests/test_naming_and_attribution.py` fails when a marked file is missing
from the notices, and `tests/test_upstream_lock.py` when a marker is not
indexed in the lock. Never use upstream marks (Gentle AI, gentle-shell,
gentle-pi, Engram) as a product name; use them only to describe what
hermes-odd is based on or compatible with.

## Prompt budget

The always-on prompt section is capped by a test at 3,800 characters (Hermes
allows 4,000 per section and 8,000 across all plugins). Put detail in lazy
skills under `skills/`, not in the section.

## Release process

Releases are cut from `main`:

1. Bump the version in **three places**: `plugin.yaml`, `pyproject.toml` and
   `hermes_odd/__init__.py`. `tests/test_packaging.py` and the release job
   fail if they disagree.
2. Move the `[Unreleased]` notes in `CHANGELOG.md` to
   `## [X.Y.Z] - YYYY-MM-DD` and commit (`chore(release): vX.Y.Z`).
3. Wait for CI on `main`, then tag that commit and push the tag:
   ```bash
   git tag vX.Y.Z && git push origin vX.Y.Z
   ```
   The `Release` workflow checks the versions, the changelog section and that
   the tag is on `main`, runs the checks, builds the wheel, sdist, a plugin
   zip and `SHA256SUMS.txt`, and publishes a GitHub Release whose notes
   include install and update instructions and the exact commit SHA.
