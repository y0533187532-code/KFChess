# Final Work Plan — Kung-Fu Chess Client–Server Transition

> **Superseding update (2026-07-21):** See `ARCHITECTURE_UPDATE_2026-07-21.md`. It resolves the gameplay-command gate, requires in-window OpenCV authentication for production, makes CLI authentication an optional disabled-by-default development fallback, and requires Windows/Linux/macOS portability. Older conflicting statements in this plan are obsolete.

> A binding implementation plan based on the manager’s specification, the existing project structure, and all 40 approved clarification answers.

## Delivery Status and Decision Gate

- This plan is the source of truth for the new implementation task.
- The baseline is complete: 518 tests pass with 90% total coverage under Python 3.11.1.
- Do not change the existing `GameEngine` API or freeze the final `move_request`/`jump_request` payload before receiving the lecturer’s answer included at the end of this document.
- Until then, continue every independent task: protocol envelope, configuration, logging, SQLite, both token types, `GameSession`, queue/worker, and infrastructure tests.
- If a contradiction, ambiguity, or undocumented decision appears, do not choose a solution independently. Explain the options and impact and request a decision from the project owner.

## Page 1 of 5 — Objective, Scope, and Architecture

### 1. Project Objective

The objective is to transition the existing Kung-Fu Chess game from a local, single-process application to a decoupled Client–Server system. The game remains real-time: pieces belonging to both players may move simultaneously, pieces have movement, jump, and rest states, and the primary game-ending condition is king capture. The online version must not be converted into conventional alternating-turn chess.

The server will be the sole source of truth. It will own the game state, advance authoritative time, validate actions, resolve captures and results, assign colors, and manage users, matchmaking, rooms, spectators, sessions, and Elo. The client will render the game through OpenCV, collect user input, and send requests. It must never update authoritative game state or ratings on its own.

Initial development will use a local server on Windows. The server address, port, and all system limits will be loaded from configuration so that the server can later move to Linux, a local network, or the public internet. Plain `ws` is acceptable in the local environment. Public exposure will require `wss/TLS` and additional security hardening.

### 2. Binding Product Decisions

- The primary transport format will be structured JSON containing fields such as `type`, `request_id`, `game_id`, and a stable `piece_id`. A compact command such as `WQe2e5` may remain for demonstration or backward compatibility only.
- The server processes commands according to authoritative arrival order. A new command for the same busy piece is rejected with `piece_busy`; other pieces may act concurrently when the requested actions are legal.
- Black sees a client-side 180-degree board rotation. The server always uses canonical coordinates. Spectators see White’s perspective by default.
- All `Login`, `Registration`, `Play`, `Room`, room-code entry, names, ratings, errors, and disconnect countdowns will appear in the OpenCV window. No external Windows dialog will be opened.
- The interface will support English and Hebrew, including RTL presentation for Hebrew. The server returns stable result and error codes; the client maps them to localized text resources.
- Audio is outside the MVP. The existing animation-state system remains in use, with no new requirement for separate start/end animations.
- `Play` games created through matchmaking are rated. `Room` games are friendly and do not affect Elo.
- A room contains two player seats and up to 10 spectators. Large-scale concurrency is achieved by supporting many rooms and games at the same time.

### 3. Mandatory Engineering Principles

1. **DRY:** Every game rule, Elo rule, and authorization rule has exactly one implementation owner.
2. **SRP:** Every component has one responsibility; for example, `EloService` calculates ratings only, while `RoomManager` manages room membership only.
3. **No hard-coded constants:** Addresses, ports, 20/60-second timers, Elo range, K-factor, room limits, and user-facing strings come from configuration.
4. **Strict encapsulation:** Internal collections, SQLite connections, and engine objects are never exposed directly. Components communicate through interfaces, DTOs, and repositories.
5. **Idempotency:** Requests with the same `request_id` are not executed twice. A game result and its Elo update are also applied only once.
6. **Server authority:** All timers, snapshots, outcomes, and permissions are decided by the server.
7. **Privacy by design:** Passwords, tokens, phone numbers, and email addresses are never included in game events or logs.
8. **Engine isolation:** The game engine and Domain modules know nothing about users, rooms, SQLite, WebSocket, JSON, or OpenCV. Only the Application layer translates engine events into system services.
9. **Single Writer per game:** Every `GameSession` has an `asyncio.Queue` and one worker. Every engine mutation goes through the queue, so no broad lock surrounds `GameEngine`. A short lock is allowed only for seat allocation or registries outside the engine.
10. **Authoritative time:** A hybrid authoritative tick advances an active game even when no client command arrives; only the server decides when timed actions finish.
11. **Recoverable synchronization:** Every authoritative change receives a `sequence`; a gap causes the client to request a full snapshot.
12. **Idempotent persistence:** Database constraints and transactions prevent duplicate results and Elo updates.

### 4. Target Structure

```text
OpenCV Client
  UI/View -> Client Controller -> WebSocket Client -> JSON Protocol
                                                    |
                                                    v
Authoritative Server
  WebSocket Gateway -> Authentication/Session -> Message Router
                                         |-> Matchmaking Service
                                         |-> Room Manager
                                         |-> Game Session -> Existing Game Engine
                                         |-> Elo Service -> Repositories -> SQLite
                                         |-> Reconnect Manager
```

The main components will be `ConfigProvider`, `SchemaValidator`, `WebSocketGateway`, `MessageRouter`, `AuthService`, `SessionManager`, `MatchmakingService`, `RoomManager`, `GameSession`, `ReconnectManager`, `EloService`, `UserRepository`, and `MatchRepository`. The game engine must not depend on OpenCV, WebSocket, JSON, or SQLite.

Events will be separated into three layers: Domain events for one game engine, Application events carrying context such as `game_id`, and JSON network messages. A `GameOverEvent` will be added to the engine and published exactly once when a game transitions from active to finished.

<div style="page-break-after: always;"></div>

## Page 2 of 5 — Foundation, Message Bus, and Client–Server Separation

### Phase 0 — Freeze Contracts and Establish a Safety Net

**Objective:** Create a stable foundation on which multiple Agents can work concurrently without producing conflicting implementations.

**Shared engineering tasks**

1. Map the current input flow: OpenCV → `Game` → `GameEngine` → `GameSnapshot` → rendering.
2. Preserve the existing Kung-Fu Chess engine and the `idle`, `move`, `jump`, `short_rest`, and `long_rest` states as the source of truth for game rules.
3. Create external configuration with a validated schema for address/port, tick rate, matchmaking timeout, grace period, Elo settings, room limits, logging, SQLite path, and backup path.
4. Define the protocol version, common message envelope, and stable event/error codes.
5. Add characterization tests for simultaneous movement, busy pieces, capture, king capture, both kings captured during the same tick, and snapshot generation.
6. Add a test proving that `GameOverEvent` is published exactly once when the ending condition is met and is not published again during later ticks.
7. Divide Agent work only after the shared interfaces are frozen. An Agent must not change a shared contract without a documented update and an integration review.

**Deliverable:** Shared contracts, configuration, baseline engine tests, and an approved list of event and error codes.

### Phase 1 — Communication Channel Abstraction

**Objective:** Separate UI commands from game logic before introducing the network.

**Backend / Domain**

- Extend the existing Event Bus with strongly typed contracts without treating it as a replacement for WebSocket transport.
- Distinguish Commands that request changes, Events that record what occurred, and Snapshots that describe read-only state.
- Add `GameOverEvent` as a Domain event containing the winner and authoritative ending time. `GameEngine` publishes it at the single point where the game changes to game over.
- `GameService` translates `GameOverEvent` into an Application-level `GameEndedEvent` containing `game_id`, ending reason, and result. The network layer translates that into a `game_over` JSON message for all players and spectators.
- Define single-owner handlers for game actions and ensure that every state change flows through `GameEngine`.
- Prevent the UI from directly accessing engine internals.

**Frontend**

- Introduce a `ClientController` between mouse/keyboard input and the game.
- Initially connect it to a local adapter that simulates a server, proving that the UI no longer depends directly on the engine implementation.
- Display an action as accepted or rejected based on a result code, rather than relying on an unconfirmed optimistic local state change.

**Recommended patterns:** Command, Observer/Event Bus, Adapter, immutable DTOs, and Ports and Adapters.

**Risks and tests:** Prevent duplicate event publication, preserve event ordering, ensure snapshots cannot be mutated after publication, and verify that extracting the UI does not alter game rules.

### Phase 2 — WebSocket and Separate Processes

**Objective:** Run the server and clients in independent processes and synchronize at least two clients in real time.

**Backend**

1. Create an asynchronous local WebSocket server with no graphical interface.
2. Implement `ConnectionRegistry` and `MessageRouter` without binding sockets directly to `GameEngine`.
3. Validate every JSON message against a schema: protocol version, message type, required fields, values, and size limits.
4. Create `GameSession` to own one game engine, an authoritative clock, two player seats, and a spectator list.
5. Give every game an `asyncio.Queue` and one worker. Move, jump, tick, disconnect, reconnect, and timeout operations enter the same queue; only the worker mutates `GameEngine`.
6. Process `move_request` messages in arrival order; reject an unauthorized piece, wrong game, illegal destination, or busy piece.
7. Run a configurable authoritative periodic tick for games with active movement, jumps, or cooldowns so that time advances even when no client command arrives.
8. Broadcast `command_result`, state updates, and snapshots with sequence numbers. A client that detects a gap requests resynchronization.
9. Randomly assign White and Black in `Play`. In a room, the creator is White and the first joining opponent is Black.

A `sequence` is a monotonically increasing state-version number. If a client receives version 41 followed by 43, it knows an update is missing and does not attempt to infer it. It requests a snapshot—a complete current representation of the board, pieces, active motions, cooldowns, and game state—and replaces its local presentation state with that snapshot.

The existing code already assigns every piece a stable integer `piece_id` within one game, preserves it during movement and promotion, and exposes it in `GameSnapshot`. A network command will contain `game_id`, `piece_id`, `expected_from`, and `target`. `GameService` locates the piece through the snapshot, validates its color, state, and expected position, and translates the request into the coordinates required by the existing `GameEngine`. The `Piece` model does not need to change.

**Frontend**

- Replace the local adapter with a WebSocket client.
- Retain presentation state only and replace it with server-approved snapshots.
- Rotate Black’s view without changing coordinates sent to the server.
- Display connecting, connected, reconnecting, and error states.

**Database:** SQLite is not yet required. Temporary test identities may be used only until this phase passes its acceptance gate.

**Exit criteria:** Two separate clients see the same game; forged commands are rejected; duplicate requests are not executed twice; and resynchronization repairs a client that missed an update.

<div style="page-break-after: always;"></div>

## Page 3 of 5 — Users, SQLite, Elo, and Matchmaking

### Phase 3 — Registration, Login, and Persistence

**Objective:** Identify users appropriately for the local MVP environment and persist ratings and match results consistently.

**Backend**

- Implement explicit self-registration followed by Login.
- A `username` must be unique, contain 3–20 English letters, digits, or underscores, and be case-sensitive: `Dana` and `dana` are different accounts. A first/display name, if stored, is not an account identifier.
- A password must contain at least six characters and be stored using a salted password-hashing algorithm, never as plain text.
- After Login, the server issues an Authentication token. The clear value is returned to the client; only its hash is stored in SQLite with configurable expiry and revocation state.
- On joining a game, the server issues a separate Game token bound to `game_id`, the user, and the seat. Only its hash is stored in SQLite.
- The Authentication token proves general identity; the Game token proves ownership of one seat in one game. Reconnect requires both.
- A Game token is revoked when the game ends or is cancelled, on resign, or after a 20-second disconnect without reconnect.
- A restart without active-game recovery marks active games interrupted and revokes their Game tokens. Authentication tokens may remain valid according to their expiry.
- Phone-number matching is a temporary password-recovery mechanism for local development only. A later phase will send a time-limited recovery code by email and enforce attempt limits.

**Frontend**

- Build Registration and Login screens, validation messages, and navigation to the home screen inside OpenCV.
- Do not display or retain a plain-text password after submission.
- Store a token only in the safest practical client location and remove it on logout or rejection by the server.

**Database**

- Use repositories/wrappers and migrations. UI code and WebSocket handlers must never execute SQL directly.
- The user table will include an internal identifier, username, password hash, email, phone, starting Elo of 1200, status, and creation/update timestamps.
- `auth_sessions` stores Authentication-token hashes, owners, expiry, and revocation state.
- `game_session_tokens` stores Game-token hashes, `game_id`, owner, color/role, status, `grace_expires_at`, and revocation data.
- `rooms` stores room metadata: code, creator, status, creation/start/close timestamps, and ending reason.
- `room_members` stores historical membership: user, role, color, join time, and leave time. It never stores a live socket.
- The rated-match table will include a unique game identifier, players, result, Elo before/after, and termination reason.
- Email and phone are private: they are not displayed, included in game messages, or logged.
- When an account is deleted, identifying and login data is removed or anonymized. Match results remain in anonymous form to preserve rating-history consistency.

**Backup and authorization**

- Back up SQLite before every significant version update and automatically once per day.
- Retain match results indefinitely unless a future policy changes this requirement.
- Only a system administrator may restore a backup or delete system data. Every such action must be recorded in an audit log.

### Phase 4 — Elo and `Play` Matchmaking

**Objective:** Pair two compatible users in a rated game and persist exactly one correct Elo update.

**Elo rules**

- Starting rating: `1200`; scale: `400`; fixed K-factor: `32`; rating floor: `100`.
- Result values: win `1`, loss `0`, technical draw `0.5`.
- Use Half-Up rounding: a fractional part below `.5` rounds down, while `.5` or above rounds up.
- There is no draw offer. Only the server may declare a draw, for example when both kings are captured during the same tick or a technical ending has no clear winner.
- Store the match result and both rating changes in one transaction, protected by a unique game-result identifier.
- The rating-change table will include a unique constraint preventing another result from being applied to the same game/user combination. A repeated request returns the stored result instead of recalculating Elo.

**Matchmaking backend**

1. `Play` creates one ticket for an authenticated user who is not already queued or playing.
2. The matching range is inclusive ±100 Elo and remains fixed for 60 seconds.
3. If several candidates match, select the oldest compatible ticket.
4. Randomly assign White and Black on the server.
5. `Cancel` or disconnection while waiting removes the ticket with no loss and no Elo change.
6. A 60-second timeout returns a localized error code and removes the ticket.

**Rating rules for early termination**

- Only `Play` is rated. `Room` is unranked.
- A single-player disconnect becomes a rated loss only when the game has started, the disconnected player has moved at least one of their pieces, the player does not reconnect within 20 seconds, and the server declares a forfeit.
- A manual `resign`, if added, affects Elo only after the resigning player has completed at least one legal action.
- If both players disconnect, the game continues only if both return in time. If only one or neither returns, the game is cancelled with no Elo change.
- A server failure or restart cancels the game without Elo changes in the MVP.

**Exit criteria:** Formula and boundary tests pass; duplicate tickets are blocked; 1200 matches inclusively against 1100–1300; timeout and cancellation are correct; and Elo is applied exactly once.

<div style="page-break-after: always;"></div>

## Page 4 of 5 — Rooms, Spectators, Reconnect, and Complete UI

### Phase 5 — Private Rooms and Spectators

**Objective:** Separate rated `Play` from friendly `Room` games, with explicit player and spectator permissions.

**Backend**

- `Create Room` generates a random six-character code from English letters and digits, excluding `O`, `0`, `I`, and `1`. Codes are case-insensitive and normalized to uppercase by the server.
- The room creator automatically occupies White. The first joining user occupies Black. Additional users become spectators, up to a maximum of 10.
- The MVP does not support a non-playing host, room password, or invitation link. An email invitation link belongs to a later phase.
- A spectator may join after the game starts and first receives a complete current snapshot, followed by immediate updates.
- A spectator may not send game commands, access private information, or be promoted to a seat during an active game.
- New spectators cannot join after game end. Existing spectators see the result, and the room closes after a configurable delay.
- If the creator leaves before game start, close the room with `room_closed`. If another player leaves before the start, release that seat for the next joining user.

**Frontend**

- Selecting `Room` opens an in-OpenCV form containing a six-character code field, `Join`, `Cancel`, and error presentation.
- The room-creation view displays the code and waiting status for the Black player.
- Spectator mode is read-only, uses White’s perspective, and displays player names, ratings, and the final result.
- Map `room_not_found`, `room_full`, `room_closed`, `already_in_game`, and `invalid_room_code` to Hebrew/English resources.

**Database:** Use a hybrid model. Room metadata and membership history are persisted in `rooms` and `room_members`. Live WebSocket connections, `GameSession`, `GameEngine`, queues, timers, and live game state remain in memory. Persisting a room row does not provide game recovery. After restart, a `WAITING` or `ACTIVE` room is marked `INTERRUPTED`/`CLOSED`, its Game tokens are revoked, and the interrupted game does not affect Elo.

### Phase 6 — Disconnect and Reconnect

**Objective:** Restore a player safely without giving the connected player an unfair advantage or allowing seat theft.

**Single-player disconnect**

1. The server moves the game into `grace_pause` for 20 seconds.
2. No new action is accepted from either player. Actions approved before the disconnect may finish authoritatively.
3. The seat remains reserved for the same user; a spectator cannot take it.
4. The connected client displays a countdown derived from server time.
5. A reconnect request sends the Authentication token, Game token, `game_id`, and `request_id`.
6. The server derives the user identity from the Authentication token, verifies that the Game token belongs to the same user and game, checks seat ownership and the grace deadline, and then sends a current snapshot.
7. If the user does not return, the server applies the forfeit and rating rules from Phase 4.

Intentionally closing the application is treated as a disconnect and receives the same 20-second grace period. Only an explicit `Resign` action, if implemented, ends the game immediately.

**Two-player disconnect**

- Reserve both seats and pause the game for 20 seconds.
- Continue only if both users reconnect and authenticate in time.
- If only one or neither returns, cancel the game with no winner, loser, or Elo update.
- A sole returning player receives an explanation that the game was cancelled due to a double disconnect.

**Server failure**

- Active games are not persisted in SQLite in the MVP.
- A restart cancels the game without an Elo update and revokes Game tokens for active games. A valid Authentication token remains usable; only an expired or revoked token requires Login again.
- Record the event as `server_interrupted_game`.

### Final UI Integration

Implement an OpenCV screen state machine containing `LOGIN`, `REGISTER`, `HOME`, `MATCHMAKING`, `ROOM_LOBBY`, `PLAYING`, `SPECTATING`, `GRACE_PAUSED`, and `RESULT`. Server events drive screen transitions so that navigation conditions are not scattered throughout the UI. Store all text in localization resources, including RTL strings and authentication, room, timeout, and reconnect messages.

**Exit criteria:** Role assignment is correct; spectator commands are rejected; a late spectator receives a snapshot; the same user restores the same seat; double disconnect cancels without Elo; and rooms close correctly.

<div style="page-break-after: always;"></div>

## Page 5 of 5 — Reliability, Testing, Risks, and Delivery

### Phase 7 — Logging, Capacity, and Hardening

**Logging**

- Client and server write JSON Lines containing `timestamp`, `level`, `event`, relevant identifiers, and `request_id`.
- Retain logs for 14 days or 100MB per side, whichever comes first, using rotation.
- Full payload logging is allowed only in local DEBUG mode and only after masking.
- Never log passwords, password hashes, tokens, email addresses, or phone numbers.
- Critical events include connection, authentication failure, queue entry, match creation, room creation/joining, accepted/rejected commands, reconnect, forfeit, cancellation, Elo update, backup, and failure.

**Initial capacity targets for one server process**

- Up to 50 active games.
- Up to 200 queued users.
- Up to 100 open rooms.
- Up to 10 spectators per room.
- Up to 500 total WebSocket connections.

These are configurable design and load-test targets, not production guarantees before measurement. The 500-connection value is the overall ceiling; the other maximum values do not all have to occur simultaneously. Supporting thousands of users will later require multiple processes/servers, shared state, and a server-grade database instead of SQLite.

### Test Strategy

| Layer | Mandatory tests |
|---|---|
| Domain | Concurrent movement, busy pieces, capture, king capture, technical draw, snapshot, and a single `GameOverEvent` |
| Protocol | Schema, version, unknown message, missing field, oversized payload, duplicate `request_id` |
| Authentication | Registration, case-sensitive username, hashing, duplicate Login, invalid/expired token |
| SQLite | Migrations, constraints, Elo transaction, anonymization, authorized backup/restore |
| Matchmaking | Inclusive ±100, FIFO, timeout, cancellation, disconnect, concurrent requests |
| Rooms | Normalized code, seats, 10 spectators, permissions, creator exit, late join |
| Reconnect | One player, both players, boundary timing, forged token, server restart |
| UI | Black rotation, RTL, screens, errors, countdown, spectator presentation |
| Load | 500 connections, 50 games, large queue, spectator broadcast, memory consumption |

Every phase ends with unit tests, integration tests, and a demonstrable scenario. No Agent-produced change is merged until it passes relevant tests and is reviewed against the shared contracts.

### Primary Risks and Mitigations

1. **Real-time command races:** Use an authoritative loop and defined processing order per `GameSession`.
2. **Duplicate game-ending event:** Publish `GameOverEvent` only on the first transition to game over and enforce idempotency in every consumer.
3. **Client desynchronization:** Use sequence numbers, full snapshots, and resynchronization.
4. **Duplicate or partial Elo updates:** Use a unique result identifier and one transaction.
5. **Reconnect impersonation:** Use random expiring tokens, verify seat ownership, and never log tokens.
6. **Blocked event loop:** Do not run long SQLite or backup operations in the network loop.
7. **SQLite under load:** Use short writes, indexes, transactions, and measurement; migrate if required.
8. **Weak phone recovery:** Restrict it to local development and replace it with an emailed temporary code before internet deployment.
9. **Concurrent Agent work:** Freeze interfaces per milestone, assign clear file ownership, use separate branches, and perform central integration testing.
10. **Account deletion versus history:** Anonymize results rather than breaking historical rating records.

### Delivery Order and Dependencies

```text
Contracts and Engine Tests
  -> Message Bus and UI Separation
  -> WebSocket and Separate Processes
  -> Authentication + SQLite
  -> Elo + Matchmaking
  -> Rooms + Spectators
  -> Reconnect + Reliability
  -> Load, Security, and Release
```

Only work that does not depend on a changing decision should run concurrently. After the protocol contract is frozen, the WebSocket server, OpenCV client, and SQLite repositories can be developed in parallel. After user and game services are stable, Matchmaking, Rooms, and load tests can proceed concurrently. The project owner remains the final approver for every milestone.

### Final Acceptance Criteria

The project is complete when two users can register and log in, select `Play`, match according to the approved rules, receive colors, play in real time from separate processes, and receive one correct Elo update. A user must also be able to create a `Room`, add one opponent and up to 10 spectators, while spectators receive immediate state without the ability to play. Disconnects must follow the 20-second single/double-disconnect rules, all information must appear inside OpenCV in English or Hebrew, a server restart must not produce an incorrect Elo update, private data must remain protected, logging and backups must operate correctly, and all acceptance and load tests must pass.

### Outside the MVP

Replay and complete move history, persistence of live game state and room/game recovery after restart, email invitation links, competitive spectator delay, dynamic K-factor, Linux/macOS clients, and public deployment with TLS are later-stage capabilities and must not block the local MVP.

### Lecturer Question — Gate Before Piece-Command Implementation

> In the existing implementation, every piece already has a stable integer `piece_id` exposed in `GameSnapshot`, while the public `GameEngine` API accepts coordinates through `request_move(from_row, from_col, to_row, to_col)`. Is it acceptable to keep the game engine and offline application unchanged and add a server-side Adapter that receives `game_id`, `piece_id`, `expected_from`, and `target`, locates the piece in the snapshot, validates ownership/state/location, and translates the request into the existing coordinate-based call? Or must the `GameEngine` API itself be changed to accept `piece_id` directly? The architectural preference is the Adapter so that backward compatibility, separation of responsibilities, and engine independence from networking are preserved. Does this satisfy the assignment requirements?

Until the answer is received, do not change `GameEngine`, implement `NetworkGameAdapter`, or freeze the `move_request`/`jump_request` contract. When the answer arrives, present it to the project owner, update this plan, and only then continue those parts.
