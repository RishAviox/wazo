import google.generativeai as genai
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache

from questionnaire.models import DailyWellnessQuestionnaire
from .utils import get_answer_id, extract_question_details, update_or_insert_wellness_response
from .prompts import get_wellness_prompt

user_sessions = {}

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
  
      
class GameOverviewAPIView(APIView):
    pass