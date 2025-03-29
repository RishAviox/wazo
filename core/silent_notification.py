import requests
from django.conf import settings

def send_silent_notification(user_ids, card_names, game_created):
    url = settings.WAJO_NOTIFICATIONS_API_URL + "/silent-notification"
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        "user_ids": user_ids,
        "card_names": card_names,
        "is_game_created": game_created
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(response.text)
    except Exception as e:
        print("Failed to send silent notification: ", e)
        