# Architecture Update — 2026-07-21

This document supersedes older conflicting statements in the master plans.

## Authentication presentation

- Production registration and login are rendered and operated inside the existing OpenCV application window.
- `AuthService` remains server/application logic and has no dependency on OpenCV, terminal input, or client presentation.
- Client authentication is separated behind `AuthScreen` and `AuthInputProvider` ports.
- Terminal authentication is optional development/debug behavior only. It must be controlled by client configuration and is disabled by default.
- Credentials and tokens must never be logged, and sensitive form fields must be cleared after submission.

## Supported operating systems

- The intended supported platforms are Windows, Linux, and macOS.
- Server and application code must remain OS-neutral.
- Use `pathlib` and external configuration for paths; do not hard-code separators, drive letters, shell commands, or native Windows dialogs.
- The OpenCV client must use portable window/input behavior.
- Any unavoidable OS-specific operation belongs behind a narrow adapter with tests where practical.

## Network gameplay commands

Both `move_request` and `jump_request` use the versioned protocol envelope and this structured payload:

```json
{
  "auth_token": "...",
  "game_token": "...",
  "game_id": "...",
  "piece_id": 123,
  "expected_from": {"row": 1, "col": 4},
  "target": {"row": 3, "col": 4}
}
```

- `request_id` remains in the surrounding envelope and is mandatory.
- Authentication and the game-scoped token are validated before authorization.
- Internal ownership uses neutral `FIRST_PLAYER` / `SECOND_PLAYER` seats. The Chess compatibility adapter maps them to `w` / `b` only at required boundaries.
- The latest `GameSnapshot` is searched by `piece_id`; ownership and `expected_from` are checked before calling the engine's existing coordinate API.
- Missing pieces return `invalid_piece`, opponent pieces return `forbidden_piece`, and outdated source coordinates return `stale_client_state`.
- Every gameplay command is submitted to the matching `GameSession`; only its single worker may inspect-and-mutate the engine.
- Accepted state changes increment and return the per-game sequence. Duplicate `request_id` values return the cached result without executing the engine twice.
- `jump_request.target` is required and must equal `expected_from`. A different target returns `invalid_field`. Jumping remains in-place and `GameEngine.request_jump` is unchanged.

Rooms, spectator UI, target-based jumping, and changes to current Chess rules or `GameEngine` APIs are outside this update.
