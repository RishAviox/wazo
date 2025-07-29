from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets, mixins
from django.core.cache import cache
from django.utils import timezone
from django.utils.timezone import datetime
import ast

from questionnaire.models import DailyWellnessQuestionnaire, RPEQuestionnaire
from calendar_entry.models import CalendarEventEntry, CalendarGoalEntry
from calendar_entry.serializers import CalendarEventSerializer, CalendarGoalSerializer
from .utils import (
        get_answer_id, 
        get_rpe_answer_id, 
        update_or_insert_wellness_response, 
        update_or_insert_rpe_response,
        calculate_recurrence_dates,
    )


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