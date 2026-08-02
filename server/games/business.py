"""Boardroom Tycoon — 4-player business strategy game state."""

import random
import string
import threading
import time
import uuid

MAX_PLAYERS = 4
TOTAL_ROUNDS = 10
STARTING_CASH = 50_000
ROUND_TIMEOUT_SEC = 90
ROOM_TTL_SEC = 24 * 3600

ACTIONS = {
    "product": {
        "name": "Launch Product",
        "icon": "📦",
        "cost": 8_000,
        "desc": "Spend cash to launch a product line.",
    },
    "marketing": {
        "name": "Marketing Blitz",
        "icon": "📣",
        "cost": 5_000,
        "desc": "Boost brand reputation.",
    },
    "team": {
        "name": "Expand Team",
        "icon": "👥",
        "cost": 10_000,
        "desc": "Hire talent to cut future costs.",
    },
    "funding": {
        "name": "Raise Funding",
        "icon": "💰",
        "cost": 0,
        "desc": "Inject cash but lose reputation.",
    },
    "hold": {
        "name": "Hold & Invest",
        "icon": "📈",
        "cost": 0,
        "desc": "Earn 8% interest on cash reserves.",
    },
}

MARKET_EVENTS = [
    {"id": "bull", "name": "Bull Market", "mult": 1.3, "desc": "Investors are bullish — products worth more."},
    {"id": "bear", "name": "Bear Market", "mult": 0.7, "desc": "Markets are down — product values shrink."},
    {"id": "boom", "name": "Tech Boom", "mult": 1.15, "desc": "Tech sector soars — product launches pay extra."},
    {"id": "steady", "name": "Steady Growth", "mult": 1.0, "desc": "Stable economy — business as usual."},
    {"id": "hype", "name": "Brand Hype", "mult": 1.0, "desc": "Marketing campaigns earn double reputation."},
]

_lock = threading.Lock()
_rooms = {}


def _new_room_code():
    for _ in range(50):
        code = "".join(random.choices(string.ascii_uppercase, k=4))
        if code not in _rooms:
            return code
    return uuid.uuid4().hex[:4].upper()


def _new_player(name):
    return {
        "id": uuid.uuid4().hex,
        "name": name[:20],
        "cash": STARTING_CASH,
        "products": 0,
        "reputation": 50,
        "efficiency": 0,
        "submitted": False,
        "last_action": None,
    }


def _cost(player, base_cost):
    discount = min(player["efficiency"] * 0.1, 0.3)
    return int(base_cost * (1 - discount))


def company_value(player, market_mult):
    return int(
        player["cash"]
        + player["products"] * 12_000 * market_mult
        + player["reputation"] * 200
        + player["efficiency"] * 5_000
    )


def _pick_market():
    return dict(random.choice(MARKET_EVENTS))


def _cleanup_stale_rooms():
    now = time.time()
    stale = [
        code for code, room in _rooms.items()
        if now - room.get("updated_at", room["created_at"]) > ROOM_TTL_SEC
    ]
    for code in stale:
        del _rooms[code]


def _auto_submit_missing(room):
    """Auto-submit hold for players who exceed the round time limit."""
    if room["phase"] != "playing":
        return False

    deadline = room.get("round_deadline")
    if not deadline or time.time() < deadline:
        return False

    changed = False
    for player in room["players"]:
        if player["id"] not in room["submissions"]:
            room["submissions"][player["id"]] = "hold"
            player["submitted"] = True
            changed = True

    if changed and len(room["submissions"]) == len(room["players"]):
        _resolve_round(room)
    return changed


def _apply_action(player, action_id, market):
    action = ACTIONS.get(action_id)
    if not action:
        return "Invalid action."

    if action_id == "product":
        cost = _cost(player, action["cost"])
        if player["cash"] < cost:
            return f"Not enough cash (need ${cost:,})."
        player["cash"] -= cost
        bonus = 1
        if market["id"] == "boom":
            bonus = 2
        player["products"] += bonus
        return f"Launched product (+{bonus}). Spent ${cost:,}."

    if action_id == "marketing":
        cost = _cost(player, action["cost"])
        if player["cash"] < cost:
            return f"Not enough cash (need ${cost:,})."
        player["cash"] -= cost
        rep_gain = 15
        if market["id"] == "hype":
            rep_gain = 30
        player["reputation"] += rep_gain
        return f"Marketing blitz (+{rep_gain} reputation). Spent ${cost:,}."

    if action_id == "team":
        if player["efficiency"] >= 3:
            return "Team is fully staffed (max efficiency)."
        cost = _cost(player, action["cost"])
        if player["cash"] < cost:
            return f"Not enough cash (need ${cost:,})."
        player["cash"] -= cost
        player["efficiency"] += 1
        return f"Hired talent (+1 efficiency). Spent ${cost:,}."

    if action_id == "funding":
        player["cash"] += 15_000
        player["reputation"] = max(0, player["reputation"] - 10)
        return "Raised $15,000 funding (-10 reputation)."

    if action_id == "hold":
        interest = int(player["cash"] * 0.08)
        player["cash"] += interest
        return f"Earned ${interest:,} in interest."

    return "Unknown action."


def _resolve_round(room):
    market = room["market"]
    results = []

    for player in room["players"]:
        action_id = room["submissions"].get(player["id"])
        if not action_id:
            continue
        message = _apply_action(player, action_id, market)
        player["last_action"] = action_id
        results.append({
            "name": player["name"],
            "action": ACTIONS[action_id]["name"],
            "icon": ACTIONS[action_id]["icon"],
            "result": message,
        })

    room["last_round"] = {
        "round": room["round"],
        "market": market,
        "results": results,
    }
    room["submissions"] = {}
    for player in room["players"]:
        player["submitted"] = False

    room["round"] += 1
    if room["round"] > TOTAL_ROUNDS:
        room["phase"] = "finished"
        room["round_deadline"] = None
        ranked = sorted(
            room["players"],
            key=lambda p: company_value(p, 1.0),
            reverse=True,
        )
        room["winner"] = ranked[0]["name"]
    else:
        room["market"] = _pick_market()
        room["round_deadline"] = time.time() + ROUND_TIMEOUT_SEC


def _player_public(player, market, submissions, viewer_id):
    return {
        "id": player["id"],
        "name": player["name"],
        "cash": player["cash"],
        "products": player["products"],
        "reputation": player["reputation"],
        "efficiency": player["efficiency"],
        "value": company_value(player, market["mult"]),
        "submitted": player["id"] in submissions,
        "you": player["id"] == viewer_id,
    }


def _room_state(room, viewer_id=None):
    market = room.get("market") or _pick_market()
    if "market" not in room:
        room["market"] = market

    players = [
        _player_public(p, market, room["submissions"], viewer_id)
        for p in room["players"]
    ]

    viewer = next((p for p in room["players"] if p["id"] == viewer_id), None)
    host_id = room["players"][0]["id"] if room["players"] else None

    round_deadline = room.get("round_deadline")
    seconds_left = max(0, int(round_deadline - time.time())) if round_deadline else None

    return {
        "room": room["code"],
        "phase": room["phase"],
        "round": room["round"],
        "total_rounds": TOTAL_ROUNDS,
        "market": market,
        "players": players,
        "player_count": len(room["players"]),
        "max_players": MAX_PLAYERS,
        "round_timeout_sec": ROUND_TIMEOUT_SEC,
        "round_seconds_left": seconds_left,
        "actions": [
            {"id": k, "name": v["name"], "icon": v["icon"], "cost": v["cost"], "desc": v["desc"]}
            for k, v in ACTIONS.items()
        ],
        "you": {
            "player_id": viewer_id,
            "joined": viewer is not None,
            "is_host": viewer_id == host_id,
            "submitted": viewer_id in room["submissions"] if viewer_id else False,
        },
        "last_round": room.get("last_round"),
        "winner": room.get("winner"),
        "share_url": f"/games/business?room={room['code']}",
    }


def create_room(name):
    with _lock:
        code = _new_room_code()
        host = _new_player(name)
        now = time.time()
        _rooms[code] = {
            "code": code,
            "phase": "lobby",
            "round": 1,
            "market": _pick_market(),
            "players": [host],
            "submissions": {},
            "last_round": None,
            "winner": None,
            "round_deadline": None,
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

        player = _new_player(name)
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
        _auto_submit_missing(room)
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
        room["round"] = 1
        room["market"] = _pick_market()
        room["submissions"] = {}
        room["round_deadline"] = time.time() + ROUND_TIMEOUT_SEC
        room["updated_at"] = time.time()
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


def submit_action(code, player_id, action_id):
    code = code.strip().upper()
    with _lock:
        room = _rooms.get(code)
        if not room:
            return {"error": "Room not found."}
        if room["phase"] != "playing":
            return {"error": "Game is not in progress."}

        player = next((p for p in room["players"] if p["id"] == player_id), None)
        if not player:
            return {"error": "You are not in this room."}
        if player_id in room["submissions"]:
            return {"error": "You already submitted this round."}
        if action_id not in ACTIONS:
            return {"error": "Invalid action."}

        _auto_submit_missing(room)

        if player_id in room["submissions"]:
            return {"error": "You already submitted this round."}

        room["submissions"][player_id] = action_id
        player["submitted"] = True
        room["updated_at"] = time.time()

        if len(room["submissions"]) == len(room["players"]):
            _resolve_round(room)

        return {"state": _room_state(room, player_id)}
