from accounts.models import WajoUser
from teams.models import TeamStats
import google.generativeai as genai
from datetime import timedelta , time ,date ,datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

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
        question_id = request.data.get('questionId')

        print("[Chat Wellness] => User_id" , user_id)
        print("[Chat Wellness] => user_lang" , selected_language)
        
        if not user_message or not session_id:
            return Response({
                "error": "Missing required fields: 'message' and 'session_id'."
            }, status=status.HTTP_400_BAD_REQUEST)

        daily_wellness_questionnaire = DailyWellnessQuestionnaire.objects.filter(language=selected_language)
        system_instruction = get_wellness_prompt(selected_language, daily_wellness_questionnaire)

        print("system_instruction", system_instruction)
        
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        if session_id not in user_sessions[user_id]:
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
            chat_session = model.start_chat(history=[{"role": "user", "parts": [user_message]}])
            user_sessions[user_id][session_id] = chat_session
            print("chat_session" , chat_session)
        else:
            chat_session = user_sessions[user_id][session_id]
            chat_session.history.append({"role": "user", "parts": [user_message]})
        
        response = chat_session.send_message(user_message)
        user_sessions[user_id][session_id] = chat_session
        print("response", response)
        
        if question_id is not None:
            answer_id = get_answer_id(question_id, user_message, daily_wellness_questionnaire)
            print("answer_id" , answer_id)
            update_or_insert_wellness_response(user_id, answer_id)
    
    # Extract the main message, question id, and any follow-up options from the response
        main_message, new_question_id, options = extract_question_details(response.text, daily_wellness_questionnaire)
        chat_session.history.append({"role": "model", "parts": [main_message]})
        user_sessions[user_id][session_id] = chat_session
        print("main Re" , main_message)
        print("new" ,new_question_id)
        print("op" , options)

        return Response({'message': main_message, 'question_id': new_question_id, 'options': options}) 


class GameOverviewAPIView(APIView):
    pass