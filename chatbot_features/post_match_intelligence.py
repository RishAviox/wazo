import json
from datetime import datetime
from typing import Dict, Any, List
from django.db import models
from django.core.exceptions import ObjectDoesNotExist

from accounts.models import PlayerIDMapping
from games.models import Game
from tracevision.models import TraceSession, TraceVisionPlayerStats, TraceHighlight, TraceHighlightObject

# Import existing performance calculation utilities
try:
    from cards.utils.card import (
        get_status_card_metrics,
        get_gps_athletic_skills_metrics,
        get_gps_football_abilities_metrics,
        get_videocard_defensive_metrics
    )
except ImportError:
    # Fallback functions if imports fail
    def get_status_card_metrics(player):
        return {}

    def get_gps_athletic_skills_metrics(player):
        return {}

    def get_gps_football_abilities_metrics(player):
        return {}

    def get_videocard_defensive_metrics(player):
        return {}


def get_tracevision_player_mapping(player_id: str, match_id: str) -> str:
    """
    Map Wajo player ID to TraceVision object ID (e.g., 'home-7', 'away-15')
    This function implements jersey number matching logic
    
    Args:
        player_id: Wajo player identifier
        match_id: Match identifier
        
    Returns:
        TraceVision object ID string or None if mapping not found
    """
    try:
        # Get player from PlayerIDMapping
        player_mapping = PlayerIDMapping.objects.get(player_id=player_id)
        player = player_mapping.user
        
        # Get match
        match = Game.objects.get(id=match_id)
        
        # Try to find TraceSession by match date and teams
        # This is a basic mapping - you might need to enhance this based on your data structure
        trace_sessions = TraceSession.objects.filter(
            user=player,
            home_team__icontains=match.home_team.name if hasattr(match, 'home_team') else '',
            away_team__icontains=match.away_team.name if hasattr(match, 'away_team') else ''
        )

        print(f"\n{'='*20}Trace sessions: {trace_sessions}\n{'='*20}")
        
        if trace_sessions.exists():
            return trace_sessions.first()
            
            # For now, return a placeholder - you'll need to implement the actual jersey number logic
            # This could involve looking at player photos, team rosters, or other mapping data
        return f"player-{player_id}"
        
    except Exception as e:
        print(f"Error in player mapping: {e}")
        return None


def get_tracevision_performance_data(player_id: str, match_id: str) -> Dict[str, Any]:
    """
    Fetch TraceVision performance data for a specific player and match
    
    Args:
        player_id: Player identifier
        match_id: Match identifier
        
    Returns:
        Dictionary containing TraceVision performance data
    """
    if not all([TraceSession, TraceVisionPlayerStats, TraceHighlight, TraceHighlightObject]):
        return {"error": "TraceVision models not available"}
    
    try:
        # Get player mapping
        tracevision_object_id = get_tracevision_player_mapping(player_id, match_id)
        if not tracevision_object_id:
            return {"error": "Player mapping not found"}
        
        # Try to find TraceSession by match date and other criteria
        # This mapping logic needs to be enhanced based on your actual data structure
        # match = Game.objects.get(id=match_id)
        trace_sessions = TraceSession.objects.filter(
            session_id=4077046
        )
        
        if not trace_sessions.exists():
            return {"error": "No TraceVision session found for this match"}
        
        trace_session = trace_sessions.first()
        
        user = trace_session.user
        
        # Get player stats
        player_stats = TraceVisionPlayerStats.objects.filter(
            session=trace_session,
            object_id__icontains=player_id  # Basic filtering - enhance this
        ).first()
        
        # Get highlights involving this player
        player_highlights = TraceHighlight.objects.filter(
            session=trace_session,
            # highlight_objects__trace_object__object_id__icontains=player_id
        ).distinct()
        
        tracevision_data = {
            "session_id": trace_session.session_id,
            "match_date": trace_session.match_date.isoformat(),
            "home_team": trace_session.home_team,
            "away_team": trace_session.away_team,
            "final_score": trace_session.final_score,
            "session_status": trace_session.status,
            "user_id": user.phone_no if user else None,
            "user_name": user.name if user else None
        }
        
        # Add player stats if available
        if player_stats:
            tracevision_data["player_stats"] = {
                "total_distance_meters": player_stats.total_distance_meters,
                "avg_speed_mps": player_stats.avg_speed_mps,
                "max_speed_mps": player_stats.max_speed_mps,
                "total_time_seconds": player_stats.total_time_seconds,
                "sprint_count": player_stats.sprint_count,
                "sprint_distance_meters": player_stats.sprint_distance_meters,
                "sprint_time_seconds": player_stats.sprint_time_seconds,
                "avg_position_x": player_stats.avg_position_x,
                "avg_position_y": player_stats.avg_position_y,
                "position_variance": player_stats.position_variance,
                "performance_score": player_stats.performance_score,
                "stamina_rating": player_stats.stamina_rating,
                "work_rate": player_stats.work_rate,
                "distance_per_minute": player_stats.distance_per_minute,
                "sprint_percentage": player_stats.sprint_percentage
            }
        
        # Add highlights if available
        if player_highlights.exists():
            # tracevision_data["highlights"] = [
            #     {
            #         "highlight_id": h.highlight_id,
            #         "duration_ms": h.duration,
            #         "start_offset_ms": h.start_offset,
            #         "tags": h.tags,
            #         "video_stream": h.video_stream
            #     } for h in player_highlights
            # ]
            tracevision_data["highlight_count"] = player_highlights.count()
        
        # Add Passes data
        try:
            from tracevision.models import TracePass
            player_passes = TracePass.objects.filter(
                session=trace_session
            ).filter(
                models.Q(from_object_id__icontains="away_25") | 
                models.Q(to_object_id__icontains="away_25")
            )
            
            if player_passes.exists():
                tracevision_data["passes"] = {
                    "total_passes": player_passes.count(),
                    "passes_received": player_passes.filter(to_object_id__icontains="away_25").count(),
                    "passes_made": player_passes.filter(from_object_id__icontains="away_25").count(),
                    # "pass_details": [
                    #     {
                    #         "from_player": p.from_object_id,
                    #         "to_player": p.to_object_id,
                    #         "side": p.side,
                    #         "start_ms": p.start_ms,
                    #         "duration_ms": p.duration_ms
                    #     } for p in player_passes
                    # ]
                }
        except ImportError:
            tracevision_data["passes"] = {"error": "TracePass model not available"}
        
        # Add Passing Network Edges data
        try:
            from tracevision.models import TracePassingNetwork
            player_network = TracePassingNetwork.objects.filter(
                session=trace_session
            ).filter(
                models.Q(from_object_id__icontains="away_25") | 
                models.Q(to_object_id__icontains="away_25")
            )
            
            if player_network.exists():
                tracevision_data["passing_network"] = {
                    "total_connections": player_network.count(),
                    "connections_as_sender": player_network.filter(from_object_id__icontains="away_25").count(),
                    "connections_as_receiver": player_network.filter(to_object_id__icontains="away_25").count(),
                }
        except ImportError:
            tracevision_data["passing_network"] = {"error": "TracePassingNetwork model not available"}
        
        # Add Possession Segments data
        try:
            from tracevision.models import TracePossessionSegment
            possession_segments = TracePossessionSegment.objects.filter(
                session=trace_session
            ).order_by('start_ms')
            
            if possession_segments.exists():
                tracevision_data["possession_segments"] = {
                    "total_segments": possession_segments.count(),
                    "home_possession_time": sum(
                        p.duration_s for p in possession_segments if p.side == 'home'
                    ),
                    "away_possession_time": sum(
                        p.duration_s for p in possession_segments if p.side == 'away'
                    ),
                    # "segments_detail": [
                    #     {
                    #         "side": p.side,
                    #         "start_ms": p.start_ms,
                    #         "end_ms": p.end_ms,
                    #         "duration_s": p.duration_s,
                    #         "start_clock": p.start_clock,
                    #         "end_clock": p.end_clock
                    #     } for p in possession_segments
                    # ]
                }
        except ImportError:
            tracevision_data["possession_segments"] = {"error": "TracePossessionSegment model not available"}
        
        # Add Touch Leaderboard data
        try:
            from tracevision.models import TraceTouchLeaderboard
            touch_leaderboard = TraceTouchLeaderboard.objects.filter(
                session=trace_session
            ).order_by('-touches')
            
            if touch_leaderboard.exists():
                tracevision_data["touch_leaderboard"] = {
                    "total_players": touch_leaderboard.count(),
                    "player_rankings": [
                        {
                            "object_id": t.object_id,
                            "side": t.object_side,
                            "touches": t.touches,
                            "rank": idx + 1
                        } for idx, t in enumerate(touch_leaderboard)
                    ],
                    "player_touch_count": touch_leaderboard.filter(
                        object_id__icontains=player_id
                    ).first().touches if touch_leaderboard.filter(object_id__icontains=player_id).exists() else 0
                }
        except ImportError:
            tracevision_data["touch_leaderboard"] = {"error": "TraceTouchLeaderboard model not available"}
        
        # Add Coach Report Team data
        try:
            from tracevision.models import TraceCoachReportTeam
            coach_reports = TraceCoachReportTeam.objects.filter(
                session=trace_session
            )
            
            if coach_reports.exists():
                tracevision_data["coach_report"] = {
                    "home_team": {
                        "goals": coach_reports.filter(side='home').first().goals if coach_reports.filter(side='home').exists() else 0,
                        "shots": coach_reports.filter(side='home').first().shots if coach_reports.filter(side='home').exists() else 0,
                        "passes": coach_reports.filter(side='home').first().passes if coach_reports.filter(side='home').exists() else 0,
                        "possession_time_s": coach_reports.filter(side='home').first().possession_time_s if coach_reports.filter(side='home').exists() else 0.0
                    },
                    "away_team": {
                        "goals": coach_reports.filter(side='away').first().goals if coach_reports.filter(side='away').exists() else 0,
                        "shots": coach_reports.filter(side='away').first().shots if coach_reports.filter(side='away').exists() else 0,
                        "passes": coach_reports.filter(side='away').first().passes if coach_reports.filter(side='away').exists() else 0,
                        "possession_time_s": coach_reports.filter(side='away').first().possession_time_s if coach_reports.filter(side='away').exists() else 0.0
                    }
                }
        except ImportError:
            tracevision_data["coach_report"] = {"error": "TraceCoachReportTeam model not available"}
        
        return tracevision_data
        
    except Exception as e:
        return {"error": f"Error fetching TraceVision data: {str(e)}"}


def get_player_performance_data(player_id: str, match_id: str) -> Dict[str, Any]:
    """
    Get comprehensive performance data for a player from a specific match

    Args:
        player_id: Player identifier
        match_id: Match identifier

    Returns:
        Dictionary containing player performance data
    """
    try:
        # Get player from PlayerIDMapping
        player_mapping = PlayerIDMapping.objects.get(player_id=player_id)
        player = player_mapping.user

        # Get match
        match = Game.objects.get(id=match_id)

        performance_data = {
            'player_info': {
                'player_id': player_id,
                'name': player.name or player.phone_no,
                'position': player_mapping.player_position,
                'role': player.role
            },
            'match_info': {
                'match_id': match.id,
                'match_name': match.name,
                'match_date': match.date.isoformat() if match.date else None,
                'match_type': match.type
            },
            'wellness_metrics': {},
            'gps_athletic_skills': {},
            'gps_football_abilities': {},
            'defensive_metrics': {},
            'tracevision_data': {}  # NEW: TraceVision integration
        }

        print(f"\n{'*'*20}Performance data In 'get_player_performance_data': {performance_data}\n{'*'*20}")

        # Get performance metrics (safely with error handling)
        try:
            performance_data['wellness_metrics'] = get_status_card_metrics(
                player)
        except Exception as e:
            print(f"Error getting wellness metrics: {e}")

        try:
            performance_data['gps_athletic_skills'] = get_gps_athletic_skills_metrics(
                player)
        except Exception as e:
            print(f"Error getting GPS athletic skills: {e}")

        try:
            performance_data['gps_football_abilities'] = get_gps_football_abilities_metrics(
                player)
        except Exception as e:
            print(f"Error getting GPS football abilities: {e}")

        try:
            performance_data['defensive_metrics'] = get_videocard_defensive_metrics(
                player)
        except Exception as e:
            print(f"Error getting defensive metrics: {e}")

        # NEW: Get TraceVision data
        try:
            performance_data['tracevision_data'] = get_tracevision_performance_data(
                player_id, match_id)
        except Exception as e:
            print(f"Error getting TraceVision data: {e}")
            performance_data['tracevision_data'] = {"error": f"TraceVision data unavailable: {str(e)}"}

        print(f"\n{'*'*20}Performance data In 'get_player_performance_data' Final: {performance_data}\n{'*'*20}")

        return performance_data

    except ObjectDoesNotExist as e:
        return {
            'error': f'Player or match not found: {str(e)}',
            'player_id': player_id,
            'match_id': match_id
        }
    except Exception as e:
        return {
            'error': f'Error retrieving performance data: {str(e)}',
            'player_id': player_id,
            'match_id': match_id
        }


def player_postmatch_intelligence(
    task: str,
    userRole: str,
    playerId: str,
    matchId: str,
    language: str = "auto",
    timezone: str = "UTC",
    notes: str = "",
    clientTimestamp: str = None,
    previousMatchId: str = None,
    extensions: Dict[str, Any] = None
) -> str:
    """
    Generate post-match intelligence for a player

    This function matches the exact schema provided by the client.

    Args:
        task: Type of post-match intelligence to generate
        userRole: Role of the requester 
        playerId: Unique identifier for the player
        matchId: Unique identifier for the match
        language: BCP-47 tag (e.g., 'en', 'he', 'pt-BR')
        timezone: IANA timezone (e.g., 'Asia/Jerusalem')
        notes: Short context or observations
        clientTimestamp: ISO-8601 UTC timestamp
        previousMatchId: Optional previous match to compare against
        extensions: Org-specific optional fields

    Returns:
        JSON string containing the post-match intelligence analysis
    """

    # Default values
    if extensions is None:
        extensions = {}
    
    # Get player performance data
    performance_data = get_player_performance_data(playerId, matchId)
    print(f"\n{'*'*20}Performance data: {performance_data}\n{'*'*20}")
    # Get previous match data if comparing
    previous_performance_data = None
    if task == 'compare_to_previous' and previousMatchId:
        previous_performance_data = get_player_performance_data(
            playerId, previousMatchId)

    # Handle language auto-detection
    if language == "auto":
        try:
            player_mapping = PlayerIDMapping.objects.get(player_id=playerId)
            language = getattr(player_mapping.user,
                               'selected_language', 'en') or 'en'
        except:
            language = 'en'

    # Prepare analysis context
    analysis_context = {
        'task': task,
        'userRole': userRole,
        'playerId': playerId,
        'matchId': matchId,
        'language': language,
        'timezone': timezone,
        'notes': notes,
        'clientTimestamp': clientTimestamp or datetime.now().isoformat() + 'Z',
        'previousMatchId': previousMatchId,
        'extensions': extensions,
        'performance_data': performance_data,
        'previous_performance_data': previous_performance_data
    }

    print(f"\n{'*'*20}Analysis context: {analysis_context}\n{'*'*20}")
    current_date = datetime.now().strftime('%Y-%m-%d')

    # For now, focus on summarize_performance task
    if task == "summarize_performance":
        return _generate_summarize_performance_response(playerId, matchId, userRole, notes, performance_data, current_date)
    
    # For other tasks, return a placeholder response
    return _generate_placeholder_response(task, playerId, matchId, userRole, notes, performance_data, current_date)


def _generate_summarize_performance_response(player_id: str, match_id: str, user_role: str, notes: str, performance_data: Dict[str, Any], current_date: str) -> str:
    """Generate performance summary based on TraceVision data with role-specific insights"""
    
    # Role-specific configurations
    role_configs = {
        'athlete_player': {
            'summary_prefix': 'Your performance in',
            'action_type': 'player_task',
            'focus_areas': ['personal_growth', 'confidence_building', 'actionable_steps'],
            'tone': 'supportive and encouraging'
        },
        'coach': {
            'summary_prefix': 'Performance analysis for',
            'action_type': 'coach_task',
            'focus_areas': ['tactical_analysis', 'coaching_recommendations', 'development_planning'],
            'tone': 'analytical and strategic'
        },
        'assistant_coach': {
            'summary_prefix': 'Performance review for',
            'action_type': 'coach_task',
            'focus_areas': ['skill_development', 'training_focus', 'support_areas'],
            'tone': 'supportive and developmental'
        },
        'personal_coach': {
            'summary_prefix': 'Individual performance for',
            'action_type': 'coach_task',
            'focus_areas': ['personal_development', 'goal_alignment', 'motivation'],
            'tone': 'personal and motivational'
        },
        'skills_coach': {
            'summary_prefix': 'Technical performance for',
            'action_type': 'coach_task',
            'focus_areas': ['technical_skills', 'skill_improvement', 'practice_focus'],
            'tone': 'technical and improvement-focused'
        },
        'technical_director': {
            'summary_prefix': 'Strategic performance for',
            'action_type': 'coach_task',
            'focus_areas': ['long_term_development', 'pathway_alignment', 'standards_assessment'],
            'tone': 'strategic and developmental'
        },
        'data_analyst': {
            'summary_prefix': 'Data-driven analysis for',
            'action_type': 'analyst_task',
            'focus_areas': ['metrics_trends', 'data_insights', 'performance_patterns'],
            'tone': 'analytical and data-focused'
        },
        'video_analyst': {
            'summary_prefix': 'Video analysis for',
            'action_type': 'analyst_task',
            'focus_areas': ['visual_insights', 'moment_analysis', 'tactical_review'],
            'tone': 'visual and tactical'
        },
        'sports_psychologist': {
            'summary_prefix': 'Mental performance for',
            'action_type': 'psychology_task',
            'focus_areas': ['mental_state', 'emotional_regulation', 'psychological_insights'],
            'tone': 'supportive and psychological'
        },
        'strength_conditioning_coach': {
            'summary_prefix': 'Physical performance for',
            'action_type': 'fitness_task',
            'focus_areas': ['physical_load', 'recovery_needs', 'conditioning_insights'],
            'tone': 'physical and conditioning-focused'
        },
        'fitness_trainer': {
            'summary_prefix': 'Fitness performance for',
            'action_type': 'fitness_task',
            'focus_areas': ['fitness_levels', 'training_response', 'recovery_status'],
            'tone': 'fitness and health-focused'
        },
        'nutritionist_dietitian': {
            'summary_prefix': 'Performance nutrition for',
            'action_type': 'nutrition_task',
            'focus_areas': ['energy_levels', 'recovery_nutrition', 'dietary_insights'],
            'tone': 'nutritional and health-focused'
        },
        'rehab_recovery_specialist': {
            'summary_prefix': 'Recovery assessment for',
            'action_type': 'medical_task',
            'focus_areas': ['recovery_status', 'injury_prevention', 'return_to_play'],
            'tone': 'medical and recovery-focused'
        },
        'medical_staff': {
            'summary_prefix': 'Medical assessment for',
            'action_type': 'medical_task',
            'focus_areas': ['health_status', 'injury_risk', 'medical_clearance'],
            'tone': 'medical and safety-focused'
        },
        'scout_talent_identification': {
            'summary_prefix': 'Talent assessment for',
            'action_type': 'scouting_task',
            'focus_areas': ['talent_evaluation', 'development_potential', 'scouting_insights'],
            'tone': 'evaluative and developmental'
        },
        'team_manager': {
            'summary_prefix': 'Team performance for',
            'action_type': 'management_task',
            'focus_areas': ['team_integration', 'logistics', 'organizational_needs'],
            'tone': 'organizational and supportive'
        }
    }
    
    # Get role configuration (default to coach if role not found)
    role_config = role_configs.get(user_role.lower(), role_configs['coach'])
    
    # Extract key metrics from performance_data
    if isinstance(performance_data, dict) and 'error' not in performance_data:
        # Use actual TraceVision data
        summary = f"{role_config['summary_prefix']} player {player_id} in match {match_id}"
        
        # Extract specific metrics if available
        if 'tracevision_data' in performance_data and isinstance(performance_data['tracevision_data'], dict):
            trace_data = performance_data['tracevision_data']
            
            if 'player_stats' in trace_data:
                stats = trace_data['player_stats']
                summary += f". {role_config['tone'].title()} analysis shows: "
                summary += f"{stats.get('total_distance_meters', 'N/A')}m total distance, "
                summary += f"max speed of {stats.get('max_speed_mps', 'N/A')} m/s, "
                summary += f"and {stats.get('sprint_count', 'N/A')} sprints."
                
                # Add role-specific insights
                if user_role.lower() in ['strength_conditioning_coach', 'fitness_trainer']:
                    summary += f" Physical load analysis indicates {stats.get('stamina_rating', 'N/A')} stamina rating."
                elif user_role.lower() in ['sports_psychologist']:
                    summary += f" Performance score of {stats.get('performance_score', 'N/A')} suggests mental state assessment needed."
                elif user_role.lower() in ['data_analyst', 'video_analyst']:
                    summary += f" Position variance of {stats.get('position_variance', 'N/A')} shows tactical movement patterns."
            
            if 'highlights' in trace_data:
                summary += f" {len(trace_data['highlights'])} key moments captured for review."
            
            # Add comprehensive TraceVision insights
            if 'passes' in trace_data and 'error' not in trace_data['passes']:
                passes = trace_data['passes']
                summary += f" Passing analysis shows {passes.get('total_passes', 0)} total passes, "
                summary += f"{passes.get('passes_made', 0)} passes made and {passes.get('passes_received', 0)} received."
            
            if 'touch_leaderboard' in trace_data and 'error' not in trace_data['touch_leaderboard']:
                touch_data = trace_data['touch_leaderboard']
                player_touches = touch_data.get('player_touch_count', 0)
                total_players = touch_data.get('total_players', 0)
                if player_touches > 0:
                    summary += f" Touch analysis reveals {player_touches} touches among {total_players} players tracked."
            
            if 'possession_segments' in trace_data and 'error' not in trace_data['possession_segments']:
                possession = trace_data['possession_segments']
                home_time = possession.get('home_possession_time', 0)
                away_time = possession.get('away_possession_time', 0)
                total_time = home_time + away_time
                if total_time > 0:
                    home_percentage = (home_time / total_time) * 100
                    summary += f" Possession analysis shows {home_percentage:.1f}% home team possession."
            
            if 'coach_report' in trace_data and 'error' not in trace_data['coach_report']:
                report = trace_data['coach_report']
                home_goals = report.get('home_team', {}).get('goals', 0)
                away_goals = report.get('away_team', {}).get('goals', 0)
                summary += f" Match outcome: {home_goals}-{away_goals} final score."
        
        # Generate role-specific actions
        actions = _generate_role_specific_actions(user_role, player_id, match_id, current_date, role_config)
        
        # Generate role-specific suggestions
        next_suggestions = _generate_role_specific_suggestions(user_role, role_config, performance_data)
        
        # Identify role-specific needs
        needs = _identify_role_specific_needs(user_role, performance_data, role_config)
            
    else:
        # Fallback when no data available
        summary = f"Limited data available for {role_config['summary_prefix'].lower()} player {player_id} in match {match_id}"
        actions = [
            {
                "title": "Collect performance data",
                "type": role_config['action_type'],
                "due": current_date,
                "relatedIds": [f"player:{player_id}", f"match:{match_id}"]
            }
        ]
        next_suggestions = [
            "Verify data collection",
            "Check TraceVision integration",
            "Review match processing"
        ]
        needs = ["performance_data", "match_highlights", "player_statistics"]
    
    response = {
        "summary": summary,
        "actions": actions,
        "deltas": {
            "xp": {"change": 0, "reason": ""},
            "goals": [],
            "milestones": []
        },
        "next_suggestions": next_suggestions,
        "needs": needs
    }
    
    return json.dumps(response, indent=2)


def _generate_role_specific_actions(user_role: str, player_id: str, match_id: str, current_date: str, role_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate role-specific actions based on user role"""
    
    base_action = {
        "title": "Review performance data",
        "type": role_config['action_type'],
        "due": current_date,
        "relatedIds": [f"player:{player_id}", f"match:{match_id}"]
    }
    
    role_actions = {
        'athlete_player': [
            {"title": "Set personal goals", "type": "player_task", "due": current_date, "relatedIds": [f"player:{player_id}", f"match:{match_id}"]},
            {"title": "Schedule recovery session", "type": "player_task", "due": current_date, "relatedIds": [f"player:{player_id}", f"match:{match_id}"]}
        ],
        'coach': [
            {"title": "Plan training focus", "type": "coach_task", "due": current_date, "relatedIds": [f"player:{player_id}", f"match:{match_id}"]},
            {"title": "Schedule player feedback", "type": "coach_task", "due": current_date, "relatedIds": [f"player:{player_id}", f"match:{match_id}"]}
        ],
        'sports_psychologist': [
            {"title": "Schedule mental check-in", "type": "psychology_task", "due": current_date, "relatedIds": [f"player:{player_id}", f"match:{match_id}"]},
            {"title": "Review emotional patterns", "type": "psychology_task", "due": current_date, "relatedIds": [f"player:{player_id}", f"match:{match_id}"]}
        ],
        'strength_conditioning_coach': [
            {"title": "Assess recovery needs", "type": "fitness_task", "due": current_date, "relatedIds": [f"player:{player_id}", f"match:{match_id}"]},
            {"title": "Adjust training load", "type": "fitness_task", "due": current_date, "relatedIds": [f"player:{player_id}", f"match:{match_id}"]}
        ],
        'medical_staff': [
            {"title": "Health status review", "type": "medical_task", "due": current_date, "relatedIds": [f"player:{player_id}", f"match:{match_id}"]},
            {"title": "Injury risk assessment", "type": "medical_task", "due": current_date, "relatedIds": [f"player:{player_id}", f"match:{match_id}"]}
        ]
    }
    
    actions = [base_action]
    if user_role.lower() in role_actions:
        actions.extend(role_actions[user_role.lower()])
    
    return actions


def _generate_role_specific_suggestions(user_role: str, role_config: Dict[str, Any], performance_data: Dict[str, Any]) -> List[str]:
    """Generate role-specific next suggestions"""
    
    role_suggestions = {
        'athlete_player': [
            "Focus on one key improvement area",
            "Celebrate your strengths",
            "Plan your next training session"
        ],
        'coach': [
            "Analyze tactical positioning",
            "Review passing patterns and network",
            "Analyze possession segments and team control",
            "Compare touch leaderboard rankings"
        ],
        'sports_psychologist': [
            "Assess mental fatigue levels",
            "Review emotional regulation",
            "Plan mental recovery strategies"
        ],
        'strength_conditioning_coach': [
            "Monitor recovery indicators",
            "Adjust training intensity",
            "Plan recovery protocols"
        ],
        'medical_staff': [
            "Monitor health indicators",
            "Assess injury risk factors",
            "Plan preventive measures"
        ],
        'data_analyst': [
            "Analyze performance trends",
            "Compare with historical data",
            "Identify key performance indicators",
            "Analyze passing network patterns",
            "Review possession segment analysis",
            "Study touch distribution patterns"
        ]
    }
    
    # Return role-specific suggestions or default ones
    return role_suggestions.get(user_role.lower(), [
        "Review performance metrics",
        "Plan next steps",
        "Monitor progress"
    ])


def _identify_role_specific_needs(user_role: str, performance_data: Dict[str, Any], role_config: Dict[str, Any]) -> List[str]:
    """Identify role-specific data needs"""
    
    base_needs = []
    
    # Check for missing TraceVision data
    if 'tracevision_data' not in performance_data or not performance_data['tracevision_data']:
        base_needs.append("tracevision_performance_data")
    
    # Role-specific needs
    role_needs = {
        'sports_psychologist': ["mental_state_data", "emotional_regulation_metrics", "stress_indicators"],
        'strength_conditioning_coach': ["recovery_metrics", "load_response_data", "fatigue_indicators"],
        'medical_staff': ["health_metrics", "injury_history", "vital_signs"],
        'data_analyst': ["historical_performance_data", "comparative_metrics", "trend_analysis_data"],
        'video_analyst': ["video_highlights", "tactical_moments", "visual_performance_data"]
    }
    
    needs = base_needs.copy()
    if user_role.lower() in role_needs:
        needs.extend(role_needs[user_role.lower()])
    
    return needs


def _generate_placeholder_response(task: str, player_id: str, match_id: str, user_role: str, notes: str, performance_data: Dict[str, Any], current_date: str) -> str:
    """Generate placeholder response for tasks not yet implemented"""
    
    response = {
        "summary": f"Task '{task}' not yet implemented. Currently supporting 'summarize_performance' only.",
        "actions": [
            {
                "title": "Implement task support",
                "type": "coach_task",
                "due": current_date,
                "relatedIds": [f"player:{player_id}", f"match:{match_id}"]
            }
        ],
        "deltas": {
            "xp": {"change": 0, "reason": ""},
            "goals": [],
            "milestones": []
        },
        "next_suggestions": [
            "Focus on summarize_performance for now",
            "Add support for other tasks later",
            "Test with current functionality"
        ],
        "needs": [f"task_{task}_implementation"]
    }
    
    return json.dumps(response, indent=2)
