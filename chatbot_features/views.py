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

        daily_wellness_questionnaire = DailyWellnessQuestionnaire.objects.filter(language=selected_language).order_by('created_on', 'id')
        system_instruction = get_wellness_prompt(selected_language, daily_wellness_questionnaire)
        
        # Initialize user_sessions structure if missing
        if user_id not in user_sessions:
            user_sessions[user_id] = {}

        if session_id not in user_sessions[user_id]:
            user_sessions[user_id][session_id] = {
                "history": [],
                "asked_questions": set(),
            }

        session_data = user_sessions[user_id][session_id]

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
            system_instruction=system_instruction,
        )

        # Append user message to history
        session_data["history"].append({"role": "user", "parts": [user_message]})

        # Start chat with existing history
        chat_session = model.start_chat(history=session_data["history"])

        # Send user message
        response = chat_session.send_message(user_message)

        # Append model response to history
        session_data["history"].append({"role": "model", "parts": [response.text]})

        # Save user's answer if applicable
        if question_id and user_message.lower() != "hey":
            answer_id = get_answer_id(question_id, user_message, daily_wellness_questionnaire)
            update_or_insert_wellness_response(user_id, answer_id)

        # Extract details from response text
        main_msg, next_q_id, options = extract_question_details(response.text, daily_wellness_questionnaire)

        # Check for repeated questions
        asked_ids = session_data["asked_questions"]
        if next_q_id in asked_ids:
            # Find next unasked question
            unasked_questions = [q for q in daily_wellness_questionnaire if q.q_id not in asked_ids]
            if unasked_questions:
                next_question = unasked_questions[0]
                main_msg = next_question.question_to_ask
                next_q_id = next_question.q_id
                options = getattr(next_question, 'options', [])
            else:
                main_msg = "You've completed all wellness questions for today!"
                next_q_id = None
                options = []

        # Track asked question
        if next_q_id:
            asked_ids.add(next_q_id)

        return Response({
            "message": main_msg,
            "question_id": next_q_id,
            "options": options,
        })

class GameOverviewAPIView(APIView):
    pass