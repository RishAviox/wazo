# either sum or average of all the raw values then calculate metrics

def get_team_stats_sheet(stats_sheet):
    aggregation_dict = {col: 'sum' for col in stats_sheet.columns if col not in ['team_id', 'player_id', 'rating', 'play_time']}
    aggregation_dict.update({
        'rating': 'mean',  # Average rating
        'play_time': 'sum'  # Total play time
    })

    team_stats = stats_sheet.groupby('team_id').agg(aggregation_dict).reset_index()

    # Average Play Time per Player in minutes (/60,000)
    team_stats['play_time'] = team_stats['play_time'] / (stats_sheet['player_id'].nunique())

    # print("team_stats: ", team_stats)
    # team_stats.to_csv("test.csv")

    return team_stats


def get_team_gps_sheet(gps_sheet):
    skip_columns = ['Team ID', 'Player ID', 'MatchID', 'Date', 'Session ID', 'Session Name', 'Session Type' ]
    aggregation_dict = {col: 'sum' for col in gps_sheet.columns if col not in skip_columns }
    aggregation_dict.update({
        'Top Speed (km/h)': 'mean',
        'Kick Power (km/h)': 'mean',
        'Session Intensity': 'mean',
        'Session Intensity Speed': 'mean',
        'Session Intensity Acceleration': 'mean'
    })
    # Group by 'Team ID' and apply the aggregation
    team_gps = gps_sheet.groupby('Team ID').agg(aggregation_dict).reset_index()

    # Average Play Time per Player in minutes
    team_gps['Corrected Play Time (min)'] = team_gps['Corrected Play Time (min)'] /  gps_sheet['Player ID'].nunique()

    # print("team_gps: ", team_gps)
    # team_gps.to_csv("test_gps.csv")

    return team_gps