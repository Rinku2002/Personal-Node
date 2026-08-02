"""Ludo — 4-player turn-based board game."""

import random
import string
import threading
import time
import uuid

MAX_PLAYERS = 4
TOKENS_PER_PLAYER = 4
TRACK_LEN = 52
FINISH_STEPS = 57  # steps 0-56 playable; 56 = home, 57 = finished marker
TURN_TIMEOUT_SEC = 60
ROOM_TTL_SEC = 24 * 3600

START_POS = [0, 13, 26, 39]
SAFE_SQUARES = {0, 8, 13, 21, 26, 34, 39, 47}

COLORS = [
    {"name": "Red", "hex": "#ef4444"},
    {"name": "Green", "hex": "#22c55e"},
    {"name": "Yellow", "hex": "#eab308"},
    {"name": "Blue", "hex": "#3b82f6"},
]

_lock = threading.Lock()
_rooms = {}


def _new_room_code():
    for _ in range(50):
        code = "".join(random.choices(string.ascii_uppercase, k=4))
        if code not in _rooms:
            return code
    return uuid.uuid4().hex[:4].upper()


def _new_tokens():
    return [{"steps": -1} for _ in range(TOKENS_PER_PLAYER)]


def _new_player(name, color_idx):
    return {
        "id": uuid.uuid4().hex,
        "name": name[:20],
        "color": color_idx,
        "tokens": _new_tokens(),
    }


def _absolute_pos(color_idx, steps):
    if steps < 0 or steps >= 51:
        return None
    return (START_POS[color_idx] + steps) % TRACK_LEN


def _is_finished(token):
    return token["steps"] >= 56


def _player_has_moves(player, dice):
    return bool(_valid_moves_for_player(player, dice))


def _valid_moves_for_player(player, dice):
    moves = []
    for idx, token in enumerate(player["tokens"]):
        if _is_finished(token):
            continue
        new_steps = _simulate_move(player["color"], token["steps"], dice)
        if new_steps is not None:
            moves.append({"token": idx, "steps": new_steps})
    return moves


def _simulate_move(color_idx, steps, dice):
    if steps == -1:
        return 0 if dice == 6 else None

    new_steps = steps + dice
    if new_steps > 56:
        return None
    return new_steps


def _apply_capture(room, mover, new_steps):
    if new_steps >= 51:
        return False

    landing = _absolute_pos(mover["color"], new_steps)
    if landing is None or landing in SAFE_SQUARES:
        return False

    captured = False
    for player in room["players"]:
        if player["id"] == mover["id"]:
            continue
        for token in player["tokens"]:
            if token["steps"] < 0 or token["steps"] >= 51:
                continue
            if _absolute_pos(player["color"], token["steps"]) == landing:
                token["steps"] = -1
                captured = True
    return captured


def _check_winner(room):
    for player in room["players"]:
        if all(_is_finished(t) for t in player["tokens"]):
            room["phase"] = "finished"
            room["winner"] = player["name"]
            room["winner_id"] = player["id"]
            room["turn_deadline"] = None
            return True
    return False


def _reset_turn(room):
    room["turn_phase"] = "roll"
    room["dice"] = None
    room["valid_moves"] = []
    room["last_event"] = None
    room["turn_deadline"] = time.time() + TURN_TIMEOUT_SEC


def _advance_turn(room, extra=False):
    if _check_winner(room):
        return

    if extra:
        _reset_turn(room)
        return

    n = len(room["players"])
    start = room["current_turn"]
    for offset in range(1, n + 1):
        idx = (start + offset) % n
        player = room["players"][idx]
        if not all(_is_finished(t) for t in player["tokens"]):
            room["current_turn"] = idx
            _reset_turn(room)
            return

    room["phase"] = "finished"
    room["turn_deadline"] = None


def _cleanup_stale_rooms():
    now = time.time()
    stale = [
        code for code, room in _rooms.items()
        if now - room.get("updated_at", room["created_at"]) > ROOM_TTL_SEC
    ]
    for code in stale:
        del _rooms[code]


def _current_player(room):
    return room["players"][room["current_turn"]]


def _auto_play_turn(room):
    if room["phase"] != "playing":
        return False

    deadline = room.get("turn_deadline")
    if not deadline or time.time() < deadline:
        return False

    player = _current_player(room)
    if room["turn_phase"] == "roll":
        dice = random.randint(1, 6)
        room["dice"] = dice
        room["last_roll"] = dice
        moves = _valid_moves_for_player(player, dice)
        room["valid_moves"] = moves
        room["last_event"] = f"{player['name']} timed out — rolled {dice}."
        if not moves:
            room["last_event"] += " No moves — turn skipped."
            _advance_turn(room, extra=False)
            room["updated_at"] = time.time()
            return True

        move = moves[0]
        _execute_move(room, player, move["token"], move["steps"], dice)
        room["updated_at"] = time.time()
        return True

    if room["turn_phase"] == "move" and room["valid_moves"]:
        move = room["valid_moves"][0]
        _execute_move(room, player, move["token"], move["steps"], room["dice"])
        room["updated_at"] = time.time()
        return True

    return False


def _execute_move(room, player, token_idx, new_steps, dice):
    token = player["tokens"][token_idx]
    old_steps = token["steps"]
    token["steps"] = new_steps

    finished = _is_finished(token)
    captured = _apply_capture(room, player, new_steps)
    extra = dice == 6 or captured or finished

    event = f"{player['name']} moved token {token_idx + 1}"
    if captured:
        event += " and captured a piece!"
    if finished:
        event += " — token home!"
    room["last_event"] = event

    if _check_winner(room):
        return

    _advance_turn(room, extra=extra)


def _token_public(token, color_idx):
    steps = token["steps"]
    return {
        "steps": steps,
        "finished": _is_finished(token),
        "home": steps == -1,
        "track_pos": _absolute_pos(color_idx, steps) if 0 <= steps < 51 else None,
        "home_pos": steps - 51 if 51 <= steps < 56 else None,
    }


def _player_public(player, viewer_id):
    return {
        "id": player["id"],
        "name": player["name"],
        "color": player["color"],
        "color_name": COLORS[player["color"]]["name"],
        "color_hex": COLORS[player["color"]]["hex"],
        "tokens": [_token_public(t, player["color"]) for t in player["tokens"]],
        "finished_count": sum(1 for t in player["tokens"] if _is_finished(t)),
        "you": player["id"] == viewer_id,
    }


def _room_state(room, viewer_id=None):
    current = _current_player(room) if room["phase"] == "playing" else None
    host_id = room["players"][0]["id"] if room["players"] else None
    deadline = room.get("turn_deadline")
    seconds_left = max(0, int(deadline - time.time())) if deadline else None

    return {
        "room": room["code"],
        "phase": room["phase"],
        "players": [_player_public(p, viewer_id) for p in room["players"]],
        "player_count": len(room["players"]),
        "max_players": MAX_PLAYERS,
        "colors": COLORS,
        "current_turn": room.get("current_turn", 0),
        "current_player_id": current["id"] if current else None,
        "current_player_name": current["name"] if current else None,
        "turn_phase": room.get("turn_phase"),
        "dice": room.get("dice"),
        "last_roll": room.get("last_roll"),
        "valid_moves": room.get("valid_moves", []),
        "last_event": room.get("last_event"),
        "turn_seconds_left": seconds_left,
        "you": {
            "player_id": viewer_id,
            "joined": any(p["id"] == viewer_id for p in room["players"]),
            "is_host": viewer_id == host_id,
            "your_turn": current is not None and current["id"] == viewer_id,
        },
        "winner": room.get("winner"),
        "share_url": f"/games/ludo?room={room['code']}",
    }


def create_room(name):
    with _lock:
        code = _new_room_code()
        now = time.time()
        host = _new_player(name, 0)
        _rooms[code] = {
            "code": code,
            "phase": "lobby",
            "players": [host],
            "current_turn": 0,
            "turn_phase": "roll",
            "dice": None,
            "last_roll": None,
            "valid_moves": [],
            "last_event": None,
            "winner": None,
            "winner_id": None,
            "turn_deadline": None,
            "created_at": now,
            "updated_at": now,
        }
        return {"room": code, "player_id": host["id"], "state": _room_state(_rooms[code], host["id"])}


def join_room(code, name):
    code = code.strip().upper()
    with _lock:
        room = _rooms.get(code)
        if not room:
            return {"error": "Room not found."}
        if room["phase"] != "lobby":
            return {"error": "Game already started."}
        if len(room["players"]) >= MAX_PLAYERS:
            return {"error": "Room is full (4 players max)."}
        if any(p["name"].lower() == name.strip().lower()[:20] for p in room["players"]):
            return {"error": "That name is already taken in this room."}

        color_idx = len(room["players"])
        player = _new_player(name, color_idx)
        room["players"].append(player)
        room["updated_at"] = time.time()
        return {"room": code, "player_id": player["id"], "state": _room_state(room, player["id"])}


def get_state(code, player_id=None):
    code = code.strip().upper()
    with _lock:
        _cleanup_stale_rooms()
        room = _rooms.get(code)
        if not room:
            return {"error": "Room not found."}
        _auto_play_turn(room)
        room["updated_at"] = time.time()
        return _room_state(room, player_id)


def start_game(code, player_id):
    code = code.strip().upper()
    with _lock:
        room = _rooms.get(code)
        if not room:
            return {"error": "Room not found."}
        if room["phase"] != "lobby":
            return {"error": "Game already started."}
        if not room["players"] or room["players"][0]["id"] != player_id:
            return {"error": "Only the host can start the game."}
        if len(room["players"]) < 2:
            return {"error": "Need at least 2 players to start."}

        room["phase"] = "playing"
        room["current_turn"] = 0
        _reset_turn(room)
        room["updated_at"] = time.time()
        return {"state": _room_state(room, player_id)}


def roll_dice(code, player_id):
    code = code.strip().upper()
    with _lock:
        room = _rooms.get(code)
        if not room:
            return {"error": "Room not found."}
        if room["phase"] != "playing":
            return {"error": "Game is not in progress."}

        player = _current_player(room)
        if player["id"] != player_id:
            return {"error": "Not your turn."}
        if room["turn_phase"] != "roll":
            return {"error": "Already rolled — pick a token."}

        dice = random.randint(1, 6)
        room["dice"] = dice
        room["last_roll"] = dice
        moves = _valid_moves_for_player(player, dice)
        room["valid_moves"] = moves
        room["last_event"] = f"{player['name']} rolled a {dice}."
        room["updated_at"] = time.time()

        if not moves:
            room["last_event"] += " No valid moves."
            _advance_turn(room, extra=False)
            return {"state": _room_state(room, player_id)}

        if len(moves) == 1:
            _execute_move(room, player, moves[0]["token"], moves[0]["steps"], dice)
            return {"state": _room_state(room, player_id)}

        room["turn_phase"] = "move"
        return {"state": _room_state(room, player_id)}


def leave_room(code, player_id):
    code = code.strip().upper()
    with _lock:
        room = _rooms.get(code)
        if not room:
            return {"ok": True, "deleted": True}

        idx = next((i for i, p in enumerate(room["players"]) if p["id"] == player_id), None)
        if idx is None:
            return {"ok": True, "deleted": False}

        if idx == 0:
            del _rooms[code]
            return {"ok": True, "deleted": True}

        if room["phase"] == "lobby":
            room["players"].pop(idx)
            room["updated_at"] = time.time()
        return {"ok": True, "deleted": False}


def move_token(code, player_id, token_idx):
    code = code.strip().upper()
    with _lock:
        room = _rooms.get(code)
        if not room:
            return {"error": "Room not found."}
        if room["phase"] != "playing":
            return {"error": "Game is not in progress."}

        player = _current_player(room)
        if player["id"] != player_id:
            return {"error": "Not your turn."}
        if room["turn_phase"] != "move":
            return {"error": "Roll the dice first."}

        valid = {m["token"]: m["steps"] for m in room["valid_moves"]}
        if token_idx not in valid:
            return {"error": "Invalid move for that token."}

        _execute_move(room, player, token_idx, valid[token_idx], room["dice"])
        room["updated_at"] = time.time()
        return {"state": _room_state(room, player_id)}
