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

    def post(self , request):
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

        # Initialize user_sessions dict safely
        if user_id not in user_sessions:
            print(f"[Chat Wellness] => Initializing user_sessions for user_id: {user_id}")
            user_sessions[user_id] = {}

        if session_id not in user_sessions[user_id]:
            print(f"[Chat Wellness] => Initializing session data for session_id: {session_id}")
            user_sessions[user_id][session_id] = {
                "asked_questions": set()
            }

        session_data = user_sessions[user_id][session_id]
        asked_ids = session_data["asked_questions"]
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
            "options" : next_question.response_choices or []
        })

        
class GameOverviewAPIView(APIView):
    pass