import pandas as pd

def add_padding(start_time: int, end_time: int, half: str, padding_time):
    if half == "FIRST_HALF":
        start_time = start_time - padding_time['START_TIME_PADDING']
        end_time = end_time + padding_time['END_TIME_PADDING']
    elif half == "SECOND_HALF":
        start_time = start_time - padding_time['PADDING_START_TIME_SECOND_HALF'] - padding_time['START_TIME_PADDING']
        end_time = end_time - padding_time['PADDING_END_TIME_SECOND_HALF'] + padding_time['END_TIME_PADDING']
    return start_time, end_time


def convert_event_type_en_to_he(event: str):
    event_in_he = ""
    if event == "Shots & Goals (all)":
        event_in_he = "בעיטות ושערים"
    elif event == "Goal":
        event_in_he = "שערים"
    elif event == "Goal Conceded":
        event_in_he = "ספיגות שערים"
    elif event == "Passes":
        event_in_he = "מסירות"
    elif event == "Crosses":
        event_in_he = "הגבהות"
    elif event == "Assists":
        event_in_he = "בישולים"
    elif event == "Key Passes":
        event_in_he = "מסירות מפתח"
    elif event == "Pass Received":
        event_in_he = "מסירות שהתקבלו"
    elif event == "Tackles":
        event_in_he = "תיקולים"
    elif event == "Aerial Clearances (all)":
        event_in_he = "ניקויים אוויריים"
    elif event == "Aerial Control":
        event_in_he = "שליטה אווירית"
    elif event == "Ball Received":
        event_in_he = "קבלת כדור"
    elif event == "Blocks":
        event_in_he = "חסימות"
    elif event == "Step-in":
        event_in_he = "התערבות הגנתית"
    elif event == "Clearances":
        event_in_he = "הרחקות"
    elif event == "Cross Received":
        event_in_he = "קבלת הגבהה"
    elif event == "Defensive Line Supports":
        event_in_he = "תמיכה בקו ההגנה"
    elif event == "Duels":
        event_in_he = "קרבות"
    elif event == "Duels (continued)":
        event_in_he = "דו קרב (המשך"
    elif event == "Errors":
        event_in_he = "טעויות"
    elif event == "Fouls":
        event_in_he = "עבירות"
    elif event == "Interceptions":
        event_in_he = "חטיפת מסירה"
    elif event == "Interventions":
        event_in_he = "פעולות הגנתיות"
    elif event == "Offsides":
        event_in_he = "נבדלים"
    elif event == "Pauses":
        event_in_he = "עצירות משחק"
    elif event == "Recoveries":
        event_in_he = "השגת כדור חוזר"
    elif event == "Saves":
        event_in_he = "הצלות"
    elif event == "Set Pieces":
        event_in_he = "מצבים נייחים"
    elif event == "Substitutions":
        event_in_he = "חילופים"
    return event_in_he

def convert_subevent_en_to_he(subevent):
    subevent_in_he = ""
    if subevent == "Missed Shots":
        subevent_in_he = "החמצות"
    elif subevent == "On Target":
        subevent_in_he = "למסגרת"
    elif subevent == "Off Target":
        subevent_in_he = "החטיא"
    return subevent_in_he


def generate_teams_json(df: pd.DataFrame) -> list[dict]:
    """Generates JSON structure for home and away teams."""
    teams = [
        {
            "team_id": str(df["home_team.id"].iloc[0]),
            "team_name": df["home_team.name"].iloc[0],
            "logo_url": "https://upload.wikimedia.org/wikipedia/vi/thumb/a/a1/Man_Utd_FC_.svg/882px-Man_Utd_FC_.svg.png?20230723221716",
        },
        {
            "team_id": str(df["away_team.id"].iloc[0]),
            "team_name": df["away_team.name"].iloc[0],
            "logo_url": "https://e7.pngegg.com/pngimages/268/475/png-clipart-leicester-city-football-club-logo-king-power-stadium-leicester-city-f-c-premier-league-manchester-city-f-c-a-f-c-bournemouth-arsenal-f-c-logo-transfer-thumbnail.png",
        },
    ]
    return teams


def generate_goals_json(df, teams, players_df, sequence_df, padding_time):
    """Generates JSON structure for goals scored."""
    goals = []
    df_goals = df[df["eventType"] == "Goal Conceded"]  # Filter relevant events

    for row in df_goals.itertuples():
        half = row.event_period
        filtered_df = players_df[players_df["id"] == row.player_id]
        sequence_filter_df = sequence_df[
            (
                sequence_df["event_ids_list"].apply(
                    lambda event_list: row.id in event_list
                )
            )
        ]
        if not sequence_filter_df.empty:
            start_time = int(sequence_filter_df["start_time"].iloc[0])
            end_time = int(sequence_filter_df["end_time"].iloc[0])
            start_time, end_time = add_padding(start_time, end_time, half, padding_time)
        else:
            start_time = None
            end_time = None
            
        if not filtered_df.empty:
            event_time = int(row.event_time)
            if not start_time:
                start_time = int(event_time - padding_time['START_TIME_PADDING'])
            if not end_time:
                end_time = int(event_time + padding_time['END_TIME_PADDING'])
            goals.append(
                {
                    "team_id": str(int(row.team_id)),
                    "team_name": teams.get(str(int(row.team_id)), "Unknown"),
                    "player_id": str(int(row.player_id)),
                    "player_name": filtered_df["player_name_en"].iloc[0],
                    "event_time": event_time,
                    "start_time": 0 if start_time < 0 else start_time,
                    "end_time": end_time,
                    "half": half.lower(),
                }
            )

    return goals


def generate_highlights_json( df, teams, players_df, sequence_df, padding_time):
    """Generates JSON for highlights i.e, Shot - 'Off Target', 'On Target', 'Goal'"""
    highlights = []
    df_highlights = df[
        (df["eventType"] == "Shot")
        & (
            (df["outcome"] == "Off Target")
            | (df["outcome"] == "On Target")
            | (df["outcome"] == "Goal")
        )
    ]

    for row in df_highlights.itertuples():
        half = row.event_period
        filtered_df = players_df[players_df["id"] == row.player_id]
        sequence_filter_df = sequence_df[
            (
                sequence_df["event_ids_list"].apply(
                    lambda event_list: row.id in event_list
                )
            )
        ]
        if not sequence_filter_df.empty:
            start_time = int(sequence_filter_df["start_time"].iloc[0])
            end_time = int(sequence_filter_df["end_time"].iloc[0])
            start_time, end_time = add_padding(start_time, end_time, half, padding_time)
        else:
            start_time = None
            end_time = None
        if not filtered_df.empty:
            event_time = int(row.event_time)
            if not start_time:
                start_time = int(event_time - padding_time['START_TIME_PADDING'])
            if not end_time:
                end_time = int(event_time + padding_time['END_TIME_PADDING'])
            event_type = row.eventType
            sub_event_type = row.outcome

            highlights.append(
                {
                    "team_id": str(int(row.team_id)),
                    "team_name": teams.get(str(int(row.team_id)), "Unknown"),
                    "player_id": str(int(row.player_id)),
                    "player_name": filtered_df["player_name_en"].iloc[0],
                    "start_time": 0 if start_time < 0 else start_time,
                    "end_time": end_time,
                    "eventType": event_type,
                    "subEventType": sub_event_type,
                    "eventTypeHe": convert_event_type_en_to_he(event_type),
                    "subEventTypeHe": convert_subevent_en_to_he(sub_event_type),
                    "half": half.lower(),
                }
            )

    return highlights


def generate_event_details_json(df, teams, players_df, sequence_df, padding_time, reference_df):
    """Generates JSON of all events"""
    events = []

    for idx, row in df.iterrows():
        half = row.event_period
        try:
            # If player id not found then pass that iteration
            filtered_df = players_df[players_df["id"] == int(row.player_id)]
        except ValueError:
            continue

        sequence_filter_df = sequence_df[
            (
                sequence_df["event_ids_list"].apply(
                    lambda event_list: row.id in event_list
                )
            )
        ]
        if not sequence_filter_df.empty:
            start_time = int(sequence_filter_df["start_time"].iloc[0])
            end_time = int(sequence_filter_df["end_time"].iloc[0])
            start_time, end_time = add_padding(start_time, end_time, half, padding_time)
        else:
            start_time = None
            end_time = None
        
        mapped_events, sub_event = map_event_and_subevent(row, row.eventType, reference_df)

        for idx, event in enumerate(mapped_events):
            if not filtered_df.empty:
                event_time = int(row.event_time)
                if not start_time:
                    start_time = int(event_time - padding_time['START_TIME_PADDING'])
                if not end_time:
                    end_time = int(event_time + padding_time['END_TIME_PADDING'])

                events.append(
                    {
                        "team_id": str(int(row.team_id)),
                        "team_name": teams.get(str(int(row.team_id)), "Unknown"),
                        "player_id": str(int(row.player_id)),
                        "player_name": filtered_df["player_name_en"].iloc[0],
                        "start_time": 0 if start_time < 0 else start_time,
                        "end_time": end_time,
                        "eventType": event,
                        "subEventType": sub_event[idx],
                        "half": half.lower(),
                    }
                )

    return events


def map_event_and_subevent(df, event_type, reference_df):
    if isinstance(event_type, str):
        event_type = event_type.strip()
    cols_list = []
    if event_type == "Pass":
        cols_list.append(["eventType", "outcome", "cross", "keyPass", "assist", "bodyPart"])
    if df['cross'] == True:
        cols_list.append(["cross", "outcome", "bodyPart"])
    if df['assist'] == True:
        cols_list.append(["assist"])
    if df["keyPass"] == True:
        cols_list.append(["keyPass"])
    if event_type == "Shot":
        cols_list.append(["eventType", "outcome", "subEventType", "bodyPart"])
    if event_type == "Goal Conceded":
        cols_list.append(["eventType"])
    if event_type == "Tackle":
        cols_list.append(["eventType", "outcome"])
    if event_type == "Aerial Clearance":
        cols_list.append(["eventType", "outcome"])
        cols_list.append(["subEventType", "outcome"])
    if event_type in ["Pass Received", "Ball Received", "Block", "Carry", "Clearance", "Cross Received", "Error", "Interception", "Intervention", "Offside", "Pause", "Recovery"]:
        cols_list.append(["eventType"])
    if event_type == "Defensive Line Support":
        cols_list.append(["eventType", "outcome"])
    if event_type == "Duel":
        cols_list.append(["eventType", "subEventType"])
    if event_type == "Foul":
        cols_list.append(["eventType", "subEventType", "outcome"])
    if event_type == "Save":
        cols_list.append(["eventType", "subEventType", "bodyPart"])
    if event_type == "Set Piece":
        cols_list.append(["eventType", "subEventType"])
    if event_type == "Substitution":
        cols_list.append(["eventType", "outcome"])
    
    event_list = []
    sub_event_list = []

    for cols in cols_list:
        flag = False
    
        if len(cols) == 1:
            for col in cols:
                header_name = f"{col}_{df[col]}"
                if header_name.endswith("_True"):
                    header_name = header_name.replace("_True", "_true")
                if reference_df['index'].eq(header_name).any():
                    matching_rows = reference_df[reference_df['index'] == header_name]
                    for _, row in matching_rows.iterrows():
                        event_list.append(str(row['eventType']))
                        sub_event_list.append(str(row['subEvent']))
                        flag = True
        if flag:
            continue
        first_col = cols[0]

        for col in cols[1:]:
            header_name = f"{first_col}_{df[first_col]}, {col}_{df[col]}"
            if header_name.endswith("_True"):
                header_name = header_name.replace("_True", "_true")
            if reference_df['index'].eq(header_name).any():
                matching_rows = reference_df[reference_df['index'] == header_name]
                for _, row in matching_rows.iterrows():
                    event_list.append(str(row['eventType']))
                    sub_event_list.append(str(row['subEvent']))
                    flag = True
        
        if flag:
            continue
        
        header_name = f"{first_col}_{df[first_col]}"
        if header_name.endswith("_True"):
            header_name = header_name.replace("_True", "_true")
        if reference_df['index'].eq(header_name).any():
            matching_rows = reference_df[reference_df['index'] == header_name]
            for _, row in matching_rows.iterrows():
                event_list.append(str(row['eventType']))
                sub_event_list.append(str(row['subEvent']))
    
    return event_list, sub_event_list


def generate_video_urls() -> dict:
    return {
        "highlight_url": "https://hiwajovideov2.azureedge.net/videos/Jul 7, 2024 Haifa Goldshinfeld vs Bnei Sakhnin Highlights_2024-08-23_21-52-47.mp4",
        "first_half_url": "https://hiwajovideov2.azureedge.net/videos/Jul 7, 2024 Haifa Goldshinfeld vs Bnei Sakhnin 1st Half.mp4",
        "second_half_url": "https://hiwajovideov2.azureedge.net/videos/Jul 7, 2024 Haifa Goldshinfeld vs Bnei Sakhnin 2nd Half.mp4",
    }
