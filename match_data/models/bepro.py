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
    home_team_score = models.PositiveSmallIntegerField(null=True)
    away_team_score = models.PositiveSmallIntegerField(null=True)
    is_analysis_finished = models.CharField(max_length=5, null=True)
    live_analysing = models.CharField(max_length=5, null=True)
    venue_ground_width = models.CharField(max_length=5, null=True)
    venue_ground_height = models.CharField(max_length=5, null=True)

    def __str__(self):
        return f"{self.season_name} - ({self.match_id})"

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
        return f"{self.event_type}"


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
    event_time = models.PositiveSmallIntegerField(null=True)
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
    back_number = models.PositiveSmallIntegerField(null=True)
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
    aerial_clearance = models.PositiveSmallIntegerField(null=True)
    aerial_clearance_failed = models.PositiveSmallIntegerField(null=True)
    aerial_clearance_succeeded = models.PositiveSmallIntegerField(null=True)
    aerial_duel = models.PositiveSmallIntegerField(null=True)
    aerial_duel_failed = models.PositiveSmallIntegerField(null=True)
    aerial_duel_succeeded = models.PositiveSmallIntegerField(null=True)
    assist = models.PositiveSmallIntegerField(null=True)
    backward_pass = models.PositiveSmallIntegerField(null=True)
    backward_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    block = models.PositiveSmallIntegerField(null=True)
    clearance = models.PositiveSmallIntegerField(null=True)
    control_under_pressure = models.PositiveSmallIntegerField(null=True)
    corner_kick = models.PositiveSmallIntegerField(null=True)
    cross = models.PositiveSmallIntegerField(null=True)
    cross_succeeded = models.PositiveSmallIntegerField(null=True)
    defensive_area_pass = models.PositiveSmallIntegerField(null=True)
    defensive_area_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    defensive_line_support = models.PositiveSmallIntegerField(null=True)
    defensive_line_support_failed = models.PositiveSmallIntegerField(null=True)
    defensive_line_support_succeeded = models.PositiveSmallIntegerField(null=True)
    final_third_area_pass = models.PositiveSmallIntegerField(null=True)
    final_third_area_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    forward_pass = models.PositiveSmallIntegerField(null=True)
    forward_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    foul = models.PositiveSmallIntegerField(null=True)
    foul_won = models.PositiveSmallIntegerField(null=True)
    free_kick = models.PositiveSmallIntegerField(null=True)
    goal_conceded = models.PositiveSmallIntegerField(null=True)
    goal_kick = models.PositiveSmallIntegerField(null=True)
    goal_kick_succeeded = models.PositiveSmallIntegerField(null=True)
    ground_duel = models.PositiveSmallIntegerField(null=True)
    ground_duel_failed = models.PositiveSmallIntegerField(null=True)
    ground_duel_succeeded = models.PositiveSmallIntegerField(null=True)
    intercept = models.PositiveSmallIntegerField(null=True)
    intervention = models.PositiveSmallIntegerField(null=True)
    key_pass = models.PositiveSmallIntegerField(null=True)
    long_pass = models.PositiveSmallIntegerField(null=True)
    long_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    loose_ball_duel = models.PositiveSmallIntegerField(null=True)
    loose_ball_duel_failed = models.PositiveSmallIntegerField(null=True)
    loose_ball_duel_succeeded = models.PositiveSmallIntegerField(null=True)
    medium_range_pass = models.PositiveSmallIntegerField(null=True)
    medium_range_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    middle_area_pass = models.PositiveSmallIntegerField(null=True)
    middle_area_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    mistake = models.PositiveSmallIntegerField(null=True)
    offside = models.PositiveSmallIntegerField(null=True)
    own_goal = models.PositiveSmallIntegerField(null=True)
    _pass = models.PositiveSmallIntegerField(null=True)
    pass_failed = models.PositiveSmallIntegerField(null=True)
    pass_succeeded = models.PositiveSmallIntegerField(null=True)
    penalty_kick = models.PositiveSmallIntegerField(null=True)
    play_time = models.PositiveSmallIntegerField(null=True)
    rating = models.FloatField(null=True)
    recovery = models.PositiveSmallIntegerField(null=True)
    red_card = models.PositiveSmallIntegerField(null=True)
    save_by_catching = models.PositiveSmallIntegerField(null=True)
    save_by_punching = models.PositiveSmallIntegerField(null=True)
    short_pass = models.PositiveSmallIntegerField(null=True)
    short_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    shot_blocked = models.PositiveSmallIntegerField(null=True)
    shot_in_PA = models.PositiveSmallIntegerField(null=True)
    shot_off_target = models.PositiveSmallIntegerField(null=True)
    shot_on_target = models.PositiveSmallIntegerField(null=True)
    shot_outside_of_PA = models.PositiveSmallIntegerField(null=True)
    sideways_pass = models.PositiveSmallIntegerField(null=True)
    sideways_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    tackle = models.PositiveSmallIntegerField(null=True)
    tackle_succeeded = models.PositiveSmallIntegerField(null=True)
    take_on = models.PositiveSmallIntegerField(null=True)
    take_on_succeeded = models.PositiveSmallIntegerField(null=True)
    throw_in = models.PositiveSmallIntegerField(null=True)
    total_shot = models.PositiveSmallIntegerField(null=True)
    yellow_card = models.PositiveSmallIntegerField(null=True)

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
    full_time = models.PositiveSmallIntegerField(null=True)
    extra_full_time = models.PositiveSmallIntegerField(null=True)
    home_team_score = models.PositiveSmallIntegerField(verbose_name="detail_match_result__home_team_score", null=True)
    away_team_score = models.PositiveSmallIntegerField(verbose_name="detail_match_result__away_team_score", null=True)
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
    back_number = models.PositiveSmallIntegerField(null=True)
    player_name = models.CharField(max_length=20, null=True)
    player_last_name = models.CharField(max_length=20, null=True)
    player_name_en = models.CharField(max_length=20, null=True)
    player_last_name_en = models.CharField(max_length=20, null=True)
    player_role = models.CharField(max_length=20, null=True)

    def __str__(self):
        return f"{self.player_name_en} {self.player_last_name_en}"


class BeproTeamStat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4())
    team_id = models.PositiveIntegerField(null=True)
    aerial_clearance = models.PositiveSmallIntegerField(null=True)
    aerial_clearance_failed = models.PositiveSmallIntegerField(null=True)
    aerial_clearance_succeeded = models.PositiveSmallIntegerField(null=True)
    aerial_duel = models.PositiveSmallIntegerField(null=True)
    aerial_duel_failed = models.PositiveSmallIntegerField(null=True)
    aerial_duel_succeeded = models.PositiveSmallIntegerField(null=True)
    assist = models.PositiveSmallIntegerField(null=True)
    backward_pass = models.PositiveSmallIntegerField(null=True)
    backward_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    block = models.PositiveSmallIntegerField(null=True)
    clearance = models.PositiveSmallIntegerField(null=True)
    control_under_pressure = models.PositiveSmallIntegerField(null=True)
    corner_kick = models.PositiveSmallIntegerField(null=True)
    cross = models.PositiveSmallIntegerField(null=True)
    cross_succeeded = models.PositiveSmallIntegerField(null=True)
    defensive_area_pass = models.PositiveSmallIntegerField(null=True)
    defensive_area_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    defensive_line_support = models.PositiveSmallIntegerField(null=True)
    defensive_line_support_failed = models.PositiveSmallIntegerField(null=True)
    defensive_line_support_succeeded = models.PositiveSmallIntegerField(null=True)
    final_third_area_pass = models.PositiveSmallIntegerField(null=True)
    final_third_area_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    forward_pass = models.PositiveSmallIntegerField(null=True)
    forward_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    foul = models.PositiveSmallIntegerField(null=True)
    foul_won = models.PositiveSmallIntegerField(null=True)
    free_kick = models.PositiveSmallIntegerField(null=True)
    goal = models.PositiveSmallIntegerField(null=True)
    goal_conceded = models.PositiveSmallIntegerField(null=True)
    goal_kick = models.PositiveSmallIntegerField(null=True)
    goal_kick_succeeded = models.PositiveSmallIntegerField(null=True)
    ground_duel = models.PositiveSmallIntegerField(null=True)
    ground_duel_failed = models.PositiveSmallIntegerField(null=True)
    ground_duel_succeeded = models.PositiveSmallIntegerField(null=True)
    intercept = models.PositiveSmallIntegerField(null=True)
    intervention = models.PositiveSmallIntegerField(null=True)
    key_pass = models.PositiveSmallIntegerField(null=True)
    long_pass = models.PositiveSmallIntegerField(null=True)
    long_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    loose_ball_duel = models.PositiveSmallIntegerField(null=True)
    loose_ball_duel_failed = models.PositiveSmallIntegerField(null=True)
    loose_ball_duel_succeeded = models.PositiveSmallIntegerField(null=True)
    medium_range_pass = models.PositiveSmallIntegerField(null=True)
    medium_range_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    middle_area_pass = models.PositiveSmallIntegerField(null=True)
    middle_area_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    mistake = models.PositiveSmallIntegerField(null=True)
    offside = models.PositiveSmallIntegerField(null=True)
    own_goal = models.PositiveSmallIntegerField(null=True)
    passed = models.PositiveSmallIntegerField(null=True)
    pass_failed = models.PositiveSmallIntegerField(null=True)
    pass_succeeded = models.PositiveSmallIntegerField(null=True)
    penalty_kick = models.PositiveSmallIntegerField(null=True)
    possession = models.FloatField(null=True)
    recovery = models.PositiveSmallIntegerField(null=True)
    red_card = models.PositiveSmallIntegerField(null=True)
    save_by_catching = models.PositiveSmallIntegerField(null=True)
    save_by_punching = models.PositiveSmallIntegerField(null=True)
    short_pass = models.PositiveSmallIntegerField(null=True)
    short_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    shot_blocked = models.PositiveSmallIntegerField(null=True)
    shot_in_PA = models.PositiveSmallIntegerField(null=True)
    shot_off_target = models.PositiveSmallIntegerField(null=True)
    shot_on_target = models.PositiveSmallIntegerField(null=True)
    shot_outside_of_PA = models.PositiveSmallIntegerField(null=True)
    sideways_pass = models.PositiveSmallIntegerField(null=True)
    sideways_pass_succeeded = models.PositiveSmallIntegerField(null=True)
    tackle = models.PositiveSmallIntegerField(null=True)
    tackle_succeeded = models.PositiveSmallIntegerField(null=True)
    take_on = models.PositiveSmallIntegerField(null=True)
    take_on_succeeded = models.PositiveSmallIntegerField(null=True)
    throw_in = models.PositiveSmallIntegerField(null=True)
    total_shot = models.PositiveSmallIntegerField(null=True)
    yellow_card = models.PositiveSmallIntegerField(null=True)

    def __str__(self):
        return f"{self.team_id}"
