from django.conf import settings
from django.db import transaction
from django.utils import timezone

import secrets
import requests
import jwt
from django.conf import settings

import pandas as pd

from .models import OTPStore
from teams.models import Team
from games.models import Game
from cards.utils import calculate_gps_athletic_skills, calculate_gps_football_abilities
from cards.utils import calculate_attacking_skills, calculate_videocard_defensive, calculate_videocard_distributions
from cards.models import GPSAthleticSkills, GPSFootballAbilities, AttackingSkills, VideoCardDefensive, VideoCardDistributions


def generate_access_token(user):
    payload = {
        'id': user.phone_no,
        'exp': timezone.now() + settings.JWT_ACCESS_TOKEN_EXPIRATION,  # Short-lived
        'iat': timezone.now(),
        'token_type': 'access',
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

def generate_refresh_token(user):
    payload = {
        'id': user.phone_no,
        'exp': timezone.now() + settings.JWT_REFRESH_TOKEN_EXPIRATION,  # Long-lived
        'iat': timezone.now(),
        'token_type': 'refresh',
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


# generate, store and send otp
def generate_and_send_otp(phone_no):
    # For guest account
    if phone_no == "+14085551234":
        return "123456"
    otp_number = secrets.randbelow(900000) + 100000 # 6 digit 
    otp = OTPStore(data=str(otp_number), phone_no=phone_no)
    otp.save()

    # send OTP via API call
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        "number": phone_no,
        "OTP": str(otp_number)
    }
    print(data)
    if not settings.DEBUG:
        response = requests.post(settings.WAJO_OTP_SERVICE_URL, headers=headers, json=data)
        print(response.text)
    return otp


def validate_otp(phone_no, input_otp):
    """
        Prevent race conditions with atomic and select_for_update() for row level locking
        Reference: https://docs.djangoproject.com/en/5.0/topics/db/transactions/
    """
    # For guest account
    if phone_no == "+14085551234" and input_otp == "123456":
        return True
    with transaction.atomic(): 
        try:
            otp = OTPStore.objects.select_for_update().filter(phone_no=phone_no).latest('created_on')
            if otp.is_valid() and otp.data == input_otp:
                otp.is_used = True
                otp.save()
                return True
            else:
                return False
        except OTPStore.DoesNotExist:
            return False


def process_gps_file(player_id_instance, data_file):
    try:
        gps_sheet = pd.read_excel(data_file, sheet_name='Oliver GPS Metrcis')

        match_id = gps_sheet['MatchID'].iloc[0]
    
        player_id = player_id_instance.player_id
        user = player_id_instance.user

        
        # fetch the game
        game = Game.objects.get(
            id=match_id,
        )
        print(f"Game retrieved : {game}")

        # *************** cards stats calculations
        print(f"processing for player with id: {player_id}")
        
        # Convert player_id columns to strings for consistent comparison
        gps_sheet['Player ID'] = gps_sheet['Player ID'].astype(int).astype(str)
        
        gps_row = gps_sheet[gps_sheet['Player ID'] == player_id]
            
        if gps_row.empty:
            print(f"GPS data is not available for the player({user}) with ID({player_id}).")
        else:
            gps_athletic_skills = calculate_gps_athletic_skills(gps_row)
            gps_football_abilities = calculate_gps_football_abilities(gps_row)
            print(f"Calculated GPS Athletic Skills for player {player_id}: {gps_athletic_skills}.")
            print(f"Calculated GPS Football Abilities for player {player_id}: {gps_football_abilities}.")
                
            # Create or update the GPS Athletic skills for the user
            athletic_skills, created = GPSAthleticSkills.objects.update_or_create(
                user=user,
                game=game,
                defaults={'metrics': gps_athletic_skills}
            )
            if created:
                print(f"Created GPS Athletic Skills for player {player_id} (phone: {user}).")
            else:
                print(f"Updated GPS Athletic Skills for player {player_id} (phone: {user}).")
            # Create or update the GPS Football abilities for the user
            football_abilities, created = GPSFootballAbilities.objects.update_or_create(
                user=user,
                game=game,
                defaults={'metrics': gps_football_abilities}
            )
            if created:
                print(f"Created GPS Football Abilities for player {player_id} (phone: {user}).")
            else:
                print(f"Updated GPS Football Abilities for player {player_id} (phone: {user}).")
    except Exception as e:
        print(f"Error processing GPS data file: {e}")        
        
        
def process_video_file(player_id_instance, data_file):
    try:
        stats_sheet = pd.read_excel(data_file, sheet_name='PlayerStats_137183')
        match_sheet = pd.read_excel(data_file, sheet_name='MatchDetails')

        # Extract Match ID
        if 'id' not in match_sheet.columns:
            raise ValueError("Match Details sheet is missing the 'match_id' column.")
            
        match_id = match_sheet['id'].iloc[0]
        
        player_id = player_id_instance.player_id
        user = player_id_instance.user

        #  fetch the game
        game = Game.objects.get(
            id=match_id,
        )
        print(f"Game retrieved: {game}")
        
        # *************** cards stats calculations
        print(f"processing for player with id: {player_id}")

        # Convert player_id columns to strings for consistent comparison
        stats_sheet['player_id'] = stats_sheet['player_id'].astype(int).astype(str)
            
        stats_row = stats_sheet[stats_sheet['player_id'] == player_id]
                
        if stats_row.empty:
            print(f"Stats Video data is not available for the player({user}) with ID({player_id}).")
        else:                    
            # Extract data from rows
            stats_data = stats_row.iloc[0].to_dict()
                    
            attacking_skills = calculate_attacking_skills(stats_data, match_sheet)
            videocard_defensive = calculate_videocard_defensive(stats_data, match_sheet)
            videocard_distributions = calculate_videocard_distributions(stats_data, match_sheet)

            print(f"Calculated Attacking Skills for player {player_id}: {attacking_skills}.")
            print(f"Calculated Video Card Defensive for player {player_id}: {videocard_defensive}.")
            print(f"Calculated Video Card Distributions for player {player_id}: {videocard_distributions}.")

            # Create or update the Attacking skills for the user
            _attacking_skills, created = AttackingSkills.objects.update_or_create(
                user=user,
                game=game,
                defaults={'metrics': attacking_skills}
            )

            if created:
                print(f"Created Attacking Skills for player {player_id} (phone: {user}).")
            else:
                print(f"Updated Attacking Skills for player {player_id} (phone: {user}).")


            # Create or update the Video Card Defensive for the user
            _videocard_defensive, created = VideoCardDefensive.objects.update_or_create(
                user=user,
                game=game,
                defaults={'metrics': videocard_defensive}
            )
            
            if created:
                print(f"Created Video Card Defensive for player {player_id} (phone: {user}).")
            else:
                print(f"Updated Video Card Defensive for player {player_id} (phone: {user}).")

            # Create or update the Video Card Distributions for the user
            _videocard_distributions, created = VideoCardDistributions.objects.update_or_create(
                user=user,
                game=game,
                defaults={'metrics': videocard_distributions}
            )

            if created:
                print(f"Created Video Card Distributions for player {player_id} (phone: {user}).")
            else:
                print(f"Updated Video Card Distributions for player {player_id} (phone: {user}).")
 
    except Exception as e:
        print(f"Error processing video data file: {e}")
    

