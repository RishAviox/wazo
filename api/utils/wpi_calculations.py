"""
    Calculations for Wajo Performance Index(WPI).
    Overall Score, Pace, Shooting, Passing, Dribbling, Defending, 
    Physicality, Game Intelligence, Composure, Goal Keeping
"""
from .calculation_weights import WPI_WEIGHTS

MAX_GAME_TIME = 90

def calculate_pace_score(gps_row, player_position, player_age, wpi_weights=WPI_WEIGHTS):
    """
        Req: GPS data
    """
    Category = 'Pace' # weight category
    # Coalesce equivalent: replace None with 0 for calculation
    top_speed = gps_row.get('Top Speed (km/h)', 0)
    high_intensity_runs = gps_row.get('High Intensity Run (#)', 0) 
    max_intensity_run = gps_row.get('Max. Intensity Run (m)', 0)
    high_intensity_acceleration = gps_row.get('High Int. Acceleration (#)', 0)
    max_intensity_acceleration = gps_row.get('Max. Int. Acceleration (m)', 0)
    
    # NULLIF equivalent: avoid division by zero
    play_time = gps_row.get('Corrected Play Time (min)', 1)
    
    # Calculate weighted sum
    weighted_sum = (
        top_speed * wpi_weights['Metric Specific'][Category]['Top Speed'] +
        high_intensity_runs * wpi_weights['Metric Specific'][Category]['High Intensity Run'] +
        max_intensity_run * wpi_weights['Metric Specific'][Category]['Max Intensity Run'] +
        high_intensity_acceleration * wpi_weights['Metric Specific'][Category]['High Intensity Acceleration'] +
        max_intensity_acceleration * wpi_weights['Metric Specific'][Category]['Max Intensity Acceleration']
    )
    # Calculate pace score per minute
    pace_score = (weighted_sum / play_time) * MAX_GAME_TIME
    
    # Position boost logic
    position_multiplier = wpi_weights['Position Boosters'][Category][player_position] if player_position in wpi_weights['Position Boosters'][Category].keys() else 1
    
    # Age decline logic
    age_factor = max(1 - ((player_age - wpi_weights['Decline Rate'][Category]['Peak Age']) / wpi_weights['Decline Rate'][Category]['Decline Rate']), 0)
    
    # Final calculation with scaling factor and shift
    scaling_factor = 1.0
    shift_value = 0
    score = (pace_score * position_multiplier * age_factor) * scaling_factor + shift_value
    
    # Round and multiply by 100
    final_score = round(max(score, 0) * 100)
    
    return final_score


def calculate_shooting_score(gps_row, stats_row, player_position, player_age, wpi_weights=WPI_WEIGHTS):
    """
        Req: Player Stats data
    """
    Category = 'Shooting' # weight category
    # Coalesce equivalent: replace None with 0 for calculation
    goal = stats_row.get('goal', 0)
    shot_on_target = stats_row.get('shot_on_target', 0) 
    shot_off_target = stats_row.get('shot_off_target', 0)
    shot_blocked = stats_row.get('shot_blocked', 0)
    shot_in_pa = stats_row.get('shot_in_pa', 0)
    shot_outside_of_pa = stats_row.get('shot_outside_of_pa', 0)
    kick_power = stats_row.get('kick_power', 0)
    
    # NULLIF equivalent: avoid division by zero
    play_time = gps_row.get('Corrected Play Time (min)', 1)
    
    # Calculate weighted sum
    weighted_sum = (
        goal * wpi_weights['Metric Specific'][Category]['Goal'] +
        shot_on_target * wpi_weights['Metric Specific'][Category]['Shot on Target'] +
        shot_off_target * wpi_weights['Metric Specific'][Category]['Shot Off Target'] +
        shot_blocked * wpi_weights['Metric Specific'][Category]['Shot Blocked'] +
        shot_in_pa * wpi_weights['Metric Specific'][Category]['Shot in PA'] +
        shot_outside_of_pa * wpi_weights['Metric Specific'][Category]['Shot outside PA'] +
        kick_power * wpi_weights['Metric Specific'][Category]['Kick Power']
    )
    
    # Calculate shooting score per minute
    shooting_score = (weighted_sum / play_time) * MAX_GAME_TIME
    
    # Position boost logic
    position_multiplier = wpi_weights['Position Boosters'][Category][player_position] if player_position in wpi_weights['Position Boosters'][Category].keys() else 1
    
    # Age decline logic
    age_factor = max(1 - ((player_age - wpi_weights['Decline Rate'][Category]['Peak Age']) / wpi_weights['Decline Rate'][Category]['Decline Rate']), 0)
    
    # Final calculation with scaling factor and shift
    scaling_factor = 1.0
    shift_value = 0
    score = (shooting_score * position_multiplier * age_factor) * scaling_factor + shift_value
    
    # Round and multiply by 100
    final_score = round(max(score, 0) * 100)
    
    return final_score


def calculate_passing_score(gps_row, stats_row, player_position, player_age, wpi_weights=WPI_WEIGHTS):
    """
        Reg: GPS and Player Stats Data
    """
    Category = 'Passing' # weight category

    key_pass = stats_row.get('key_pass', 0)
    long_pass_succeeded  = stats_row.get('long_pass_succeeded', 0) 
    cross_succeeded = stats_row.get('cross_succeeded', 0)
    pass_succeeded = stats_row.get('pass_succeeded', 0)
    final_third_area_pass_succeeded  = stats_row.get('final_third_area_pass_succeeded ', 0)
    pass_failed  = stats_row.get('pass_failed ', 0)
    intercept  = stats_row.get('intercept ', 0)
    backward_pass_succeeded  = stats_row.get('backward_pass_succeeded ', 0)

    play_time = gps_row.get('Corrected Play Time (min)', 1)

    # Calculate weighted sum
    weighted_sum = (
        key_pass * wpi_weights['Metric Specific'][Category]['Key Pass'] +
        long_pass_succeeded * wpi_weights['Metric Specific'][Category]['Long Pass Succeeded'] +
        cross_succeeded * wpi_weights['Metric Specific'][Category]['Cross Succeeded'] +
        pass_succeeded * wpi_weights['Metric Specific'][Category]['Pass Succeeded'] +
        final_third_area_pass_succeeded * wpi_weights['Metric Specific'][Category]['Final Third Area Pass Succeeded'] +
        pass_failed * wpi_weights['Metric Specific'][Category]['Pass Failed'] +
        intercept * wpi_weights['Metric Specific'][Category]['Intercept'] +
        backward_pass_succeeded * wpi_weights['Metric Specific'][Category]['Backward Pass Succeeded'] 
    )

    # Calculate passing score
    passing_score =  (weighted_sum / play_time) * MAX_GAME_TIME

    # Position boost logic
    position_multiplier = wpi_weights['Position Boosters'][Category][player_position] if player_position in wpi_weights['Position Boosters'][Category].keys() else 1
    
    # Age decline logic
    age_factor = max(1 - ((player_age - wpi_weights['Decline Rate'][Category]['Peak Age']) / wpi_weights['Decline Rate'][Category]['Decline Rate']), 0)
    
    # Final calculation with scaling factor and shift
    scaling_factor = 1.0
    shift_value = 0
    score = (passing_score * position_multiplier * age_factor) * scaling_factor + shift_value

    # Round and multiply by 100
    final_score = round(max(score, 0) * 100)
    
    return final_score


def calculate_dribbling_score(gps_row, stats_row, player_position, player_age, wpi_weights=WPI_WEIGHTS):
    """
        Reg: GPS and Player Stats Data
    """
    Category = 'Dribbling' # weight category

    take_on_succeeded = stats_row.get('take_on_succeeded', 0)
    take_on_failed  = stats_row.get('take_on_failed', 0) 
    
    high_intensity_runs = gps_row.get('High Intensity Run (#)', 0)
    dribbling_count  = gps_row.get('Dribbling Count (#)', 0)
    dribbling_dist  = gps_row.get('Dribbling Dist. (m)', 0)

    play_time = gps_row.get('Corrected Play Time (min)', 1)

    # Calculate weighted sum
    weighted_sum = (
        take_on_succeeded * wpi_weights['Metric Specific'][Category]['Take-On Succeeded'] +
        take_on_failed * wpi_weights['Metric Specific'][Category]['Take-On Failed'] +
        high_intensity_runs * wpi_weights['Metric Specific'][Category]['High Intensity Runs'] +
        dribbling_count * wpi_weights['Metric Specific'][Category]['Dribbling Count'] +
        dribbling_dist * wpi_weights['Metric Specific'][Category]['Dribbling Distance'] 
    )

    # Calculate dribbling score
    dribbling_score =  (weighted_sum / play_time) * MAX_GAME_TIME

    # Position boost logic
    position_multiplier = wpi_weights['Position Boosters'][Category][player_position] if player_position in wpi_weights['Position Boosters'][Category].keys() else 1
    
    # Age decline logic
    age_factor = max(1 - ((player_age - wpi_weights['Decline Rate'][Category]['Peak Age']) / wpi_weights['Decline Rate'][Category]['Decline Rate']), 0)
    
    # Final calculation with scaling factor and shift
    scaling_factor = 1.0
    shift_value = 0
    score = (dribbling_score * position_multiplier * age_factor) * scaling_factor + shift_value

    # Round and multiply by 100
    final_score = round(max(score, 0) * 100)
    
    return final_score


def calculate_defending_score(gps_row, stats_row, player_position, player_age, wpi_weights=WPI_WEIGHTS):
    """
        Reg: GPS and Player Stats Data
    """
    Category = 'Defending' # weight category

    tackle_succeeded = stats_row.get('tackle_succeeded', 0)
    intercept  = stats_row.get('intercept', 0) 
    clearance  = stats_row.get('clearance', 0) 
    block  = stats_row.get('block', 0) 
    defensive_line_support_succeeded  = stats_row.get('defensive_line_support_succeeded', 0) 
    loose_ball_duel_succeeded  = stats_row.get('loose_ball_duel_succeeded', 0) 
    tackle_failed  = stats_row.get('tackle_failed', 0) 
    

    play_time = gps_row.get('Corrected Play Time (min)', 1)

    # Calculate weighted sum
    weighted_sum = (
        tackle_succeeded * wpi_weights['Metric Specific'][Category]['Tackle Succeeded'] +
        intercept * wpi_weights['Metric Specific'][Category]['Intercept'] +
        clearance * wpi_weights['Metric Specific'][Category]['Clearance'] +
        block * wpi_weights['Metric Specific'][Category]['Block'] +
        defensive_line_support_succeeded * wpi_weights['Metric Specific'][Category]['Defensive Line Support Succeeded'] +
        loose_ball_duel_succeeded * wpi_weights['Metric Specific'][Category]['Loose Ball Duel Succeeded'] +
        tackle_failed * wpi_weights['Metric Specific'][Category]['Tackle Failed'] 
    )

    # Calculate defending score
    defending_score =  (weighted_sum / play_time) * MAX_GAME_TIME

    # Position boost logic
    position_multiplier = wpi_weights['Position Boosters'][Category][player_position] if player_position in wpi_weights['Position Boosters'][Category].keys() else 1
    
    # Age decline logic
    age_factor = max(1 - ((player_age - wpi_weights['Decline Rate'][Category]['Peak Age']) / wpi_weights['Decline Rate'][Category]['Decline Rate']), 0)
    
    # Final calculation with scaling factor and shift
    scaling_factor = 1.0
    shift_value = 0
    score = (defending_score * position_multiplier * age_factor) * scaling_factor + shift_value

    # Round and multiply by 100
    final_score = round(max(score, 0) * 100)
    
    return final_score


def calculate_physicality_score(gps_row, stats_row, player_position, player_age, wpi_weights=WPI_WEIGHTS):
    """
        Reg: GPS and Player Stats Data
    """
    Category = 'Physicality' # weight category

    aerial_duel_succeeded = stats_row.get('aerial_duel_succeeded', 0)
    aerial_duel_failed  = stats_row.get('aerial_duel_failed', 0) 
    ground_duel_succeeded  = stats_row.get('ground_duel_succeeded', 0) 
    ground_duel_failed  = stats_row.get('ground_duel_failed', 0) 
    recovery  = stats_row.get('recovery', 0) 
    
    high_intensity_acceleration_count = gps_row.get('High Int. Acceleration (#)', 0)
    high_int_deceleration_count  = gps_row.get('High Int. Deceleration (#)', 0)
    max_int_acceleration  = gps_row.get('Max. Int. Acceleration (m)', 0)
    max_int_deceleration   = gps_row.get('Max. Int. Deceleration (m)', 0)
    

    play_time = gps_row.get('Corrected Play Time (min)', 1)

    # Calculate weighted sum
    weighted_sum = (
        aerial_duel_succeeded * wpi_weights['Metric Specific'][Category]['Aerial Duel Succeeded'] +
        aerial_duel_failed * wpi_weights['Metric Specific'][Category]['Aerial Duel Failed'] +
        ground_duel_succeeded * wpi_weights['Metric Specific'][Category]['Ground Duel Succeeded'] +
        ground_duel_failed * wpi_weights['Metric Specific'][Category]['Ground Duel Failed'] +
        recovery * wpi_weights['Metric Specific'][Category]['Recovery'] +
        
        high_intensity_acceleration_count * wpi_weights['Metric Specific'][Category]['High Intensity Acceleration'] +
        high_int_deceleration_count * wpi_weights['Metric Specific'][Category]['High Intensity Deceleration'] +
        max_int_acceleration * wpi_weights['Metric Specific'][Category]['Max Intensity Acceleration'] +
        max_int_deceleration * wpi_weights['Metric Specific'][Category]['Max Intensity Deceleration'] 
    )

    # Calculate physicality score
    physicality_score =  (weighted_sum / play_time) * MAX_GAME_TIME

    # Position boost logic
    position_multiplier = wpi_weights['Position Boosters'][Category][player_position] if player_position in wpi_weights['Position Boosters'][Category].keys() else 1
    
    # Age decline logic
    age_factor = max(1 - ((player_age - wpi_weights['Decline Rate'][Category]['Peak Age']) / wpi_weights['Decline Rate'][Category]['Decline Rate']), 0)
    
    # Final calculation with scaling factor and shift
    scaling_factor = 1.0
    shift_value = 0
    score = (physicality_score * position_multiplier * age_factor) * scaling_factor + shift_value

    # Round and multiply by 100
    final_score = round(max(score, 0) * 100)
    
    return final_score


def calculate_game_intelligence_score(gps_row, stats_row, player_position, player_age, wpi_weights=WPI_WEIGHTS):
    """
        Reg: GPS and Player Stats Data
    """
    Category = 'Game Intelligence' # weight category

    key_pass  = stats_row.get('key_pass ', 0)
    mistake  = stats_row.get('mistake', 0) 
    offside  = stats_row.get('offside', 0) 
    own_goal  = stats_row.get('own_goal', 0) 
    assist  = stats_row.get('assist', 0) 
    intercept  = stats_row.get('intercept', 0) 
    pass_succeeded  = stats_row.get('pass_succeeded', 0) 
    pass_failed  = stats_row.get('pass_failed', 0) 

    # Calculate pass accuracy ratio
    pass_accuracy_ratio = pass_succeeded / (pass_succeeded + pass_failed) if (pass_succeeded + pass_failed) != 0 else 0
    
    play_time = gps_row.get('Corrected Play Time (min)', 1)

    # Calculate weighted sum
    weighted_sum = (
        key_pass * wpi_weights['Metric Specific'][Category]['Key Pass'] +
        mistake * wpi_weights['Metric Specific'][Category]['Mistake'] +
        offside * wpi_weights['Metric Specific'][Category]['Offside'] +
        own_goal * wpi_weights['Metric Specific'][Category]['Own Goal'] +
        assist * wpi_weights['Metric Specific'][Category]['Assist'] +
        intercept * wpi_weights['Metric Specific'][Category]['Intercept'] +
        pass_accuracy_ratio * wpi_weights['Metric Specific'][Category]['Pass Accuracy Ratio'] 
    )

    # Calculate game_intelligence score
    game_intelligence_score =  (weighted_sum / play_time) * MAX_GAME_TIME

    # Position boost logic
    position_multiplier = wpi_weights['Position Boosters'][Category][player_position] if player_position in wpi_weights['Position Boosters'][Category].keys() else 1
    
    # Age decline logic
    age_factor = max(1 - ((player_age - wpi_weights['Decline Rate'][Category]['Peak Age']) / wpi_weights['Decline Rate'][Category]['Decline Rate']), 0)
    
    # Final calculation with scaling factor and shift
    scaling_factor = 1.0
    shift_value = 0
    score = (game_intelligence_score * position_multiplier * age_factor) * scaling_factor + shift_value

    # Round and multiply by 100
    final_score = round(max(score, 0) * 100)
    
    return final_score


def calculate_composure_score(gps_row, stats_row, player_position, player_age, wpi_weights=WPI_WEIGHTS):
    """
        Reg: GPS and Player Stats Data
    """
    Category = 'Composure' # weight category

    control_under_pressure = stats_row.get('control_under_pressure', 0)
    recovery  = stats_row.get('recovery', 0) 
    intervention  = stats_row.get('intervention', 0) 
    block  = stats_row.get('block', 0) 
    aerial_duel_succeeded  = stats_row.get('aerial_duel_succeeded', 0) 
    ground_duel_succeeded  = stats_row.get('ground_duel_succeeded', 0) 
    pass_succeeded  = stats_row.get('pass_succeeded', 0) 
    pass_  = stats_row.get('pass_', 0) 
    
    yellow_card  = stats_row.get('yellow_card', 0) 
    red_card  = stats_row.get('red_card', 0) 
    mistake  = stats_row.get('mistake', 0) 
    offside  = stats_row.get('offside', 0) 
    foul  = stats_row.get('foul', 0) 
    own_goal  = stats_row.get('own_goal', 0) 
    aerial_duel_failed  = stats_row.get('aerial_duel_failed', 0) 
    ground_duel_failed  = stats_row.get('ground_duel_failed', 0) 



    # Calculate pass accuracy ratio
    pass_accuracy_ratio = pass_succeeded / pass_  if pass_ != 0 else 0
    
    play_time = gps_row.get('Corrected Play Time (min)', 1)

    # Calculate weighted sum of positive actions
    weighted_positive_actions = (
        control_under_pressure * wpi_weights['Metric Specific'][Category]['Control Under Pressure'] +
        recovery * wpi_weights['Metric Specific'][Category]['Recovery'] +
        intervention * wpi_weights['Metric Specific'][Category]['Intervention'] +
        block * wpi_weights['Metric Specific'][Category]['Block'] +
        aerial_duel_succeeded * wpi_weights['Metric Specific'][Category]['Aerial Duel Succeeded'] +
        ground_duel_succeeded * wpi_weights['Metric Specific'][Category]['Ground Duel Succeeded'] +
        pass_accuracy_ratio * wpi_weights['Metric Specific'][Category]['Pass Accuracy Ratio'] 
    )

    # Calculate weighted sum of negative actions (penalties)
    weighted_negative_actions = (
        yellow_card * wpi_weights['Metric Specific'][Category]['Yellow Card'] +
        red_card * wpi_weights['Metric Specific'][Category]['Red Card'] +
        mistake * wpi_weights['Metric Specific'][Category]['Mistake'] +
        offside * wpi_weights['Metric Specific'][Category]['Offside'] +
        foul * wpi_weights['Metric Specific'][Category]['Foul'] +
        own_goal * wpi_weights['Metric Specific'][Category]['Own Goal'] +
        aerial_duel_failed * wpi_weights['Metric Specific'][Category]['Aerial Duel Failed'] +
        ground_duel_failed * wpi_weights['Metric Specific'][Category]['Ground Duel Failed'] 
    )

    # Calculate net score (positive - negative actions)
    net_score = weighted_positive_actions - weighted_negative_actions

    # Calculate composure score
    composure_score =  (net_score / play_time) * MAX_GAME_TIME

    # Age decline logic
    age_factor = max(1 - ((player_age - wpi_weights['Decline Rate'][Category]['Peak Age']) / wpi_weights['Decline Rate'][Category]['Decline Rate']), 0)
    
    # Final calculation with scaling factor and shift
    scaling_factor = 1.0
    shift_value = 0
    score = (composure_score * age_factor) * scaling_factor + shift_value

    # Round and multiply by 100
    final_score = round(max(score, 0) * 100)
    
    return final_score


def calculate_goal_keeping_score(gps_row, stats_row, player_position, player_age, wpi_weights=WPI_WEIGHTS):
    """
        Reg: GPS and Player Stats Data
    """
    Category = 'Goal Keeping' # weight category

    saves = stats_row.get('saves', 0)
    save_percentage  = stats_row.get('save_percentage', 0) 
    goal_conceded  = stats_row.get('goal_conceded', 0) 
    clean_sheets  = stats_row.get('clean_sheets', 0) 
    save_by_punching  = stats_row.get('save_by_punching', 0) 
    save_by_catching  = stats_row.get('save_by_catching', 0) 
    aerial_clearance_succeeded  = stats_row.get('aerial_clearance_succeeded', 0) 
    intervention  = stats_row.get('intervention', 0) 
    control_under_pressure  = stats_row.get('control_under_pressure', 0) 
    goal_kick_succeeded  = stats_row.get('goal_kick_succeeded', 0) 

    play_time = gps_row.get('Corrected Play Time (min)', 1)

    # Calculate weighted sum
    weighted_sum = (
        saves * wpi_weights['Metric Specific'][Category]['Saves'] +
        save_percentage * wpi_weights['Metric Specific'][Category]['Save Percentage'] +
        goal_conceded * wpi_weights['Metric Specific'][Category]['Goal Conceded'] +
        clean_sheets * wpi_weights['Metric Specific'][Category]['Clean Sheets'] +
        save_by_punching * wpi_weights['Metric Specific'][Category]['Save By Punching'] +
        save_by_catching * wpi_weights['Metric Specific'][Category]['Save By Catching'] +
        aerial_clearance_succeeded * wpi_weights['Metric Specific'][Category]['Aerial Clearance Succeeded'] +
        intervention * wpi_weights['Metric Specific'][Category]['Intervention'] +
        control_under_pressure * wpi_weights['Metric Specific'][Category]['Control Under Pressure'] +
        goal_kick_succeeded * wpi_weights['Metric Specific'][Category]['Goal Kick Succeeded'] 
    )

    # Calculate goal_keeping score
    goal_keeping_score =  (weighted_sum / play_time) * MAX_GAME_TIME

    # Age decline logic
    age_factor = max(1 - ((player_age - wpi_weights['Decline Rate'][Category]['Peak Age']) / wpi_weights['Decline Rate'][Category]['Decline Rate']), 0)
    
    # Final calculation with scaling factor and shift
    scaling_factor = 1.0
    shift_value = 0
    score = (goal_keeping_score * age_factor) * scaling_factor + shift_value

    # Round and multiply by 100
    final_score = round(max(score, 0) * 100)
    
    return final_score


def calculate_overall_score(
                        pace, 
                        shooting, 
                        passing, 
                        dribbling, 
                        defending, 
                        physicality, 
                        game_intelligence, 
                        composure, 
                        goal_keeping,
                        player_position,
                        wpi_weights=WPI_WEIGHTS
                    ):
    Category = "Overall Score"

    # Calculate weighted sum
    weighted_sum = (
        pace * wpi_weights[Category]['Pace'] +
        shooting * wpi_weights[Category]['Shooting'] +
        passing * wpi_weights[Category]['Passing'] +
        dribbling * wpi_weights[Category]['Dribbling'] +
        defending * wpi_weights[Category]['Defending'] +
        physicality * wpi_weights[Category]['Physicality'] +
        game_intelligence * wpi_weights[Category]['Game Intelligence'] +
        composure * wpi_weights[Category]['Composure'] +
        goal_keeping * wpi_weights[Category]['Goal Keeping'] if player_position == 'GK' else 0
    )

    total_weight = sum(value for key, value in wpi_weights[Category].items() if key != 'Goal Keeping')

    total_weight += wpi_weights[Category]['Goal Keeping'] if player_position == 'GK' else 0

    # Prevent division by zero for total weight
    normalized_weighted_sum = (
        weighted_sum / total_weight if total_weight != 0 else 0
    )

    # Final calculation with scaling factor and shift
    scaling_factor = 1.0
    shift_value = 0
    score = (normalized_weighted_sum) * scaling_factor + shift_value

    # Round and multiply by 100
    final_score = round(score * 100)
    
    return final_score