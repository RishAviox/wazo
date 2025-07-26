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

        print("[Chat Wellness] => User_id" , user_id)
        print("[Chat Wellness] => user_lang" , selected_language)
        
        if not user_message or not session_id:
            return Response({
                "error": "Missing required fields: 'message' and 'session_id'."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get all questions in order
        all_questions = list(DailyWellnessQuestionnaire.objects.filter(
            language=selected_language
        ).order_by('created_on', 'id'))

        if not all_questions:
            return Response({"message": "No questions found for this language."}, status=404)

        if user_id not in user_sessions:
            user_sessions[user_id] = {}
            
        # Ensure session_id entry exists
        if session_id not in user_sessions[user_id]:
            user_sessions[user_id][session_id] = {
                "asked_questions": set()
            }
            
        session_data = user_sessions[user_id][session_id]
        asked_ids = session_data["asked_questions"]

        # Save previous answer (if not greeting)
        if question_id and user_message.lower() != "hey":
            answer_id = get_answer_id(question_id, user_message, all_questions)
            update_or_insert_wellness_response(user_id, answer_id)
            asked_ids.add(question_id)

        # Determine next question
        next_question = None
        for question in all_questions:
            print("[Chat Wellness] => Checking question ID:", question.q_id)
            if question.q_id not in asked_ids:
                next_question = question
                break

        if not next_question:
            return Response({
                "message": "You've completed all wellness questions for today!",
                "question_id": None,
                "options": []
            })

        return Response({
            "message": next_question.question_to_ask,
            "question_id": next_question.q_id,
            "options" : next_question.response_choices or []
        })
        
class GameOverviewAPIView(APIView):
    pass