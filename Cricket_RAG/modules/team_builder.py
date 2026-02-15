from __future__ import annotations
from typing import List, Dict, Any
import math

def build_balanced_teams(players: List[Dict[str, Any]], num_teams: int = 2, team_size: int | None = None) -> Dict[str, Any]:
    if team_size is None:
        team_size = math.floor(len(players) / num_teams)

    # Sort by rating desc for strong balancing
    players_sorted = sorted(players, key=lambda x: x.get("rating", 5), reverse=True)

    teams = [{"name": f"Team {chr(65+i)}", "players": [], "total_rating": 0} for i in range(num_teams)]

    def add_player(team_i: int, p: Dict[str, Any]):
        teams[team_i]["players"].append(p)
        teams[team_i]["total_rating"] += int(p.get("rating", 5))

    t = 0
    forward = True

    for p in players_sorted:
        # find next team with space
        if len(teams[t]["players"]) >= team_size:
            found = False
            for j in range(num_teams):
                if len(teams[j]["players"]) < team_size:
                    t = j
                    found = True
                    break
            if not found:
                break

        add_player(t, p)

        # snake movement
        if forward:
            if t == num_teams - 1:
                forward = False
            else:
                t += 1
        else:
            if t == 0:
                forward = True
            else:
                t -= 1

    out = {}
    for team in teams:
        out[team["name"]] = {
            "total_rating": team["total_rating"],
            "avg_rating": round(team["total_rating"] / max(1, len(team["players"])), 2),
            "players": [{"name": p["name"], "role": p["role"], "rating": p["rating"]} for p in team["players"]],
        }
    return out
