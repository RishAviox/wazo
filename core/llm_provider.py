from django.conf import settings
import google.generativeai as genai

genai.configure(api_key=settings.WAJO_GOOGLE_GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

def generate_llm_response(prompt):
    return gemini_model.generate_content(prompt).text