from django.db.models.signals import post_save
from django.dispatch import receiver
import pandas as pd

from .models import * 

from .utils import *

from datetime import date

def calculate_age(dob):
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# auto create entrypoint
@receiver(post_save, sender=WajoUser)
def create_onboarding_entryflow(sender, instance, created, **kwargs):
    print("Signal triggered: Onboard Entrypoint Creator")
    if created:
        OnboardingStep.objects.create(user=instance)


# we have JSON field as Response which stores partial or all 8 
# if partial for long time then schedule notification
# if all 8 are present then calculate metrics
# remove PainLocation, so now count is 7
@receiver(post_save, sender=DailyWellnessUserResponse, weak=False)
def process_daily_wellness_responses(sender, instance, created, **kwargs):
    print("Signal triggered: DailyWellness User Response")
    responses_count = len(instance.response) if instance.response else 0
    # number of questions(7) can be made dynamic
    if responses_count > 0 and responses_count < 7:
        # schedule notification in `Notification server`
        # get the latest, if less than for 30 minutes
        # schedule notification to inform user
        # here just skip it
        print("but responses count is: ", responses_count)
    else:
        # create/save metrics table
        calculate_and_store_status_card_metrics(instance.user)

# 14 questions
@receiver(post_save, sender=RPEUserResponse, weak=False)
def process_rpe_responses(sender, instance, created, **kwargs):
    print("Signal triggered: RPE User Response")
    responses_count = len(instance.response) if instance.response else 0
    # number of questions(14) can be made dynamic
    if responses_count > 0 and responses_count < 14:
        # schedule notification in `Notification server`
        # get the latest, if less than for 30 minutes
        # schedule notification to inform user
        # here just skip it
        print("but responses count is: ", responses_count)
    else:
        # create/save metrics table
        calculate_and_store_status_card_metrics(instance.user)



    

# match event data signal
@receiver(post_save, sender=MatchEventsDataFile, weak=False)
def process_file(sender, instance, created, **kwargs):
    print("Match Events Data File Signal is called.")

    if instance._type == 'BEPRO':
        stats_instance = instance
        gps_instance = MatchEventsDataFile.objects.filter(_type='GPS').order_by('-updated_on').first()
    elif instance._type == 'GPS':
        stats_instance = MatchEventsDataFile.objects.filter(_type='BEPRO').order_by('-updated_on').first()
        gps_instance = instance

    if stats_instance and gps_instance:
        stats_sheet = pd.read_excel(stats_instance.file, sheet_name='PlayerStats_137183')
        gps_sheet = pd.read_excel(gps_instance.file, sheet_name='Oliver GPS Metrcis')
        match_sheet = pd.read_excel(stats_instance.file, sheet_name='MatchDetails')
        
        player_mappings = PlayerIDMapping.objects.select_related('user').all().values(
                    'player_id', 
                    'player_position', 
                    'user__phone_no', 
                    'user__dob'
                )
        
        player_mapping_dict = {
            str(mapping['player_id']): {
                'phone_no': mapping['user__phone_no'],
                'position': mapping['player_position'],
                'dob': mapping['user__dob']
            }
            for mapping in player_mappings
        }
        
        print("player_mapping_dict: ", player_mapping_dict)
        
        player_ids = set(player_mapping_dict.keys())
        # print("player_ids: ", player_ids, player_mapping_dict.keys())

        # Convert player_id columns to strings for consistent comparison
        stats_sheet['player_id'] = stats_sheet['player_id'].astype(int).astype(str)
        gps_sheet['Player ID'] = gps_sheet['Player ID'].astype(int).astype(str)


        # Filter stats_sheet and gps_sheet once based on player_ids
        filtered_stats_sheet = stats_sheet[stats_sheet['player_id'].isin(player_ids)]
        filtered_gps_sheet = gps_sheet[gps_sheet['Player ID'].isin(player_ids)]
            
        # print("filtered_stats_sheet: ", filtered_stats_sheet)
        # print("filtered_gps_sheet: ", filtered_gps_sheet)

        for player_id, player_info in player_mapping_dict.items():
            user_phone = player_info['phone_no']
            player_position = player_info['position']
            player_dob = player_info['dob']

            stats_row = filtered_stats_sheet[filtered_stats_sheet['player_id'] == player_id]
            gps_row = filtered_gps_sheet[filtered_gps_sheet['Player ID'] == player_id]
            
            if stats_row.empty or gps_row.empty:
                print("Either stats data or gps data is not available.")
            else:
                # Calculate age based on DOB
                player_age = calculate_age(player_dob)
                
                # Extract data from rows
                stats_data = stats_row.iloc[0].to_dict()
                gps_data = gps_row.iloc[0].to_dict()

                # Calculate game statistics and performance metrics
                game_stats = calculate_game_stats(stats_data)
                performance_metrics = calculate_performance_metrics(stats_data)
                defensive_performance_metrics = calculate_defensive_performance_metrics(stats_data)
                offensive_performance_metrics = calculate_offensive_performance_metrics(stats_data)
                season_overview = calculate_season_overview_metrics(stats_data)

                # new formulas by freelancer
                attacking_skills = calculate_attacking_skills(stats_data, match_sheet)
                videocard_defensive = calculate_videocard_defensive(stats_data, match_sheet)
                videocard_distributions = calculate_videocard_distributions(stats_data, match_sheet)

                gps_athletic_skills = calculate_gps_athletic_skills(gps_row)
                gps_football_abilities = calculate_gps_football_abilities(gps_row)

                # Calculate pace and shooting scores
                pace_score = calculate_pace_score(
                    gps_row=gps_data,
                    player_position=player_position,
                    player_age=player_age
                )
                shooting_score = calculate_shooting_score(
                    gps_row=gps_data,
                    stats_row=stats_data,
                    player_position=player_position,
                    player_age=player_age
                )

                passing_score = calculate_passing_score(
                    gps_row=gps_data,
                    stats_row=stats_data,
                    player_position=player_position,
                    player_age=player_age
                )

                dribbling_score = calculate_dribbling_score(
                    gps_row=gps_data,
                    stats_row=stats_data,
                    player_position=player_position,
                    player_age=player_age
                )

                defending_score = calculate_defending_score(
                    gps_row=gps_data,
                    stats_row=stats_data,
                    player_position=player_position,
                    player_age=player_age
                )

                physicality_score = calculate_physicality_score(
                    gps_row=gps_data,
                    stats_row=stats_data,
                    player_position=player_position,
                    player_age=player_age
                )

                game_intelligence_score = calculate_game_intelligence_score(
                    gps_row=gps_data,
                    stats_row=stats_data,
                    player_position=player_position,
                    player_age=player_age
                )

                composure_score = calculate_composure_score(
                    gps_row=gps_data,
                    stats_row=stats_data,
                    player_position=player_position,
                    player_age=player_age
                )

                goal_keeping_score = calculate_goal_keeping_score(
                    gps_row=gps_data,
                    stats_row=stats_data,
                    player_position=player_position,
                    player_age=player_age
                )

                overall_score = calculate_overall_score(
                    pace_score,
                    shooting_score,
                    passing_score,
                    dribbling_score,
                    defending_score,
                    physicality_score,
                    game_intelligence_score,
                    composure_score,
                    goal_keeping_score,
                    player_position=player_position
                )
                # print(f"game_stats for user {user_phone}: ", game_stats)
                # print(f"performance_metrics for user {user_phone}: ", performance_metrics)
                # print(f"defensive_performance_metrics for user {user_phone}: ", defensive_performance_metrics)
                # print(f"offensive_performance_metrics for user {user_phone}: ", offensive_performance_metrics)
                # print(f"season_overview for user {user_phone}: ", season_overview)
                print("*"*100)
                # print(f"pace_score for user {user_phone}: ", pace_score)
                # print(f"shooting_score for user {user_phone}: ", shooting_score)
                # print(f"passing_score for user {user_phone}: ", passing_score)
                # print(f"passing_score for user {user_phone}: ", passing_score)
                # print(f"dribbling_score for user {user_phone}: ", dribbling_score)
                # print(f"defending_score for user {user_phone}: ", defending_score)
                # print(f"physicality_score for user {user_phone}: ", physicality_score)
                # print(f"game_intelligence_score for user {user_phone}: ", game_intelligence_score)
                # print(f"composure_score for user {user_phone}: ", composure_score)
                # print(f"goal_keeping_score for user {user_phone}: ", goal_keeping_score)
                # print(f"overall_score for user {user_phone}: ", overall_score)

                # Create or update the wajo performance index for the user
                WajoPerformanceIndex.objects.update_or_create(
                    user_id=user_phone,
                    defaults={'metrics': {
                        "pace_score": pace_score,
                        "shooting_score": shooting_score,
                        "passing_score": passing_score,
                        "dribbling_score": dribbling_score,
                        "defending_score": defending_score,
                        "physicality_score": physicality_score,
                        "game_intelligence_score": game_intelligence_score,
                        "composure_score": composure_score,
                        "goal_keeping_score": goal_keeping_score,
                        "overall_score": overall_score
                    }}
                )
        
                # Create or update the game stats for the user
                GameStats.objects.update_or_create(
                    user_id=user_phone,
                    defaults={'metrics': game_stats}
                )

                # # Create or update the Season Overiview Metrics for the user
                SeasonOverviewMetrics.objects.update_or_create(
                    user_id=user_phone,
                    defaults={'metrics': season_overview}
                )
                
                # # Create or update the performance metrics for the user
                PerformanceMetrics.objects.update_or_create(
                    user_id=user_phone,
                    defaults={'metrics': performance_metrics}
                )

                # # Create or update the Defensive performance metrics for the user
                DefensivePerformanceMetrics.objects.update_or_create(
                    user_id=user_phone,
                    defaults={'metrics': defensive_performance_metrics}
                )

                # # Create or update the Offensive performance metrics for the user
                OffensivePerformanceMetrics.objects.update_or_create(
                    user_id=user_phone,
                    defaults={'metrics': offensive_performance_metrics}
                )

                # # Create or update the Attacking Skills for the user
                AttackingSkills.objects.update_or_create(
                    user_id=user_phone,
                    defaults={'metrics': attacking_skills}
                )

                # # Create or update the VideoCard Defensive Skills for the user
                VideoCardDefensive.objects.update_or_create(
                    user_id=user_phone,
                    defaults={'metrics': videocard_defensive}
                )

                # # Create or update the VideoCard Defensive Skills for the user
                VideoCardDistributions.objects.update_or_create(
                    user_id=user_phone,
                    defaults={'metrics': videocard_distributions}
                )

                # Create or update the GPS Athletic skills for the user
                GPSAthleticSkills.objects.update_or_create(
                    user_id=user_phone,
                    defaults={'metrics': gps_athletic_skills}
                )

                # Create or update the GPS Football abilities for the user
                GPSFootballAbilities.objects.update_or_create(
                    user_id=user_phone,
                    defaults={'metrics': gps_football_abilities}
                )
    else:
        print("Either Stats or GPS file is not available.")

