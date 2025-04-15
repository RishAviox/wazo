from django.db import models
from uuid import uuid4


class BeproLeagueDetail(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4())
    league_id = models.PositiveIntegerField(null=True)
    name = models.CharField(max_length=100, null=True)
    name_en = models.CharField(max_length=100, null=True)
    iso_country_code = models.CharField(max_length=10, null=True)
    age_limit = models.CharField(max_length=20, null=True)
    division = models.PositiveIntegerField(null=True)
    season_ids = models.PositiveIntegerField(null=True)

    def __str__(self):
        return f"{self.league_id} - {self.name}"


class BeproSeason(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4())
    league_id = models.PositiveIntegerField(null=True)
    name = models.CharField(max_length=100, null=True)
    name_en = models.CharField(max_length=100, null=True)
    iso_country_code = models.CharField(max_length=10, null=True)
    age_limit = models.CharField(max_length=20, null=True)
    division = models.PositiveIntegerField(null=True)
    season_ids = models.PositiveIntegerField(null=True)

    def __str__(self):
        return f"{self.season_ids} / {self.division}"


class BeproMatchData(models.Model):
    """
        Keeps all matches and their higher level details
    """
    id = models.UUIDField(primary_key=True, default=uuid4())
    match_id = models.PositiveIntegerField()
    season_id = models.PositiveIntegerField(null=True)
    season_name = models.CharField(max_length=10, null=True)
    round_name = models.CharField(max_length=10, null=True)
    home_team_id = models.PositiveIntegerField(null=True)
    home_team_name = models.CharField(max_length=50, null=True)
    home_team_name_en = models.CharField(max_length=50, null=True)
    away_team_id = models.PositiveIntegerField(null=True)
    away_team_name = models.CharField(max_length=50, null=True)
    away_team_name_en = models.CharField(max_length=50, null=True)
    start_time = models.DateTimeField(null=True)
    venue_display_name = models.CharField(max_length=100, null=True)
    full_time = models.PositiveIntegerField(null=True)
    extra_full_time = models.PositiveIntegerField(null=True)
    home_team_score = models.PositiveIntegerField(null=True)
    away_team_score = models.PositiveIntegerField(null=True)
    is_analysis_finished = models.CharField(max_length=5, null=True)
    live_analysing = models.CharField(max_length=5, null=True)
    venue_ground_width = models.CharField(max_length=5, null=True)
    venue_ground_height = models.CharField(max_length=5, null=True)

    def __str__(self):
        return f"{self.season_name} - ({self.match_id})"
    
    def recent_results(self):
        """Fetches the last 5 matches between the same teams."""
        matches = BeproMatchData.objects.filter(
            home_team_id__in=[self.home_team_id, self.away_team_id],
            away_team_id__in=[self.home_team_id, self.away_team_id]
        ).exclude(match_id=self.match_id).order_by('-start_time')[:5]

        return [f"{m.final_score()} ({m.start_time.strftime('%Y-%m-%d')})" for m in matches]


class BeproMatchDetail(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4())
    record_id = models.PositiveBigIntegerField(null=True)
    match_id = models.ForeignKey(to=BeproMatchData, on_delete=models.CASCADE)
    team_id = models.PositiveIntegerField(null=True)
    player_id = models.PositiveIntegerField(null=True)
    event_period = models.CharField(max_length=30, null=True)
    event_time = models.CharField(max_length=10, null=True)
    x = models.CharField(max_length=10, null=True)
    y = models.CharField(max_length=10, null=True)
    ball_position_x = models.CharField(max_length=10, null=True)
    ball_position_y = models.CharField(max_length=10, null=True)
    relative_event_id = models.CharField(max_length=30, null=True)
    relative_event_x = models.CharField(max_length=10, null=True)
    relative_event_y = models.CharField(max_length=10, null=True)
    xg = models.CharField(max_length=30, null=True)
    event_type = models.CharField(max_length=30, null=True)
    outcome = models.CharField(max_length=30, null=True)
    sub_event_type = models.CharField(max_length=30, null=True)
    cross = models.CharField(max_length=5, null=True)
    key_pass = models.CharField(max_length=5, null=True)
    assist = models.CharField(max_length=5, null=True)
    body_part = models.CharField(max_length=20, null=True)

    def __str__(self):
        return f"{self.match_id}"


class BeproEventData(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    match_id = models.ForeignKey(to=BeproMatchData, on_delete=models.CASCADE, related_name="events")
    event = models.CharField(max_length=100)
    event_sub_event = models.CharField(max_length=100, null=True, blank=True)
    reference = models.CharField(max_length=100)
    explanation = models.TextField(null=True, blank=True)

    event_hebrew = models.CharField(max_length=100, null=True, blank=True)
    sub_event_hebrew = models.CharField(max_length=100, null=True, blank=True)
    explanation_hebrew = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bepro Event Data"
        verbose_name_plural = "Bepro Event Data"

    def __str__(self):
        return f"{self.event} - {self.event_sub_event} ({self.reference})"

# class BeproEventData(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid4())
#     record_id = models.PositiveBigIntegerField(null=True)
#     match_id = models.ForeignKey(to=BeproMatchData, on_delete=models.CASCADE)
#     team_id = models.PositiveIntegerField(null=True)
#     player_id = models.PositiveIntegerField(null=True)
#     event_period = models.CharField(max_length=30, null=True)
#     event_time = models.CharField(max_length=10, null=True)
#     x = models.CharField(max_length=10, null=True)
#     y = models.CharField(max_length=10, null=True)
#     ball_position_x = models.CharField(max_length=10, null=True)
#     ball_position_y = models.CharField(max_length=10, null=True)
#     relative_event_id = models.CharField(max_length=30, null=True)
#     relative_event_x = models.CharField(max_length=10, null=True)
#     relative_event_y = models.CharField(max_length=10, null=True)
#     xg = models.CharField(max_length=30, null=True)
#     event_type = models.CharField(max_length=30, null=True)
#     outcome = models.CharField(max_length=30, null=True)
#     sub_event_type = models.CharField(max_length=30, null=True)
#     cross = models.CharField(max_length=5, null=True)
#     key_pass = models.CharField(max_length=5, null=True)
#     assist = models.CharField(max_length=5, null=True)
#     body_part = models.CharField(max_length=20, null=True)

#     def __str__(self):
#         return f"{self.event_type}"


class BeproFormationData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4())
    team_id = models.PositiveIntegerField(null=True)
    event_period = models.CharField(max_length=20, null=True)
    changed_time = models.CharField(max_length=20, null=True)
    player_id = models.IntegerField(null=True)
    x = models.CharField(max_length=50, null=True)
    y =  models.CharField(max_length=50, null=True)

    def __str__(self):
        return f"{self.team_id}"


class BeproSequenceData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4())
    team_id = models.PositiveIntegerField(null=True)
    event_period = models.CharField(max_length=20, null=True)
    start_time = models.PositiveIntegerField(null=True)
    end_time = models.PositiveIntegerField(null=True)
    event_ids = models.JSONField(null=True)

    def __str__(self):
        return f"{self.team_id}"


class BeproPhysicalEventData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4())
    match_id = models.ForeignKey(to=BeproMatchData, on_delete=models.CASCADE)
    team_id = models.IntegerField(null=True)
    player_id = models.IntegerField(null=True)
    event_period = models.CharField(max_length=20, null=True)
    event_time = models.PositiveIntegerField(null=True)
    x = models.FloatField(null=True)
    y = models.FloatField(null=True)
    ball_position_x = models.FloatField(null=True)
    ball_position_y = models.FloatField(null=True)
    relative_event_id = models.CharField(max_length=20, null=True)
    relative_event_x = models.CharField(max_length=20, null=True)
    relative_event_y = models.CharField(max_length=20, null=True)
    xg = models.CharField(max_length=30, null=True)
    event_type = models.CharField(max_length=30, null=True)
    outcome = models.CharField(max_length=30, null=True)
    sub_event_type = models.CharField(max_length=30, null=True)
    cross = models.CharField(max_length=5, null=True)
    key_pass = models.CharField(max_length=5, null=True)
    assist = models.CharField(max_length=5, null=True)
    body_part = models.CharField(max_length=20, null=True)

    def __str__(self):
        return f"{self.event_type}"


class BeproLineUp(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4())
    record_id = models.IntegerField(null=True)
    team_id = models.PositiveIntegerField(null=True)
    player_id = models.PositiveIntegerField(null=True)
    position_name = models.CharField(max_length=20, null=True)
    back_number = models.PositiveIntegerField(null=True)
    player_name = models.CharField(max_length=20, null=True)
    player_last_name = models.CharField(max_length=30, null=True)
    is_starting_lineup = models.CharField(max_length=5, null=True)
    position_x = models.FloatField(null=True)
    position_y = models.FloatField(null=True)

    def __str__(self):
        return f"{self.record_id}"


class BeproPlayerStat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4())
    team_id = models.PositiveIntegerField(null=True)
    player_id = models.PositiveIntegerField(null=True)
    aerial_clearance = models.PositiveIntegerField(null=True)
    aerial_clearance_failed = models.PositiveIntegerField(null=True)
    aerial_clearance_succeeded = models.PositiveIntegerField(null=True)
    aerial_duel = models.PositiveIntegerField(null=True)
    aerial_duel_failed = models.PositiveIntegerField(null=True)
    aerial_duel_succeeded = models.PositiveIntegerField(null=True)
    assist = models.PositiveIntegerField(null=True)
    backward_pass = models.PositiveIntegerField(null=True)
    backward_pass_succeeded = models.PositiveIntegerField(null=True)
    block = models.PositiveIntegerField(null=True)
    clearance = models.PositiveIntegerField(null=True)
    control_under_pressure = models.PositiveIntegerField(null=True)
    corner_kick = models.PositiveIntegerField(null=True)
    cross = models.PositiveIntegerField(null=True)
    cross_succeeded = models.PositiveIntegerField(null=True)
    defensive_area_pass = models.PositiveIntegerField(null=True)
    defensive_area_pass_succeeded = models.PositiveIntegerField(null=True)
    defensive_line_support = models.PositiveIntegerField(null=True)
    defensive_line_support_failed = models.PositiveIntegerField(null=True)
    defensive_line_support_succeeded = models.PositiveIntegerField(null=True)
    final_third_area_pass = models.PositiveIntegerField(null=True)
    final_third_area_pass_succeeded = models.PositiveIntegerField(null=True)
    forward_pass = models.PositiveIntegerField(null=True)
    forward_pass_succeeded = models.PositiveIntegerField(null=True)
    foul = models.PositiveIntegerField(null=True)
    foul_won = models.PositiveIntegerField(null=True)
    free_kick = models.PositiveIntegerField(null=True)
    goal_conceded = models.PositiveIntegerField(null=True)
    goal_kick = models.PositiveIntegerField(null=True)
    goal_kick_succeeded = models.PositiveIntegerField(null=True)
    ground_duel = models.PositiveIntegerField(null=True)
    ground_duel_failed = models.PositiveIntegerField(null=True)
    ground_duel_succeeded = models.PositiveIntegerField(null=True)
    intercept = models.PositiveIntegerField(null=True)
    intervention = models.PositiveIntegerField(null=True)
    key_pass = models.PositiveIntegerField(null=True)
    long_pass = models.PositiveIntegerField(null=True)
    long_pass_succeeded = models.PositiveIntegerField(null=True)
    loose_ball_duel = models.PositiveIntegerField(null=True)
    loose_ball_duel_failed = models.PositiveIntegerField(null=True)
    loose_ball_duel_succeeded = models.PositiveIntegerField(null=True)
    medium_range_pass = models.PositiveIntegerField(null=True)
    medium_range_pass_succeeded = models.PositiveIntegerField(null=True)
    middle_area_pass = models.PositiveIntegerField(null=True)
    middle_area_pass_succeeded = models.PositiveIntegerField(null=True)
    mistake = models.PositiveIntegerField(null=True)
    offside = models.PositiveIntegerField(null=True)
    own_goal = models.PositiveIntegerField(null=True)
    _pass = models.PositiveIntegerField(null=True)
    pass_failed = models.PositiveIntegerField(null=True)
    pass_succeeded = models.PositiveIntegerField(null=True)
    penalty_kick = models.PositiveIntegerField(null=True)
    play_time = models.PositiveIntegerField(null=True)
    rating = models.FloatField(null=True)
    recovery = models.PositiveIntegerField(null=True)
    red_card = models.PositiveIntegerField(null=True)
    save_by_catching = models.PositiveIntegerField(null=True)
    save_by_punching = models.PositiveIntegerField(null=True)
    short_pass = models.PositiveIntegerField(null=True)
    short_pass_succeeded = models.PositiveIntegerField(null=True)
    shot_blocked = models.PositiveIntegerField(null=True)
    shot_in_PA = models.PositiveIntegerField(null=True)
    shot_off_target = models.PositiveIntegerField(null=True)
    shot_on_target = models.PositiveIntegerField(null=True)
    shot_outside_of_PA = models.PositiveIntegerField(null=True)
    sideways_pass = models.PositiveIntegerField(null=True)
    sideways_pass_succeeded = models.PositiveIntegerField(null=True)
    tackle = models.PositiveIntegerField(null=True)
    tackle_succeeded = models.PositiveIntegerField(null=True)
    take_on = models.PositiveIntegerField(null=True)
    take_on_succeeded = models.PositiveIntegerField(null=True)
    throw_in = models.PositiveIntegerField(null=True)
    total_shot = models.PositiveIntegerField(null=True)
    yellow_card = models.PositiveIntegerField(null=True)

    def __str__(self):
        return f"{self.player_id}"
    

class BeproPlayerStatsExtended(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4())
    match_id = models.ForeignKey(to=BeproMatchData, on_delete=models.CASCADE)
    season_id = models.IntegerField(null=True)
    season_name = models.CharField(max_length=10, null=True)
    round_name = models.CharField(max_length=10, null=True)
    home_team_id = models.PositiveIntegerField(null=True)
    home_team_name = models.CharField(max_length=50, null=True)
    home_team_name_en = models.CharField(max_length=50, null=True)
    away_team_id = models.PositiveIntegerField(null=True)
    away_team_name = models.CharField(max_length=50, null=True)
    away_team_name_en = models.CharField(max_length=50, null=True)
    start_time = models.DateTimeField(null=True)
    venue_display_name = models.CharField(max_length=50, null=True)
    full_time = models.PositiveIntegerField(null=True)
    extra_full_time = models.PositiveIntegerField(null=True)
    home_team_score = models.PositiveIntegerField(verbose_name="detail_match_result__home_team_score", null=True)
    away_team_score = models.PositiveIntegerField(verbose_name="detail_match_result__away_team_score", null=True)
    is_analysis_finsihed = models.CharField(max_length=5, null=True)
    live_analysing = models.CharField(max_length=5, null=True)
    venue_ground_width = models.CharField(max_length=10, null=True)
    venue_ground_height = models.CharField(max_length=10, null=True)

    def __str__(self):
        return f"{self.season_id} / {self.season_name}"


class BeproPlayer(models.Model):
    """Stores all player data"""
    id = models.UUIDField(primary_key=True, default=uuid4())
    record_id = models.PositiveIntegerField(null=True)
    main_position = models.CharField(max_length=10, null=True)
    back_number = models.PositiveIntegerField(null=True)
    player_name = models.CharField(max_length=20, null=True)
    player_last_name = models.CharField(max_length=20, null=True)
    player_name_en = models.CharField(max_length=20, null=True)
    player_last_name_en = models.CharField(max_length=20, null=True)
    player_role = models.CharField(max_length=20, null=True)

    def __str__(self):
        return f"{self.player_name_en} {self.player_last_name_en}"


class BeproTeamStat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4())
    match = models.ForeignKey(BeproMatchData, on_delete=models.CASCADE)
    team_id = models.PositiveIntegerField(null=True)
    aerial_clearance = models.PositiveIntegerField(null=True)
    aerial_clearance_failed = models.PositiveIntegerField(null=True)
    aerial_clearance_succeeded = models.PositiveIntegerField(null=True)
    aerial_duel = models.PositiveIntegerField(null=True)
    aerial_duel_failed = models.PositiveIntegerField(null=True)
    aerial_duel_succeeded = models.PositiveIntegerField(null=True)
    assist = models.PositiveIntegerField(null=True)
    backward_pass = models.PositiveIntegerField(null=True)
    backward_pass_succeeded = models.PositiveIntegerField(null=True)
    block = models.PositiveIntegerField(null=True)
    clearance = models.PositiveIntegerField(null=True)
    control_under_pressure = models.PositiveIntegerField(null=True)
    corner_kick = models.PositiveIntegerField(null=True)
    cross = models.PositiveIntegerField(null=True)
    cross_succeeded = models.PositiveIntegerField(null=True)
    defensive_area_pass = models.PositiveIntegerField(null=True)
    defensive_area_pass_succeeded = models.PositiveIntegerField(null=True)
    defensive_line_support = models.PositiveIntegerField(null=True)
    defensive_line_support_failed = models.PositiveIntegerField(null=True)
    defensive_line_support_succeeded = models.PositiveIntegerField(null=True)
    final_third_area_pass = models.PositiveIntegerField(null=True)
    final_third_area_pass_succeeded = models.PositiveIntegerField(null=True)
    forward_pass = models.PositiveIntegerField(null=True)
    forward_pass_succeeded = models.PositiveIntegerField(null=True)
    foul = models.PositiveIntegerField(null=True)
    foul_won = models.PositiveIntegerField(null=True)
    free_kick = models.PositiveIntegerField(null=True)
    goal = models.PositiveIntegerField(null=True)
    goal_conceded = models.PositiveIntegerField(null=True)
    goal_kick = models.PositiveIntegerField(null=True)
    goal_kick_succeeded = models.PositiveIntegerField(null=True)
    ground_duel = models.PositiveIntegerField(null=True)
    ground_duel_failed = models.PositiveIntegerField(null=True)
    ground_duel_succeeded = models.PositiveIntegerField(null=True)
    intercept = models.PositiveIntegerField(null=True)
    intervention = models.PositiveIntegerField(null=True)
    key_pass = models.PositiveIntegerField(null=True)
    long_pass = models.PositiveIntegerField(null=True)
    long_pass_succeeded = models.PositiveIntegerField(null=True)
    loose_ball_duel = models.PositiveIntegerField(null=True)
    loose_ball_duel_failed = models.PositiveIntegerField(null=True)
    loose_ball_duel_succeeded = models.PositiveIntegerField(null=True)
    medium_range_pass = models.PositiveIntegerField(null=True)
    medium_range_pass_succeeded = models.PositiveIntegerField(null=True)
    middle_area_pass = models.PositiveIntegerField(null=True)
    middle_area_pass_succeeded = models.PositiveIntegerField(null=True)
    mistake = models.PositiveIntegerField(null=True)
    offside = models.PositiveIntegerField(null=True)
    own_goal = models.PositiveIntegerField(null=True)
    passed = models.PositiveIntegerField(null=True)
    pass_failed = models.PositiveIntegerField(null=True)
    pass_succeeded = models.PositiveIntegerField(null=True)
    penalty_kick = models.PositiveIntegerField(null=True)
    possession = models.FloatField(null=True)
    recovery = models.PositiveIntegerField(null=True)
    red_card = models.PositiveIntegerField(null=True)
    save_by_catching = models.PositiveIntegerField(null=True)
    save_by_punching = models.PositiveIntegerField(null=True)
    short_pass = models.PositiveIntegerField(null=True)
    short_pass_succeeded = models.PositiveIntegerField(null=True)
    shot_blocked = models.PositiveIntegerField(null=True)
    shot_in_PA = models.PositiveIntegerField(null=True)
    shot_off_target = models.PositiveIntegerField(null=True)
    shot_on_target = models.PositiveIntegerField(null=True)
    shot_outside_of_PA = models.PositiveIntegerField(null=True)
    sideways_pass = models.PositiveIntegerField(null=True)
    sideways_pass_succeeded = models.PositiveIntegerField(null=True)
    tackle = models.PositiveIntegerField(null=True)
    tackle_succeeded = models.PositiveIntegerField(null=True)
    take_on = models.PositiveIntegerField(null=True)
    take_on_succeeded = models.PositiveIntegerField(null=True)
    throw_in = models.PositiveIntegerField(null=True)
    total_shot = models.PositiveIntegerField(null=True)
    yellow_card = models.PositiveIntegerField(null=True)

    def __str__(self):
        return f"{self.team_id}"


class PostMatchAnalysis(models.Model):
    overview_json = models.JSONField()
    overview_json_he = models.JSONField()
    key_tactical_insight_report_json = models.JSONField()
    key_tactical_insight_report_json_he = models.JSONField()
    individual_player_performance_report_json = models.JSONField()
    individual_player_performance_report_json_he = models.JSONField()
    team_performance_report_json = models.JSONField()
    team_performance_report_json_he = models.JSONField()
    set_piece_analysis_report_json = models.JSONField()
    set_piece_analysis_report_json_he = models.JSONField()
    fitness_recovery_suggestion_json = models.JSONField()
    fitness_recovery_suggestion_json_he = models.JSONField()
    training_recommendation_report_json = models.JSONField()
    training_recommendation_report_json_he = models.JSONField()
    summary_json = models.JSONField()
    summary_json_he = models.JSONField()

    class Meta:
        verbose_name_plural = "Post Match Analysis"


# class MatchSummaryStats(models.Model):
#     summary_json = models.JSONField()

#     class Meta:
#         verbose_name_plural = "Match Summary Stats"
