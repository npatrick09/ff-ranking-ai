"""
Debug script to troubleshoot Yahoo Fantasy league access issues.
This will help identify the exact problem with league access.
"""

from yahoofantasy import Context
import json


def debug_league_access():
    """Debug Yahoo Fantasy league access step by step."""
    
    print("🔍 YAHOO FANTASY LEAGUE ACCESS DEBUGGER")
    print("=" * 50)
    
    try:
        # Step 1: Test basic connection
        print("Step 1: Testing Yahoo Fantasy API connection...")
        ctx = Context()
        print("✅ Successfully created Yahoo Fantasy context")
        
        # Step 2: Get all available leagues
        print("\nStep 2: Fetching all your 2024 NFL leagues...")
        leagues = list(ctx.get_leagues("nfl", 2024))
        print(f"✅ Found {len(leagues)} NFL leagues for 2024")
        
        if not leagues:
            print("❌ No leagues found! Possible issues:")
            print("   - You might not be in any Yahoo Fantasy leagues for 2024")
            print("   - Authentication might not be working")
            print("   - Check your .yahoofantasy config file")
            return
        
        # Step 3: List all available leagues
        print("\nStep 3: Your available leagues:")
        print("-" * 30)
        for i, league in enumerate(leagues, 1):
            print(f"{i}. League ID: {league.id}")
            print(f"   Name: {league.name}")
            print(f"   Type: {league.league_type}")
            print(f"   Teams: {len(list(league.teams()))}")
            print()
        
        # Step 4: Test specific league access
        target_leagues = ["135009", "nfl.l.135009", 135009]
        
        print("Step 4: Testing access to your target league...")
        print("-" * 30)
        
        for target in target_leagues:
            print(f"Testing league key: {target}")
            found = False
            
            for league in leagues:
                if str(league.id) == str(target):
                    print(f"✅ FOUND! League '{league.name}' matches key {target}")
                    print(f"   League ID: {league.id}")
                    print(f"   League Name: {league.name}")
                    
                    # Test accessing team data
                    try:
                        teams = list(league.teams())
                        print(f"   Teams in league: {len(teams)}")
                        for team in teams[:3]:  # Show first 3 teams
                            print(f"     - {team.name}")
                        found = True
                        break
                    except Exception as e:
                        print(f"   ❌ Error accessing teams: {e}")
                        
            if not found:
                print(f"❌ League key {target} not found in your leagues")
            print()
        
        # Step 5: Provide recommendations
        print("Step 5: Recommendations")
        print("-" * 30)
        
        print("✅ Available league IDs you can use:")
        for league in leagues:
            print(f"   {league.id} - {league.name}")
        
        print(f"\n💡 Try using one of these league IDs in your script")
        
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        print("\nPossible issues:")
        print("1. Yahoo Fantasy API authentication not set up")
        print("2. Missing .yahoofantasy configuration file")
        print("3. Invalid API credentials")
        print("4. Network connectivity issues")
        print("\n🔧 Try running the original test.py to see if basic access works")


def test_yahoofantasy_setup():
    """Test if yahoofantasy library is properly configured."""
    
    print("\n🔧 TESTING YAHOOFANTASY SETUP")
    print("=" * 50)
    
    try:
        from yahoofantasy import Context
        print("✅ yahoofantasy library imported successfully")
        
        # Check if config file exists
        import os
        config_path = os.path.expanduser("~/.yahoofantasy")
        if os.path.exists(config_path):
            print("✅ .yahoofantasy config file found")
            
            # Check if it has content
            file_size = os.path.getsize(config_path)
            print(f"✅ Config file size: {file_size} bytes")
            
            if file_size == 0:
                print("⚠️  Warning: Config file is empty!")
                print("   You may need to set up authentication")
                
        else:
            print("❌ .yahoofantasy config file not found")
            print("   You need to set up Yahoo Fantasy API authentication")
            
    except ImportError as e:
        print(f"❌ Failed to import yahoofantasy: {e}")
        print("   Run: pip install yahoofantasy")
        
    except Exception as e:
        print(f"❌ Setup test failed: {e}")


if __name__ == "__main__":
    test_yahoofantasy_setup()
    print()
    debug_league_access()