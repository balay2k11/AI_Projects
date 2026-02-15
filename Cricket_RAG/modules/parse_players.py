from __future__ import annotations

from typing import List, Dict, Any, Optional
import re

ALLOWED_ROLES = {"BAT", "BOWL", "AR", "WK"}

def normalize_role(role: str) -> str:
    r = role.strip().lower()
    mapping = {
        "batsman": "BAT", "bat": "BAT",
        "bowler": "BOWL", "bowl": "BOWL",
        "allrounder": "AR", "all-rounder": "AR", "ar": "AR",
        "wicketkeeper": "WK", "wk": "WK", "keeper": "WK",
    }
    return mapping.get(r, role.strip().upper())

def safe_int(x: str, default: int = 5) -> int:
    try:
        v = int(float(x))
        return max(1, min(10, v))
    except Exception:
        return default

def parse_line_to_player(line: str) -> Optional[Dict[str, Any]]:
    line = re.sub(r"^\s*[\-\*\u2022]\s*", "", line)
    line = re.sub(r"^\s*\d+[\.\)]\s*", "", line).strip()
    if not line:
        return None

    # Try split by | , ; tab
    parts = re.split(r"\s*(?:\||,|;|\t)\s*", line)
    parts = [p.strip() for p in parts if p.strip()]

    # Try "Name - Role - Rating"
    if len(parts) == 1 and " - " in parts[0]:
        parts = [p.strip() for p in parts[0].split(" - ") if p.strip()]

    # PDF table often becomes: "Name ROLE RATING"
    if len(parts) == 1:
        m = re.match(r"^(.*?)(\bWK\b|\bBAT\b|\bBOWL\b|\bAR\b)\s+(\d{1,2})\s*$", parts[0], flags=re.I)
        if m:
            name = m.group(1).strip()
            role = normalize_role(m.group(2))
            rating = safe_int(m.group(3), default=5)
            if len(name) < 2:
                return None
            return {"name": name, "role": role, "rating": rating, "raw": line}

    if len(parts) < 1:
        return None

    name = parts[0]
    role = "BAT"
    rating = 5

    if len(parts) >= 2:
        role = normalize_role(parts[1])
    if len(parts) >= 3:
        rating = safe_int(parts[2], default=5)

    if role not in ALLOWED_ROLES:
        low = line.lower()
        if "wicket" in low or "keeper" in low or re.search(r"\bwk\b", low):
            role = "WK"
        elif "all" in low and "round" in low:
            role = "AR"
        elif "bowl" in low:
            role = "BOWL"
        else:
            role = "BAT"

    if len(name.strip()) < 2:
        return None

    return {"name": name.strip(), "role": role, "rating": rating, "raw": line}

def dedupe_players(players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for p in players:
        key = re.sub(r"\s+", " ", p["name"].strip().lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out

def parse_players(text: str) -> List[Dict[str, Any]]:
    lines = [ln.strip() for ln in text.splitlines()]
    players: List[Dict[str, Any]] = []
    for ln in lines:
        if re.search(r"\b(name|player)\b", ln.lower()) and re.search(r"\b(role|rating|level)\b", ln.lower()):
            continue
        p = parse_line_to_player(ln)
        if p:
            players.append(p)
    return dedupe_players(players)
