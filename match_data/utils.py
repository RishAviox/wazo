from django.db.models import Q

from teams.models import Team
from accounts.models import WajoUser
from games.models import Game

from .models import *


def get_match(match_id: int):
    try:
        return BeproMatchData.objects.get(match_id=match_id)
    except BeproMatchData.DoesNotExist:
        return


def get_match_details(match: BeproMatchData):
    return BeproMatchDetail.objects.filter(match_id=match)


def get_key_match_events(events: BeproMatchDetail):
    return events.filter(
        Q(outcome__iexact='goal') | Q(sub_event_type__iexact='red card')
    )


def generate_key_match_events_obj(events):
    event_list = []
    for obj in events:
        player_id = obj.player_id
        try:
            player = BeproPlayer.objects.get(record_id=player_id)
        except BeproPlayer.DoesNotExist:
            continue
        event_list.append(
            {
                "time": f"{int(int(obj.event_time) / (1000 * 60))}'",
                "event": f"{obj.outcome}: [{player.player_name_en} {player.player_last_name_en}] ({obj.event_type})",
                "insight": "Effective midfield build-up led to a clinical finish."
            }
        )
    return event_list


def get_final_score(match: BeproMatchData, team: Team):
    if match.home_team_id == team.id:
        return f"{match.home_team_name} {match.home_team_score}-{match.away_team_score} {match.away_team_name}"
    
    return f"{match.away_team_name} {match.away_team_score}-{match.home_team_score} {match.home_team_name}"

def generate_performance_metric_obj(match: BeproMatchData, team: Team):
    team_stats = BeproTeamStat.objects.filter(match=match)

    if match.home_team_id == team.id:
        my_team = team_stats.get(team_id=match.home_team_id)
        opponent_team = team_stats.get(team_id=match.away_team_id)
    else:
        my_team = team_stats.get(team_id=match.away_team_id)
        opponent_team = team_stats.get(team_id=match.home_team_id)

    metrics = [
        {
            "metric": "Possession (%)",
            "ourTeam": round(my_team.possession * 100, 1),
            "opponent": round(opponent_team.possession * 100, 1),
            "insight": "Your team controlled the tempo of the match."
        },
        {
            "metric": "Total Shots",
            "ourTeam": str(my_team.total_shot),
            "opponent": str(opponent_team.total_shot),
            "insight": "Created more chances but lacked clinical finishing."
        },
        {
            "metric": "Shots on Target",
            "ourTeam": str(my_team.shot_on_target),
            "opponent": str(opponent_team.shot_on_target),
            "insight": "Efficient shot-to-target ratio compared to the opponent."
        },
        {
            "metric": "Pass Accuracy (%)",
            "ourTeam": "88.5",
            "opponent": "77.6",
            "insight": "Precise passing helped maintain control."
        },
        {
            "metric": "Total Fouls",
            "ourTeam": str(my_team.foul),
            "opponent": str(opponent_team.foul),
            "insight": "Aggression disrupted rhythm but risked discipline."
        },
        {
            "metric": "Corners",
            "ourTeam": str(my_team.corner_kick),
            "opponent": str(opponent_team.corner_kick),
            "insight": "Set-piece opportunities provided an edge."
        },
        {
            "metric": "Offsides",
            "ourTeam": str(my_team.offside),
            "opponent": str(opponent_team.offside),
            "insight": "Frequent offside calls showed a need for timing improvement."
        },
        {
            "metric": "Expected Goals (xG)",
            "ourTeam": "2.31",
            "opponent": "1.12",
            "insight": "Exceeded xG expectations, reflecting clinical finishing."
        }
    ]

    return metrics


def get_historical_context(match: BeproMatchData, team: Team):
    team_stats = BeproTeamStat.objects.filter(match=match)

    if match.home_team_id == team.id:
        my_team = team_stats.get(team_id=match.home_team_id)
        opponent_team = team_stats.get(team_id=match.away_team_id)
    else:
        my_team = team_stats.get(team_id=match.away_team_id)
        opponent_team = team_stats.get(team_id=match.home_team_id)
    
    return {
        "recentResults": [
            "Our Team vs. Opponent last 5 results",
            "Our Team vs. Opponent last 5 results",
            "Our Team vs. Opponent last 5 results",
            "Our Team vs. Opponent last 5 results",
            "Our Team vs. Opponent last 5 results"
        ],
        "keyPlayerStats": {
        "playerA": "[Goals/assists vs. this opponent]",
        "playerB": "[Defensive actions in previous matches]"
        },
        "notableMoments": [
        "The last encounter ended in a thrilling 3-3 draw.",
        "Player A scored a brace in the previous matchup."
        ]
    }


def get_player(user_id: str):
    return WajoUser.objects.get(phone_no=user_id)

def get_my_team(player: WajoUser):
    coach = player.coach.first()
    return Team.objects.filter(coach=coach).first()

def get_latest_game(team: Team):
    return Game.objects.filter(teams=team).order_by('-created_on').first()


def get_player_rating():
    ratings = []
    player_stats = BeproPlayerStat.objects.filter(player_id__isnull=False).order_by('-rating')[:3]

    for player_stat in player_stats:
        player = BeproPlayer.objects.get(record_id=player_stat.player_id)
        ratings.append({
            "player": f"{player.player_name_en} {player.player_last_name_en}",
            "rating": round(player_stat.rating, 1),
            "contributions": "AI generated response..." # AI response
        })

    return ratings

def get_strengths_and_weakness():
    return [
      {
        "team": "Our Team",
        "strengths": "Dominated possession, effective pressing.",
        "weaknesses": "Turnovers in the midfield; gaps in transitions."
      },
      {
        "team": "Opponent",
        "strengths": "Quick counters; aerial strength.",
        "weaknesses": "Struggled under high pressing pressure."
      }
    ]

def get_tactical_adjustments():
    return {
        "forOurTeam": [
            "Introduce turnover management drills to reduce risky plays in midfield.",
            "Enhance defensive recovery with wide-area marking drills."
        ],
        "forOpponent": [
            "Focus on breaking the press with quick diagonal passes.",
            "Improve defensive shape under sustained pressure."
        ]
    }

def get_tactical_formation_breakdown():
    return {
        "startingFormation": "4-3-3 (High Press, Possession-Based)",
        "startingAnalysis": "Worked well in controlling midfield but exposed gaps in defensive transitions.",
        "formationAfterRedCard": "4-4-1 (Compact Defensive Shape)",
        "afterRedCardAnalysis": "Reduced offensive threat but stabilized defensive line.",
        "formationImpact": {
        "pressingEffectiveness": "75%",
        "defensiveTransitions": "45% (Vulnerable to quick counters)",
        "ballRecoveryTime": "8.5s (Slower than usual, needs improvement)"
        }
    }

def get_next_steps():
    return {
        "matchSummaryStats": "Full performance breakdown.",
        "keyTacticalInsights": "Strengths & weaknesses analysis",
        "individualPlayerPerformance": "Player ratings, contributions, and improvement areas.",
        "teamPerformanceOverview": "Trend analysis across matches.",
        "setPieceAnalysis": "Effectiveness on attacking & defensive set-pieces.",
        "fitnessRecoverySuggestions": "Tailored fatigue insights.",
        "trainingRecommendations": "Drills & strategies for improvement."
    }
