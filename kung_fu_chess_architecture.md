# Kung-Fu Chess — Architecture & Implementation Specification

> **Role:** Senior Software Architect & Clean Code Expert
> **Scope note:** This document is scoped strictly to the original 15 architecture rules and the 10-phase roadmap. Extended gameplay systems (Jump/Dodge, Drone piece, animations, scoring, matchmaking, networking) are defined separately in `kung_fu_chess_requirements.md` and are intentionally **out of scope** here.
> **Resolved conflict:** Castling has been **removed** from this specification. Since this game has no check/checkmate/king-safety concept, castling's core rationale does not apply — the game only supports standard movement and **pawn promotion**.

---

## 📌 Part 1 — Core Architecture & Code Design Rules

### Rule 1 — Strict Adherence to SRP (Single Responsibility Principle)
> Enforce SRP at all times. Never duplicate logic and never combine two distinct roles within a single function or class.

- Keep code highly focused: **every component must have exactly one reason to change.**

### Rule 2 — Textual I/O Simulation for Testing
- Implement dedicated, clean classes to simulate user input and terminal output (e.g., `PrintBoard`, `TextTestRunner`) to allow full testability of parallel events **without a GUI**.

### Rule 3 — Separation of Concerns (SoC)
- The **Model** must be completely decoupled from the display/screen (**View**), and vice versa.
- There must be total isolation between internal game state logic and the rendering engine.

### Rule 4 — Input Mapping & Coordinate Adaptation (`BoardMapper`)
- Implement a `BoardMapper` to map raw screen-clicks (pixel-based coordinates) to specific grid cells or pieces on the board.
- This must follow the **Coordinate Adapter pattern**.

### Rule 5 — Decouple Validation from Action in `GameEngine`
- Strictly separate the process of **verifying** a move's legality from the **processing** of the action itself (i.e., who clicked vs. where they want to go).

### Rule 6 — Separate Piece Mechanics from Board State (Strategy Pattern)
- Evaluate a piece's theoretical movement capability independently from the current board obstruction state.
- Implement each piece's movement rules using the **Strategy Pattern** (e.g., `RookRule`, `BishopRule`).
- **Promotion** must be handled via a dedicated strategy rule or sub-service.

### Rule 7 — The Validation Layer (`RuleEngine`)
- The `RuleEngine` acts as a specialized **Validation Service**.
- It checks whether a specific piece can legally move to the requested target cell based on all current constraints (including valid **Promotion** triggers) and returns a definitive answer.

### Rule 8 — Central Orchestration Layer (`GameEngine` as an Application Service)
- The `GameEngine` serves as the central facade/gateway for all game actions, exposing a `request_move(source, destination)` method.
- It must execute checks **sequentially**, in this exact order:
  1. Is the game already over?
  2. Is there already an active motion involving this piece or target cell? *(Crucial for blocking conflicting parallel moves.)*
  3. Does the `RuleEngine` validate and approve the move?
  4. If approved: initialize a **Motion**. It manages time advancement, arrival hooks, **promotion resolution upon arrival**, and triggers `game_over` if a King is captured.

### Rule 9 — Deterministic Time Management & Parallel Action Resolution
- A piece reaches its destination only after its specific travel duration has elapsed.
- Since actions occur simultaneously and in parallel, the engine must handle **thread-safety, race conditions, and simultaneous arrival conflicts deterministically**.
- Use **virtual time** or **event-driven wait mechanisms** rather than thread-blocking sleep, preventing real-time system clock test failures due to OS scheduler latency.

### Rule 10 — Atomic State Transitions (No Intermediary States)
- There is no "in-between" state during travel: the system renders the old state, and upon completion, switches immediately to the new state.
- This prevents synchronization race conditions, duplicate captures, or overlapping pieces during parallel execution.
- The piece is physically removed from its origin **only after** it successfully arrives at the destination.

### Rule 11 — Game Over Criteria
- Game over is triggered **exclusively** by capturing the opposing King.
- There is **no** traditional "Check" or "Checkmate" logic. This is not standard chess.

### Rule 12 — Incremental Feature Delivery & Unit Testing
- Do not add extra pieces until the core skeleton is functional and fully verified.
- The baseline requires: a **Rook** (`RookRule`), click mapping, time tracking, parallel arrival mechanics, and capture handling.
- Once stable, add remaining pieces — each backed by isolated, clean **Unit Tests**.

### Rule 13 — Robust Error Handling (Negative Testing)
- Thoroughly test and validate system behavior against: illegal operations, malformed inputs, out-of-bounds clicks, invalid timestamps, rule violations, and invalid simultaneous execution edge-cases.

### Rule 14 — Rendering Architecture (View Adapter / DTO)
- The rendering component functions as a **View Adapter**, mapping internal entity states to a clean, read-only format resembling a **DTO** (Data Transfer Object) for the UI.

### Rule 15 — Continuous Refactoring & Code Smell Elimination
- Perform refactoring at the end of every implementation phase.
- Eliminate code duplication, prevent oversized classes, and resolve any creeping code smells immediately to prevent monolithic file bloating.

---

## ⏱️ Part 2 — Project Roadmap (Sequential Implementation Order)

> Proceed strictly in this chronological order. Do not skip ahead.

| Phase | Name | Description |
|-------|------|-------------|
| **1** | Board Presentation without UI | Build basic Text I/O / test framework. |
| **2** | Clean State | Define and build the pure logic Model. |
| **3** | Input Interpretation | Create the `BoardMapper` and initial Controller structure. |
| **4** | First Legal Motion | Implement the isolated Rook Rule. |
| **5** | Command Pipeline | Code the `RuleEngine` and orchestration in `GameEngine`. |
| **6** | Time & Parallel Action Management | Build the `RealTimeArbiter` component to manage simultaneous actions and time synchronization. |
| **7** | Captures & Win Condition | Implement King-capture logic and game termination. |
| **8** | Extension (Core Mechanics) | Introduce **Promotion** logic into the existing framework with rigorous testing. *(Castling removed — not applicable, no check/king-safety concept in this game.)* |
| **9** | Extension (Pieces) | Introduce additional pieces with clean, dedicated test coverage. |
| **10** | Stabilization & Final Refactoring | Rigorous negative testing for parallel conflicts, architecture cleanup, and optimization. |

---

## ✅ Architectural Commitment

These 15 rules and the 10-phase roadmap above are understood and will be followed as the binding architecture for this project.

**Handling race conditions & separation of concerns under parallel execution:**
Race conditions are handled by treating time as a **deterministic, virtual/event-driven resource** rather than relying on real system clocks or blocking sleeps (Rule 9) — every Motion is scheduled and resolved through a single arbiter that evaluates simultaneous arrivals in a defined, repeatable order, and state changes are applied **atomically** only at confirmed arrival (Rule 10), eliminating any in-between state where two pieces could occupy or contest a square. Separation of concerns is maintained by keeping validation (`RuleEngine`), orchestration (`GameEngine`), piece-movement logic (Strategy-pattern rules), and rendering (View Adapter/DTO) as fully independent layers that never share responsibilities — so the concurrency-handling logic in the arbiter/`GameEngine` never leaks into piece rules or rendering, and vice versa.
