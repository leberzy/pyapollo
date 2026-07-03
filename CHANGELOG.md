# Changelog

All notable changes to this project are documented in this file.

## [1.0.0] - 2026-07-03

### Added

- True long-polling via `/notifications/v2` (aligned with Java Apollo client).
- Config fetch with `releaseKey`, `ip`, and `messages` for grey release and 304 support.
- Layered architecture: `transport`, `repository`, `cache`, `listeners`, `getters`.
- Change listeners: `add_change_listener()` with namespace/key filtering.
- Lifecycle API: `start()`, `stop()`, context managers, `autostart` parameter.
- Typed getters: `get_int()`, `get_bool()`, `get_float()`, `get_list()`.
- `is_ready()` to check whether configuration has been loaded.
- File cache layout: `{cache_root}/{app_id}/{cluster}/{namespace}.json`.
- Default cache directory under user cache dir (`~/.cache/apollo` or `%LOCALAPPDATA%/apollo`).
- Quality gate: ruff, mypy, pytest, pre-commit, CI workflow.
- Integration tests against live Apollo server (opt-in via `pytest -m integration`).

### Changed

- Package layout migrated to `src/pyapollo/`.
- Python requirement raised to **>=3.12**.
- Logging switched from `loguru` to standard library `logging`.
- Memory cache is thread-safe; reads and writes use per-instance locks.
- `get_value()` / `get_json_value()` signatures unchanged; implementation reads locked cache.

### Removed

- Implicit singleton on `ApolloClient` / `AsyncApolloClient` (each construction creates a new instance).
- `loguru` dependency.
- Legacy cache files `{app_id}_configuration_{namespace}.txt` under package directory.

### Migration

See [docs/migration-1.0.md](docs/migration-1.0.md).

**Quick replacements:**

| 0.x | 1.0 |
|-----|-----|
| `client.stop_polling_thread()` | `client.stop()` |
| `await client.stop_polling()` | `await client.stop()` |
| `from pyapollo.client import ApolloClient` | `from pyapollo import ApolloClient` |
| Same-args client reuse (singleton) | Hold one instance yourself if needed |

Old cache files are harmless; they are ignored and rebuilt on next fetch.
