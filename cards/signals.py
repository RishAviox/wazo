from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import pandas as pd

from teams.models import Team
from games.models import GameGPSData, GameVideoData, Game
from accounts.models import PlayerIDMapping
from questionnaire.models import DailyWellnessUserResponse, RPEUserResponse

from .utils import *
from .models import *

# run team stats here
from teams.signals import calculate_team_gps_stats, calculate_team_video_stats
from games.signals import generate_game_meta_data_json

from core.silent_notification import send_silent_notification

# process game gps data file
@receiver(post_save, sender=GameGPSData, weak=False)
def process_gps_data_file(sender, instance, created, **kwargs):
    if not instance.is_processed:
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

            # *************** cards stats calculations
            player_mappings = PlayerIDMapping.objects.select_related('user').all().values(
                    'player_id', 
                    # 'player_position', 
                    'user__phone_no', 
                    # 'user__dob'
                )
            
            player_mapping_dict = {
                str(mapping['player_id']): {
                    'phone_no': mapping['user__phone_no'],
                    # 'position': mapping['player_position'],
                    # 'dob': mapping['user__dob']
                }
                for mapping in player_mappings
            }
            
            print(f"Fetched and prepared player mappings: {player_mapping_dict}.")

            player_ids = set(player_mapping_dict.keys())
            # print("player_ids: ", player_ids, player_mapping_dict.keys())

            # Convert player_id columns to strings for consistent comparison
            gps_sheet['Player ID'] = gps_sheet['Player ID'].astype(int).astype(str)

            # Filter gps_sheet based on player_ids
            filtered_gps_sheet = gps_sheet[gps_sheet['Player ID'].isin(player_ids)]
            print(f"Filtered GPS data sheet to include players: {list(filtered_gps_sheet['Player ID'].unique())}.")

            # for silent notificaitions, send user_ids=[], card_names=[]
            user_ids = []
            for player_id, player_info in player_mapping_dict.items():
                user_phone = player_info['phone_no']

                gps_row = filtered_gps_sheet[filtered_gps_sheet['Player ID'] == player_id]
                
                if gps_row.empty:
                    print("GPS data is not available.")
                else:
                    gps_athletic_skills = calculate_gps_athletic_skills(gps_row)
                    gps_football_abilities = calculate_gps_football_abilities(gps_row)

                    print(f"Calculated GPS Athletic Skills for player {player_id}: {gps_athletic_skills}.")
                    print(f"Calculated GPS Football Abilities for player {player_id}: {gps_football_abilities}.")

                    # Create or update the GPS Athletic skills for the user
                    athletic_skills, created = GPSAthleticSkills.objects.update_or_create(
                        user_id=user_phone,
                        game=game,
                        defaults={'metrics': gps_athletic_skills}
                    )

                    if created:
                        print(f"Created GPS Athletic Skills for player {player_id} (phone: {user_phone}).")
                    else:
                        print(f"Updated GPS Athletic Skills for player {player_id} (phone: {user_phone}).")


                    # Create or update the GPS Football abilities for the user
                    football_abilities, created = GPSFootballAbilities.objects.update_or_create(
                        user_id=user_phone,
                        game=game,
                        defaults={'metrics': gps_football_abilities}
                    )

                    if created:
                        print(f"Created GPS Football Abilities for player {player_id} (phone: {user_phone}).")
                    else:
                        print(f"Updated GPS Football Abilities for player {player_id} (phone: {user_phone}).")

                    user_ids.append(user_phone)
                
            card_names = ['AthleticSkills', 'FootballAbilities']
            # send silent notification
            print(f"Sending silent notification for users: {user_ids} with card names: {card_names}")
            send_silent_notification(user_ids, card_names, game_created)
            # team gps stats
            calculate_team_gps_stats(instance)
        except Exception as e:
            print(f"Error processing GPS data file: {e}")
            
    else:
        print("GPS file is already processed.")


# process game video data file from provider(BEPRO, )
@receiver(post_save, sender=GameVideoData, weak=False)
def process_video_data_file(sender, instance, created, **kwargs):
    if not instance.is_processed:
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
            
            # *************** cards stats calculations
            player_mappings = PlayerIDMapping.objects.select_related('user').all().values(
                    'player_id', 
                    # 'player_position', 
                    'user__phone_no', 
                    # 'user__dob'
                )
            
            player_mapping_dict = {
                str(mapping['player_id']): {
                    'phone_no': mapping['user__phone_no'],
                    # 'position': mapping['player_position'],
                    # 'dob': mapping['user__dob']
                }
                for mapping in player_mappings
            }
            
            print(f"Fetched and prepared player mappings: {player_mapping_dict}.")

            player_ids = set(player_mapping_dict.keys())

            # Convert player_id columns to strings for consistent comparison
            stats_sheet['player_id'] = stats_sheet['player_id'].astype(int).astype(str)

            # Filter stats_sheet based on player_ids
            filtered_stats_sheet = stats_sheet[stats_sheet['player_id'].isin(player_ids)]
            print(f"Filtered stats Video data sheet to include players: {list(filtered_stats_sheet['player_id'].unique())}.")

            # for silent notificaitions, send user_ids=[], card_names=[]
            user_ids = []
            for player_id, player_info in player_mapping_dict.items():
                user_phone = player_info['phone_no']
            
                stats_row = filtered_stats_sheet[filtered_stats_sheet['player_id'] == player_id]
                
                if stats_row.empty:
                    print("Stats Video data is not available.")
                else:                    
                    # Extract data from rows
                    stats_data = stats_row.iloc[0].to_dict()
                    
                    attacking_skills = calculate_attacking_skills(stats_data, match_sheet)
                    videocard_defensive = calculate_videocard_defensive(stats_data, match_sheet)
                    videocard_distributions = calculate_videocard_distributions(stats_data, match_sheet)

                    print(f"Calculated Attacking Skills for player {player_id}: {attacking_skills}.")
                    print(f"Calculated Video Card Defensive for player {player_id}: {videocard_defensive}.")
                    print(f"Calculated Video Card Distributions for player {player_id}: {videocard_distributions}.")

                    # Create or update the Attacking skills for the user
                    _attacking_skills, created = AttackingSkills.objects.update_or_create(
                        user_id=user_phone,
                        game=game,
                        defaults={'metrics': attacking_skills}
                    )

                    if created:
                        print(f"Created Attacking Skills for player {player_id} (phone: {user_phone}).")
                    else:
                        print(f"Updated Attacking Skills for player {player_id} (phone: {user_phone}).")


                    # Create or update the Video Card Defensive for the user
                    _videocard_defensive, created = VideoCardDefensive.objects.update_or_create(
                        user_id=user_phone,
                        game=game,
                        defaults={'metrics': videocard_defensive}
                    )

                    if created:
                        print(f"Created Video Card Defensive for player {player_id} (phone: {user_phone}).")
                    else:
                        print(f"Updated Video Card Defensive for player {player_id} (phone: {user_phone}).")

                    # Create or update the Video Card Distributions for the user
                    _videocard_distributions, created = VideoCardDistributions.objects.update_or_create(
                        user_id=user_phone,
                        game=game,
                        defaults={'metrics': videocard_distributions}
                    )

                    if created:
                        print(f"Created Video Card Distributions for player {player_id} (phone: {user_phone}).")
                    else:
                        print(f"Updated Video Card Distributions for player {player_id} (phone: {user_phone}).")

                    user_ids.append(user_phone)
                    
            card_names = ['AttackingSkills', 'VideocardDefensive', 'VideocardDistribution']
            # send silent notification
            print(f"Sending silent notification for users: {user_ids} with card names: {card_names}")
            send_silent_notification(user_ids, card_names, game_created)
            
            # team video stats
            calculate_team_video_stats(instance)
            # calculate game meta data json
            generate_game_meta_data_json(instance, game)
        except Exception as e:
            print(f"Error processing video data file: {e}")
    
    else:
        print("Game Video Data file is already processed.")
        
        
# process daily wellness questionnaire
@receiver(post_save, sender=DailyWellnessUserResponse, weak=False)
def process_daily_wellness_user_responses(sender, instance, created, **kwargs):
    print("Signal triggered: DailyWellness User Response")
    
    try:
        responses_count = len(instance.response) if instance.response else 0
        # number of questions(7) can be made dynamic
        if responses_count > 0 and responses_count < 7:
            # schedule notification in `Notification server`
            # get the latest, if less than for 30 minutes
            # schedule notification to inform user
            # here just skip it
            print("but responses count is: ", responses_count)
        else:
            # Retrieve the StatusCardMetrics instance for the user
            new_metrics = calculate_wellness_metrics(instance)  # Get the new metrics
            # Get today's date in the configured timezone
            today = timezone.localdate()

            # Update or create a single entry per user per day
            status_card_metrics, created = StatusCardMetrics.objects.update_or_create(
                user=instance.user,
                created_on__date=today,  # Ensure it matches today's date
                defaults={'metrics': new_metrics}
            )
            print(f"Calculated Status Card Metrics for the user (phone: {instance.user}): {new_metrics}.")

            if created:
                print(f"Created Status Card Metrics for the user (phone: {instance.user}).")
            else:
                print(f"Updated Status Card Metrics for the user (phone: {instance.user}).")

            # send silent notification
            print(f"Sending StatusCard silent notification for user: {instance.user.phone_no}")
            send_silent_notification([instance.user.phone_no], ['StatusCard'], False)
            
    except Exception as e:
            print(f"Error processing daily wellness user responses: {e}")
            
            
# process rpe questionnaire
@receiver(post_save, sender=RPEUserResponse, weak=False)
def process_daily_wellness_user_responses(sender, instance, created, **kwargs):
    print("Signal triggered: RPE User Response")
    
    try:
        responses_count = len(instance.response) if instance.response else 0
        # number of questions(7) can be made dynamic
        if responses_count < 4:
            # changed to 4, since TT & MS have 5 and PT has 4
            # now individual set of questions will be asked based on Game/Training completed.
            # schedule notification in `Notification server`
            # get the latest, if less than for 30 minutes
            # schedule notification to inform user
            # here just skip it
            print("but responses count is: ", responses_count)
        else:
            # Get the latest status card metrics for the user
            status_card_metrics = (
                StatusCardMetrics.objects.filter(user=instance.user)
                .order_by('-created_on')  # Order by the most recent creation date
                .first()  # Get the latest entry
            )
            if status_card_metrics is None:
                # No status card exists, initialize the overall wellness value
                overall_wellness = 0
            else:
                overall_wellness = float(status_card_metrics.metrics.get('Overall Wellness', 0))

            # calculate RPE metrics
            new_metrics = calculate_physical_readiness_metrics(instance, overall_wellness)  # Get the new metrics
            
            # Get today's date in the configured timezone
            today = timezone.localdate()

            # Update or create a single entry per user per day
            rpe_metrics, created = RPEMetrics.objects.update_or_create(
                user=instance.user,
                created_on__date=today,  # Ensure it matches today's date
                defaults={'metrics': new_metrics}
            )
            print(f"Calculated RPE Metrics for the user (phone: {instance.user}): {new_metrics}.")

            if created:
                print(f"Created RPE Metrics for the user (phone: {instance.user}).")
            else:
                print(f"Updated RPE Metrics for the user (phone: {instance.user}).")

            # send silent notification
            print(f"Sending RPE silent notification for user: {instance.user.phone_no}")
            send_silent_notification([instance.user.phone_no], ['RPEMetrics'], False)
    except Exception as e:
            print(f"Error processing RPE user responses: {e}")