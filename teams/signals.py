import pandas as pd

from .utils import get_team_gps_sheet, get_team_stats_sheet
from .models import TeamStats
from cards.utils import (
                    calculate_gps_athletic_skills, 
                    calculate_gps_football_abilities,
                    calculate_attacking_skills,
                    calculate_videocard_defensive,
                    calculate_videocard_distributions
                )

# this will executed in 'cards.signals'
# after the teams and game were created 
# and cards stats calculated.
def calculate_team_gps_stats(instance):
    print("Team Stats ===> GPS Data File signal is invoked.")
    
    try:
        gps_sheet = pd.read_excel(instance.data_file, sheet_name='Oliver GPS Metrcis')
        team_gps_sheet = get_team_gps_sheet(gps_sheet)
        team_gps_sheet['Team ID'] = team_gps_sheet['Team ID'].astype(str)
        
        # Get the Game linked to the GameGPSData instance
        game = instance.game
        if not game:
            print("No game linked to this GPS data instance.")
            return
        
        # Get the Teams linked to the Game
        teams = game.teams.all()
        
        if not teams.exists():
            print(f"No teams linked to game {game.id}.")
            return
        
        for team in teams:
            gps_row = team_gps_sheet[team_gps_sheet['Team ID'] == team.id]
            
            if gps_row.empty:
                print(f"GPS Data not available for team ID: {team.id}")
            else:
                metrics = {
                    'gps_athletic_skills' : calculate_gps_athletic_skills(gps_row),
                    'gps_football_abilities' : calculate_gps_football_abilities(gps_row),
                }
                print(f"Calculated GPS metrics for team {team.id}: {metrics}.")
        
                # Create or update the Team Stats
                team_stats, created = TeamStats.objects.get_or_create(
                    team=team,
                    game=game,
                    # defaults={'metrics': metrics}
                )
                
                # Merge the new metrics into the existing metrics
                team_stats.metrics.update(metrics)

                # Save the updated TeamStats instance
                team_stats.save()
                
                if created:
                    print(f"Created GPS Metrics for team {team.id}")
                else:
                    print(f"Updated GPS Metrics for team {team.id}")
    except Exception as e:
        print(f"Error processing Team GPS data file: {e}")


def calculate_team_video_stats(instance):
    print("Team Stats ===> Game Video Data File signal is invoked.")
    
    try:
        stats_sheet = pd.read_excel(instance.data_file, sheet_name='PlayerStats_137183')
        match_sheet = pd.read_excel(instance.data_file, sheet_name='MatchDetails')

        team_stats_sheet = get_team_stats_sheet(stats_sheet)
        
        team_stats_sheet['team_id'] = team_stats_sheet['team_id'].astype(str)
        
        # Get the Game linked to the GameVideoData instance
        game = instance.game
        if not game:
            print("No game linked to this Game Video data instance.")
            return
        
        # Get the Teams linked to the Game
        teams = game.teams.all()
        
        if not teams.exists():
            print(f"No teams linked to game {game.id}.")
            return
        
        for team in teams:
            stats_row = team_stats_sheet[team_stats_sheet['team_id'] == team.id]
            
            if stats_row.empty:
                print(f"GAme Video Data is not available for team ID: {team.id}")
            else:
                # Extract data from rows
                stats_data = stats_row.iloc[0].to_dict()
                
                metrics = {
                    'attacking_skills' : calculate_attacking_skills(stats_data, match_sheet),
                    'videocard_defensive' : calculate_videocard_defensive(stats_data, match_sheet),
                    'videocard_distributions' : calculate_videocard_distributions(stats_data, match_sheet)
                }
                print(f"Calculated Video Stats metrics for team {team.id}: {metrics}.")
        
                # Create or update the Team Stats
                team_stats, created = TeamStats.objects.get_or_create(
                    team=team,
                    game=game,
                    # defaults={'metrics': metrics}
                )
                
                # Merge the new metrics into the existing metrics
                team_stats.metrics.update(metrics)

                # Save the updated TeamStats instance
                team_stats.save()

                if created:
                    print(f"Created Game Video Metrics for team {team.id}")
                else:
                    print(f"Updated Game Video Metrics for team {team.id}")
    except Exception as e:
        print(f"Error processing Team Game Video data file: {e}")