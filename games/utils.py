import pandas as pd
import logging

logger = logging.getLogger(__name__)


def add_padding(start_time: int, end_time: int, half: str, padding_time):
    if half == "FIRST_HALF":
        start_time = start_time - padding_time["START_TIME_PADDING"]
        end_time = end_time + padding_time["END_TIME_PADDING"]
    elif half == "SECOND_HALF":
        start_time = (
            start_time
            - padding_time["PADDING_START_TIME_SECOND_HALF"]
            - padding_time["START_TIME_PADDING"]
        )
        end_time = (
            end_time
            - padding_time["PADDING_END_TIME_SECOND_HALF"]
            + padding_time["END_TIME_PADDING"]
        )
    return start_time, end_time


def calculate_start_time_from_event_time(
    half: str, event_time: int, padding_time: dict
):
    if half.lower() == "first_half":
        start_time = int(event_time - padding_time["START_TIME_PADDING"])
    else:
        start_time = int(
            event_time
            - padding_time["PADDING_START_TIME_SECOND_HALF"]
            - padding_time["START_TIME_PADDING"]
        )

    return int(start_time)


def calculate_end_time_from_event_time(half: str, event_time: int, padding_time: dict):
    if half.lower() == "first_half":
        end_time = int(event_time + padding_time["END_TIME_PADDING"])
    else:
        end_time = int(
            event_time
            - padding_time["PADDING_START_TIME_SECOND_HALF"]
            + padding_time["END_TIME_PADDING"]
        )

    return int(end_time)


def convert_event_type_en_to_he(event: str):
    event_translations = {
        "Shot": "בְּעִיטָה",
        "Shots & Goals (all)": "בעיטות ושערים",
        "Goal": "שערים",
        "Goal Conceded": "ספיגות שערים",
        "Passes": "מסירות",
        "Crosses": "הגבהות",
        "Assists": "בישולים",
        "Key Passes": "מסירות מפתח",
        "Pass Received": "מסירות שהתקבלו",
        "Tackles": "תיקולים",
        "Aerial Clearances (all)": "ניקויים אוויריים",
        "Aerial Control": "שליטה אווירית",
        "Ball Received": "קבלת כדור",
        "Blocks": "חסימות",
        "Step-in": "התערבות הגנתית",
        "Clearances": "הרחקות",
        "Cross Received": "קבלת הגבהה",
        "Defensive Line Supports": "תמיכה בקו ההגנה",
        "Duels": "קרבות",
        "Duels (continued)": "דו קרב (המשך)",
        "Errors": "טעויות",
        "Fouls": "עבירות",
        "Interceptions": "חטיפת מסירה",
        "Interventions": "פעולות הגנתיות",
        "Offsides": "נבדלים",
        "Pauses": "עצירות משחק",
        "Recoveries": "השגת כדור חוזר",
        "Saves": "הצלות",
        "Set Pieces": "מצבים נייחים",
        "Substitutions": "חילופים",
    }
    return event_translations.get(event, event)


def convert_subevent_en_to_he(subevent):
    translations = {
        "Shot": "בְּעִיטָה",
        "Goals": "שערים",
        "Shots": "בעיטות",
        "On Target": "בעיטות למסגרת",
        "Off Target": "החטיא",
        "Missed Shots": "החמצות",
        "Goal Conceded": "שער שספג",
        "Goal": "שערים",
        "Blocked Shots": "בעיטות שנחסמו",
        "Keeper Rush-Out": "יציאת שוער",
        "Left Foot": "רגל שמאל",
        "Right Foot": "רגל ימין",
        "Header": "נגיחה",
        "Passes": "מסירות",
        "Successful": "הצלחה",
        "Failed": "נכשל",
        "Crosses": "הרמות",
        "Key Passes": "מסירות מפתח",
        "Assists": "בישולים",
        "Tackles": "תיקולים",
        "Aerial Clearances": "הרחקות אוויריות",
        "Unsuccessful": "לא מוצלח",
        "Successful Aerial Clearances": "הרחקות אוויריות מוצלחות",
        "Failed Aerial Clearances": "הרחקות אוויריות שנכשלו",
        "Successful Aerial Duels": "מאבקי אוויר מוצלחים",
        "Failed Aerial Duels": "מאבקי אוויר שנכשלו",
        "Defensive Line Supports": "תמיכה בקו ההגנה",
        "Duels": "מאבקים",
        "Ground": "מאבקי קרקע",
        "Aerial": "מאבקי אוויר",
        "Loose Balls": "כדורים חופשיים",
        "Errors": "טעויות",
        "Fouls": "עבירות",
        "Foul Wons": "עבירות שהושגו",
        "Yellow Cards": "כרטיסים צהובים",
        "Red Cards": "כרטיסים אדומים",
        "Pauses": "הפסקות",
        "Saves": "הצלות",
        "Parrys": "הדיפות",
        "Catches": "תפיסות",
        "Lower Body": "גוף תחתון",
        "Upper Body": "גוף עליון",
        "Hands": "ידיים",
        "Set Pieces": "מצבים נייחים",
        "Throw-In's": "חוץ",
        "Corners": "קרנות",
        "Free-kicks": "בעיטות חופשיות",
        "Goal Kicks": "בעיטות שוער",
        "Penalty Kicks": "בעיטות עונשין",
        "Substitutions": "חילופים",
        "On": "נכנס",
        "Off": "יצא",
    }
    return translations.get(subevent, subevent)


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
                start_time = calculate_start_time_from_event_time(
                    half, event_time, padding_time
                )
            if not end_time:
                end_time = calculate_end_time_from_event_time(
                    half, event_time, padding_time
                )
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


def generate_highlights_json(df, teams, players_df, sequence_df, padding_time):
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
                start_time = calculate_start_time_from_event_time(
                    half, event_time, padding_time
                )
            if not end_time:
                end_time = calculate_end_time_from_event_time(
                    half, event_time, padding_time
                )
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


def generate_event_details_json(
    df, teams, players_df, sequence_df, padding_time, reference_df
):
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

        mapped_events, sub_event = map_event_and_subevent(
            row, row.eventType, reference_df
        )

        for idx, event in enumerate(mapped_events):
            if not filtered_df.empty:
                event_time = int(row.event_time)
                if not start_time:
                    start_time = calculate_start_time_from_event_time(
                        half, event_time, padding_time
                    )
                if not end_time:
                    end_time = calculate_end_time_from_event_time(
                        half, event_time, padding_time
                    )

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
                        "eventTypeHe": convert_event_type_en_to_he(event),
                        "subEventTypeHe": convert_subevent_en_to_he(sub_event[idx]),
                        "half": half.lower(),
                    }
                )

    return events


def map_event_and_subevent(df, event_type, reference_df):
    if isinstance(event_type, str):
        event_type = event_type.strip()
    cols_list = []
    if event_type == "Pass":
        cols_list.append(
            ["eventType", "outcome", "cross", "keyPass", "assist", "bodyPart"]
        )
    if df["cross"] == True:
        cols_list.append(["cross", "outcome", "bodyPart"])
    if df["assist"] == True:
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
    if event_type in [
        "Pass Received",
        "Ball Received",
        "Block",
        "Carry",
        "Clearance",
        "Cross Received",
        "Error",
        "Interception",
        "Intervention",
        "Offside",
        "Pause",
        "Recovery",
    ]:
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
                if reference_df["index"].eq(header_name).any():
                    matching_rows = reference_df[reference_df["index"] == header_name]
                    for _, row in matching_rows.iterrows():
                        event_list.append(str(row["eventType"]))
                        sub_event_list.append(str(row["subEvent"]))
                        flag = True
        if flag:
            continue
        first_col = cols[0]

        for col in cols[1:]:
            header_name = f"{first_col}_{df[first_col]}, {col}_{df[col]}"
            if header_name.endswith("_True"):
                header_name = header_name.replace("_True", "_true")
            if reference_df["index"].eq(header_name).any():
                matching_rows = reference_df[reference_df["index"] == header_name]
                for _, row in matching_rows.iterrows():
                    event_list.append(str(row["eventType"]))
                    sub_event_list.append(str(row["subEvent"]))
                    flag = True

        if flag:
            continue

        header_name = f"{first_col}_{df[first_col]}"
        if header_name.endswith("_True"):
            header_name = header_name.replace("_True", "_true")
        if reference_df["index"].eq(header_name).any():
            matching_rows = reference_df[reference_df["index"] == header_name]
            for _, row in matching_rows.iterrows():
                event_list.append(str(row["eventType"]))
                sub_event_list.append(str(row["subEvent"]))

    return event_list, sub_event_list


def generate_video_urls() -> dict:
    return {
        "highlight_url": "https://hiwajovideov2.azureedge.net/videos/Jul 7, 2024 Haifa Goldshinfeld vs Bnei Sakhnin Highlights_2024-08-23_21-52-47.mp4",
        "first_half_url": "https://hiwajovideov2.azureedge.net/videos/Jul 7, 2024 Haifa Goldshinfeld vs Bnei Sakhnin 1st Half.mp4",
        "second_half_url": "https://hiwajovideov2.azureedge.net/videos/Jul 7, 2024 Haifa Goldshinfeld vs Bnei Sakhnin 2nd Half.mp4",
    }


def save_multilingual_data_to_game(
    excel_file_path, game_id, sync_to_trace_session=True
):
    """
    Extract multilingual data from Excel and save to Game.language_metadata.
    Optionally syncs to TraceSession and updates Team/Player multilingual data.

    Args:
        excel_file_path: Path to the Excel file containing multilingual match data
        game_id: Game ID to update (string)
        sync_to_trace_session: If True, also syncs data to TraceSession (default: True)

    Returns:
        Game instance with updated language_metadata

    Raises:
        Game.DoesNotExist: If game with given ID doesn't exist
        Exception: If extraction or saving fails
    """
    try:
        # Import here to avoid circular imports
        from tracevision.test_language import extract_multilingual_match_data
        from .models import Game

        # Extract multilingual data from Excel
        multilingual_data = extract_multilingual_match_data(excel_file_path)

        # Get game
        game = Game.objects.get(id=game_id)

        # Update language_metadata
        game.language_metadata = multilingual_data
        game.save()

        logger.info(f"Successfully saved multilingual data to Game {game_id}")

        # Sync to TraceSession if exists and requested
        if (
            sync_to_trace_session
            and hasattr(game, "trace_session")
            and game.trace_session
        ):
            game.trace_session.language_metadata = multilingual_data
            game.trace_session.save()
            logger.info(
                f"Synced multilingual data to TraceSession {game.trace_session.id}"
            )

        # Update Team and Player multilingual data
        update_team_and_player_multilingual_data(game, multilingual_data)

        return game

    except Game.DoesNotExist:
        logger.error(f"Game with ID {game_id} does not exist")
        raise
    except Exception as e:
        logger.error(f"Error saving multilingual data to Game {game_id}: {str(e)}")
        raise


def update_team_and_player_multilingual_data(game, multilingual_data):
    """
    Extract and update multilingual data for Teams and TracePlayers from the full match data.

    Args:
        game: Game instance
        multilingual_data: Full multilingual match data dictionary
    """
    try:
        from teams.models import Team
        from tracevision.models import TracePlayer, TraceSession

        en_data = multilingual_data.get("en", {})
        he_data = multilingual_data.get("he", {})

        # Get team names from match summary
        en_summary = en_data.get("Match_summary", {})
        he_summary = he_data.get("Match_summary", {})

        home_team_name_en = en_summary.get("match_home_team", "")
        away_team_name_en = en_summary.get("match_away_team", "")
        home_team_name_he = he_summary.get("match_home_team", "")
        away_team_name_he = he_summary.get("match_away_team", "")

        # Update Team multilingual names
        if home_team_name_en:
            try:
                home_team = Team.objects.get(name=home_team_name_en)
                home_team.language_metadata = {
                    "en": home_team_name_en,
                    "he": home_team_name_he,
                }
                home_team.save()
                logger.info(f"Updated multilingual names for Team {home_team.id}")
            except Team.DoesNotExist:
                logger.warning(f"Team '{home_team_name_en}' not found in database")

        if away_team_name_en:
            try:
                away_team = Team.objects.get(name=away_team_name_en)
                away_team.language_metadata = {
                    "en": away_team_name_en,
                    "he": away_team_name_he,
                }
                away_team.save()
                logger.info(f"Updated multilingual names for Team {away_team.id}")
            except Team.DoesNotExist:
                logger.warning(f"Team '{away_team_name_en}' not found in database")

        # Update TracePlayer multilingual data
        en_lineups = en_data.get("starting_lineups", {})
        he_lineups = he_data.get("starting_lineups", {})

        # Get TraceSession if exists
        trace_session = None
        if hasattr(game, "trace_session") and game.trace_session:
            trace_session = game.trace_session

        if trace_session:
            for team_name_en, players_en in en_lineups.items():
                # Find corresponding Hebrew team name
                team_name_he = None
                for he_team_name in he_lineups.keys():
                    # Try to match by position (first team = home, second = away)
                    if list(en_lineups.keys()).index(team_name_en) == list(
                        he_lineups.keys()
                    ).index(he_team_name):
                        team_name_he = he_team_name
                        break

                if not team_name_he:
                    team_name_he = (
                        list(he_lineups.keys())[0] if he_lineups else team_name_en
                    )

                players_he = he_lineups.get(team_name_he, {})

                # Update each player
                for jersey_num, player_data_en in players_en.items():
                    try:
                        jersey_int = int(jersey_num)
                        player_data_he = players_he.get(jersey_num, {})

                        # Find TracePlayer by session and jersey number
                        trace_player = TracePlayer.objects.filter(
                            session=trace_session, jersey_number=jersey_int
                        ).first()

                        if trace_player:
                            # Auto-create WajoUser for player if not exists
                            if not trace_player.user:
                                player_name = player_data_en.get(
                                    "name", "Unknown Player"
                                )
                                # Check if a user with this name already exists as a Player
                                user = WajoUser.objects.filter(
                                    name=player_name, role="Player"
                                ).first()
                                if not user:
                                    user = WajoUser.objects.create(
                                        name=player_name,
                                        role="Player",
                                        is_registered=False,
                                        created_via="EXCEL",
                                    )
                                    logger.info(
                                        f"Auto-created WajoUser for Player (placeholder): {player_name}"
                                    )
                                trace_player.user = user
                                trace_player.save()

                            trace_player.language_data = {
                                "en": {
                                    "name": player_data_en.get("name", ""),
                                    "role": player_data_en.get("role", ""),
                                },
                                "he": {
                                    "name": player_data_he.get("name", ""),
                                    "role": player_data_he.get("role", ""),
                                },
                            }
                            trace_player.save()
                            logger.debug(
                                f"Updated multilingual data for TracePlayer {trace_player.id} (jersey #{jersey_num})"
                            )
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            f"Invalid jersey number '{jersey_num}': {str(e)}"
                        )
                        continue

            # Auto-create Coaches and Referees from Match_summary
            # Coaches
            coaches_en = en_summary.get("match_coaches", [])
            if isinstance(coaches_en, list):
                for coach_name in coaches_en:
                    coach_user, created = WajoUser.objects.get_or_create(
                        name=coach_name,
                        role="Coach",
                        defaults={"is_registered": False, "created_via": "EXCEL"},
                    )
                    if created:
                        logger.info(
                            f"Auto-created WajoUser for Coach (placeholder): {coach_name}"
                        )

                    # Link to appropriate team if possible
                    if home_team_name_en in coach_name or any(
                        home_team_name_en in s for s in coach_name.split()
                    ):
                        try:
                            home_team = Team.objects.get(name=home_team_name_en)
                            home_team.coach.add(coach_user)
                        except Team.DoesNotExist:
                            pass
                    elif away_team_name_en in coach_name or any(
                        away_team_name_en in s for s in coach_name.split()
                    ):
                        try:
                            away_team = Team.objects.get(name=away_team_name_en)
                            away_team.coach.add(coach_user)
                        except Team.DoesNotExist:
                            pass

            # Referees
            referees_en = en_summary.get("match_referees", [])
            if isinstance(referees_en, list):
                for referee_name in referees_en:
                    referee_user, created = WajoUser.objects.get_or_create(
                        name=referee_name,
                        role="Referee",
                        defaults={"is_registered": False, "created_via": "EXCEL"},
                    )
                    if created:
                        logger.info(
                            f"Auto-created WajoUser for Referee (placeholder): {referee_name}"
                        )

                    # Link to the game
                    game.referees.add(referee_user)

    except Exception as e:
        logger.error(f"Error updating team and player multilingual data: {str(e)}")
        # Don't raise - this is a non-critical operation


def filter_language_metadata_for_model(multilingual_data, model_fields):
    """
    Filter language_metadata to only include fields that exist in the model.

    Args:
        multilingual_data: Full multilingual data dictionary with 'en' and 'he' keys
        model_fields: List of field names that exist in the model

    Returns:
        dict: Filtered language_metadata containing only model fields
    """
    filtered_data = {"en": {}, "he": {}}

    en_data = multilingual_data.get("en", {})
    he_data = multilingual_data.get("he", {})

    # Extract match summary data
    en_summary = en_data.get("Match_summary", {})
    he_summary = he_data.get("Match_summary", {})

    for field in model_fields:
        if field == "name":
            # Game name: combine home and away team names
            home_team_en = en_summary.get("match_home_team", "")
            away_team_en = en_summary.get("match_away_team", "")
            filtered_data["en"][field] = (
                f"{home_team_en} vs {away_team_en}"
                if home_team_en and away_team_en
                else ""
            )

            home_team_he = he_summary.get("match_home_team", "")
            away_team_he = he_summary.get("match_away_team", "")
            filtered_data["he"][field] = (
                f"{home_team_he} vs {away_team_he}"
                if home_team_he and away_team_he
                else ""
            )

        elif field == "date":
            filtered_data["en"][field] = en_summary.get("match_date", "")
            filtered_data["he"][field] = he_summary.get("match_date", "")

        elif field == "teams":
            # Teams as list
            home_team_en = en_summary.get("match_home_team", "")
            away_team_en = en_summary.get("match_away_team", "")
            filtered_data["en"][field] = (
                [home_team_en, away_team_en] if home_team_en and away_team_en else []
            )

            home_team_he = he_summary.get("match_home_team", "")
            away_team_he = he_summary.get("match_away_team", "")
            filtered_data["he"][field] = (
                [home_team_he, away_team_he] if home_team_he and away_team_he else []
            )

        elif field == "match_date":
            filtered_data["en"][field] = en_summary.get("match_date", "")
            filtered_data["he"][field] = he_summary.get("match_date", "")

        elif field == "home_score":
            filtered_data["en"][field] = en_summary.get("match_home_goals", 0)
            filtered_data["he"][field] = he_summary.get("match_home_goals", 0)

        elif field == "away_score":
            filtered_data["en"][field] = en_summary.get("match_away_goals", 0)
            filtered_data["he"][field] = he_summary.get("match_away_goals", 0)

        elif field == "home_team":
            filtered_data["en"][field] = en_summary.get("match_home_team", "")
            filtered_data["he"][field] = he_summary.get("match_home_team", "")

        elif field == "away_team":
            filtered_data["en"][field] = en_summary.get("match_away_team", "")
            filtered_data["he"][field] = he_summary.get("match_away_team", "")

        elif field == "age_group":
            filtered_data["en"][field] = en_summary.get("match_age_group", "")
            filtered_data["he"][field] = he_summary.get("match_age_group", "")

        elif field == "pitch_size":
            field_length = en_summary.get("match_field_length", "")
            field_width = en_summary.get("match_field_width", "")
            filtered_data["en"][field] = {"length": field_length, "width": field_width}
            field_length_he = he_summary.get("match_field_length", "")
            field_width_he = he_summary.get("match_field_width", "")
            filtered_data["he"][field] = {
                "length": field_length_he,
                "width": field_width_he,
            }

        elif field == "final_score":
            filtered_data["en"][field] = en_summary.get("match_full_time_score", "")
            filtered_data["he"][field] = he_summary.get("match_full_time_score", "")

        elif field == "match_start_time":
            filtered_data["en"][field] = en_summary.get("match_time", "")
            filtered_data["he"][field] = he_summary.get("match_time", "")

        elif field == "first_half_end_time":
            # Extract from half-time score or use match_time
            filtered_data["en"][field] = en_summary.get("match_half_time_score", "")
            filtered_data["he"][field] = he_summary.get("match_half_time_score", "")

        elif field == "second_half_start_time":
            # Same as first_half_end_time
            filtered_data["en"][field] = en_summary.get("match_half_time_score", "")
            filtered_data["he"][field] = he_summary.get("match_half_time_score", "")

        elif field == "match_end_time":
            filtered_data["en"][field] = en_summary.get("match_full_time_score", "")
            filtered_data["he"][field] = he_summary.get("match_full_time_score", "")

        else:
            # Try to get directly from summary if field name matches
            if field in en_summary:
                filtered_data["en"][field] = en_summary.get(field)
            if field in he_summary:
                filtered_data["he"][field] = he_summary.get(field)

    return filtered_data
