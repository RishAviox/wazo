from django.db.models import Q

from teams.models import Team
from accounts.models import WajoUser
from accounts.utils import find_user_by_phone
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
        text = f"{obj.outcome}: [{player.player_name_en} {player.player_last_name_en}] ({obj.event_type})"
        if obj.outcome.lower() == 'goal':
            text = f"⚽ " + text
        elif obj.outcome.lower() == 'red card':
            text = f"🔵 " + text
        event_list.append(
            {
                "time": f"{int(int(obj.event_time) / (1000 * 60))}'",
                "event": text,
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
    user = find_user_by_phone(user_id)
    if not user:
        raise WajoUser.DoesNotExist(f"User with phone number {user_id} not found")
    return user

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


class MatchOverView:
    # Need to be removed once llm responses integrated
    def __init__(self):
        pass

    def get_match_overview(self, lang='en'):
        report = PostMatchAnalysis.objects.first()
        if lang == "he":
            return report.overview_json_he
        return report.overview_json


class KeyTacticalInsightReport:
    def __init__(self):
        pass

    @staticmethod
    def __get_wajo_summary():
        # TODO: Need to generate AI response
        return  "Our pressing efficiency and compact defensive structure early in the game created critical opportunities, but late-game fatigue and missed marking allowed the opponent to exploit gaps. Quick counters showed promise, yet finishing in the final third remains inconsistent. Let’s tighten up transitions and sustain pressing coordination throughout the match."


    @staticmethod
    def __get_phase_analysis():
        return [
        {
            "phase": "Pressing Efficiency",
            "ourTeamPerformance": "72% success; high recoveries in midfield",
            "opponentPerformance": "Pressing disrupted in the final third",
            "outcome": "Created a critical turnover in the 65th minute that led to a goal-scoring opportunity.",
        },
        {
            "phase": "Defensive Transitions",
            "ourTeamPerformance": "Compact shape; minor lapse in the 42nd minute",
            "opponentPerformance": "Gaps in wide areas during counters",
            "outcome": "Opponent’s goal resulted from a missed marking in a crucial moment.",
        },
        {
            "phase": "Offensive Transitions",
            "ourTeamPerformance":
            "Quick counters; missed execution in the final third",
            "opponentPerformance": "Struggled with overloads",
            "outcome": "Missed high-quality chance in the 78th minute due to rushed decision-making.",
        },
    ]

    @staticmethod
    def __get_video_highlights():
        return {
            "pressingEfficiency": "[Insert Link]",
            "missedDefensiveMarkIn42": "[Insert Link]",
            "counterattackin78": "[Insert Link]",
        }


    @staticmethod
    def __get_tactical_takeaways():
        return {
            "pressingStrength": [
                "Our pressing disrupted the opponent’s rhythm, creating turnovers in critical areas.",
                "Late-game pressing dropped due to fatigue, impacting efficiency.",
            ],
            "defensiveLapses": [
                "We maintained a compact defensive shape early on, but wide-area gaps during transitions led to the opponent’s goal.",
            ],
            "offensiveOpportunities": [
                "Quick counters showed promise, but rushed decision-making and execution problems in the final third left opportunities on the table.",
            ],
        }


    @staticmethod
    def __get_wajo_suggestions():
        return {
            "improvePressingCoordination": [
                "Add positional pressing drills to improve synchronization across all players, especially in fatigue scenarios.",
            ],
            "strengthenDefensiveTransitions": [
                "Focus on recovery drills and defensive marking exercises to address gaps in wide areas.",
            ],
            "sharpenOffensiveExecution": [
                "Incorporate situational finishing drills to improve composure and decision-making during quick counterattacks.",
            ],
        }


    @staticmethod
    def __get_next_metrics():
        return {
            "IndividualPlayerPerformance": "Identify and analyze top performers and areas for improvement among the squad.",
            "teamPerformanceOverview": "Broaden the lens to uncover team-wide strengths, trends, and challenges.",
            "setPieceAnalysis": "Review our set-piece performance to refine strategies.",
        }


    def get_tactical_insights_report(self, lang: str = "en"):
        # Need to be removed once llm responses integrated
        if lang == "he":
            analysis = PostMatchAnalysis.objects.first()
            return analysis.key_tactical_insight_report_json_he

        response = {}

        response['wajoSummary'] = __class__.__get_wajo_summary()
        response['phaseAnalysis'] = __class__.__get_phase_analysis()
        response['videoHighlights'] = __class__.__get_video_highlights()
        response['keyTacticalTakeaways'] = __class__.__get_tactical_takeaways()
        response['wajoSuggestions'] = __class__.__get_wajo_suggestions()
        response['whatsNext'] = __class__.__get_next_metrics()

        return response


class IndividualPlayerPerformanceReport:
    def __init__(self):
        pass

    @staticmethod
    def __get_wajo_summary():
        return "Top performers like Midfielder A and Winger B carried the game with their creativity and explosiveness, while lapses in defensive focus and distribution from Defender D and Goalkeeper E created vulnerabilities. Let’s build on our strengths while focusing on improving composure and positioning for underperformers."
    
    @staticmethod
    def __get_top_performers():
        return [
            {
                "player": "Midfielder A",
                "keyMetrics": "Distance Covered: 12.3 km, Key Passes: 6",
                "impact":
                "Controlled midfield; created scoring chances with exceptional vision and positioning.",
            },
            {
                "player": "Winger B",
                "keyMetrics": "Sprints: 34, Dribble Success: 71%",
                "impact":
                "Constant threat on flanks; delivered a crucial assist in the second half.",
            },
            {
                "player": "Striker C",
                "keyMetrics": "Goals: 1, Final Third Passes: 15",
                "impact":
                "Clinical in the final third; converted a decisive scoring opportunity.",
            },
        ]
    
    @staticmethod
    def __get_top_performer_highlights():
        return {
            "midfielderAHighlight": "Key pressing moment leading to a goal",
            "midfielderALink": "[Insert Link]",
            "wingerBHighlight": "Assist from a cross",
            "wingerBLink": "[Insert Link]",
            "strikerCHighlight": "Goal in the 65th minute",
            "strikerCLink": "[Insert Link]",
        }
    
    @staticmethod
    def __get_under_performers():
        return [
            {
                "player": "Defender D",
                "keyMetrics": "Tackles: 3/8, Pass Accuracy: 67%",
                "issue":
                "Positional lapses led to the opponent’s goal; struggled with marking assignments.",
            },
            {
                "player": "Goalkeeper E",
                "keyMetrics": "Distribution Accuracy: 60%",
                "issue":
                "Poor decision-making under pressure resulted in turnovers in critical areas.",
            },
        ]
    
    @staticmethod
    def __get_under_performer_reviews():
        return {
            "defenderDReview": "Missed marking in the 42nd minute",
            "defenderDLink": "[Insert Link]",
            "goalkeeperEReview": "Distribution under pressure led to turnovers",
            "goalkeeperELink": "[Insert Link]",
        }
    

    @staticmethod
    def __get_key_player_takeaways():
        return {
                "topPerformers": [
                "Midfielder A and Winger B excelled in maintaining possession, breaking defensive lines, and creating opportunities.",
                "Striker C displayed excellent finishing ability, a standard to emulate for other forwards.",
            ],
            "underperformers": [
                "Defensive lapses from Defender D exposed gaps that were exploited by the opponent.",
                "Goalkeeper E’s distribution errors added unnecessary pressure on the defense.",
            ]
        }
    
    @staticmethod
    def __get_wajo_suggestions():
        return {
            "buildOnStrengths": [
                "Leverage Midfielder A’s vision and Winger B’s explosiveness to enhance tactical drills and creativity.",
                "Highlight Striker C’s finishing in team sessions as a teaching example for composure and execution.",
            ],
            "targetDefensiveLapses": [
                "Assign marking and positioning drills for Defender D to improve situational awareness.",
                "Emphasize distribution drills for Goalkeeper E under high-pressure scenarios to boost confidence and accuracy.",
            ],
            "enhanceTeamCohesion": [
                "Create combined drills for midfield and forward players to simulate real-match scenarios and improve connections in the final third.",
            ],
        }

    @staticmethod
    def __get_next_metrics():
        return {
            "teamPerformanceOverview":
                "Broaden the lens to identify team-wide trends and improvement areas.",
            "setPieceAnalysis":
                "Focus on optimizing offensive and defensive set-piece performance.",
            "fitnessRecoverySuggestions":
                "Address fatigue levels and recovery needs to ensure readiness for the next match.",
        }


    def get_report(self, lang: str = "en"):
        # Need to be removed once llm responses integrated
        if lang == "he":
            analysis = PostMatchAnalysis.objects.first()
            return analysis.individual_player_performance_report_json_he
        response = {}

        response['wajoSummary'] = __class__.__get_wajo_summary()
        response['topPerformers'] = __class__.__get_top_performers()
        response['topPerformerHighlights'] = __class__.__get_top_performer_highlights()
        response['underperformers'] = __class__.__get_under_performers()
        response['underperformerReviews'] = __class__.__get_under_performer_reviews()
        response['keyPlayerTakeaways'] = __class__.__get_key_player_takeaways()
        response['wajoSuggestions'] = __class__.__get_wajo_suggestions()
        response['whatsNext'] = __class__.__get_next_metrics()

        return response


class TeamPerformanceReport:
    @staticmethod
    def __get_wajo_summary():
        return "Our team dominated possession and pressing, translating into significant control over the game. However, lapses in defensive transitions, crossing inefficiencies, and fatigue-induced errors in the final moments need addressing. By reinforcing these areas, we can maintain our competitive edge throughout the match."
    
    @staticmethod
    def __get_strengths():
        return [
            {
            "area": "Possession Control",
            "performance": "High possession (68.2%)",
            "impact":
                "Dictated the game’s tempo and forced the opponent into a defensive posture.",
            },
            {
            "area": "Key Passing",
            "performance": "12 key passes",
            "impact":
                "Created breakthroughs in the opponent’s defensive lines, enabling goal-scoring chances.",
            },
            {
            "area": "Pressing Efficiency",
            "performance": "72% success",
            "impact":
                "Disrupted opponent build-up play, generating turnovers in critical areas.",
            },
        ]

    @staticmethod
    def __get_key_strengths():
        return {
            "dominanceInPossession": "The team’s ability to maintain 68.2% possession allowed sustained attacking pressure and limited the opponent’s time on the ball.",
            "passingAccuracy": "Exceptional passing accuracy (89.3%) ensured smooth transitions and reduced turnovers, fostering team control.",
            "pressingSuccess": "High pressing efficiency (72%) disrupted the opponent’s rhythm and created opportunities to regain possession in advanced areas.",
        }
    
    @staticmethod
    def __get_weakness():
        return [
            {
                "area": "Crossing Accuracy",
                "performance": "23.4%",
                "impact": "Limited ability to exploit wide areas, reducing the quality of deliveries into the box.",
            },
            {
                "area": "Defensive Lapses",
                "performance": "64 turnovers",
                "impact": "Turnovers in critical areas provided counterattacking opportunities, including one leading to a goal.",
            },
            {
                "area": "Fatigue Management",
                "performance": "Late-game fatigue (RPE: 8)",
                "impact": "Declining energy led to positional errors and reduced accuracy in the final 15 minutes.",
            },
        ]
    

    @staticmethod
    def __get_key_weakness():
        return {
            "crossingInefficiency": "Poor crossing accuracy hindered the team’s ability to capitalize on wide areas, limiting scoring chances.",
            "defensiveTransitions": "Lapses, particularly in wide areas, allowed the opponent to exploit gaps during counterattacks.",
            "fatigueImpact": "Late-game fatigue caused turnovers and positional mistakes, affecting overall performance in crucial moments.",
        }
    
    @staticmethod
    def __get_trends():
        return [
            {
            "trend": "Midfield Dominance",
            "observation":
                "Midfield players consistently maintained control, with Midfielder A excelling in transitions.",
            },
            {
            "trend": "Final Third Efficiency",
            "observation":
                "Opportunities were created, but finishing remains inconsistent, highlighting a need for composure.",
            },
            {
            "trend": "Defensive Organization",
            "observation":
                "Defensive structure was solid early on but declined as fatigue set in during the latter stages.",
            },
        ]
    
    @staticmethod
    def __get_wajo_suggestions():
        return {
            "enhanceStrengths": {
            "possessionAndPassing":
                "Continue building on high possession and accurate passing by implementing tactical drills that simulate high-pressure scenarios to maintain control.",
            "pressingEfficiency":
                "Reinforce pressing drills focused on coordination and timing to sustain performance throughout the match.",
            },
            "addressWeaknesses": {
            "improveCrossingAccuracy":
                "Target crossing drills to improve delivery into the box and capitalize on wide-area opportunities.",
            "reduceTurnovers":
                "Incorporate quick-decision passing drills to minimize errors in midfield under pressure.",
            "manageFatigue":
                "Implement endurance training and rotation strategies to maintain energy levels in the latter stages of matches.",
            },
        }

    @staticmethod
    def __get_video_highlights():
        return {
            "midfieldControlInAction": "[Insert Link]",
            "defensiveLapsesLeadingToGoal": "[Insert Link]",
            "crossingChallengesInWideAreas": "[Insert Link]",
        }
    
    @staticmethod
    def __get_next_metrics():
        return {
            "setPieceAnalysis": "Deep dive into offensive and defensive set-piece performance.",
            "fitnessRecoverySuggestions": "Focus on recovery strategies to address fatigue and prepare for the next game.",
            "trainingRecommendations": "Actionable drills to build on strengths and address weaknesses.",
        }
    
    def get_report(self, lang: str = "en"):
        # Need to be removed once llm responses integrated
        if lang == "he":
            analysis = PostMatchAnalysis.objects.first()
            return analysis.team_performance_report_json_he
        response = {}
        response['wajoSummary'] = __class__.__get_wajo_summary()
        response['strengths'] = __class__.__get_strengths()
        response['keyStrengths'] = __class__.__get_key_strengths()
        response['weaknesses'] = __class__.__get_weakness()
        response['keyWeaknesses'] = __class__.__get_key_weakness()
        response['trends'] = __class__.__get_trends()
        response['wajoSuggestions'] = __class__.__get_wajo_suggestions()
        response['videoHighlights'] = __class__.__get_video_highlights()
        response['whatsNext'] = __class__.__get_next_metrics()

        return response


class SetPieceAnalysisReport:
    @staticmethod
    def __get_wajo_summary():
        return "Our set-piece routines demonstrated their value, delivering a crucial goal and maintaining strong defensive organization. However, lapses in marking during defensive free kicks and limited creativity in offensive free kicks highlight areas for improvement. Let’s refine our routines and add variations to stay unpredictable."
    
    @staticmethod
    def __get_set_piece_performance():
        return [
            {
            "phase": "Offensive Corners",
            "ourTeamPerformance": "1 goal from 6 corners",
            "outcome":
                "Effective near-post routine contributed to a decisive goal.",
            },
            {
            "phase": "Defensive Free Kicks",
            "ourTeamPerformance": "Strong organization; minor lapse in 85’",
            "outcome":
                "Prevented goals but allowed a dangerous header opportunity.",
            },
            {
            "phase": "Offensive Free Kicks",
            "ourTeamPerformance": "4 attempts; 1 shot on target",
            "outcome":
                "Lacked creativity and accuracy in direct free-kick execution.",
            },
            {
            "phase": "Throw-Ins",
            "ourTeamPerformance": "High retention rate (91%)",
            "outcome":
                "Ensured possession but missed opportunities for quick transitions.",
            },
        ]


    @staticmethod
    def __get_key_takeaways():
        return {
            "offensiveCorners": "A well-rehearsed near-post routine led to a goal, showcasing the team’s preparation and execution. Additional corner variations could add unpredictability.",
            "defensiveFreeKicks": "Strong organizational discipline prevented goals, though a minor lapse in marking in the 85th minute allowed a dangerous header.",
            "offensiveFreeKicks": "Limited creativity and accuracy hindered chances from direct free-kick opportunities. More innovative routines could create better goal-scoring opportunities.",
            "throwIns": "The team maintained high possession (91%) from throw-ins but missed chances to exploit space through quicker transitions.",
        }
    

    @staticmethod
    def __get_wajo_suggestions():
        return {
                "offensiveCorners": {
                "description": "Continue practicing the near-post routine while adding variations such as:",
                "variations": [
                    "Short corners to confuse defenders.",
                    "Far-post deliveries for taller players.",
                ],
            },
            "defensiveFreeKicks": {
            "description":
                "Focus on aerial marking drills to eliminate lapses, particularly in late-game scenarios when fatigue impacts focus.",
            },
            "offensiveFreeKicks": {
                "description": "Develop creative free-kick drills, including:",
                "variations": [
                    "Quick one-touch passes to bypass the defensive wall.",
                    "Fake runs to distract defenders.",
                ],
            },
            "throwIns": {
                "description":
                    "Introduce transition-based throw-in routines, focusing on:",
                "variations": [
                    "Quick throws to exploit unorganized defenses.",
                    "Utilizing nearby players for immediate give-and-go options.",
                ],
            },
        }

    @staticmethod
    def __get_video_highlights():
        return {
            "cornerGoalIn55Min": "[Insert Link]",
            "defensiveHeaderSavedIn85Min": "[Insert Link]",
            "throwInTransitionOpportunitiesMissed": "[Insert Link]",
        }
    

    @staticmethod
    def __get_next_metrics():
        return {
            "fitnessRecoverySuggestions": "Ensure player readiness for sustained performance in future set-piece scenarios.",
            "trainingRecommendations": "Focus on drills that build precision and creativity in set-piece execution.",
            "overallMatchTrends": "Look back at how set-pieces fit into the broader match narrative.",
        }


    def get_report(self, lang: str = "en"):
        # Need to be removed once llm responses integrated
        if lang == "he":
            analysis = PostMatchAnalysis.objects.first()
            return analysis.set_piece_analysis_report_json_he
        response = {}
        response['wajoSummary'] = __class__.__get_wajo_summary()
        response['setPiecePerformanceOverview'] = __class__.__get_set_piece_performance()
        response['keyTakeaways'] = __class__.__get_key_takeaways()
        response['wajoSuggestions'] = __class__.__get_wajo_suggestions()
        response['videoHighlights'] = __class__.__get_video_highlights()
        response['whatsNext'] = __class__.__get_next_metrics()

        return response

class FitnessRecoverySuggestion:

    @staticmethod
    def __get_wajo_summary():
        return "Our set-piece routines demonstrated their value, delivering a crucial goal and maintaining strong defensive organization. However, lapses in marking during defensive free kicks and limited creativity in offensive free kicks highlight areas for improvement. Let’s refine our routines and add variations to stay unpredictable."
    

    @staticmethod
    def __get_key_metrics_observations():
        return [
            {
            "player": "Player A",
            "fatigueLevel": "High (RPE: 8)",
            "impactOnGame":
                "Declining accuracy in passing during final-third plays.",
            "actionableAdjustments": "Prioritize light recovery-focused training and aerobic sessions.",
            },
            {
            "player": "Player B",
            "fatigueLevel": "Moderate (RPE: 7)",
            "impactOnGame": "Reduced pressing efficiency in midfield late-game.",
            "actionableAdjustments": "Schedule lighter recovery sessions with sprint recovery drills.",
            },
            {
            "player": "Player C",
            "fatigueLevel": "Low (RPE: 5)",
            "impactOnGame": "Maintained sharpness throughout the match.",
            "actionableAdjustments": "Focus on high-intensity tactical drills and positional simulations.",
            },
        ]
    

    @staticmethod
    def __get_team_wise_observation():
        return {
            "lateGameDecline":
            "Fatigue impacted decision-making and execution, leading to turnovers and defensive lapses in the final 15 minutes.",
            "pressingInefficiencies":
            "Midfield pressing efficiency dropped significantly late-game, disrupting overall team shape and intensity.",
        }
    

    @staticmethod
    def __get_wajo_insight():
        return {
            "highWorkload": "Players like Player A exhibited high workload levels. Active recovery is crucial to avoid fatigue-related injuries.",
            "recoveryFocus": "Players with moderate-to-high fatigue need adjusted training loads to ensure readiness for the next match.",
            "matchReadiness": "Low-fatigue players like Player C are ideal candidates for high-intensity, tactical-focused training."
        }
    

    @staticmethod
    def __get_fitness_highlights():
        return {
            "playerAHeatmap": "[Insert Link]",
            "playerBSprintAnalysis": "[Insert Link]",
            "energyManagementPatterns": "[Insert Link]",
        }
    
    @staticmethod
    def __get_action_steps():
        return {
            "adjustTrainingIntensity":
            "Tailor training loads based on fatigue levels and RPE scores to optimize performance and recovery.",
            "focusOnRecoveryStrategies":
            "Incorporate hydration protocols, mobility drills, and light aerobic sessions to address game-specific issues (e.g., pressing lapses).",
            "enhanceTeamWideRecovery": [
            "Foam rolling",
            "Cold-water immersion",
            "Stretching routines",
            ],
        }
    
    @staticmethod
    def __get_next_metrics():
        return {
            "trainingRecommendations": "Build on these observations to design targeted training plans.",
            "reviewTacticalExecution": "Link fitness to improved set-piece and tactical efficiency.",
            "wrapItUp": "Plan ahead for the next training cycle.",
        }
    
    def get_report(self, lang="en"):
        # Need to be removed once llm responses integrated
        if lang == "he":
            analysis = PostMatchAnalysis.objects.first()
            return analysis.fitness_recovery_suggestion_json_he
        response = {}
        response['wajoSummary'] = __class__.__get_wajo_summary()
        response['keyMetricsAndObservations'] = __class__.__get_key_metrics_observations()
        response['teamWiseObservations'] = __class__.__get_team_wise_observation()
        response['wajoInsights'] = __class__.__get_wajo_insight()
        response['fitnessHighlights'] = __class__.__get_fitness_highlights()
        response['actionSteps'] = __class__.__get_action_steps()
        response['whatsNext'] = __class__.__get_next_metrics()

        return response


class TrainingRecommendationReport:
    @staticmethod
    def __get_wajo_summary():
        return "Our training focus should address weaknesses in pressing coordination, defensive marking, and final-third composure while leveraging our strengths in possession and set-pieces. Recovery plans tailored to individual fatigue levels will prepare the team for upcoming challenges. Let’s maximize our training impact with precision drills and targeted strategies."


    @staticmethod
    def __get_priority_areas():
        return [
            {
                "focusArea": "Pressing Drills",
                "drill": "Positional pressing drills focusing on coordination and timing under fatigue scenarios.",
                "outcome": "Enhance the team’s ability to disrupt opponent build-up play consistently.",
            },
            {
                "focusArea": "Finishing Drills",
                "drill": "1v1 finishing drills and situational small-sided games simulating high-pressure scenarios.",
                "outcome": "Improve composure and decision-making to increase goal conversion rates in the final third.",
            },
            {
                "focusArea": "Defensive Marking",
                "drill": "Zonal and man-marking simulations focusing on rotation and awareness in defensive phases.",
                "outcome": "Reduce positional lapses and improve defensive awareness during transitions.",
            }
        ]

    @staticmethod
    def __get_recovery_plans():
        return [
            {
                "player": "Player A",
                "recoveryFocus": "Light aerobicRecovery work and sprint recovery exercises.",
                "outcome": "Reduce fatigue levels and maintain performance consistency.",
            },
            {
                "player": "Player B",
                "recoveryFocus": "Hydration protocols, stretching, and lighter loads.",
                "outcome": "Maintain energy balance and ensure readiness for the next match.",
            },
            {
                "player": "Player C",
                "recoveryFocus": "High-intensity tactical simulations.",
                "outcome": "Refine positional understanding and improve match preparedness.",
            },
        ]
    
    @staticmethod
    def __get_tactical_reviews():
        return [
            {
                "issue": "Crossing Accuracy",
                "drill": "Wide-area crossing drills under high-pressure scenarios.",
                "outcome": "Improve delivery accuracy and maximize effectiveness in wing play.",
            },
            {
                "issue": "Turnover Reduction",
                "drill": "Quick-decision passing drills and high-pressure possession games.",
                "outcome": "Reduce risky turnovers and enhance composure under pressure.",
            }
        ]
    
    @staticmethod
    def __get_training_video_resources():
        return {
            "pressingCoordinationDrills": "[Insert Link]",
            "finishingDrillsInFinalThird": "[Insert Link]",
            "defensiveMarkingAndAwarenessDrills": "[Insert Link]"
        }
    
    @staticmethod
    def __get_effectiveness_insights():
        return {
            "teamLevelImpact": "Tactical reviews and drills will strengthen weak areas while further building on existing strengths.",
            "playerLevelDevelopment": "Recovery and improvement plans for individual players align with their match performance and team needs."
        }
    
    @staticmethod
    def __get_next_metrics():
        return {
            "tailoredTrainingPlan": "Finalize drills and schedules to prepare for the next match.",
            "individualDevelopmentInsights": "Incorporate player-specific recovery and training focus areas.",
            "matchPreparationReview": "Sync insights into upcoming match strategies and tactical objectives."
        }


    def get_report(self, lang="en"):
        # Need to be removed once llm responses integrated
        if lang == "he":
            analysis = PostMatchAnalysis.objects.first()
            return analysis.training_recommendation_report_json_he
        response = {}
        response['wajoSummary'] = __class__.__get_wajo_summary()
        response['priorityAreas'] = __class__.__get_priority_areas()
        response['recoveryPlans'] = __class__.__get_recovery_plans()
        response['tacticalReviews'] = __class__.__get_tactical_reviews()
        response['trainingVideoResources'] = __class__.__get_training_video_resources()
        response['wajoGameEffectivenessInsights'] = __class__.__get_effectiveness_insights()
        response['whatsNext'] = __class__.__get_next_metrics()

        return response


class MatchSummaryReport:
    def get_match_summary(self, lang='en'):
        summary = PostMatchAnalysis.objects.first()
        if not summary:
            return {}
        if lang == "he":
            return summary.summary_json_he
        return summary.summary_json
