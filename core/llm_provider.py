from django.conf import settings
import google.generativeai as genai
from openai import OpenAI

# Configure OpenAI
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Keep Gemini as fallback
genai.configure(api_key=settings.WAJO_GOOGLE_GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash")

def generate_llm_response(prompt):
    """Legacy function for basic prompt-response generation using Gemini"""
    return gemini_model.generate_content(prompt).text