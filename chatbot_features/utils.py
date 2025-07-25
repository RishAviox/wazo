import re
from django.utils import timezone
from django.utils.timezone import now, datetime
import json

from questionnaire.models import DailyWellnessUserResponse

def get_answer_id(question_id, user_response, daily_wellness_questionnaire):
    for question in daily_wellness_questionnaire:
        if question.q_id == question_id:
            for answer in json.loads(question.response_choices)["data"]:
                if answer["text"] == user_response:
                    return [{"question_id": question_id, "answer_id": answer["id"]}]
    return None

def get_options_by_question_id(question_id, daily_wellness_questionnaire):
        question = next((q for q in daily_wellness_questionnaire if q.q_id == question_id), None)
        return json.loads(question.response_choices)["data"] if question else []


def extract_question_details(response_text, daily_wellness_questionnaire):
    """
    Extracts the main text, question ID, and options from a response text.

    Args:
        response_text (str): The text containing the question ID and message.
        language (str): Language parameter to pass to get_options_by_question_id function.

    Returns:
        tuple: (str) response_message, (str) question_id, (list) options
    """
    # Extract the question ID from within square brackets
    match = re.search(r'\[(.*?)\]', response_text)
    question_id = match.group(1) if match else None

    # Remove the question ID from the response message if it was found
    if match:
        response_message = response_text.replace(match.group(0), '').strip()
    else:
        response_message = response_text.strip()

    # Retrieve options based on the question ID
    options = get_options_by_question_id(question_id, daily_wellness_questionnaire) if question_id else []

    return response_message, question_id, options


def update_or_insert_wellness_response(user_id, updated_json):
    print("+++update_or_insert_json_async+++")
    print("upJson:", updated_json)

    today = timezone.make_aware(datetime.combine(now().date(), datetime.min.time()))
    user_response = DailyWellnessUserResponse.objects.filter(user_id=user_id, created_on__gte=today).first()
        
    if user_response:
        print("Found existing response:", user_response, user_response.response)
        existing_response = user_response.response

        # Merge new data into existing response
        for new_entry in updated_json:
            updated = False
            for existing_entry in existing_response:
                if existing_entry["question_id"] == new_entry["question_id"]:
                    existing_entry["answer_id"] = new_entry["answer_id"]
                    updated = True
                    break
            if not updated:
                existing_response.append(new_entry)

        user_response.response = existing_response
        user_response.save()
        print("Response updated.")
        return "Updated"
    else:
        # Create new response
        new_response = DailyWellnessUserResponse(
            user_id=user_id,
            response=updated_json
        )
        new_response.save()
        print("New response created.")
        return "Created"