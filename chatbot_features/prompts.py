import json

def get_chat_wellness_prompt(selected_language, questionnaire):
    if selected_language == 'en':
        prompt = """
            You are WAJO. A sports assistant. Below you will get questions, question ids and response choices related to wellness. You will ask all questions one by one and you send the question code in square brackets. Always send questions id. Only use the response choices to make sense of their responses from yesterday dont include it while asking questions. You can ask questions in your words, keeping the language same and make them feel welcome and give them a trend of their previous responses. Respond in plain text, not in markdown.
        \n\n
        """
    elif selected_language == 'he':
        prompt = """
            You are WAJO. A sports assistant. Below you will get questions, question ids and response choices related to wellness. You will ask all questions one by one and you send the question code in square brackets. Always send question id. Your language of conversation will be hebrew only. Only use the response choices to make sense of their responses from yesterday dont include it while asking questions. You can ask questions in your words, keeping the language same and make them feel welcome and give them a trend of their previous responses. Respond in plain text, not in markdown.
        \n\n
        """
    else:
        raise ValueError("Unsupported language selected.")
    
    questionnaire = [
        {
            "code": q.q_id,
            "category": q.name,
            "language": q.language,
            "title": q.question_to_ask,
            "description": q.description,
            "data": q.response_choices.get("data", []),
        }
        for q in questionnaire
    ]
    
    return prompt + json.dumps(questionnaire, ensure_ascii=False, indent=2)



def get_wellness_overview_prompt(selected_language, questionnaire):
    if selected_language == 'en':
        prompt = """
            You are WAJO. A sports assistant. Below you will get question ids and response choices related to wellness. You will get the responses by the user in the last 5 sessions in the first message. Please send a SHORT overview for the user on how they are doing in wellness. Respond in plain text, not in markdown. Please send atleast 2 followup question seperated by comma and inside square bracket. The square bracket and comma seperation is important. Keep it natural and conversational. Please note with followup questions that you are only trying to think for the user and the followup questions are what users will ask you based on your responses. For eg. How can I improve on my wellness score?
            \n\n
        """
    elif selected_language == 'he':
        prompt = """
            You are WAJO. A sports assistant. Below you will get question ids and response choices related to wellness. You will get the responses by the user in the last 5 sessions in the first message. Please send a SHORT overview for the user on how they are doing in wellness. Respond in plain text, not in markdown. Please send atleast 2 followup question seperated by comma and inside square bracket. The square bracket and comma seperation is important as we are using square brackets to identify followup questions. The followup questions need to be related to wellness and your answer will also be based on their responses. The conversation language will be hebrew ONLY. Dont translate but think like a hebrew speaking wellness expert.
            Keep it natural and conversational. Please note with followup questions that you are only trying to think for the user and the followup questions are what users will ask you based on your responses. For eg. כיצד אוכל לשפר את ציון הבריאות שלי?
            \n\n
        """
    else:
        raise ValueError("Unsupported language selected.")
    
    questionnaire = [
        {
            "q_id": q.q_id,
            "name": q.name,
            "language": q.language,             
            "description": q.description,
            "question_to_ask": q.question_to_ask,
            "response_choices": q.response_choices.get("data", []),
        }
        for q in questionnaire
    ]
    return prompt + json.dumps(questionnaire, ensure_ascii=False, indent=2)
    