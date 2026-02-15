from __future__ import annotations
from typing import List, Dict, Any

def round_robin_pairs(team_names: List[str]) -> List[tuple[str, str]]:
    teams = team_names[:]
    if len(teams) % 2 == 1:
        teams.append("BYE")

    n = len(teams)
    rounds = n - 1
    half = n // 2
    schedule = []

    for _ in range(rounds):
        left = teams[:half]
        right = teams[half:][::-1]
        for a, b in zip(left, right):
            if a != "BYE" and b != "BYE":
                schedule.append((a, b))
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return schedule

def assign_time_slots(matches: List[tuple[str, str]], time_slots: List[str]) -> List[Dict[str, Any]]:
    out = []
    for i, (a, b) in enumerate(matches):
        slot = time_slots[i % len(time_slots)] if time_slots else f"Match {i+1}"
        out.append({"match_no": i + 1, "time_slot": slot, "team_a": a, "team_b": b})
    return out
