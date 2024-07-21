# views related to cards
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.utils.timezone import datetime
from django.utils import timezone
from django.conf import settings
from django.db.models import Sum, F, FloatField, ExpressionWrapper
from django.db.models.functions import Cast, Coalesce
from django.db.models.fields.json import KeyTextTransform


from openai import AzureOpenAI


from api.serializer import (
                        CardSuggestedActionsSerializer, StatusCardMetricsSerializer, 
                        WajoUserSerializer,
                    )
from api.models import (
                    CardSuggestedAction, StatusCardMetrics, PerformanceMetrics, 
                    DefensivePerformanceMetrics, OffensivePerformanceMetrics,
                )
from api.utils import *


openai_client = AzureOpenAI(
                azure_endpoint=settings.WAJO_AZURE_OPENAI_ENDPOINT,
                api_version="2022-12-01",
                api_key=settings.WAJO_AZURE_OPENAI_KEY
            )

# getStatusCardMetric
class StatusCardMetricAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                try:
                    metrics = StatusCardMetrics.objects.filter(user=player).latest('updated_on')
                    player_data.append({
                                'profile': WajoUserSerializer(player).data,
                                'metrics': StatusCardMetricsSerializer(metrics).data
                            })

                except StatusCardMetrics.DoesNotExist:
                    player_data.append({
                                'profile': WajoUserSerializer(player).data,
                                'metrics': {}
                            })

            print("player_data for coach: ", player_data)
            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            try:
                metrics = StatusCardMetrics.objects.filter(user=request.user).latest('updated_on')
                serializer = StatusCardMetricsSerializer(metrics)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except:
                return Response({}, status=status.HTTP_200_OK)

# Get 5 days events for the DailySnapshot card --> changed to per-day
class DailySnapshortCardAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date_str = request.query_params.get('start_date')
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            start_date = timezone.make_aware(start_date, timezone.get_current_timezone())
        else:
            start_date = datetime.today()

        one_time_events, recurring_events = get_events_for_date(user=request.user, event_date=start_date)

        one_time_events_data = [
            {
                'event_type': event.event_type,
                'event': event.event,
                'date': timezone.localtime(event.date),
                'source': event.source,
            }
            for event in one_time_events
        ]

        combined_events = one_time_events_data + recurring_events

        combined_events.sort(key=lambda x: x['date'])

        response = {
            'events': combined_events
        }

        return Response(response, status=status.HTTP_200_OK)

        # one_time_events, recurring_events = get_events_for_next_5_days(user=request.user, start_date=start_date)

        # # one_time_events_data = OneTimeEventsSerializer(one_time_events, many=True).data
        # one_time_events_data = [
        #     {       
        #         'event_type': event.event_type,
        #         'event': event.event,
        #         'date': timezone.localtime(event.date),
        #         'source': event.source,
        #     }
        #     for event in one_time_events
        # ]
    
        # combined_events = one_time_events_data + recurring_events
        # events_by_date = defaultdict(list)
        # for event in combined_events:
        #     event_date = event['date'].date().isoformat()
        #     events_by_date[event_date].append(event)

        # # Sort events for each day by time (latest first)
        # for event_date in events_by_date:
        #     events_by_date[event_date].sort(key=lambda x: x['date'])


        # # Sort the dictionary by date keys (ascending order)
        # events_by_date = OrderedDict(sorted(events_by_date.items()))


        # return Response(events_by_date, status=status.HTTP_200_OK)


# card no. 7, performance metrics API
class PerformanceMetricsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        metrics_data = PerformanceMetrics.objects.filter(user=request.user)

        # Return an empty dictionary if no data is available for the user
        if not metrics_data.exists():
            return Response({}, status=status.HTTP_200_OK)

        total_shots = metrics_data.aggregate(
            total_shots=Sum(
                Coalesce(Cast(KeyTextTransform('value', 'metrics__total_shot'), FloatField()), 0), output_field=FloatField()
            )
        )

        total_passes = metrics_data.aggregate(
            total_passes=Sum(
                Coalesce(Cast(KeyTextTransform('value', 'metrics__pass'), FloatField()), 0), output_field=FloatField()
            )
        )

        results = {
            'Rating': metrics_data.aggregate(total_rating=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__rating'), FloatField()), 0), output_field=FloatField())))['total_rating'],
            'Play Time': metrics_data.aggregate(total_play_time=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__play_time'), FloatField()), 0), output_field=FloatField())))['total_play_time'],
            'Goals': metrics_data.aggregate(total_goals=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__goal'), FloatField()), 0), output_field=FloatField())))['total_goals'],
            'Assists': metrics_data.aggregate(total_assists=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__assist'), FloatField()), 0), output_field=FloatField())))['total_assists'],
            'Shooting Accuracy (%)': (metrics_data.aggregate(total_shot_on_target=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__shot_on_target'), FloatField()), 0), output_field=FloatField())))['total_shot_on_target'] / total_shots['total_shots']) * 100 if total_shots['total_shots'] else 0,
            'Pass Accuracy (%)': (metrics_data.aggregate(total_pass_succeeded=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__pass_succeeded'), FloatField()), 0), output_field=FloatField())))['total_pass_succeeded'] / total_passes['total_passes']) * 100 if total_passes['total_passes'] else 0,
            'Expected Pass Completion (xP)': metrics_data.aggregate(total_pass_succeeded=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__pass_succeeded'), FloatField()), 0), output_field=FloatField())))['total_pass_succeeded'] / total_passes['total_passes'] if total_passes['total_passes'] else 0,
            'Expected Receiver (xReceiver)': (metrics_data.aggregate(total_take_on_succeeded=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__take_on_succeeded'), FloatField()), 0), output_field=FloatField())))['total_take_on_succeeded'] / metrics_data.aggregate(total_take_on=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__take_on'), FloatField()), 0), output_field=FloatField())))['total_take_on'] if metrics_data.aggregate(total_take_on=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__take_on'), FloatField()), 0), output_field=FloatField())))['total_take_on'] else 0) * (metrics_data.aggregate(total_forward_pass_succeeded=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__forward_pass_succeeded'), FloatField()), 0), output_field=FloatField())))['total_forward_pass_succeeded'] / metrics_data.aggregate(total_forward_pass=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__forward_pass'), FloatField()), 0), output_field=FloatField())))['total_forward_pass'] if metrics_data.aggregate(total_forward_pass=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__forward_pass'), FloatField()), 0), output_field=FloatField())))['total_forward_pass'] else 0),
            'Expected Threat (xThreat)': metrics_data.aggregate(x_threat=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__forward_pass_succeeded'), FloatField()), 0) * 1.2 + Coalesce(Cast(KeyTextTransform('value', 'metrics__final_third_area_pass_succeeded'), FloatField()), 0) * 1.5 * 2, output_field=FloatField())))['x_threat'],
        }

        print(f"performance metrics for the user({request.user}): ", results)
        return Response(results, status=status.HTTP_200_OK)

# card no. 8, Defensive Performance Metrics API
class DefensivePerformanceMetricsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        user = request.user
        metrics_data = DefensivePerformanceMetrics.objects.filter(user=user)
        
        # Return an empty dictionary if no data is available for the user
        if not metrics_data.exists():
            return Response({}, status=status.HTTP_200_OK)
        
        results = {}
        FULL_GAME_TIME = 90 * 60 * 1000  # in miliseconds

        play_time = metrics_data.aggregate(total_play_time=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__play_time'), FloatField()), 0), output_field=FloatField())))['total_play_time']
        
        if not play_time or play_time == 0:
            return Response({}, status=status.HTTP_200_OK)
        

        def get_metric(metric_name):
            return metrics_data.aggregate(total=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', f'metrics__{metric_name}'), FloatField()), 0), output_field=FloatField())))['total']

        def normalized_count(metric_name):
            return round((get_metric(metric_name) / play_time) * FULL_GAME_TIME, 2)

        # aerial_clearance = normalized_count('aerial_clearance')
        aerial_clearance_failed = normalized_count('aerial_clearance_failed')
        aerial_clearance_succeeded = normalized_count('aerial_clearance_succeeded')
        clearance = normalized_count('clearance')
        # block = normalized_count('block')
        # intercept = normalized_count('intercept')
        # intervention = normalized_count('intervention')
        tackle = normalized_count('tackle')
        tackle_succeeded = normalized_count('tackle_succeeded')
        # foul = normalized_count('foul')
        # foul_won = normalized_count('foul_won')
        # aerial_duel = normalized_count('aerial_duel')
        aerial_duel_failed = normalized_count('aerial_duel_failed')
        aerial_duel_succeeded = normalized_count('aerial_duel_succeeded')
        # ground_duel = normalized_count('ground_duel')
        ground_duel_failed = normalized_count('ground_duel_failed')
        ground_duel_succeeded = normalized_count('ground_duel_succeeded')
        # loose_ball_duel = normalized_count('loose_ball_duel')
        loose_ball_duel_failed = normalized_count('loose_ball_duel_failed')
        loose_ball_duel_succeeded = normalized_count('loose_ball_duel_succeeded')
        # defensive_line_support = normalized_count('defensive_line_support')
        defensive_line_support_failed = normalized_count('defensive_line_support_failed')
        defensive_line_support_succeeded = normalized_count('defensive_line_support_succeeded')
        # recovery = normalized_count('recovery')
        # goal_conceded = normalized_count('goal_conceded')
        # goal_kick = normalized_count('goal_kick')
        # goal_kick_succeeded = normalized_count('goal_kick_succeeded')
        # save_by_catching = normalized_count('save_by_catching')
        # save_by_punching = normalized_count('save_by_punching')
        # control_under_pressure = normalized_count('control_under_pressure')
        mistake = normalized_count('mistake')
        offside = normalized_count('offside')
        # own_goal = normalized_count('own_goal')

        clearance_success_rate = round((aerial_clearance_succeeded + clearance) / (aerial_clearance_succeeded + aerial_clearance_failed + clearance) * 100, 2) if (aerial_clearance_succeeded + aerial_clearance_failed + clearance) else 0
        tackle_success_rate = round(tackle_succeeded / (tackle) * 100, 2) if (tackle) else 0
        duel_success_rate = round((aerial_duel_succeeded + ground_duel_succeeded + loose_ball_duel_succeeded) / (aerial_duel_succeeded + ground_duel_succeeded + loose_ball_duel_succeeded + aerial_duel_failed + ground_duel_failed + loose_ball_duel_failed) * 100, 2) if (aerial_duel_succeeded + ground_duel_succeeded + loose_ball_duel_succeeded + aerial_duel_failed + ground_duel_failed + loose_ball_duel_failed) else 0
        discipline_score = round(((mistake * 1) + (offside * 3)) / (play_time / FULL_GAME_TIME), 2)

        weighted_clearances_per_full_game = round(((aerial_clearance_succeeded * 2) + (clearance * 2) - (aerial_clearance_failed * 1)) / (play_time / FULL_GAME_TIME), 2)
        overall_clearance_score = round(weighted_clearances_per_full_game * (clearance_success_rate / 100), 2)

        weighted_tackles_per_full_game = round(((tackle_succeeded * 2) - ((tackle - tackle_succeeded) * 1)) / (play_time / FULL_GAME_TIME), 2)
        overall_tackle_score = round(weighted_tackles_per_full_game * (tackle_success_rate / 100), 2)

        weighted_duels_per_full_game = round(((aerial_duel_succeeded * 2) + (ground_duel_succeeded * 2) + (loose_ball_duel_succeeded * 2) - (aerial_duel_failed * 1) - (ground_duel_failed * 1) - (loose_ball_duel_failed * 1)) / (play_time / FULL_GAME_TIME), 2)
        overall_duel_score = round(weighted_duels_per_full_game * (duel_success_rate / 100), 2)

        overall_interception_score = normalized_count('intercept') + normalized_count('intervention')
        overall_recovery_score = normalized_count('recovery')

        overall_defensive_line_support_score = round(((defensive_line_support_succeeded * 2) - (defensive_line_support_failed * 1)) / (play_time / FULL_GAME_TIME), 2)

        overall_defensive_skills_score = round((0.25 * overall_clearance_score + 0.2 * overall_tackle_score + 0.2 * overall_interception_score + 0.15 * overall_duel_score + 0.1 * overall_recovery_score + 0.1 * discipline_score), 2)

        results.update({
            'Overall Defensive Skills Score': overall_defensive_skills_score,
            'Clearances': overall_clearance_score,
            # 'Aerial Clearance': aerial_clearance,
            # 'Aerial Clearance Succeeded': aerial_clearance_succeeded,
            # 'Clearance': clearance,
            # 'Block': block,
            'Tackles': overall_tackle_score,
            # 'Tackle': tackle,
            # 'Tackle Succeeded': tackle_succeeded,
            # 'Foul': foul,
            # 'Foul Won': foul_won,
            'Interceptions': overall_interception_score,
            # 'Intercept': intercept,
            # 'Intervention': intervention,
            'Duels': overall_duel_score,
            # 'Aerial Duel': aerial_duel,
            # 'Aerial Duel Succeeded': aerial_duel_succeeded,
            # 'Aerial Duel Failed': aerial_duel_failed,
            # 'Ground Duel': ground_duel,
            # 'Ground Duel Succeeded': ground_duel_succeeded,
            # 'Ground Duel Failed': ground_duel_failed,
            # 'Loose Ball Duel': loose_ball_duel,
            # 'Loose Ball Duel Succeeded': loose_ball_duel_succeeded,
            # 'Loose Ball Duel Failed': loose_ball_duel_failed,
            'Defensive Line Support': overall_defensive_line_support_score,
            # 'Defensive Line Support Succeeded': defensive_line_support_succeeded,
            # 'Defensive Line Support Failed': defensive_line_support_failed,
            'Recovery': overall_recovery_score,
            # 'Goal Conceded': goal_conceded,
            # 'Goal Kick': goal_kick,
            # 'Goal Kick Succeeded': goal_kick_succeeded,
            # 'Save by Catching': save_by_catching,
            # 'Save by Punching': save_by_punching,
            # 'Control Under Pressure': control_under_pressure,
            # 'Mistake': mistake,
            # 'Offside': offside,
            # 'Own Goal': own_goal,
            'Discipline Score': discipline_score,
        })

        return Response(results, status=status.HTTP_200_OK)



# card no. 9, Offensive Performance Metrics API
class OffensivePerformanceMetricsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        user = request.user
        metrics_data = OffensivePerformanceMetrics.objects.filter(user=user)
        
        # Return an empty dictionary if no data is available for the user
        if not metrics_data.exists():
            return Response({}, status=status.HTTP_200_OK)
        
        results = {}
        FULL_GAME_TIME = 90 * 60 * 1000  # in miliseconds

        play_time = metrics_data.aggregate(total_play_time=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__play_time'), FloatField()), 0), output_field=FloatField())))['total_play_time']
        
        if not play_time or play_time == 0:
            return Response({}, status=status.HTTP_200_OK)

        
        def get_metric(metric_name):
            return metrics_data.aggregate(total=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', f'metrics__{metric_name}'), FloatField()), 0), output_field=FloatField())))['total']

        def normalized_count(metric_name):
            return round((get_metric(metric_name) / play_time) * FULL_GAME_TIME, 2)


        goals = normalized_count('goal')
        assists = normalized_count('assist')
        shot_on_target = normalized_count('shot_on_target')
        shot_off_target = normalized_count('shot_off_target')
        total_shot = normalized_count('total_shot')
        shot_blocked = normalized_count('shot_blocked')
        shot_in_PA = normalized_count('shot_in_PA')
        # shot_outside_of_PA = normalized_count('shot_outside_of_PA')
        # penalty_kick = normalized_count('penalty_kick')
        pass_total = normalized_count('pass')
        pass_succeeded = normalized_count('pass_succeeded')
        pass_failed = normalized_count('pass_failed')
        forward_pass = normalized_count('forward_pass')
        forward_pass_succeeded = normalized_count('forward_pass_succeeded')
        # cross = normalized_count('cross')
        cross_succeeded = normalized_count('cross_succeeded')
        # long_pass = normalized_count('long_pass')
        long_pass_succeeded = normalized_count('long_pass_succeeded')
        # short_pass = normalized_count('short_pass')
        # short_pass_succeeded = normalized_count('short_pass_succeeded')
        take_on = normalized_count('take_on')
        take_on_succeeded = normalized_count('take_on_succeeded')
        # key_pass = normalized_count('key_pass')
        # final_third_pass = normalized_count('final_third_area_pass')
        final_third_pass_succeeded = normalized_count('final_third_area_pass_succeeded')
        # middle_area_pass = normalized_count('middle_area_pass')
        # middle_area_pass_succeeded = normalized_count('middle_area_pass_succeeded')
        # backward_pass = normalized_count('backward_pass')
        # backward_pass_succeeded = normalized_count('backward_pass_succeeded')
        # defensive_area_pass = normalized_count('defensive_area_pass')
        # defensive_area_pass_succeeded = normalized_count('defensive_area_pass_succeeded')

        # pass_accuracy = round((pass_succeeded / pass_total) * 100, 2) if pass_total else 0
        xp = round(pass_succeeded / pass_total, 2) if pass_total else 0
        xreceiver = round((take_on_succeeded / take_on) * (forward_pass_succeeded / forward_pass), 2) if take_on and forward_pass else 0
        xthreat = round(forward_pass_succeeded * 1.2 + final_third_pass_succeeded * 1.5 * 2, 2)

        weighted_passes_per_full_game = round(((pass_succeeded * 1 + forward_pass_succeeded * 1.2 + cross_succeeded * 1.5 + long_pass_succeeded * 1.3 - pass_failed * 0.5) / (play_time / FULL_GAME_TIME)), 2)
        overall_passing_score = round(weighted_passes_per_full_game * (pass_succeeded / pass_total) if pass_total else 0, 2)

        weighted_shots_per_full_game = round(((shot_on_target * 2 + shot_in_PA * 1.5 - shot_off_target - shot_blocked * 0.5) / (play_time / FULL_GAME_TIME)), 2)
        # shooting_accuracy = round((shot_on_target / total_shot) * 100, 2) if total_shot else 0
        overall_shooting_score = round(weighted_shots_per_full_game * (shot_on_target / total_shot) if total_shot else 0, 2)

        weighted_dribbles_per_full_game = round(((take_on_succeeded * 2 + take_on * 2 - take_on_succeeded - take_on_succeeded) / (play_time / FULL_GAME_TIME)), 2)
        # dribbling_success_rate = round((take_on_succeeded / take_on) * 100, 2) if take_on else 0
        overall_dribbling_score = round(weighted_dribbles_per_full_game * (take_on_succeeded / take_on) if take_on else 0, 2)

        overall_offensive_skills_score = round((0.35 * goals + 0.15 * assists + 0.15 * overall_shooting_score + 0.15 * overall_passing_score + 0.1 * overall_dribbling_score + 0.05 * xp + 0.05 * xreceiver), 2)

        results.update({
            'Overall Offensive Skills Score': overall_offensive_skills_score,
            'Goals': goals,
            'Assists': assists,
            # 'Shots on Target': shot_on_target,
            # 'Shots off Target': shot_off_target,
            # 'Total Shots': total_shot,
            # 'Shots Blocked': shot_blocked,
            # 'Shots in PA': shot_in_PA,
            # 'Shots Outside PA': shot_outside_of_PA,
            # 'Penalty Kicks': penalty_kick,
            'Overall Shooting Score': overall_shooting_score,
            # 'Passes': pass_total,
            # 'Pass Accuracy (%)': pass_accuracy,
            'Overall Passing Score': overall_passing_score,
            # 'Key Passes': key_pass,
            # 'Crosses': cross,
            # 'Crosses Completed': cross_succeeded,
            # 'Long Passes': long_pass,
            # 'Long Passes Completed': long_pass_succeeded,
            # 'Short Passes': short_pass,
            # 'Short Passes Completed': short_pass_succeeded,
            # 'Forward Passes': forward_pass,
            # 'Forward Passes Completed': forward_pass_succeeded,
            # 'Final Third Passes': final_third_pass,
            # 'Final Third Passes Completed': final_third_pass_succeeded,
            # 'Middle Area Passes': middle_area_pass,
            # 'Middle Area Passes Completed': middle_area_pass_succeeded,
            # 'Backward Passes': backward_pass,
            # 'Backward Passes Completed': backward_pass_succeeded,
            # 'Defensive Area Passes': defensive_area_pass,
            # 'Defensive Area Passes Completed': defensive_area_pass_succeeded,
            'Overall Dribbling Score': overall_dribbling_score,
            # 'Take Ons': take_on,
            # 'Take Ons Completed': take_on_succeeded,
            'Expected Pass Completion (xP)': xp,
            'Expected Receiver (xReceiver)': xreceiver,
            'Expected Threat (xThreat)': xthreat,
        })
            
        return Response(results, status=status.HTTP_200_OK)


# getCardSuggestedActions
class CardSuggestedActionsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, card):
        try:
            actions = CardSuggestedAction.objects.filter(card_name=card).all()
            serializer = CardSuggestedActionsSerializer(actions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response({ 'error': 'card data not found'}, status=status.HTTP_400_BAD_REQUEST)
        

# cards greetings api
class CardGreetingsAPI(APIView):
    def get(self, request, card):
        pass