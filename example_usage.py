"""
Example usage of the Fantasy League Data Puller

This demonstrates how to use the pull_league_data.py script
to get comprehensive fantasy football data for AI analysis.
"""

from pull_league_data import FantasyLeagueDataPuller
import json


def quick_example():
    """Quick example of pulling data for your league."""
    
    print("Fantasy Football Data Puller - Example Usage")
    print("=" * 50)
    
    # Initialize with your league settings
    puller = FantasyLeagueDataPuller(
        league_key="449.l.135009",  # Your specific league - Kappa Concealed Carry
        target_week=10,            # Week 10 as requested
        season_year=2024           # 2024 season
    )
    
    # Pull all the data
    print("Connecting to Yahoo Fantasy and pulling data...")
    league_data = puller.pull_all_data()
    
    if league_data:
        print(f"\n✅ Successfully pulled data for {len(league_data)} teams!")
        
        # Show a sample team's data
        sample_team = next(iter(league_data.keys()))
        print(f"\nSample data for '{sample_team}':")
        print(json.dumps(league_data[sample_team], indent=2))
        
        # Save the data
        puller.save_data(league_data, "my_league_week10_data.json")
        
        return league_data
    else:
        print("❌ Failed to pull data. Check your league key and API access.")
        return None


def analyze_league_trends(league_data):
    """Example analysis functions you could build on top of the data."""
    
    if not league_data:
        return
    
    print("\n" + "=" * 50)
    print("LEAGUE ANALYSIS")
    print("=" * 50)
    
    # Find highest scoring team
    highest_scorer = max(league_data.items(), key=lambda x: x[1]['total_points'])
    print(f"🏆 Highest scorer: {highest_scorer[0]} ({highest_scorer[1]['total_points']} pts)")
    
    # Find longest win streak
    longest_streak = max(league_data.items(), key=lambda x: x[1]['win_streak'])
    print(f"🔥 Longest win streak: {longest_streak[0]} ({longest_streak[1]['win_streak']} wins)")
    
    # Find team with toughest schedule
    toughest_schedule = max(league_data.items(), key=lambda x: x[1]['early_schedule_strength'])
    print(f"💪 Toughest early schedule: {toughest_schedule[0]} ({toughest_schedule[1]['early_schedule_strength']})")
    
    # Teams with injuries
    injured_teams = [team for team, data in league_data.items() if data['injuries']]
    if injured_teams:
        print(f"🏥 Teams with injuries: {', '.join(injured_teams)}")


def create_ai_prompt(league_data):
    """Create a formatted prompt for AI power rankings."""
    
    if not league_data:
        return None
    
    prompt = """
Create power rankings for this fantasy football league based on the following data:

League Data (Week 10, 2024):
"""
    
    prompt += json.dumps(league_data, indent=2)
    
    prompt += """

Please analyze each team and create power rankings considering:
1. Current record and recent performance (last 3 games)
2. Star player production and injury concerns
3. Schedule strength (both past and remaining)
4. Momentum (win streaks/trends)
5. Total points scored vs league average

Provide rankings 1-{} with brief explanations for each team's position.
""".format(len(league_data))
    
    return prompt


if __name__ == "__main__":
    # Run the example
    data = quick_example()
    
    if data:
        # Do some basic analysis
        analyze_league_trends(data)
        
        # Create AI prompt
        ai_prompt = create_ai_prompt(data)
        
        # Save the AI prompt to a file
        with open("ai_prompt_week10.txt", "w") as f:
            f.write(ai_prompt)
        
        print(f"\n💡 AI prompt saved to 'ai_prompt_week10.txt'")
        print("You can now use this data with ChatGPT, Claude, or other AI tools!")