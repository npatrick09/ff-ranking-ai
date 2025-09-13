"""
Fantasy Football League Data Puller - Simple Standings Edition

This script pulls current standings, points for, and points against 
for a Yahoo Fantasy Football league without any estimations or averages.

League: Kappa Concealed Carry (461.l.13157)
Target Week: 1 (2025 season - current season data)
"""

import json
from yahoofantasy import Context
from datetime import datetime
import re
try:
    import requests
    from bs4 import BeautifulSoup
    from rapidfuzz import process as fuzz_process
except Exception:
    requests = None
    BeautifulSoup = None
    fuzz_process = None


class FantasyLeagueStandingsPuller:
    def __init__(self, league_key="461.l.13157", target_week=1, season_year=2025):
        """
        Initialize the standings puller for a specific league and week.
        
        Args:
            league_key (str): Yahoo Fantasy league key
            target_week (int): Week to analyze (default: 17 for historical 2024 data)
            season_year (int): Season year (default: 2024)
        """
        self.league_key = league_key
        self.target_week = target_week
        self.season_year = season_year
        self.ctx = Context()
        self.league = None
        self._fp_rankings = None  # cache FantasyPros rankings (unused if Sleeper enabled)
        self._sleeper_players = None  # cache Sleeper players map
        self._sleeper_pos_ranks = None  # cache Sleeper trending-based ranks by position
        self._sleeper_adp_pos_ranks = None  # cache Sleeper ADP-based ranks by position
        self._yahoo_pos_ranks = None  # cache Yahoo-only ranks by position using avg PPG
        
    def connect_to_league(self):
        """Connect to the Yahoo Fantasy league."""
        try:
            # Get all leagues for the season
            leagues = list(self.ctx.get_leagues("nfl", self.season_year))
            
            print(f"Found {len(leagues)} NFL leagues for {self.season_year}")
            print("Available leagues:")
            for league in leagues:
                print(f"  - {league.id}: {league.name}")
            
            # Find the specific league
            for league in leagues:
                if str(league.id) == str(self.league_key) or str(league.id).endswith(f"l.{self.league_key}"):
                        self.league = league
                        print(f"✅ Connected to league: {league.name} (ID: {league.id})")
                        return True
                        
            print(f"❌ League with key {self.league_key} not found!")
            print(f"Available league IDs: {[league.id for league in leagues]}")
            return False
            
        except Exception as e:
            print(f"Error connecting to league: {e}")
            print("This might be an authentication issue. Try running debug_league_access.py")
            return False
    
    def get_team_points_for_against(self, team):
        """
        Get total points for and against for a team through the target week.
        
        Args:
            team: Yahoo Fantasy team object
            
        Returns:
            tuple: (points_for, points_against)
        """
        points_for = 0.0
        points_against = 0.0
        
        try:
            # Get all weeks up to target week
            for week_num in range(1, self.target_week + 1):
                try:
                    week = self.league.weeks()[week_num - 1]
                    
                    # Find this team's matchup for the week
                    for matchup in week.matchups:
                        team_stats = None
                        opponent_stats = None
                        
                        if matchup.team1.team_id == team.team_id:
                            team_stats = matchup.team1_stats
                            opponent_stats = matchup.team2_stats
                        elif matchup.team2.team_id == team.team_id:
                            team_stats = matchup.team2_stats
                            opponent_stats = matchup.team1_stats
                        
                        if team_stats and opponent_stats:
                            # Get total points (stat_id "0" is total points)
                            for stat in team_stats:
                                if stat.stat_id == "0":
                                    points_for += float(stat.value)
                                    break
                            
                            for stat in opponent_stats:
                                if stat.stat_id == "0":
                                    points_against += float(stat.value)
                                    break
                            break
                        
                except IndexError:
                    # Week doesn't exist yet, skip
                    continue
                except Exception as e:
                    print(f"Error processing week {week_num} for {team.name}: {e}")
                    continue
            
        except Exception as e:
            print(f"Error getting points for {team.name}: {e}")
            
        return round(points_for, 2), round(points_against, 2)

    def _to_plain(self, value):
        """Convert library-specific objects into JSON-serializable plain types."""
        try:
            import collections.abc as cabc
        except Exception:
            cabc = None
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        # Mapping/dict-like
        if isinstance(value, dict):
            return {str(k): self._to_plain(v) for k, v in value.items()}
        # Iterable/list-like (but not string)
        if cabc and isinstance(value, cabc.Iterable):
            try:
                return [self._to_plain(v) for v in value]
            except Exception:
                pass
        # Fallback to string
        try:
            return str(value)
        except Exception:
            return None

    def serialize_roster(self, team):
        """
        Return full roster details for a team for ChatGPT consumption.
        Fields per player: name, status, display_position, eligible_positions,
        editorial_team_abbr, player_id, player_key, selected_position.
        """
        roster = []
        try:
            players = list(team.players())
        except Exception:
            players = []

        # Yahoo-only ranking is computed at league level; ensure present
        if self._yahoo_pos_ranks is None:
            self._yahoo_pos_ranks = {}

        for p in players:
            try:
                name_full = (
                    getattr(getattr(p, "name", None), "full", None)
                    or getattr(p, "name", None)
                    or ""
                )
                entry = {
                    "name": name_full,
                    "status": self._to_plain(getattr(p, "status", "") or ""),
                    "display_position": self._to_plain(getattr(p, "display_position", "") or ""),
                    "eligible_positions": self._to_plain(getattr(p, "eligible_positions", []) or []),
                    "editorial_team_abbr": self._to_plain(getattr(p, "editorial_team_abbr", "") or ""),
                    "player_id": self._to_plain(getattr(p, "player_id", None)),
                    "player_key": self._to_plain(getattr(p, "player_key", "") or ""),
                    "selected_position": self._to_plain(getattr(p, "selected_position", None)),
                }
                # Attach FantasyPros position rank if available
                # Attach Sleeper trending-based position rank if available
                try:
                    pos_rank = self._lookup_yahoo_pos_rank(entry)
                except Exception:
                    pos_rank = None
                entry["pos_rank"] = pos_rank
                roster.append(entry)
            except Exception:
                continue

        return roster

    # ---------- FantasyPros helpers ----------
    def _normalize_name(self, s):
        if not s:
            return ""
        s = s.lower()
        s = re.sub(r"[^a-z0-9\s\.\-]", "", s)
        # remove suffixes
        s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _normalize_team(self, team):
        if not team:
            return ""
        t = str(team).upper()
        aliases = {
            "WSH": "WAS",
            "JAX": "JAC",
            "LA": "LAR",
            "OAK": "LV",
            "STL": "LAR",
            "SD": "LAC",
        }
        return aliases.get(t, t)

    def _fetch_fantasypros_weekly_rankings(self):
        if not requests or not BeautifulSoup:
            return {}
        urls = {
            "QB": "https://www.fantasypros.com/nfl/rankings/qb.php",
            "RB": "https://www.fantasypros.com/nfl/rankings/rb.php",
            "WR": "https://www.fantasypros.com/nfl/rankings/wr.php",
            "TE": "https://www.fantasypros.com/nfl/rankings/te.php",
            "K":  "https://www.fantasypros.com/nfl/rankings/k.php",
            "DST": "https://www.fantasypros.com/nfl/rankings/dst.php",
        }
        pos_to_ranks = {}
        headers = {"User-Agent": "Mozilla/5.0"}
        for pos, url in urls.items():
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                table = soup.find("table")
                ranks = []
                rank_num = 0
                rows = table.find_all("tr") if table else []
                for tr in rows:
                    # Skip header rows
                    tds = tr.find_all("td")
                    if len(tds) < 2:
                        continue
                    # Try to find rank
                    try:
                        rank_text = tds[0].get_text(strip=True)
                        rank_num = int(re.sub(r"[^0-9]", "", rank_text) or "0")
                        if rank_num == 0:
                            rank_num += 1
                    except Exception:
                        rank_num += 1
                    # Find player name and team
                    name_txt = tr.get_text(" ", strip=True)
                    # Prefer anchor text
                    a = tr.find("a")
                    if a and a.get_text(strip=True):
                        name_field = a.get_text(strip=True)
                    else:
                        name_field = name_txt
                    # Extract team token if present
                    team_span = tr.find("span", class_=re.compile("team", re.I))
                    team_abbr = team_span.get_text(strip=True) if team_span else ""
                    clean_name = self._normalize_name(name_field)
                    if clean_name:
                        ranks.append({"rank": rank_num, "name": clean_name, "team": team_abbr.upper()})
                # Fallback: use anchors to player pages if no ranks parsed
                if not ranks:
                    anchors = soup.select('a[href*="/nfl/players/"]')
                    for idx, a in enumerate(anchors, start=1):
                        nm = self._normalize_name(a.get_text(strip=True))
                        if nm:
                            ranks.append({"rank": idx, "name": nm, "team": ""})
                pos_to_ranks[pos] = ranks
                # Debug: print parsed count and sample
                try:
                    sample = [(r.get("rank"), r.get("name")) for r in ranks[:5]]
                    print(f"FantasyPros {pos}: parsed {len(ranks)} rows, sample: {sample}")
                except Exception:
                    pass
            except Exception:
                continue
        return pos_to_ranks

    # ---------- Sleeper helpers ----------
    # ---------- Yahoo-only ranking helpers ----------
    def _compute_completed_weeks(self):
        # Use all weeks up to target_week; per-player points retrieval will skip missing
        try:
            max_week = min(self.target_week, len(list(self.league.weeks())))
        except Exception:
            max_week = self.target_week
        return list(range(1, max_week + 1))

    def _collect_all_players_ppg(self, completed_weeks):
        """
        Build per-position average points per game for all players on all rosters.
        Returns {POS: {normalized_name: (avg_ppg, last_week_pts, original_name)}}
        """
        pos_to_stats = {}
        last_week = max(completed_weeks) if completed_weeks else None
        try:
            teams = list(self.league.teams())
        except Exception:
            teams = []
        for team in teams:
            try:
                players = list(team.players())
            except Exception:
                players = []
            for p in players:
                try:
                    name = (
                        getattr(getattr(p, "name", None), "full", None)
                        or getattr(p, "name", None)
                        or ""
                    )
                    if not name:
                        continue
                    pos = str(getattr(p, "display_position", "") or "").split("/")[0].upper()
                    if pos == "DEF":
                        pos = "DST"
                    if not pos:
                        continue
                    total = 0.0
                    games = 0
                    last_pts = 0.0
                    for wk in completed_weeks:
                        try:
                            pts = p.get_points(week_num=wk)
                            if pts is not None:
                                total += float(pts)
                                games += 1
                                if last_week is not None and wk == last_week:
                                    try:
                                        last_pts = float(pts)
                                    except Exception:
                                        last_pts = 0.0
                        except Exception:
                            continue
                    avg = (total / games) if games > 0 else 0.0
                    norm = self._normalize_name(name)
                    pos_to_stats.setdefault(pos, {})[norm] = (avg, last_pts, name)
                except Exception:
                    continue
        return pos_to_stats

    def _build_yahoo_pos_ranks(self):
        completed_weeks = self._compute_completed_weeks()
        # If no completed weeks yet, ranks will be None
        if not completed_weeks:
            self._yahoo_pos_ranks = {}
            return self._yahoo_pos_ranks
        pos_to_stats = self._collect_all_players_ppg(completed_weeks)
        pos_to_rankmap = {}
        for pos, stats in pos_to_stats.items():
            # sort by avg desc, then last_week_pts desc
            items = sorted(
                stats.items(),
                key=lambda kv: (kv[1][0], kv[1][1]),
                reverse=True,
            )
            rank_map = {}
            for idx, (norm_name, (_avg, _last_pts, _orig)) in enumerate(items, start=1):
                rank_map[norm_name] = idx
            pos_to_rankmap[pos] = rank_map
        self._yahoo_pos_ranks = pos_to_rankmap
        return self._yahoo_pos_ranks

    def _get_team_week_points(self, team, week_num):
        """Return (team_points, opponent_points) for a given team and week, or (None, None)."""
        try:
            week = self.league.weeks()[week_num - 1]
            for matchup in week.matchups:
                team_stats = None
                opp_stats = None
                if matchup.team1.team_id == team.team_id:
                    team_stats = matchup.team1_stats
                    opp_stats = matchup.team2_stats
                elif matchup.team2.team_id == team.team_id:
                    team_stats = matchup.team2_stats
                    opp_stats = matchup.team1_stats
                if team_stats is None or opp_stats is None:
                    continue
                team_pts = None
                opp_pts = None
                for st in team_stats:
                    if getattr(st, "stat_id", None) == "0":
                        try:
                            team_pts = float(st.value)
                        except Exception:
                            team_pts = None
                        break
                for st in opp_stats:
                    if getattr(st, "stat_id", None) == "0":
                        try:
                            opp_pts = float(st.value)
                        except Exception:
                            opp_pts = None
                        break
                return team_pts, opp_pts
        except Exception:
            pass
        return None, None

    def _get_last_week_result(self, team):
        """Return a compact last-week result string like 'W 104.9-98.2' or None if not available."""
        if self.target_week <= 1:
            return None
        last_week = self.target_week - 1
        team_pts, opp_pts = self._get_team_week_points(team, last_week)
        if team_pts is None or opp_pts is None:
            return None
        if team_pts > opp_pts:
            res = "W"
        elif team_pts < opp_pts:
            res = "L"
        else:
            res = "T"
        return f"{res} {round(team_pts, 2)}-{round(opp_pts, 2)}"

    def _get_last3_points_total(self, team):
        """Return sum of the last 3 completed weeks points (only after week 3), else None."""
        if self.target_week <= 3:
            return None
        start_wk = max(1, self.target_week - 3)
        end_wk = self.target_week - 1
        total = 0.0
        found = 0
        for wk in range(start_wk, end_wk + 1):
            team_pts, _ = self._get_team_week_points(team, wk)
            if team_pts is not None:
                total += float(team_pts)
                found += 1
        if found < 3:
            # If fewer than 3 completed games found, still return the sum of what exists after week 3
            return round(total, 2)
        return round(total, 2)

    def _lookup_yahoo_pos_rank(self, roster_entry):
        if not self._yahoo_pos_ranks:
            return None
        name = roster_entry.get("name") or ""
        pos = (roster_entry.get("display_position") or "").split("/")[0].upper()
        if pos == "DEF":
            pos = "DST"
        if not name or not pos:
            return None
        norm = self._normalize_name(name)
        rank_map = self._yahoo_pos_ranks.get(pos) or {}
        return rank_map.get(norm)
    def _fetch_sleeper_adp_pos_ranks(self):
        """
        Fetch season-long positional ranks using Sleeper ADP as a proxy.
        Returns a dict: {POS: {player_id: rank_int}}
        """
        if not requests:
            return {}
        year = self.season_year
        candidates = [
            f"https://api.sleeper.app/v1/players/nfl/adp?season={year}&format=redraft_ppr",
            f"https://api.sleeper.app/v1/players/nfl/adp?season={year}",
            "https://api.sleeper.app/v1/players/nfl/adp",
        ]
        adp_records = []
        for url in candidates:
            try:
                r = requests.get(url, timeout=20)
                if r.status_code != 200:
                    continue
                data = r.json()
                if isinstance(data, list):
                    for item in data:
                        try:
                            pid = (
                                item.get("player_id")
                                or item.get("playerId")
                                or item.get("player")
                                or item.get("id")
                            )
                            adp_val = (
                                item.get("adp")
                                or item.get("avg_pick")
                                or item.get("average_pick")
                                or item.get("rank")
                            )
                            if pid is None or adp_val is None:
                                continue
                            adp_val = float(adp_val)
                            adp_records.append((str(pid), adp_val))
                        except Exception:
                            continue
                if len(adp_records) >= 300:
                    break
            except Exception:
                continue

        if not adp_records:
            return {}

        players_map = self._fetch_sleeper_players()
        id_to_player = players_map.get("id_to_player", {})

        pos_to_list = {}
        for pid, adp_val in adp_records:
            p = id_to_player.get(pid) or {}
            pos = (p.get("position") or "").upper()
            if pos == "DEF":
                pos = "DST"
            if not pos:
                continue
            pos_to_list.setdefault(pos, []).append((adp_val, pid))

        pos_to_ranks = {}
        for pos, items in pos_to_list.items():
            items.sort(key=lambda x: x[0])  # lower ADP first
            rank_map = {}
            for idx, (_adp, pid) in enumerate(items, start=1):
                rank_map[pid] = idx
            pos_to_ranks[pos] = rank_map

        return pos_to_ranks
    def _fetch_sleeper_players(self):
        if self._sleeper_players is not None:
            return self._sleeper_players
        if not requests:
            self._sleeper_players = {}
            return self._sleeper_players
        url = "https://api.sleeper.app/v1/players/nfl"
        try:
            r = requests.get(url, timeout=20)
            if r.status_code != 200:
                self._sleeper_players = {}
                return self._sleeper_players
            data = r.json() or {}
            # Build quick lookup maps
            name_to_ids = {}
            id_to_player = {}
            for pid, p in data.items():
                if not isinstance(p, dict):
                    continue
                full_name = p.get("full_name") or p.get("last_name")
                if not full_name:
                    continue
                norm = self._normalize_name(full_name)
                id_to_player[pid] = p
                if norm:
                    name_to_ids.setdefault(norm, []).append(pid)
            self._sleeper_players = {
                "name_to_ids": name_to_ids,
                "id_to_player": id_to_player,
            }
            return self._sleeper_players
        except Exception:
            self._sleeper_players = {}
            return self._sleeper_players

    def _fetch_sleeper_trending_pos_ranks(self, lookback_hours=720, limit=2000):
        if not requests:
            return {}
        players_map = self._fetch_sleeper_players()
        id_to_player = players_map.get("id_to_player", {})
        pos_to_list = {"QB": [], "RB": [], "WR": [], "TE": [], "K": [], "DST": []}
        add_url = f"https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours={lookback_hours}&limit={limit}"
        drop_url = f"https://api.sleeper.app/v1/players/nfl/trending/drop?lookback_hours={lookback_hours}&limit={limit}"
        try:
            combined = []
            for endpoint in (add_url, drop_url):
                r = requests.get(endpoint, timeout=15)
                if r.status_code != 200:
                    continue
                combined.extend(r.json() or [])
            # Aggregate counts per player across adds/drops
            counts = {}
            for item in combined:
                pid = str(item.get("player_id"))
                counts[pid] = counts.get(pid, 0) + int(item.get("count", 0))
            for pid, count in counts.items():
                p = id_to_player.get(pid)
                if not p:
                    continue
                pos = (p.get("position") or "").upper()
                if pos == "DEF":
                    pos = "DST"
                if pos not in pos_to_list:
                    continue
                pos_to_list[pos].append((pid, count))
            # Sort by count desc, assign 1-based ranks
            pos_ranks = {}
            for pos, lst in pos_to_list.items():
                lst.sort(key=lambda x: (-x[1], x[0]))
                rank_map = {}
                for idx, (pid, _cnt) in enumerate(lst, start=1):
                    rank_map[pid] = idx
                pos_ranks[pos] = rank_map
            # Debug counts
            try:
                for pos in ["QB", "RB", "WR", "TE", "K", "DST"]:
                    print(f"Sleeper trending {pos}: {len(pos_ranks.get(pos, {}))} ranked")
            except Exception:
                pass
            return pos_ranks
        except Exception:
            return {}

    def _match_sleeper_trending_rank(self, roster_entry):
        if not self._sleeper_pos_ranks:
            return None
        name = roster_entry.get("name") or ""
        if not name:
            return None
        pos = (roster_entry.get("display_position") or "").split("/")[0].upper()
        if pos == "DEF":
            pos = "DST"
        rank_map = self._sleeper_pos_ranks.get(pos)
        if not rank_map:
            return None
        players_map = self._fetch_sleeper_players()
        name_to_ids = players_map.get("name_to_ids", {})
        id_to_player = players_map.get("id_to_player", {})
        team = self._normalize_team(roster_entry.get("editorial_team_abbr") or "")
        norm = self._normalize_name(name)
        candidate_ids = name_to_ids.get(norm, [])
        if not candidate_ids and fuzz_process is not None:
            # Fuzzy match name to available keys
            choices = list(name_to_ids.keys())
            try:
                match = fuzz_process.extractOne(norm, choices, score_cutoff=85)
                if match:
                    candidate_ids = name_to_ids.get(match[0], [])
            except Exception:
                candidate_ids = []
        # Filter candidates by team and position
        filtered = []
        for pid in candidate_ids:
            p = id_to_player.get(pid) or {}
            ppos = (p.get("position") or "").upper()
            pteam = self._normalize_team(p.get("team") or "")
            if ppos == pos and (not team or not pteam or team == pteam):
                filtered.append(pid)
        use_ids = filtered or candidate_ids
        # Return best available rank among candidates
        best_rank = None
        for pid in use_ids:
            r = rank_map.get(pid)
            if r is not None:
                if best_rank is None or r < best_rank:
                    best_rank = r
        return best_rank

    def _match_sleeper_adp_rank(self, roster_entry):
        if not self._sleeper_adp_pos_ranks:
            return None
        name = roster_entry.get("name") or ""
        if not name:
            return None
        pos = (roster_entry.get("display_position") or "").split("/")[0].upper()
        if pos == "DEF":
            pos = "DST"
        rank_map = self._sleeper_adp_pos_ranks.get(pos)
        if not rank_map:
            return None
        players_map = self._fetch_sleeper_players()
        name_to_ids = players_map.get("name_to_ids", {})
        id_to_player = players_map.get("id_to_player", {})
        team = self._normalize_team(roster_entry.get("editorial_team_abbr") or "")
        norm = self._normalize_name(name)
        candidate_ids = name_to_ids.get(norm, [])
        if not candidate_ids and fuzz_process is not None:
            choices = list(name_to_ids.keys())
            try:
                match = fuzz_process.extractOne(norm, choices, score_cutoff=85)
                if match:
                    candidate_ids = name_to_ids.get(match[0], [])
            except Exception:
                candidate_ids = []
        filtered = []
        for pid in candidate_ids:
            p = id_to_player.get(pid) or {}
            ppos = (p.get("position") or "").upper()
            pteam = self._normalize_team(p.get("team") or "")
            if ppos == pos and (not team or not pteam or team == pteam):
                filtered.append(pid)
        use_ids = filtered or candidate_ids
        best_rank = None
        for pid in use_ids:
            r = rank_map.get(pid)
            if r is not None:
                if best_rank is None or r < best_rank:
                    best_rank = r
        return best_rank

    def _match_sleeper_composite_rank(self, roster_entry):
        """Prefer ADP rank; fallback to trending; else place after all ADP ranks for that position."""
        adp_rank = self._match_sleeper_adp_rank(roster_entry)
        if adp_rank is not None:
            return adp_rank
        trending_rank = self._match_sleeper_trending_rank(roster_entry)
        if trending_rank is not None:
            return trending_rank
        # If we can match a same-position player id, return 999
        try:
            players_map = self._fetch_sleeper_players()
            name_to_ids = players_map.get("name_to_ids", {})
            id_to_player = players_map.get("id_to_player", {})
            name = roster_entry.get("name") or ""
            team = self._normalize_team(roster_entry.get("editorial_team_abbr") or "")
            pos = (roster_entry.get("display_position") or "").split("/")[0].upper()
            if pos == "DEF":
                pos = "DST"
            norm = self._normalize_name(name)
            candidate_ids = name_to_ids.get(norm, [])
            if not candidate_ids and fuzz_process is not None:
                choices = list(name_to_ids.keys())
                match = fuzz_process.extractOne(norm, choices, score_cutoff=85)
                if match:
                    candidate_ids = name_to_ids.get(match[0], [])
            for pid in candidate_ids:
                p = id_to_player.get(pid) or {}
                if (p.get("position") or "").upper() == pos:
                    # determine fallback rank = max ADP rank for this position + 1
                    fallback = None
                    try:
                        rank_map = (self._sleeper_adp_pos_ranks or {}).get(pos) or {}
                        if rank_map:
                            fallback = max(rank_map.values()) + 1
                        else:
                            # if no ADP ranks, place after trending ranks if present
                            tmap = (self._sleeper_pos_ranks or {}).get(pos) or {}
                            if tmap:
                                fallback = max(tmap.values()) + 1
                    except Exception:
                        fallback = None
                    return fallback if fallback is not None else None
        except Exception:
            pass
        return None

    def _match_fantasypros_rank(self, roster_entry):
        if not self._fp_rankings or fuzz_process is None:
            return None
        pos = (roster_entry.get("display_position") or "").split("/")[0].upper()
        if pos == "DEF":
            pos = "DST"
        if pos not in self._fp_rankings:
            return None
        name = roster_entry.get("name") or ""
        team = (roster_entry.get("editorial_team_abbr") or "").upper()
        target = self._normalize_name(name)
        if not target:
            return None
        candidates = self._fp_rankings.get(pos, [])
        if not candidates:
            return None
        # Build a list of candidate names for fuzzy match
        names_list = [c["name"] for c in candidates]
        match = None
        try:
            match = fuzz_process.extractOne(target, names_list, score_cutoff=80)
        except Exception:
            match = None
        if not match:
            return None
        matched_name = match[0]
        # Find candidate dict
        for c in candidates:
            if c["name"] == matched_name:
                return int(c.get("rank")) if isinstance(c.get("rank"), int) else None
        return None

    def get_star_players(self, team, games_played):
        """
        Compute star players based on average actual points over the last 3 completed weeks.
        Returns empty list until at least 3 games have been played.
        """
        if games_played < 3:
            return []

        # Determine recent weeks to evaluate
        recent_weeks = list(range(max(1, self.target_week - 2), self.target_week + 1))
        try:
            players = list(team.players())
        except Exception:
            players = []

        star_entries = []
        for p in players:
            total = 0.0
            count = 0
            for wk in recent_weeks:
                try:
                    pts = p.get_points(week_num=wk)
                    if pts is not None:
                        total += float(pts)
                        count += 1
                except Exception:
                    continue
            avg = round(total / count, 2) if count > 0 else 0.0
            name = (
                getattr(getattr(p, "name", None), "full", None)
                or getattr(p, "name", None)
                or ""
            )
            status = getattr(p, "status", "") or ""
            if name:
                star_entries.append({
                    "name": name,
                    "avg_points_last3": avg,
                    "latest_status": status
                })

        # Sort by average points desc and take top 3
        star_entries.sort(key=lambda x: x.get("avg_points_last3", 0.0), reverse=True)
        return star_entries[:3]
    
    def pull_team_standings_data(self, team):
        """
        Pull current standings data for a single team.
        
        Args:
            team: Yahoo Fantasy team object
            
        Returns:
            dict: Team standings data
        """
        print(f"Processing team: {team.name}")
        
        try:
            # Get team standings info
            standings = list(self.league.standings())
            team_standing = None
            for standing in standings:
                if standing.team_id == team.team_id:
                    team_standing = standing
                    break
            
            if not team_standing:
                print(f"Could not find standings for {team.name}")
                return None
            
            # Get basic record
            outcomes = team_standing.team_standings.outcome_totals
            wins = outcomes.wins
            losses = outcomes.losses
            ties = outcomes.ties
            
            # Format record string
            record = f"{wins}-{losses}"
            if ties > 0:
                record += f"-{ties}"
            
            # Calculate win percentage
            total_games = wins + losses + ties
            win_percentage = round(wins / total_games, 3) if total_games > 0 else 0.0
            
            # Get points for and against from standings if available; otherwise fall back to matchup aggregation
            points_for = None
            points_against = None
            try:
                ts = team_standing.team_standings
                points_for = getattr(ts, "points_for", None)
                points_against = getattr(ts, "points_against", None)
            except Exception:
                points_for = None
                points_against = None

            if points_for is None or points_against is None:
                points_for, points_against = self.get_team_points_for_against(team)
            
            # Calculate point differential
            point_differential = round(float(points_for) - float(points_against), 2)
            
            # Full roster snapshot
            roster = self.serialize_roster(team)

            # Last week result
            last_week_result = self._get_last_week_result(team)
            # Last 3 weeks points total (gated until after week 3)
            last3_points_total = self._get_last3_points_total(team)
        
            return {
                "record": record,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "win_percentage": win_percentage,
                "points_for": points_for,
                "points_against": points_against,
                "point_differential": point_differential,
                "games_played": total_games,
                "roster": roster,
                "last_week_result": last_week_result,
                "last3_points_total": last3_points_total
            }
            
        except Exception as e:
            print(f"Error processing team {team.name}: {e}")
            return None
    
    def pull_all_standings(self):
        """
        Pull standings data for all teams in the league.
        
        Returns:
            dict: Complete league standings data
        """
        if not self.connect_to_league():
            return None
        
        print(f"Pulling standings data for Week {self.target_week}, {self.season_year}")
        print(f"League: {self.league.name}")
        print("-" * 50)
        
        league_data = {
            "league_info": {
                "name": self.league.name,
                "league_id": self.league.id,
                "season_year": self.season_year,
                "target_week": self.target_week,
                "data_pulled_at": datetime.now().isoformat()
            },
            "teams": {}
        }
        
        try:
            # Build Yahoo-only positional ranks once per league pull
            try:
                self._build_yahoo_pos_ranks()
            except Exception:
                self._yahoo_pos_ranks = {}
            teams = list(self.league.teams())
            
            for team in teams:
                team_data = self.pull_team_standings_data(team)
                if team_data:
                    league_data["teams"][team.name] = team_data
                    
        except Exception as e:
            print(f"Error pulling league standings: {e}")
            return None
        
        # Sort teams by win percentage (highest first)
        if league_data["teams"]:
            sorted_teams = sorted(
                league_data["teams"].items(), 
                key=lambda x: (-x[1]["win_percentage"], -x[1]["points_for"])
            )
            league_data["teams"] = dict(sorted_teams)
        
        return league_data
    
    def save_data(self, data, filename=None):
        """
        Save the pulled standings data to a JSON file.
        
        Args:
            data (dict): League standings data to save
            filename (str): Output filename (auto-generated if None)
        """
        if filename is None:
            filename = f"league_standings_week{self.target_week}_{self.season_year}.json"
            
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Standings data saved to {filename}")
        except Exception as e:
            print(f"Error saving data: {e}")

    def build_chatgpt_prompt(self, league_data):
        """
        Build a compact JSON for ChatGPT summarization.
        Includes each team's core stats and a condensed position rank list.
        """
        if not league_data or "teams" not in league_data:
            return {}
        teams_prompt = []
        for team_name, td in league_data.get("teams", {}).items():
            roster = td.get("roster", []) or []
            pos_to_ranks = {}
            injuries = []
            injuries_count = 0
            for player in roster:
                pos = (player.get("display_position") or "").split("/")[0].upper()
                if pos == "DEF":
                    pos = "DST"
                rank = player.get("pos_rank")
                if pos and isinstance(rank, (int, float)):
                    pos_to_ranks.setdefault(pos, []).append(int(rank))
                status = (player.get("status") or "").upper()
                if status in {"Q", "O", "IR", "PUP", "D", "NA", "SUS"}:
                    injuries_count += 1
                    try:
                        nm = str(player.get("name") or "").strip()
                        if nm:
                            # include position and rank if available
                            if pos and isinstance(rank, (int, float)):
                                injuries.append(f"{nm} ({status}, {pos}:{int(rank)})")
                            else:
                                injuries.append(f"{nm} ({status})")
                    except Exception:
                        pass
            # sort and uniq ranks per position
            for pos, ranks in pos_to_ranks.items():
                ranks = sorted(set(ranks))
                pos_to_ranks[pos] = ranks
            teams_prompt.append({
                "team_name": team_name,
                "record": td.get("record"),
                "win_pct": td.get("win_percentage"),
                "points_for": td.get("points_for"),
                "points_against": td.get("points_against"),
                "point_diff": td.get("point_differential"),
                "games_played": td.get("games_played"),
                "position_ranks": pos_to_ranks,
                "injuries_count": injuries_count,
                "injuries_list": injuries[:5],
                "last_week_result": td.get("last_week_result"),
                "last3_points_total": td.get("last3_points_total"),
            })
        return {
            "league": league_data.get("league_info", {}).get("name"),
            "season": league_data.get("league_info", {}).get("season_year"),
            "week": league_data.get("league_info", {}).get("target_week"),
            "instructions": (
                "Create power rankings for this league in the tone of a snarky, R-rated football analyst. "
                "Return a ranked order from 1 (best) to N (worst). For each team, write 2–3 sentences of "
                "edgy, comedic analysis; roast underperformers hard with crude humor and mild profanity, but "
                "avoid slurs or hateful language. Use provided stats and position_ranks; consider injuries with "
                "position and rank where noted."
            ),
            "teams": teams_prompt,
        }

    def save_prompt(self, prompt_obj, filename="chat_prompt.json"):
        try:
            with open(filename, "w") as f:
                json.dump(prompt_obj, f, indent=2)
            print(f"ChatGPT prompt saved to {filename}")
        except Exception as e:
            print(f"Error saving prompt: {e}")

    def _load_openai_key(self):
        import os
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass
        key = (
            os.getenv("OPENAI_key")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("OPENAIKEY")
        )
        return key

    def generate_power_rankings_html(self, prompt_file="chat_prompt.json", output_html="index.html"):
        try:
            with open(prompt_file, "r") as f:
                payload = json.load(f)
        except Exception as e:
            print(f"Error reading {prompt_file}: {e}")
            return False
        key = self._load_openai_key()
        if not key:
            print("OpenAI API key not found in environment. Skipping AI generation.")
            return False
        try:
            from openai import OpenAI
        except Exception as e:
            print(f"OpenAI client not available: {e}")
            return False
        try:
            client = OpenAI(api_key=key)
            system_msg = (
                "You are a snarky, R-rated (no slurs), edgy football analyst who writes clean, semantic HTML. "
                "Use comedic roasts, mild profanity, and punchy phrasing."
            )
            user_msg = (
                "Using this JSON, produce a ranked power rankings page as clean semantic HTML. "
                "Include an ordered list with each team’s rank, team name, record, PF/PA. For each team, write 2–3 sentences: "
                "insightful, crude, and funny; roast losers. Briefly cite injuries and positional strengths where relevant. "
                "Keep styles minimal.\n\n"
                + json.dumps(payload)
            )
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.7,
            )
            content = resp.choices[0].message.content if resp and resp.choices else ""
            if not content:
                print("Empty response from OpenAI.")
                return False
            # Ensure basic HTML scaffolding
            if "<html" not in content.lower():
                content = f"<html><head><meta charset='utf-8'><title>Power Rankings</title></head><body>{content}</body></html>"
            with open(output_html, "w") as f:
                f.write(content)
            print(f"Power rankings HTML saved to {output_html}")
            return True
        except Exception as e:
            print(f"Error generating HTML with OpenAI: {e}")
            return False
    
    def print_standings_summary(self, data):
        """
        Print a formatted summary of the standings.
        
        Args:
            data (dict): League standings data
        """
        if not data or "teams" not in data:
            print("No data to display")
            return
        
        print("\n" + "="*70)
        print(f"CURRENT STANDINGS - Week {self.target_week}")
        print("="*70)
        print(f"{'Rank':<4} {'Team':<20} {'Record':<8} {'Win%':<6} {'PF':<8} {'PA':<8} {'Diff':<6}")
        print("-"*70)
        
        for rank, (team_name, team_data) in enumerate(data["teams"].items(), 1):
            print(f"{rank:<4} {team_name:<20} {team_data['record']:<8} "
                  f"{team_data['win_percentage']:<6.3f} {team_data['points_for']:<8} "
                  f"{team_data['points_against']:<8} {team_data['point_differential']:<+6.1f}")


def update_to_current_week():
    """
    Helper function to easily update to current week once season starts.
    Modify the week number here when the season is active.
    """
    # Updated for 2025 season - week 1
    
    current_season = 2025  # Updated to 2025 season
    current_week = 1       # Updated to week 1 for new season
    
    return current_season, current_week


def main():
    """Main execution function."""
    # Get current season/week settings
    season_year, target_week = update_to_current_week()
    
    # Initialize the standings puller
    puller = FantasyLeagueStandingsPuller(
        league_key="461.l.13157",  # Updated for 2025 season
        target_week=target_week,
        season_year=season_year
    )
    
    # Pull all standings data
    standings_data = puller.pull_all_standings()
    
    if standings_data:
        # Print formatted standings
        puller.print_standings_summary(standings_data)
        
        # Save to file
        puller.save_data(standings_data)
        # Build and save ChatGPT prompt JSON
        prompt_obj = puller.build_chatgpt_prompt(standings_data)
        puller.save_prompt(prompt_obj)
        # Optionally generate HTML power rankings via OpenAI
        puller.generate_power_rankings_html()
        
        print(f"\nStandings data pulled for {len(standings_data['teams'])} teams")
        print("Ready for AI power rankings analysis!")
        
    else:
        print("Failed to pull league standings data")


if __name__ == "__main__":
    main()