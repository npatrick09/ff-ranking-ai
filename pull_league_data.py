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
            
            # Get points for and against
            points_for, points_against = self.get_team_points_for_against(team)
            
            # Calculate point differential
            point_differential = round(points_for - points_against, 2)
            
            return {
                "record": record,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "win_percentage": win_percentage,
                "points_for": points_for,
                "points_against": points_against,
                "point_differential": point_differential,
                "games_played": total_games
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
        
        print(f"\nStandings data pulled for {len(standings_data['teams'])} teams")
        print("Ready for AI power rankings analysis!")
        
    else:
        print("Failed to pull league standings data")


if __name__ == "__main__":
    main()