from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets, mixins
from django.core.cache import cache
from django.utils import timezone
from django.utils.timezone import datetime
from datetime import datetime as std_datetime
import ast
import re
import json

import google.generativeai as genai

from questionnaire.models import DailyWellnessQuestionnaire, RPEQuestionnaire
from calendar_entry.models import CalendarEventEntry, CalendarGoalEntry
from calendar_entry.serializers import CalendarEventSerializer, CalendarGoalSerializer
from .utils import (
        get_answer_id, 
        get_rpe_answer_id, 
        update_or_insert_wellness_response, 
        update_or_insert_rpe_response,
        calculate_recurrence_dates,
        get_latest_welness_responses_for_user,
    )
from .prompts import get_wellness_overview_prompt


# [Mobile App] feature name: update_wellness
class ChatwellnessAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        user_id = user.phone_no
        selected_language = user.selected_language

        session_id = request.data.get('session_id')
        user_message = request.data.get('message')
        question_id = request.data.get('question_id')

        print("[Chat Wellness] => User_id:", user_id)
        print("[Chat Wellness] => Selected Language:", selected_language)
        print("[Chat Wellness] => Session ID:", session_id)
        print("[Chat Wellness] => User Message:", user_message)
        print("[Chat Wellness] => Question ID:", question_id)

        if not user_message or not session_id:
            print("[Chat Wellness] => Missing 'message' or 'session_id' in request")
            return Response({
                "error": "Missing required fields: 'message' and 'session_id'."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Fetch questions for this language
        all_questions = list(DailyWellnessQuestionnaire.objects.filter(
            language=selected_language
        ).order_by('created_on', 'id'))
        print(f"[Chat Wellness] => Total questions fetched: {len(all_questions)}")

        if not all_questions:
            print("[Chat Wellness] => No questions found for selected language.")
            return Response({"message": "No questions found for this language."}, status=404)

        # Cache key format
        cache_key = f"wellness_session_{user_id}_{session_id}"

        # Get or initialize session data from cache
        session_data = cache.get(cache_key)
        if session_data is None:
            print(f"[Chat Wellness] => Initializing session data in cache for session_id: {session_id}")
            session_data = {"asked_questions": []}
        else:
            print(f"[Chat Wellness] => Loaded session data from cache for session_id: {session_id}")

        asked_ids = set(session_data.get("asked_questions", []))
        print(f"[Chat Wellness] => Already asked question IDs: {asked_ids}")

        # Save previous answer if applicable (and not greeting)
        if question_id and user_message.lower() != "hey":
            print(f"[Chat Wellness] => Processing answer for question_id: {question_id}")
            answer_id = get_answer_id(question_id, user_message, all_questions)
            print(f"[Chat Wellness] => Mapped answer_id: {answer_id}")
            update_or_insert_wellness_response(user_id, answer_id)
            asked_ids.add(question_id)
            print(f"[Chat Wellness] => Updated asked_ids: {asked_ids}")
            
            # ✅ Early termination condition for WQ-7 in English and Hebrew
            early_termination_responses = {"no pain at all.", "ללא כאב בכלל."}
            if question_id == "WQ-7" and user_message.strip().lower() in early_termination_responses:
                print("[Chat Wellness] => Ending session early due to WQ-7 response: No pain at all.")
                cache.delete(cache_key)
                return Response({
                    "message": "You've completed all wellness questions for today!",
                    "question_id": None,
                    "options": []
                })
        else:
            print("[Chat Wellness] => Skipping answer processing (greeting or no question_id)")

        # Find next question not asked yet
        next_question = None
        for question in all_questions:
            print(f"[Chat Wellness] => Checking question ID: {question.q_id} - Asked? {'Yes' if question.q_id in asked_ids else 'No'}")
            if question.q_id not in asked_ids:
                next_question = question
                print(f"[Chat Wellness] => Next question selected: {question.q_id}")
                break

        # Update cache with current session state
        session_data["asked_questions"] = list(asked_ids)
        cache.set(cache_key, session_data, timeout=60 * 60 * 24)  # Cache for 24 hours
        print(f"[Chat Wellness] => Session data updated in cache: {session_data}")

        if not next_question:
            print("[Chat Wellness] => All questions completed.")
            return Response({
                "message": "You've completed all wellness questions for today!",
                "question_id": None,
                "options": []
            })

        print(f"[Chat Wellness] => Returning question_id: {next_question.q_id}, options: {next_question.response_choices or []}")

        return Response({
            "message": next_question.question_to_ask,
            "question_id": next_question.q_id,
            "options": next_question.response_choices or []
        })

# [Mobile App] feature name: log_rpe
class RPEChatAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        user_id = user.phone_no
        session_id = request.data.get('session_id')
        user_message = request.data.get('message')
        question_id = request.data.get('question_id')
        after_session_type = request.data.get('after_session_type') 
        selected_language = (user.selected_language or 'en').lower()

        if not session_id or not user_message or not after_session_type:
            return Response({"error": "Missing required fields"}, status=400)

        # Load or initialize session cache
        cache_key = f"rpe_session_{user_id}_{session_id}"
        session_data = cache.get(cache_key) or {"asked_questions": []}
        asked_ids = set(session_data.get("asked_questions", []))
        
        print(f"[Chat RPE] => Already asked question IDs: {asked_ids}")
        
        
         # Get next question
        all_questions = RPEQuestionnaire.objects.filter(
            after_session_type=after_session_type,
            language=selected_language
        ).order_by('created_on')


        # Save previous answer (if any)
        if question_id and user_message.lower() != "hey":
            answer_id = get_rpe_answer_id(question_id, user_message, all_questions)
            update_or_insert_rpe_response(user_id, answer_id)
            asked_ids.add(question_id)

       

        next_question = None
        for q in all_questions:
            print(f"Checking question ID: {q.q_id} - Asked? {'Yes' if q.q_id in asked_ids else 'No'}")
            if q.q_id not in asked_ids:
                next_question = q
                print(f"[Chat RPE] => Next question selected: {q.q_id}")
                
                break

        # Update cache
        session_data["asked_questions"] = list(asked_ids)
        cache.set(cache_key, session_data, timeout=60 * 60 * 24)

        if not next_question:
            return Response({
                "message": "You've completed all RPE questions for this session!",
                "question_id": None,
                "options": []
            })
            
        print(f"[Chat RPE] => Returning question_id: {next_question.q_id}, options: {next_question.response_choices or []}")


        return Response({
            "message": next_question.question_to_ask,
            "question_id": next_question.q_id,
            "options": next_question.response_choices or {"data": []}
        })
 
# [Mobile App] feature name: how am i doing?
class WellnessOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        user_id = f"{user.phone_no}"
        session_id = request.data.get('session_id')
        user_message = request.data.get('message')
        selected_language = f"{user.selected_language}"

        if not session_id or not user_message:
            return Response({"error": "Missing required fields [session_id, message]"}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"wellness_overview_{user_id}_{session_id}"
        chat_history = cache.get(cache_key) or []

        try:
            if user_message == "Hey":
                user_message = get_latest_welness_responses_for_user(user)

            # Ensure user_message is string
            if not isinstance(user_message, str):
                user_message = json.dumps(user_message)

            all_questions = DailyWellnessQuestionnaire.objects.filter(
                language=selected_language
            ).order_by('created_on')

            prompt = get_wellness_overview_prompt(selected_language, all_questions)

            generation_config = {
                "temperature": 1,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
                "response_mime_type": "text/plain",
            }

            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config=generation_config,
                system_instruction=prompt,
            )

            # Start chat with history if available
            chat_session = model.start_chat(history=chat_history)

            # Add user's message
            chat_session.history.append({
                "role": "user",
                "parts": [user_message]
            })

            # Send message
            response = chat_session.send_message(user_message)

            # Format model's response
            response_message = response.text.strip()
            follow_up_questions = []

            # Extract options from response text
            match = re.search(r'\[(.*?)\]', response_message)
            if match:
                options = [option.strip() for option in match.group(1).split(',')]
                follow_up_questions = [
                    {"id": f"option_{i+1}", "text": option, "emoji": "👉"}
                    for i, option in enumerate(options)
                ]
                response_message = response_message.replace(match.group(0), '').strip()

            # Add model's response to history
            chat_session.history.append({
                "role": "model",
                "parts": [response_message]
            })

            # Cache only the chat history
            cache.set(cache_key, chat_session.history, timeout=60 * 60 * 24)

            return Response({
                'message': response_message,
                'options': follow_up_questions
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
  
  
class CalendarAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        custom_repeat = request.query_params.getlist("custom_repeat")
        
        if not start_date and not end_date:
            return Response({"error": "Both start_date and end_date are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        start_date = timezone.make_aware(start_date, timezone.get_current_timezone())
        
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
        end_date = timezone.make_aware(end_date, timezone.get_current_timezone())
        
        today = timezone.now().date()
        
        # [Needs Review]: Why can't start_date be in the past?
        if start_date.date() < today:
            return Response({"error": "Start date cannot be in the past."}, status=status.HTTP_400_BAD_REQUEST)
        
        if end_date.date() < today:
            return Response({"error": "End date cannot be in the past."}, status=status.HTTP_400_BAD_REQUEST)
        
        if start_date > end_date:
            return Response({"error": "End date cannot be before start date."}, status=status.HTTP_400_BAD_REQUEST)
        
        if custom_repeat:
            try:
                custom_repeat = ast.literal_eval(custom_repeat) 
            except Exception:
                return Response({"error": "Invalid format for custom_repeat."})
 
        filters = {
            'user': user,
            'date__gte': start_date,
            'date__lte': end_date,
        }
        
        if custom_repeat:
            filters['custom_repeat__days'] = custom_repeat

        # Fetch and serialize events
        events = CalendarEventEntry.objects.filter(**filters)
        event_serializer = CalendarEventSerializer(events, many=True).data
        
        goals = CalendarGoalEntry.objects.filter(user=user, start_date__gte=start_date, end_date__lte=end_date)
        goal_serializer = CalendarGoalSerializer(goals, many=True).data
        
        # Get recurring events (that may start before the given start_date)
        recurring_events = CalendarEventEntry.objects.filter(
            user=user,
            repeat__in=['Daily', 'Weekly', 'Monthly', 'Yearly']
        )

        expanded_recurring_events = []
        for event in recurring_events:
            rec_dates = calculate_recurrence_dates(event, start_date, end_date)
            for date in rec_dates:
                # Clone the event with updated date only for serialization (do not save to DB)
                cloned_event = CalendarEventEntry(
                    id=event.id,
                    user=event.user,
                    category=event.category,
                    sub_category=event.sub_category,
                    detail=event.detail,
                    title=event.title,
                    date=date.date(),  # Use just the date part
                    start_time=event.start_time,
                    end_time=event.end_time,
                    location=event.location,
                    repeat=event.repeat,
                    custom_repeat=event.custom_repeat,
                    participants=event.participants,
                    notes=event.notes,
                )
                expanded_recurring_events.append(cloned_event)

        expanded_serializer = CalendarEventSerializer(expanded_recurring_events, many=True).data
        combined_events = event_serializer + expanded_serializer
 
        return Response({
            "events": combined_events,
            "goals": goal_serializer
        }, status=status.HTTP_200_OK)

class CalendarEventAPIViewSet(mixins.CreateModelMixin,
                           mixins.UpdateModelMixin,
                           mixins.DestroyModelMixin,
                           viewsets.GenericViewSet
                        ):
    # here GET method is not allowed
    queryset = CalendarEventEntry.objects.all()
    serializer_class = CalendarEventSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
class CalendarGoalAPIViewSet(mixins.CreateModelMixin,
                          mixins.UpdateModelMixin,
                          mixins.DestroyModelMixin,
                          viewsets.GenericViewSet
                        ):
    # here GET method is not allowed
    queryset = CalendarGoalEntry.objects.all()
    serializer_class = CalendarGoalSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
   
class GameOverviewAPIView(APIView):
    pass


class PlayerPostMatchIntelligenceAPIView(APIView):
    """
    API endpoint for OpenAI function calling with player_postmatch_intelligence.
    Generates performance analysis, tactical insights, and coaching recommendations.
    Integrates with TraceVision data for comprehensive player analysis.
    
    OpenAI automatically determines the analysis type based on the context and user input.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Process post-match intelligence requests with OpenAI function calling.
        OpenAI automatically decides what type of analysis to perform based on the context.
        
        Expected payload:
        {
            "playerId": "player_123",
            "matchId": "match_789",
            "userRole": "Coach",
            "notes": "Player showed good work rate but faded after 70 minutes",
            "language": "auto",
            "timezone": "UTC"
        }
        """
        try:
            from .conversation_runner import run_conversation_sync
            
            # Extract required parameters
            player_id = request.data.get('playerId')
            match_id = request.data.get('matchId')
            user_role = request.data.get('userRole')
            notes = request.data.get('notes', '')
            language = request.data.get('language', 'auto')
            timezone = request.data.get('timezone', 'UTC')
            
            # Validate required fields
            if not all([player_id, match_id, user_role]):
                return Response({
                    'error': 'Missing required fields: playerId, matchId, and userRole are required.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate user role - now supports all 16 roles
            valid_roles = [
                "athlete_player", "coach", "assistant_coach", "personal_coach", 
                "skills_coach", "technical_director", "data_analyst", "video_analyst",
                "sports_psychologist", "strength_conditioning_coach", "fitness_trainer",
                "nutritionist_dietitian", "rehab_recovery_specialist", "medical_staff",
                "scout_talent_identification", "team_manager"
            ]
            if user_role.lower() not in [role.lower() for role in valid_roles]:
                return Response({
                    'error': f'Invalid userRole. Must be one of: {", ".join(valid_roles)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Handle language auto-detection
            if language == "auto":
                user = request.user
                language = getattr(user, 'selected_language', 'en') or 'en'
            
            print(f"[Post-Match Intelligence] => Processing request for player: {player_id}, match: {match_id}, role: {user_role}")
            
            # Construct intelligent prompt for OpenAI function calling
            prompt = self._construct_analysis_prompt(
                player_id=player_id,
                match_id=match_id,
                user_role=user_role,
                notes=notes,
                language=language,
                timezone=timezone
            )
            
            print(f"[Post-Match Intelligence] => Constructed prompt for OpenAI analysis")
            
            # Process with OpenAI conversation runner (includes TraceVision data)
            try:
                response_text = run_conversation_sync(prompt)
                
                if not response_text:
                    return Response({
                        'error': 'Failed to generate AI response'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                print(f"[Post-Match Intelligence] => OpenAI response generated successfully")
                
                # Try to parse the response as JSON
                try:
                    parsed_response = json.loads(response_text)
                    return Response({
                        'success': True,
                        'data': parsed_response,
                        'raw_response': response_text,
                        'metadata': {
                            'playerId': player_id,
                            'matchId': match_id,
                            'userRole': user_role,
                            'language': language,
                            'analysis_type': 'ai_determined',
                            'generated_at': std_datetime.now().isoformat()
                        }
                    })
                except json.JSONDecodeError:
                    # If response is not valid JSON, return it as text
                    return Response({
                        'success': True,
                        'data': {
                            'summary': 'AI analysis completed',
                            'raw_analysis': response_text
                        },
                        'raw_response': response_text,
                        'metadata': {
                            'playerId': player_id,
                            'matchId': match_id,
                            'userRole': user_role,
                            'language': language,
                            'analysis_type': 'ai_determined',
                            'generated_at': std_datetime.now().isoformat(),
                            'note': 'Response was not in expected JSON format'
                        }
                    })
                    
            except Exception as e:
                print(f"[Post-Match Intelligence] => Error in OpenAI processing: {e}")
                return Response({
                    'error': f'Error generating AI analysis: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            print(f"Error in PlayerPostMatchIntelligenceAPIView: {e}")
            return Response({
                'error': 'Internal server error',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _construct_analysis_prompt(self, player_id, match_id, user_role, notes, language, timezone):
        """
        Construct an intelligent prompt for OpenAI function calling.
        The LLM will decide which function to call based on the user's intent.
        """

        base = (
            f"Generate a post-match report using the `player_postmatch_intelligence` function.\n\n"
            f"Details:\n"
            f"- Player ID: {player_id}\n"
            f"- Match ID: {match_id}\n"
            f"- Task: summarize_performance\n"
            f"- User Role: {user_role}\n"
            f"- Language: {language}\n"
            f"- Notes: {notes.strip() if notes.strip() else 'None'}"
            f"Respond in {language} if specified, otherwise use English."
        )
        return base
        
        # Base prompt for function calling
        prompt = f"""
        You are an AI assistant for football performance analysis. A {user_role} is requesting analysis for player {player_id} from match {match_id}.
        
        User Context:
        - Role: {user_role}
        - Notes: {notes if notes else 'None provided'}
        - Language: {language}
        - Timezone: {timezone}
        
        Available Functions:
        - player_postmatch_intelligence: Generate post-match intelligence with role-specific insights
        
        Instructions:
        Based on the user's request and role, determine the appropriate function to call and parameters.
        Focus on providing role-appropriate analysis and actionable insights.
        
        Use the player_postmatch_intelligence function with appropriate parameters to generate the analysis.
        The function will automatically fetch all necessary performance data including TraceVision statistics.
        
        Respond in {language} if specified, otherwise use English.
        """
        
        return prompt


