# Function schema for OpenAI function calling
PLAYER_POSTMATCH_INTELLIGENCE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "player_postmatch_intelligence",
        "description": "Generate post-match intelligence for a player, including performance insights, tactical alignment, and guided reflection.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Type of post-match intelligence to generate.",
                    "enum": [
                        "summarize_performance",
                        "compare_to_previous",
                        "highlight_strengths",
                        "identify_improvement_areas",
                        "evaluate_tactical_fit",
                        "trigger_emotional_reflection"
                    ]
                },
                "userRole": {
                    "type": "string",
                    "description": "Role of the requester.",
                    "enum": [
                        "athlete_player",
                        "coach",
                        "assistant_coach",
                        "personal_coach",
                        "skills_coach",
                        "technical_director",
                        "data_analyst",
                        "video_analyst",
                        "sports_psychologist",
                        "strength_conditioning_coach",
                        "fitness_trainer",
                        "nutritionist_dietitian",
                        "rehab_recovery_specialist",
                        "medical_staff",
                        "scout_talent_identification",
                        "team_manager"
                    ],
                    "description": "Comprehensive role support for all team members and staff positions"
                },
                "playerId": {
                    "type": "string",
                    "description": "Unique identifier for the player."
                },
                "matchId": {
                    "type": "string",
                    "description": "Unique identifier for the match."
                },
                "language": {
                    "type": "string",
                    "description": "BCP-47 tag (e.g., 'en', 'he', 'pt-BR'). If omitted or 'auto', mirror the requester's language.",
                    "default": "auto"
                },
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone (e.g., 'Asia/Jerusalem').",
                    "default": "UTC"
                },
                "notes": {
                    "type": "string",
                    "description": "Short context or observations.",
                    "default": ""
                },
                "clientTimestamp": {
                    "type": "string",
                    "description": "ISO-8601 UTC (e.g., 2025-08-17T12:00:00Z)."
                },
                "previousMatchId": {
                    "type": "string",
                    "description": "Optional: previous match to compare against."
                },
                "extensions": {
                    "type": "object",
                    "description": "Org-specific optional fields."
                }
            },
            "required": ["task", "userRole", "playerId", "matchId"]
        },
    },
    "strict": True
}
