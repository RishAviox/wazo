from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from uuid import uuid4
import pandas as pd

from match_data.models.generic import ExcelFile
from match_data.models.bepro import *


@receiver(post_save, sender=ExcelFile)
def process_excel_file(sender, instance, created, **kwargs):
    if created:
        try:
            with transaction.atomic():                
                # Read Excel File
                df = pd.read_excel(instance.file, sheet_name=None)
                
                for sheet_name, data in df.items():
                    if sheet_name == "LeagueDetails":
                        details = []
                        for _, row in data.iterrows():
                            details.append(
                                BeproLeagueDetail(
                                    league_id=row['id'] if pd.notna(row['id']) else None,
                                    name=row['name'] if pd.notna(row['name']) else None,
                                    name_en=row['name_en'] if pd.notna(row['name_en']) else None,
                                    iso_country_code=row['iso_country_code'] if pd.notna(row['iso_country_code']) else None,
                                    age_limit=row['age_limit'] if pd.notna(row['age_limit']) else None,
                                    division=row['division'] if pd.notna(row['division']) else None,
                                    season_ids=row['season_ids'] if pd.notna(row['season_ids']) else None
                                )
                            )
                        BeproLeagueDetail.objects.bulk_create(details)
                    elif sheet_name == "Seasons":
                        details = []
                        for _, row in data.iterrows():
                            details.append(
                                BeproSeason(
                                    league_id=row['id'] if pd.notna(row['id']) else None,
                                    name=row['name'] if pd.notna(row['name']) else None,
                                    name_en=row['name_en'] if pd.notna(row['name_en']) else None,
                                    iso_country_code=row['iso_country_code'] if pd.notna(row['iso_country_code']) else None,
                                    age_limit=row['age_limit'] if pd.notna(row['age_limit']) else None,
                                    division=row['division'] if pd.notna(row['division']) else None,
                                    season_ids=row['season_ids'] if pd.notna(row['season_ids']) else None
                                )
                            )
                        BeproSeason.objects.bulk_create(details)
                    elif sheet_name == "MatchDetails":
                        details = []
                        for _, row in data.iterrows():
                            details.append(
                                BeproMatchData(
                                    match_id=row['id'] if pd.notna(row['id']) else None,
                                    season_id=row['season.id'] if pd.notna(row['season.id']) else None,
                                    season_name=row['season.name'] if pd.notna(row['season.name']) else None,
                                    round_name=row['round.name'] if pd.notna(row['round.name']) else None,
                                    home_team_id=row['home_team.id'] if pd.notna(row['home_team.id']) else None,
                                    home_team_name=row['home_team.name'] if pd.notna(row['home_team.name']) else None,
                                    home_team_name_en=row['home_team.name_en'] if pd.notna(row['home_team.name_en']) else None,
                                    away_team_id=row['away_team.id'] if pd.notna(row['away_team.id']) else None,
                                    away_team_name=row['away_team.name'] if pd.notna(row['away_team.name']) else None,
                                    start_time=row['start_time'] if pd.notna(row['start_time']) else None,
                                    venue_display_name=row['venue.display_name'] if pd.notna(row['venue.display_name']) else None,
                                    full_time=row['full_time'] if pd.notna(row['full_time']) else None,
                                    extra_full_time=row['extra_full_time'] if pd.notna(row['extra_full_time']) else None,
                                    home_team_score=row['detail_match_result.home_team_score'] if pd.notna(row['detail_match_result.home_team_score']) else None,
                                    away_team_score=row['detail_match_result.away_team_score'] if pd.notna(row['detail_match_result.away_team_score']) else None,
                                    is_analysis_finished=row['is_analysis_finished'] if pd.notna(row['is_analysis_finished']) else None,
                                    live_analysing=row['live_analysing'] if pd.notna(row['live_analysing']) else None,
                                    venue_ground_width=row['venue.ground_width'] if pd.notna(row['venue.ground_width']) else None,
                                    venue_ground_height=row['venue.ground_height'] if pd.notna(row['venue.ground_height']) else None
                                )
                            )
                        BeproMatchData.objects.bulk_create(details)
                    elif sheet_name == f"MatchDetails_{instance.match_id}":
                        details = []
                        match_data = BeproMatchData.objects.get(match_id=instance.match_id)
                        for _, row in data.iterrows():
                            details.append(
                                BeproMatchDetail(
                                    record_id=row['id'] if pd.notna(row['id']) else None,
                                    match_id=match_data,
                                    team_id=row['team_id'] if pd.notna(row['team_id']) else None,
                                    player_id=row['player_id'] if pd.notna(row['player_id']) else None,
                                    event_period=row['event_period'] if pd.notna(row['event_period']) else None,
                                    event_time=row['event_time'] if pd.notna(row['event_time']) else None,
                                    x=round(float(row['x']), 8) if pd.notna(row['x']) else None,
                                    y=round(float(row['y']), 8) if pd.notna(row['y']) else None,
                                    ball_position_x=row['ball_position.x'] if pd.notna(row['ball_position.x']) else None,
                                    ball_position_y=row['ball_position.y'] if pd.notna(row['ball_position.y']) else None,
                                    relative_event_id=row['relative_event.id'] if pd.notna(row['relative_event.id']) else None,
                                    relative_event_x=row['relative_event.x'] if pd.notna(row['relative_event.x']) else None,
                                    relative_event_y=row['relative_event.y'] if pd.notna(row['relative_event.y']) else None,
                                    xg=row['xg'] if pd.notna(row['xg']) else None,
                                    event_type=row['eventType'] if pd.notna(row['eventType']) else None,
                                    outcome=row['outcome'] if pd.notna(row['outcome']) else None,
                                    sub_event_type=row['subEventType'] if pd.notna(row['subEventType']) else None,
                                    cross=row['cross'] if pd.notna(row['cross']) else None,
                                    key_pass=row['keyPass'] if pd.notna(row['keyPass']) else None,
                                    assist=row['assist'] if pd.notna(row['assist']) else None,
                                    body_part=row['bodyPart'] if pd.notna(row['bodyPart']) else None
                                )
                            )
                        BeproMatchDetail.objects.bulk_create(details)
                    elif sheet_name == f"FormationData_{instance.match_id}":
                        details = []
                        for _, row in data.iterrows():
                            details.append(
                                BeproFormationData(
                                    team_id=row['team_id'] if pd.notna(row['team_id']) else None,
                                    event_period=row['event_period'] if pd.notna(row['event_period']) else None,
                                    changed_time=row['changed_time'] if pd.notna(row['changed_time']) else None,
                                    player_id=row['player_id'] if pd.notna(row['player_id']) else None,
                                    x=row['x'] if pd.notna(row['x']) else None,
                                    y=row['y'] if pd.notna(row['y']) else None
                                )
                            )
                        BeproFormationData.objects.bulk_create(details)
                    # elif sheet_name == f"SequenceData_{instance.match_id}":
                    #     details = []
                    #     for _, row in data.iterrows():
                    #         details.append(
                    #             BeproSequenceData(
                    #                 id=uuid4(),
                    #                 team_id=int(row['team_id']) if pd.notna(row['team_id']) else None,
                    #                 event_period=row['event_period'] if pd.notna(row['event_period']) else None,
                    #                 start_time=int(row['start_time']) if pd.notna(row['start_time']) else None,
                    #                 end_time=int(row['end_time']) if pd.notna(row['end_time']) else None,
                    #                 event_ids=row['event_ids'] if pd.notna(row['event_ids']) else None
                    #             )
                    #         )
                    #     BeproSequenceData.objects.bulk_create(details)
                    elif sheet_name == f"PhysicalEventData_{instance.match_id}":
                        details = []
                        match_data = BeproMatchData.objects.get(match_id=instance.match_id)
                        for _, row in data.iterrows():
                            details.append(
                                BeproPhysicalEventData(
                                    match_id=match_data,
                                    team_id=row['team_id'] if pd.notna(row['team_id']) else None,
                                    player_id=row['player_id'] if pd.notna(row['player_id']) else None,
                                    event_period=row['event_period'] if pd.notna(row['event_period']) else None,
                                    event_time=row['event_time'] if pd.notna(row['event_time']) else None,
                                    x=row['x'] if pd.notna(row['x']) else None,
                                    y=row['y'] if pd.notna(row['y']) else None,
                                    ball_position_x=row['ball_position.x'] if pd.notna(row['ball_position.x']) else None,
                                    ball_position_y=row['ball_position.y'] if pd.notna(row['ball_position.y']) else None,
                                    relative_event_id=row['relative_event.id'] if pd.notna(row['relative_event.id']) else None,
                                    relative_event_x=row['relative_event.x'] if pd.notna(row['relative_event.x']) else None,
                                    relative_event_y=row['relative_event.y'] if pd.notna(row['relative_event.y']) else None,
                                    xg=row['xg'] if pd.notna(row['xg']) else None,
                                    event_type=row['eventType'] if pd.notna(row['eventType']) else None,
                                    outcome=row['outcome'] if pd.notna(row['outcome']) else None,
                                    sub_event_type=row['subEventType'] if pd.notna(row['subEventType']) else None,
                                    cross=row['cross'] if pd.notna(row['cross']) else None,
                                    key_pass=row['keyPass'] if pd.notna(row['keyPass']) else None,
                                    assist=row['assist'] if pd.notna(row['assist']) else None,
                                    body_part=row['bodyPart'] if pd.notna(row['bodyPart']) else None
                                )
                            )
                        BeproPhysicalEventData.objects.bulk_create(details)
                    elif sheet_name == f"LineUp_{instance.match_id}":
                        details = []
                        for _, row in data.iterrows():
                            details.append(
                                BeproLineUp(
                                    record_id=row['id'] if pd.notna(row['id']) else None,
                                    team_id=row['team_id'] if pd.notna(row['team_id']) else None,
                                    player_id=row['player_id'] if pd.notna(row['player_id']) else None,
                                    position_name=row['position_name'] if pd.notna(row['position_name']) else None,
                                    back_number=row['back_number'] if pd.notna(row['back_number']) else None,
                                    player_name=row['player_name'] if pd.notna(row['player_name']) else None,
                                    player_last_name=row['player_last_name'] if pd.notna(row['player_last_name']) else None,
                                    is_starting_lineup=row['is_starting_lineup'] if pd.notna(row['is_starting_lineup']) else None,
                                    position_x=row['position.x'] if pd.notna(row['position.x']) else None,
                                    position_y=row['position.y'] if pd.notna(row['position.y']) else None
                                )
                            )
                        BeproLineUp.objects.bulk_create(details)
                    elif sheet_name == f"PlayerStats_{instance.match_id}":
                        details = []
                        for _, row in data.iterrows():
                            details.append(
                                BeproPlayerStat(
                                    team_id=row['team_id'] if pd.notna(row['team_id']) else None,
                                    player_id=row['player_id'] if pd.notna(row['player_id']) else None,
                                    aerial_clearance=row['aerial_clearance'] if pd.notna(row['aerial_clearance']) else None,
                                    aerial_clearance_failed=row['aerial_clearance_failed'] if pd.notna(row['aerial_clearance_failed']) else None,
                                    aerial_clearance_succeeded=row['aerial_clearance_succeeded'] if pd.notna(row['aerial_clearance_succeeded']) else None,
                                    aerial_duel=row['aerial_duel'] if pd.notna(row['aerial_duel']) else None,
                                    aerial_duel_failed=row['aerial_duel_failed'] if pd.notna(row['aerial_duel_failed']) else None,
                                    aerial_duel_succeeded=row['aerial_duel_succeeded'] if pd.notna(row['aerial_duel_succeeded']) else None,
                                    assist=row['assist'] if pd.notna(row['assist']) else None,
                                    backward_pass=row['backward_pass'] if pd.notna(row['backward_pass']) else None,
                                    backward_pass_succeeded=row['backward_pass_succeeded'] if pd.notna(row['backward_pass_succeeded']) else None,
                                    block=row['block'] if pd.notna(row['block']) else None,
                                    clearance=row['clearance'] if pd.notna(row['clearance']) else None,
                                    control_under_pressure=row['control_under_pressure'] if pd.notna(row['control_under_pressure']) else None,
                                    corner_kick=row['corner_kick'] if pd.notna(row['corner_kick']) else None,
                                    cross=row['cross'] if pd.notna(row['cross']) else None,
                                    cross_succeeded=row['cross_succeeded'] if pd.notna(row['cross_succeeded']) else None,
                                    defensive_area_pass=row['defensive_area_pass'] if pd.notna(row['defensive_area_pass']) else None,
                                    defensive_area_pass_succeeded=row['defensive_area_pass_succeeded'] if pd.notna(row['defensive_area_pass_succeeded']) else None,
                                    defensive_line_support=row['defensive_line_support'] if pd.notna(row['defensive_line_support']) else None,
                                    defensive_line_support_failed=row['defensive_line_support_failed'] if pd.notna(row['defensive_line_support_failed']) else None,
                                    defensive_line_support_succeeded=row['defensive_line_support_succeeded'] if pd.notna(row['defensive_line_support_succeeded']) else None,
                                    final_third_area_pass=row['final_third_area_pass'] if pd.notna(row['final_third_area_pass']) else None,
                                    final_third_area_pass_succeeded=row['final_third_area_pass_succeeded'] if pd.notna(row['final_third_area_pass_succeeded']) else None,
                                    forward_pass=row['forward_pass'] if pd.notna(row['forward_pass']) else None,
                                    forward_pass_succeeded=row['forward_pass_succeeded'] if pd.notna(row['forward_pass_succeeded']) else None,
                                    foul=row['foul'] if pd.notna(row['foul']) else None,
                                    foul_won=row['foul_won'] if pd.notna(row['foul_won']) else None,
                                    free_kick=row['free_kick'] if pd.notna(row['free_kick']) else None,
                                    goal_conceded=row['goal_conceded'] if pd.notna(row['goal_conceded']) else None,
                                    goal_kick=row['goal_kick'] if pd.notna(row['goal_kick']) else None,
                                    goal_kick_succeeded=row['goal_kick_succeeded'] if pd.notna(row['goal_kick_succeeded']) else None,
                                    ground_duel=row['ground_duel'] if pd.notna(row['ground_duel']) else None,
                                    ground_duel_failed=row['ground_duel_failed'] if pd.notna(row['ground_duel_failed']) else None,
                                    ground_duel_succeeded=row['ground_duel_succeeded'] if pd.notna(row['ground_duel_succeeded']) else None,
                                    intercept=row['intercept'] if pd.notna(row['intercept']) else None,
                                    intervention=row['intervention'] if pd.notna(row['intervention']) else None,
                                    key_pass=row['key_pass'] if pd.notna(row['key_pass']) else None,
                                    long_pass=row['long_pass'] if pd.notna(row['long_pass']) else None,
                                    long_pass_succeeded=row['long_pass_succeeded'] if pd.notna(row['long_pass_succeeded']) else None,
                                    loose_ball_duel=row['loose_ball_duel'] if pd.notna(row['loose_ball_duel']) else None,
                                    loose_ball_duel_failed=row['loose_ball_duel_failed'] if pd.notna(row['loose_ball_duel_failed']) else None,
                                    loose_ball_duel_succeeded=row['loose_ball_duel_succeeded'] if pd.notna(row['loose_ball_duel_succeeded']) else None,
                                    medium_range_pass=row['medium_range_pass'] if pd.notna(row['medium_range_pass']) else None,
                                    medium_range_pass_succeeded=row['medium_range_pass_succeeded'] if pd.notna(row['medium_range_pass_succeeded']) else None,
                                    middle_area_pass=row['middle_area_pass'] if pd.notna(row['middle_area_pass']) else None,
                                    middle_area_pass_succeeded=row['middle_area_pass_succeeded'] if pd.notna(row['middle_area_pass_succeeded']) else None,
                                    mistake=row['mistake'] if pd.notna(row['mistake']) else None,
                                    offside=row['offside'] if pd.notna(row['offside']) else None,
                                    own_goal=row['own_goal'] if pd.notna(row['own_goal']) else None,
                                    _pass=row['pass'] if pd.notna(row['pass']) else None,
                                    pass_failed=row['pass_failed'] if pd.notna(row['pass_failed']) else None,
                                    pass_succeeded=row['pass_succeeded'] if pd.notna(row['pass_succeeded']) else None,
                                    penalty_kick=row['penalty_kick'] if pd.notna(row['penalty_kick']) else None,
                                    play_time=row['play_time'] if pd.notna(row['play_time']) else None,
                                    rating=row['rating'] if pd.notna(row['rating']) else None,
                                    recovery=row['recovery'] if pd.notna(row['recovery']) else None,
                                    red_card=row['red_card'] if pd.notna(row['red_card']) else None,
                                    save_by_catching=row['save_by_catching'] if pd.notna(row['save_by_catching']) else None,
                                    save_by_punching=row['save_by_punching'] if pd.notna(row['save_by_punching']) else None,
                                    short_pass=row['short_pass'] if pd.notna(row['short_pass']) else None,
                                    short_pass_succeeded=row['short_pass_succeeded'] if pd.notna(row['short_pass_succeeded']) else None,
                                    shot_blocked=row['shot_blocked'] if pd.notna(row['shot_blocked']) else None,
                                    shot_in_PA=row['shot_in_PA'] if pd.notna(row['shot_in_PA']) else None,
                                    shot_off_target=row['shot_off_target'] if pd.notna(row['shot_off_target']) else None,
                                    shot_on_target=row['shot_on_target'] if pd.notna(row['shot_on_target']) else None,
                                    shot_outside_of_PA=row['shot_outside_of_PA'] if pd.notna(row['shot_outside_of_PA']) else None,
                                    sideways_pass=row['sideways_pass'] if pd.notna(row['sideways_pass']) else None,
                                    sideways_pass_succeeded=row['sideways_pass_succeeded'] if pd.notna(row['sideways_pass_succeeded']) else None,
                                    tackle=row['tackle'] if pd.notna(row['tackle']) else None,
                                    tackle_succeeded=row['tackle_succeeded'] if pd.notna(row['tackle_succeeded']) else None,
                                    take_on=row['take_on'] if pd.notna(row['take_on']) else None,
                                    take_on_succeeded=row['take_on_succeeded'] if pd.notna(row['take_on_succeeded']) else None,
                                    throw_in=row['throw_in'] if pd.notna(row['throw_in']) else None,
                                    total_shot=row['total_shot'] if pd.notna(row['total_shot']) else None,
                                    yellow_card=row['yellow_card'] if pd.notna(row['yellow_card']) else None
                                )
                            )
                        BeproPlayerStat.objects.bulk_create(details)
                    elif sheet_name == f"PlayerStatsExtended_{instance.match_id}":
                        details = []
                        match_data = BeproMatchData.objects.get(match_id=instance.match_id)
                        for _, row in data.iterrows():
                            details.append(
                                BeproPlayerStatsExtended(
                                    match_id=match_data,
                                    season_id=row['season.id'] if pd.notna(row['season.id']) else None,
                                    season_name=row['season.name'] if pd.notna(row['season.name']) else None,
                                    round_name=row['round_name'] if pd.notna(row['round_name']) else None,
                                    home_team_id=row['home_team.id'] if pd.notna(row['home_team.id']) else None,
                                    home_team_name=row['home_team.name'] if pd.notna(row['home_team.name']) else None,
                                    home_team_name_en=row['home_team.name_en'] if pd.notna(row['home_team.name_en']) else None,
                                    away_team_id=row['away_team.id'] if pd.notna(row['away_team.id']) else None,
                                    away_team_name=row['away_team.name'] if pd.notna(row['away_team.name']) else None,
                                    away_team_name_en=row['away_team.name_en'] if pd.notna(row['away_team.name_en']) else None,
                                    start_time=row['start_time'] if pd.notna(row['start_time']) else None,
                                    venue_display_name=row['venue.display_name'] if pd.notna(row['venue.display_name']) else None,
                                    full_time=row['full_time'] if pd.notna(row['full_time']) else None,
                                    extra_full_time=row['extra_full_time'] if pd.notna(row['extra_full_time']) else None,
                                    home_team_score=row['detail_match_result.home_team_score'] if pd.notna(row['detail_match_result.home_team_score']) else None,
                                    away_team_score=row['detail_match_result.away_team_score'] if pd.notna(row['detail_match_result.away_team_score']) else None,
                                    is_analysis_finsihed=row['is_analysis_finished'] if pd.notna(row['is_analysis_finished']) else None,
                                    live_analysing=row['live_analysing'] if pd.notna(row['live_analysing']) else None,
                                    venue_ground_width=row['venue.ground_width'] if pd.notna(row['venue.ground_width']) else None,
                                    venue_ground_height=row['venue.ground_height'] if pd.notna(row['venue.ground_height']) else None
                                )
                            )
                        BeproPlayerStatsExtended.objects.bulk_create(details)
                    elif sheet_name == f"Players_{instance.match_id}" or sheet_name == f"Players_{instance.match_id}_2":
                        details = []
                        for _, row in data.iterrows():
                            details.append(
                                BeproPlayer(
                                    record_id=row['id'] if pd.notna(row['id']) else None,
                                    main_position=row['main_position'] if pd.notna(row['main_position']) else None,
                                    back_number=row['back_number'] if pd.notna(row['back_number']) else None,
                                    player_name=row['player_name'] if pd.notna(row['player_name']) else None,
                                    player_last_name=row['player_last_name'] if pd.notna(row['player_last_name']) else None,
                                    player_name_en=row['player_name_en'] if pd.notna(row['player_name_en']) else None,
                                    player_last_name_en=row['player_last_name_en'] if pd.notna(row['player_last_name_en']) else None,
                                    player_role=row['player_role'] if pd.notna(row['player_role']) else None
                                )
                            )
                        BeproPlayer.objects.bulk_create(details)
                    elif sheet_name == f"TeamStats_{instance.match_id}":
                        details = []
                        match_data = BeproMatchData.objects.get(match_id=instance.match_id)
                        for _, row in data.iterrows():
                            details.append(
                                BeproTeamStat(
                                    match=match_data,
                                    team_id=row['team_id'] if pd.notna(row['team_id']) else None,
                                    aerial_clearance=row['aerial_clearance'] if pd.notna(row['aerial_clearance']) else None,
                                    aerial_clearance_failed=row['aerial_clearance_failed'] if pd.notna(row['aerial_clearance_failed']) else None,
                                    aerial_clearance_succeeded=row['aerial_clearance_succeeded'] if pd.notna(row['aerial_clearance_succeeded']) else None,
                                    aerial_duel=row['aerial_duel'] if pd.notna(row['aerial_duel']) else None,
                                    aerial_duel_failed=row['aerial_duel_failed'] if pd.notna(row['aerial_duel_failed']) else None,
                                    aerial_duel_succeeded=row['aerial_duel_succeeded'] if pd.notna(row['aerial_duel_succeeded']) else None,
                                    assist=row['assist'] if pd.notna(row['assist']) else None,
                                    backward_pass=row['backward_pass'] if pd.notna(row['backward_pass']) else None,
                                    backward_pass_succeeded=row['backward_pass_succeeded'] if pd.notna(row['backward_pass_succeeded']) else None,
                                    block=row['block'] if pd.notna(row['block']) else None,
                                    clearance=row['clearance'] if pd.notna(row['clearance']) else None,
                                    control_under_pressure=row['control_under_pressure'] if pd.notna(row['control_under_pressure']) else None,
                                    corner_kick=row['corner_kick'] if pd.notna(row['corner_kick']) else None,
                                    cross=row['cross'] if pd.notna(row['cross']) else None,
                                    cross_succeeded=row['cross_succeeded'] if pd.notna(row['cross_succeeded']) else None,
                                    defensive_area_pass=row['defensive_area_pass'] if pd.notna(row['defensive_area_pass']) else None,
                                    defensive_area_pass_succeeded=row['defensive_area_pass_succeeded'] if pd.notna(row['defensive_area_pass_succeeded']) else None,
                                    defensive_line_support=row['defensive_line_support'] if pd.notna(row['defensive_line_support']) else None,
                                    defensive_line_support_failed=row['defensive_line_support_failed'] if pd.notna(row['defensive_line_support_failed']) else None,
                                    defensive_line_support_succeeded=row['defensive_line_support_succeeded'] if pd.notna(row['defensive_line_support_succeeded']) else None,
                                    final_third_area_pass=row['final_third_area_pass'] if pd.notna(row['final_third_area_pass']) else None,
                                    final_third_area_pass_succeeded=row['final_third_area_pass_succeeded'] if pd.notna(row['final_third_area_pass_succeeded']) else None,
                                    forward_pass=row['forward_pass'] if pd.notna(row['forward_pass']) else None,
                                    forward_pass_succeeded=row['forward_pass_succeeded'] if pd.notna(row['forward_pass_succeeded']) else None,
                                    foul=row['foul'] if pd.notna(row['foul']) else None,
                                    foul_won=row['foul_won'] if pd.notna(row['foul_won']) else None,
                                    free_kick=row['free_kick'] if pd.notna(row['free_kick']) else None,
                                    goal=row['goal'] if pd.notna(row['goal']) else None,
                                    goal_conceded=row['goal_conceded'] if pd.notna(row['goal_conceded']) else None,
                                    goal_kick=row['goal_kick'] if pd.notna(row['goal_kick']) else None,
                                    goal_kick_succeeded=row['goal_kick_succeeded'] if pd.notna(row['goal_kick_succeeded']) else None,
                                    ground_duel=row['ground_duel'] if pd.notna(row['ground_duel']) else None,
                                    ground_duel_failed=row['ground_duel_failed'] if pd.notna(row['ground_duel_failed']) else None,
                                    ground_duel_succeeded=row['ground_duel_succeeded'] if pd.notna(row['ground_duel_succeeded']) else None,
                                    intercept=row['intercept'] if pd.notna(row['intercept']) else None,
                                    intervention=row['intervention'] if pd.notna(row['intervention']) else None,
                                    key_pass=row['key_pass'] if pd.notna(row['key_pass']) else None,
                                    long_pass=row['long_pass'] if pd.notna(row['long_pass']) else None,
                                    long_pass_succeeded=row['long_pass_succeeded'] if pd.notna(row['long_pass_succeeded']) else None,
                                    loose_ball_duel=row['loose_ball_duel'] if pd.notna(row['loose_ball_duel']) else None,
                                    loose_ball_duel_failed=row['loose_ball_duel_failed'] if pd.notna(row['loose_ball_duel_failed']) else None,
                                    loose_ball_duel_succeeded=row['loose_ball_duel_succeeded'] if pd.notna(row['loose_ball_duel_succeeded']) else None,
                                    medium_range_pass=row['medium_range_pass'] if pd.notna(row['medium_range_pass']) else None,
                                    medium_range_pass_succeeded=row['medium_range_pass_succeeded'] if pd.notna(row['medium_range_pass_succeeded']) else None,
                                    middle_area_pass=row['middle_area_pass'] if pd.notna(row['middle_area_pass']) else None,
                                    middle_area_pass_succeeded=row['middle_area_pass_succeeded'] if pd.notna(row['middle_area_pass_succeeded']) else None,
                                    mistake=row['mistake'] if pd.notna(row['mistake']) else None,
                                    offside=row['offside'] if pd.notna(row['offside']) else None,
                                    own_goal=row['own_goal'] if pd.notna(row['own_goal']) else None,
                                    passed=row['pass'] if pd.notna(row['pass']) else None,
                                    pass_failed=row['pass_failed'] if pd.notna(row['pass_failed']) else None,
                                    pass_succeeded=row['pass_succeeded'] if pd.notna(row['pass_succeeded']) else None,
                                    penalty_kick=row['penalty_kick'] if pd.notna(row['penalty_kick']) else None,
                                    possession=row['possession'] if pd.notna(row['possession']) else None,
                                    recovery=row['recovery'] if pd.notna(row['recovery']) else None,
                                    red_card=row['red_card'] if pd.notna(row['red_card']) else None,
                                    save_by_catching=row['save_by_catching'] if pd.notna(row['save_by_catching']) else None,
                                    save_by_punching=row['save_by_punching'] if pd.notna(row['save_by_punching']) else None,
                                    short_pass=row['short_pass'] if pd.notna(row['short_pass']) else None,
                                    short_pass_succeeded=row['short_pass_succeeded'] if pd.notna(row['short_pass_succeeded']) else None,
                                    shot_blocked=row['shot_blocked'] if pd.notna(row['shot_blocked']) else None,
                                    shot_in_PA=row['shot_in_PA'] if pd.notna(row['shot_in_PA']) else None,
                                    shot_off_target=row['shot_off_target'] if pd.notna(row['shot_off_target']) else None,
                                    shot_on_target=row['shot_on_target'] if pd.notna(row['shot_on_target']) else None,
                                    shot_outside_of_PA=row['shot_outside_of_PA'] if pd.notna(row['shot_outside_of_PA']) else None,
                                    sideways_pass=row['sideways_pass'] if pd.notna(row['sideways_pass']) else None,
                                    sideways_pass_succeeded=row['sideways_pass_succeeded'] if pd.notna(row['sideways_pass_succeeded']) else None,
                                    tackle=row['tackle'] if pd.notna(row['tackle']) else None,
                                    tackle_succeeded=row['tackle_succeeded'] if pd.notna(row['tackle_succeeded']) else None,
                                    take_on=row['take_on'] if pd.notna(row['take_on']) else None,
                                    take_on_succeeded=row['take_on_succeeded'] if pd.notna(row['take_on_succeeded']) else None,
                                    throw_in=row['throw_in'] if pd.notna(row['throw_in']) else None,
                                    total_shot=row['total_shot'] if pd.notna(row['total_shot']) else None,
                                    yellow_card=row['yellow_card'] if pd.notna(row['yellow_card']) else None
                                )
                            )
                        BeproTeamStat.objects.bulk_create(details)

                    if sheet_name == f"EventData_{instance.match_id}":
                        match_data = BeproMatchData.objects.get(match_id=instance.match_id)
                        event_data = []
                        for _, row in data.iterrows():
                            event_data.append(
                                BeproEventData(
                                    match_id=match_data,
                                    event=row['Event'] if pd.notna(row['Event']) else "",
                                    event_sub_event=row['Event Sub-event'] if pd.notna(row['Event Sub-event']) else None,
                                    reference=row['Reference'] if pd.notna(row['Reference']) else "",
                                    explanation=row['Explanation'] if pd.notna(row['Explanation']) else None,
                                    event_hebrew=row['אירוע/Event'] if pd.notna(row['אירוע/Event']) else None,
                                    sub_event_hebrew=row['אירוע משנה/Sub-event'] if pd.notna(row['אירוע משנה/Sub-event']) else None,
                                    explanation_hebrew=row['הסבר/Explanation'] if pd.notna(row['הסבר/Explanation']) else None,
                                )
                            )
                        # Bulk insert event data
                        BeproEventData.objects.bulk_create(event_data)

                
                print("Excel file processed successfully!")

        except Exception as e:
            print(f"Error processing Excel file: {e}")
            raise  # This will rollback the database transaction
