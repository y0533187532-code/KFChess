"""Ordered, append-only SQLite schema migrations."""

MIGRATIONS = (
    (
        1,
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE BINARY UNIQUE,
            password_hash TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            rating INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE'
                CHECK (status IN ('ACTIVE', 'DISABLED', 'ANONYMIZED')),
            created_at_ms INTEGER NOT NULL,
            updated_at_ms INTEGER NOT NULL
        );

        CREATE TABLE auth_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            token_hash TEXT NOT NULL UNIQUE,
            created_at_ms INTEGER NOT NULL,
            expires_at_ms INTEGER NOT NULL,
            last_used_at_ms INTEGER NOT NULL,
            revoked_at_ms INTEGER,
            CHECK (expires_at_ms > created_at_ms)
        );
        CREATE INDEX idx_auth_sessions_user ON auth_sessions(user_id);

        CREATE TABLE game_session_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id),
            token_hash TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL CHECK (role IN ('PLAYER', 'SPECTATOR')),
            color TEXT CHECK (color IN ('w', 'b') OR color IS NULL),
            status TEXT NOT NULL DEFAULT 'ACTIVE'
                CHECK (status IN ('ACTIVE', 'GRACE', 'REVOKED')),
            issued_at_ms INTEGER NOT NULL,
            grace_expires_at_ms INTEGER,
            revoked_at_ms INTEGER
        );
        CREATE INDEX idx_game_tokens_game_user
            ON game_session_tokens(game_id, user_id);

        CREATE TABLE game_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL UNIQUE,
            white_user_id INTEGER REFERENCES users(id),
            black_user_id INTEGER REFERENCES users(id),
            outcome TEXT NOT NULL CHECK (outcome IN ('WHITE_WIN', 'BLACK_WIN', 'DRAW')),
            reason TEXT NOT NULL,
            ranked INTEGER NOT NULL CHECK (ranked IN (0, 1)),
            white_rating_before INTEGER,
            white_rating_after INTEGER,
            black_rating_before INTEGER,
            black_rating_after INTEGER,
            created_at_ms INTEGER NOT NULL
        );

        CREATE TABLE rating_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL REFERENCES game_results(game_id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            rating_before INTEGER NOT NULL,
            rating_after INTEGER NOT NULL,
            UNIQUE (game_id, user_id)
        );

        CREATE TABLE rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL COLLATE NOCASE UNIQUE,
            creator_user_id INTEGER REFERENCES users(id),
            status TEXT NOT NULL
                CHECK (status IN ('WAITING', 'ACTIVE', 'CLOSED', 'INTERRUPTED')),
            created_at_ms INTEGER NOT NULL,
            started_at_ms INTEGER,
            closed_at_ms INTEGER,
            close_reason TEXT
        );

        CREATE TABLE room_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL REFERENCES rooms(id),
            user_id INTEGER REFERENCES users(id),
            role TEXT NOT NULL CHECK (role IN ('PLAYER', 'SPECTATOR')),
            color TEXT CHECK (color IN ('w', 'b') OR color IS NULL),
            joined_at_ms INTEGER NOT NULL,
            left_at_ms INTEGER
        );
        CREATE INDEX idx_room_members_room ON room_members(room_id);
        """,
    ),
    (
        2,
        """
        CREATE TABLE rooms_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL COLLATE NOCASE UNIQUE
                CHECK (length(code) = 6 AND code = upper(code)
                    AND code NOT GLOB '*[^A-Z0-9]*'),
            game_id TEXT NOT NULL UNIQUE,
            creator_user_id INTEGER REFERENCES users(id),
            status TEXT NOT NULL
                CHECK (status IN ('WAITING', 'ACTIVE', 'CLOSED', 'INTERRUPTED', 'ENDED')),
            created_at_ms INTEGER NOT NULL,
            started_at_ms INTEGER,
            closed_at_ms INTEGER,
            close_reason TEXT
        );

        INSERT INTO rooms_v2(
            id, code, game_id, creator_user_id, status, created_at_ms,
            started_at_ms, closed_at_ms, close_reason
        )
        SELECT id, code, 'legacy-room-' || id, creator_user_id, status,
               created_at_ms, started_at_ms, closed_at_ms, close_reason
        FROM rooms;

        CREATE TABLE room_members_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL REFERENCES rooms_v2(id),
            user_id INTEGER REFERENCES users(id),
            role TEXT NOT NULL CHECK (role IN ('PLAYER', 'SPECTATOR')),
            color TEXT CHECK (color IN ('w', 'b') OR color IS NULL),
            joined_at_ms INTEGER NOT NULL,
            left_at_ms INTEGER
        );

        INSERT INTO room_members_v2(
            id, room_id, user_id, role, color, joined_at_ms, left_at_ms
        )
        SELECT id, room_id, user_id, role, color, joined_at_ms, left_at_ms
        FROM room_members;

        DROP TABLE room_members;
        DROP TABLE rooms;
        ALTER TABLE rooms_v2 RENAME TO rooms;
        ALTER TABLE room_members_v2 RENAME TO room_members;

        CREATE INDEX idx_room_members_room ON room_members(room_id);
        CREATE UNIQUE INDEX idx_room_active_user
            ON room_members(room_id, user_id)
            WHERE left_at_ms IS NULL AND user_id IS NOT NULL;
        CREATE UNIQUE INDEX idx_room_active_color
            ON room_members(room_id, color)
            WHERE left_at_ms IS NULL AND role = 'PLAYER' AND color IS NOT NULL;
        """,
    ),
    (
        3,
        """
        CREATE TABLE game_lifecycles (
            game_id TEXT PRIMARY KEY,
            mode TEXT NOT NULL CHECK (mode IN ('PLAY', 'ROOM')),
            ranked INTEGER NOT NULL CHECK (ranked IN (0, 1)),
            state TEXT NOT NULL CHECK (state IN (
                'CREATED', 'WAITING_TO_START', 'ACTIVE',
                'PAUSED_FOR_RECONNECT', 'ENDED', 'CANCELLED', 'INTERRUPTED'
            )),
            room_id INTEGER REFERENCES rooms(id),
            double_disconnect INTEGER NOT NULL DEFAULT 0
                CHECK (double_disconnect IN (0, 1)),
            winner_seat TEXT CHECK (
                winner_seat IN ('FIRST_PLAYER', 'SECOND_PLAYER')
                OR winner_seat IS NULL
            ),
            terminal_reason TEXT,
            version INTEGER NOT NULL DEFAULT 0,
            created_at_ms INTEGER NOT NULL,
            started_at_ms INTEGER,
            ended_at_ms INTEGER
        );

        CREATE TABLE game_lifecycle_players (
            game_id TEXT NOT NULL REFERENCES game_lifecycles(game_id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            seat TEXT NOT NULL CHECK (seat IN ('FIRST_PLAYER', 'SECOND_PLAYER')),
            connected INTEGER NOT NULL DEFAULT 1 CHECK (connected IN (0, 1)),
            reconnect_deadline_ms INTEGER,
            meaningful_activity INTEGER NOT NULL DEFAULT 0
                CHECK (meaningful_activity IN (0, 1)),
            PRIMARY KEY (game_id, user_id),
            UNIQUE (game_id, seat)
        );
        CREATE INDEX idx_game_lifecycle_state ON game_lifecycles(state);
        """,
    ),
)
