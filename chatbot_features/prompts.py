import json

def get_wellness_prompt(selected_language, questionnaire):
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

    