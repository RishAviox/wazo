from django.db.models.signals import post_save
from django.dispatch import receiver
import pandas as pd
from teams.models import Team

from .models import GameGPSData, GameVideoData, Game


# process game gps data file
@receiver(post_save, sender=GameGPSData, weak=False)
def process_gps_data_file(sender, instance, created, **kwargs):
    if created:
        print("GPS Data File signal is invoked.")

        try:
            gps_sheet = pd.read_excel(instance.data_file, sheet_name='Oliver GPS Metrcis')

            match_id = gps_sheet['MatchID'].iloc[0]
            team_ids = gps_sheet['Team ID'].unique()
            session_date = gps_sheet['Date'].iloc[0]

            # Create or fetch teams
            teams = []
            for team_id in team_ids:
                team, team_created = Team.objects.get_or_create(
                    id=team_id,
                    defaults={'name': f"Team {team_id}"}
                )
                teams.append(team)
                print(f"Team {'created' if team_created else 'retrieved'}: {team}")

            # Create or fetch the game
            game, game_created = Game.objects.get_or_create(
                id=match_id,
                defaults={
                    'type': instance.game_type,
                    'name': f"Game-{match_id}",
                    'date': session_date,
                }
            )
            print(f"Game {'created' if game_created else 'retrieved'}: {game}")

            # Link teams to the game
            game.teams.set(teams)  # Replace existing teams with the new ones
            print(f"Linked teams to game {game.id}")

            # Link the Game to the GPS data instance
            instance.game = game
            instance.is_processed = True
            instance.save()

        except Exception as e:
            print(f"Error processing GPS data file: {e}")


# process game video data file from provider(BEPRO, )
@receiver(post_save, sender=GameVideoData, weak=False)
def process_gps_data_file(sender, instance, created, **kwargs):
    if created:
        print("Game Video Data File signal is invoked.")

        try:
            stats_sheet = pd.read_excel(instance.data_file, sheet_name='PlayerStats_137183')
            match_sheet = pd.read_excel(instance.data_file, sheet_name='MatchDetails')

            # Extract Match ID
            if 'id' not in match_sheet.columns:
                raise ValueError("Match Details sheet is missing the 'match_id' column.")
            
            match_id = match_sheet['id'].iloc[0]
            game_date = pd.to_datetime(match_sheet['start_time'].iloc[0]).date()
            home_team_id = match_sheet['home_team.id'].iloc[0]
            home_team_name = match_sheet['home_team.name'].iloc[0]
            away_team_id = match_sheet['away_team.id'].iloc[0]
            away_team_name = match_sheet['away_team.name'].iloc[0]


            # Create or fetch home and away teams
            home_team, home_team_created = Team.objects.get_or_create(
                id=home_team_id,
                defaults={'name': home_team_name}
            )
            if not home_team_created and home_team.name != home_team_name:
                home_team.name = home_team_name
                home_team.save()
                print(f"Home team name updated to: {home_team_name}")
            else:
                print(f"Home team {'created' if home_team_created else 'retrieved'}: {home_team}")

            away_team, away_team_created = Team.objects.get_or_create(
                id=away_team_id,
                defaults={'name': away_team_name}
            )

            if not away_team_created and away_team.name != away_team_name:
                away_team.name = away_team_name
                away_team.save()
                print(f"Home team name updated to: {away_team_name}")
            else:
                print(f"Away team {'created' if away_team_created else 'retrieved'}: {away_team}")


            # Create or fetch the game
            game, game_created = Game.objects.get_or_create(
                id=match_id,
                defaults={
                    'type': instance.game_type,
                    'name': f"Game-{match_id}",
                    'date': game_date,
                }
            )
            print(f"Game {'created' if game_created else 'retrieved'}: {game}")

            # Link teams to the game
            game.teams.set([home_team, away_team])  # Replace existing teams with the new ones
            print(f"Linked teams to game {game.id}")

            # Link the Game to the GPS data instance
            instance.game = game
            instance.is_processed = True
            instance.save()

        except Exception as e:
            print(f"Error processing video data file: {e}")