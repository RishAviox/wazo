import pandas as pd
import json
from .utils import *
from .models import GameMetaData


# process on GameVideoData
def generate_game_meta_data_json(instance, game):
    padding_time = {
        "PADDING_START_TIME_FIRST_HALF": instance.first_half_padding * 1000,
        "PADDING_START_TIME_SECOND_HALF": instance.second_half_padding * 1000,
        "PADDING_END_TIME_FIRST_HALF": instance.first_half_padding * 1000,
        "PADDING_END_TIME_SECOND_HALF": instance.second_half_padding * 1000,
        "START_TIME_PADDING": instance.start_time_padding * 1000,
        "END_TIME_PADDING": instance.end_time_padding * 1000,
    }

    match_details_df = pd.read_excel(instance.data_file, sheet_name="MatchDetails")
    teams = generate_teams_json(match_details_df)

    # Map team_id to team_name
    team_mapping = {
        teams[0]["team_id"]: teams[0]["team_name"],
        teams[1]["team_id"]: teams[1]["team_name"],
    }

    # Read player data
    home_team_players_df = pd.read_excel(
        instance.data_file, sheet_name="Players_137183"
    )
    away_team_players_df = pd.read_excel(
        instance.data_file, sheet_name="Players_137183_2"
    )
    players_df = pd.concat(
        [home_team_players_df, away_team_players_df], ignore_index=True
    )

    # Read event data
    event_data_df = pd.read_excel(instance.data_file, sheet_name="EventData_137183")

    sequence_data_df = pd.read_excel(
        instance.data_file, sheet_name="SequenceData_137183"
    )
    sequence_data_df["event_ids_list"] = sequence_data_df["event_ids"].apply(
        lambda x: list(map(int, x.split(",")))
    )

    # Generate goals JSON
    goals = generate_goals_json(
        event_data_df, team_mapping, players_df, sequence_data_df, padding_time
    )

    # Generate highlights JSON
    highlights = generate_highlights_json(
        event_data_df, team_mapping, players_df, sequence_data_df, padding_time
    )

    # Load reference dataframe
    reference_df = pd.read_json("games/constants.json", orient="index").reset_index()

    # Generate Event Details JSON
    events = generate_event_details_json(
        event_data_df,
        team_mapping,
        players_df,
        sequence_data_df,
        padding_time,
        reference_df,
    )

    # Generate Video urls JSON
    video_urls = {
        "highlights_url": instance.highlights_url,
        "first_half_url": instance.first_half_url,
        "second_half_url": instance.second_half_url,
    }

    # Merge all JSON responses to one
    overall_outcome = {
        "teams": teams,
        "goals": goals,
        "highlights": highlights,
        "events_details": events,
        "video_urls": video_urls,
    }

    # Save the JSON data to the GameMetaData model
    GameMetaData.objects.update_or_create(game=game, defaults={"data": overall_outcome})
