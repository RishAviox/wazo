from ..models import GPSAthleticSkills, GPSFootballAbilities


def __convert_m_to_km(value, metric_unit_mapping="m"):
        if value >= 1000:
            value = round(value/1000, 2)
            metric_unit_mapping = "km"
        return value, metric_unit_mapping


def calculate_gps_athletic_skills(row):
    metric_mappings = {
        "Corrected Play Time (min)": "min",
        "Top Speed (km/h)": "km/h",
        "Session Intensity Speed": "Km/h",
        "Dist. Covered (m)": "m",
        "Max. Intensity Run (m)": "m",
        "High Intensity Run (#)": "",
        "High Intensity Run (m)": "m",
        "Max. Int. Acceleration (#)": "",
        "Max. Int. Acceleration (m)": "m",
        "Max. Int. Deceleration (#)": "",
        "Max. Int. Deceleration (m)": "m",
        "Session Intensity Acceleration": "",
        "High Int. Acceleration (#)": "",
        "High Int. Acceleration (m)": "m",
        "High Int. Deceleration (#)": "",
        "High Int. Deceleration (m)": "m",
        "Jogging (m)": "m",
        "Walking (m)": "m",
        "Session Volume": "m",
        "Session Intensity": "m",
    }

    performance_weights = {
        "Corrected Play Time (min)": 0,
        "Top Speed (km/h)": 8,
        "Session Intensity Speed": 4,
        "Dist. Covered (m)": 5,
        "Max. Intensity Run (m)": 8,
        "High Intensity Run (#)": 8,
        "High Intensity Run (m)": 8,
        "Max. Int. Acceleration (#)": 5,
        "Max. Int. Acceleration (m)": 5,
        "Max. Int. Deceleration (#)": 5,
        "Max. Int. Deceleration (m)": 5,
        "Session Intensity Acceleration": 4,
        "High Int. Acceleration (#)": 5,
        "High Int. Acceleration (m)": 5,
        "High Int. Deceleration (#)": 5,
        "High Int. Deceleration (m)": 5,
        "Jogging (m)": 4,
        "Walking (m)": 3,
        "Session Volume": 5,
        "Session Intensity": 3,
    }

    skills_and_metrics_mapping = {
        "Play Time": "Corrected Play Time (min)",
        "Top Speed": "Top Speed (km/h)",
        "Int. Speed": "Session Intensity Speed",
        "Distance Covered": "Dist. Covered (m)",
        "Max Int. Run": "Max. Intensity Run (m)",
        "High Int. Run": "High Intensity Run (#), High Intensity Run (m)",
        "Max Int. Acceleration": "Max. Int. Acceleration (#), Max. Int. Acceleration (m)",
        "Max Int. Deceleration": "Max. Int. Deceleration (#), Max. Int. Deceleration (m)",
        "Session Int. Acceleration": "Session Intensity Acceleration",
        "High Int. Acceleration": "High Int. Acceleration (#), High Int. Acceleration (m)",
        "High Int. Deceleration": "High Int. Deceleration (#), High Int. Deceleration (m)",
        "Jogging": "Jogging (m)",
        "Walking": "Walking (m)",
        "Session Volume": "Session Volume",
        "Session Intensity": "Session Intensity",
    }

    response = {}


    def calculate_pnm(metric_key, metric_value, play_time):
        if metric_key in [
            "Top Speed (km/h)",
            "Corrected Play Time (min)",
            "Session Volume",
            "Session Intensity",
        ]:
            return metric_value
        else:
            return (metric_value / play_time) * 90


    def calculate_performance_base_scores(metrics_used: str, metrics_val):
        if metrics_used == "Top Speed (km/h)":
            if metrics_val > 26:
                return 10
            elif metrics_val > 24:
                return 7.5
            elif metrics_val > 22:
                return 5
            else:
                return 2.5
        elif metrics_used == "Max. Intensity Run (m)":
            if metrics_val > 130:
                return 10
            elif metrics_val > 120:
                return 7.5
            elif metrics_val > 100:
                return 5
            else:
                return 2.5
        elif metrics_used == "High Intensity Run (#)":
            if metrics_val > 7:
                return 10
            elif metrics_val > 6:
                return 7.5
            elif metrics_val > 5:
                return 5
            else:
                return 2.5
        elif metrics_used == "High Intensity Run (m)":
            if metrics_val > 550:
                return 10
            elif metrics_val > 500:
                return 7.5
            elif metrics_val > 400:
                return 5
            else:
                return 2.5
        elif metrics_used == "Max. Int. Acceleration (m)":
            if metrics_val > 18:
                return 10
            elif metrics_val > 17:
                return 7.5
            elif metrics_val > 15:
                return 5
            else:
                return 2.5
        elif metrics_used in [
            "Max. Int. Acceleration (#)",
            "Max. Int. Deceleration (#)",
            "High Int. Acceleration (#)",
            "High Int. Deceleration (#)",
        ]:
            if metrics_val > 7:
                return 10
            elif metrics_val > 5:
                return 7.5
            elif metrics_val > 4:
                return 5
            else:
                return 2.5
        elif metrics_used in ["Max. Int. Deceleration (m)", "High Int. Deceleration (m)"]:
            if metrics_val > 25:
                return 10
            elif metrics_val > 22:
                return 7.5
            elif metrics_val > 20:
                return 5
            else:
                return 2.5
        elif metrics_used in ["Session Intensity Acceleration", "Session Volume"]:
            if metrics_val > 8:
                return 10
            elif metrics_val > 6:
                return 7.5
            elif metrics_val > 4:
                return 5
            else:
                return 2.5
        elif metrics_used == "Jogging (m)":
            if metrics_val > 2.5:
                return 10
            elif metrics_val > 2:
                return 7.5
            elif metrics_val > 1.8:
                return 5
            else:
                return 2.5
        elif metrics_used == "Walking (m)":
            if metrics_val > 1.8:
                return 10
            elif metrics_val > 1.6:
                return 7.5
            elif metrics_val > 1.5:
                return 5
            else:
                return 2.5
        elif metrics_used == "Session Intensity":
            if metrics_val > 85:
                return 10
            elif metrics_val > 75:
                return 7.5
            elif metrics_val > 60:
                return 5
            else:
                return 2.5
        elif metrics_used in ["High Int. Acceleration (m)", "Session Intensity Speed"]:
            if metrics_val > 20:
                return 10
            elif metrics_val > 18:
                return 7.5
            elif metrics_val > 15:
                return 5
            else:
                return 2.5
        elif metrics_used == "Dist. Covered (m)":
            if metrics_val > 10000:
                return 10
            elif metrics_val > 9000:
                return 7.5
            elif metrics_val > 7000:
                return 5
            else:
                return 2.5

    metric_value_mapping = {}

    for column_name, _ in metric_mappings.items():
        try:
            metric_value_mapping[column_name] = int(row[column_name].iloc[0])
        except:
            metric_value_mapping[column_name] = 0

    metric_value_mapping_copy = metric_value_mapping.copy()
    play_time = metric_value_mapping["Corrected Play Time (min)"]
    for key, value in metric_value_mapping.items():
        pnm = calculate_pnm(key, value, play_time)
        metric_value_mapping[key] = pnm

    def calculate_pws(skill, metric):
        data = metric.split(",")
        if len(data) == 1:
            metric_1 = data[0].strip()
            metric_unit_mapping = metric_mappings[metric_1]
            value = metric_value_mapping_copy[metric_1]
            if metric_unit_mapping == "m":
                value, metric_unit_mapping = __convert_m_to_km(value, metric_unit_mapping)
            return (
                calculate_performance_base_scores(
                    metric_1, metric_value_mapping_copy[metric_1]
                )
                * performance_weights[metric_1]
                / 100
            ), f"{value} {metric_unit_mapping}"
        elif len(data) == 2:
            metric_1 = data[0].strip()
            metric_2 = data[1].strip()
            metric_unit_mapping = metric_mappings[metric_2]
            value = metric_value_mapping_copy[metric_2]
            if metric_unit_mapping == "m":
                value, metric_unit_mapping = __convert_m_to_km(value, metric_unit_mapping)
            response_1 = (
                calculate_performance_base_scores(
                    metric_1, metric_value_mapping_copy[metric_1]
                )
                * performance_weights[metric_1]
                / 100
            )
            response_2 = (
                calculate_performance_base_scores(
                    metric_2, metric_value_mapping_copy[metric_2]
                )
                * performance_weights[metric_2]
                / 100
            )
            return (
                    response_1 + response_2
            ), f"{int(metric_value_mapping_copy[metric_1])}|{value} {metric_mappings[metric_1]}{metric_unit_mapping}"


    sum_of_pws = 0
    for skill, metric in skills_and_metrics_mapping.items():
        if skill == "Play Time":
            response[skill] = f'{metric_value_mapping["Corrected Play Time (min)"]} min'
        else:
            pws, value = calculate_pws(skill, metric)
            response[skill] = value
            sum_of_pws += pws

    response["Athletic Skills"] = str(round(sum_of_pws, 1))

    return response


def calculate_gps_football_abilities(row):

    metric_mappings = {
        "Corrected Play Time (min)": "min",
        "Dribbling Count (#)": "",
        "Dribbling Dist. (m)": "m",
        "Power Kicks (#)": "",
        "Kick Power (km/h)": "km/h",
        "Low Int. Kicks (#)": "",
        "Med. Int. Kicks (#)": "",
        "High Int. Kicks (#)": "",
        "Max. Intensity Run (#)": "",
        "Session Volume": "",
        "Session Intensity": "",
    }

    performance_weights = {
        "Dribbling Count (#)": 15,
        "Dribbling Dist. (m)": 12,
        "Low Int. Kicks (#)": 10,
        "Med. Int. Kicks (#)": 10,
        "High Int. Kicks (#)": 12,
        "Kick Power (km/h)": 10,
        "Power Kicks (#)": 10,
        "Max. Intensity Run (#)": 10,
        "Session Volume": 11,
        "Session Intensity": 10,
    }

    skills_and_metrics_mapping = {
        "Play Time": "Corrected Play Time (min)",
        "Dribbling": "Dribbling Count (#) | Dribbling Dist. (m)",
        "Power Kicks": "Power Kicks (#)",
        "Kick Power": "Kick Power (km/h)",
        "Low Int. Kicks": "Low Int. Kicks (#)",
        "Med. Int. Kicks": "Med. Int. Kicks (#)",
        "High Int. Kicks": "High Int. Kicks (#)",
        "Max. Intensity Run": "Max. Intensity Run (#)",
        "Session Volume": "Session Volume",
        "Session Intensity": "Session Intensity",
    }

    response = {}


    def calculate_pnm(metric_key, metric_value, play_time):
        if metric_key in [
            "Corrected Play Time (min)",
            "Session Volume",
            "Session Intensity",
        ]:
            return metric_value
        else:
            return (metric_value / play_time) * 90


    def calculate_performance_base_scores(metrics_used: str, metrics_val):
        if metrics_used == "Dribbling Count (#)":
            if metrics_val > 50:
                return 10
            elif metrics_val > 40:
                return 7.5
            elif metrics_val > 30:
                return 5
            else:
                return 2.5
        elif metrics_used == "Dribbling Dist. (m)":
            if metrics_val > 250:
                return 10
            elif metrics_val > 200:
                return 7.5
            elif metrics_val > 150:
                return 5
            else:
                return 2.5
        elif metrics_used == "Low Int. Kicks (#)":
            if metrics_val > 50:
                return 10
            elif metrics_val > 40:
                return 7.5
            elif metrics_val > 30:
                return 5
            else:
                return 2.5
        elif metrics_used == "Med. Int. Kicks (#)":
            if metrics_val > 40:
                return 10
            elif metrics_val > 30:
                return 7.5
            elif metrics_val > 20:
                return 5
            else:
                return 2.5
        elif metrics_used == "High Int. Kicks (#)":
            if metrics_val > 30:
                return 10
            elif metrics_val > 20:
                return 7.5
            elif metrics_val > 10:
                return 5
            else:
                return 2.5
        elif metrics_used in ["Kick Power (km/h)", "Power Kicks (#)"]:
            if metrics_val > 70:
                return 10
            elif metrics_val > 60:
                return 7.5
            elif metrics_val > 50:
                return 5
            else:
                return 2.5
        elif metrics_used == "Max. Intensity Run (#)":
            if metrics_val > 7:
                return 10
            elif metrics_val > 5:
                return 7.5
            elif metrics_val > 3:
                return 5
            else:
                return 2.5
        elif metrics_used == "Session Volume":
            if metrics_val > 8:
                return 10
            elif metrics_val > 6:
                return 7.5
            elif metrics_val > 4:
                return 5
            else:
                return 2.5
        elif metrics_used == "Session Intensity":
            if metrics_val > 85:
                return 10
            elif metrics_val > 75:
                return 7.5
            elif metrics_val > 60:
                return 5
            else:
                return 2.5

    metric_value_mapping = {}

    for column_name in metric_mappings.keys():
        try:
            metric_value_mapping[column_name] = int(row[column_name].iloc[0])
        except:
            metric_value_mapping[column_name] = 0

    metric_value_mapping_copy = metric_value_mapping.copy()
    play_time = metric_value_mapping["Corrected Play Time (min)"]
    for key, value in metric_value_mapping.items():
        pnm = calculate_pnm(key, value, play_time)
        metric_value_mapping[key] = pnm


    def calculate_pws(metric):
        data = metric.split("|")
        if len(data) == 1:
            metric_1: str = data[0].strip()
            metric_unit_mapping = metric_mappings[metric_1]
            value = metric_value_mapping_copy[metric_1]
            if metric_unit_mapping == "m":
                value, metric_unit_mapping = __convert_m_to_km(value, metric_unit_mapping)
            return (
                calculate_performance_base_scores(
                    metric_1, metric_value_mapping_copy[metric_1]
                )
                * performance_weights[metric_1]
                / 100
            ), f"{metric_value_mapping_copy[metric_1]} {metric_mappings[metric_1]}"
        elif len(data) == 2:
            metric_1 = data[0].strip()
            metric_2 = data[1].strip()
            metric_unit_mapping = metric_mappings[metric_2]
            value = metric_value_mapping_copy[metric_2]
            if metric_unit_mapping == "m":
                value, metric_unit_mapping = __convert_m_to_km(value, metric_unit_mapping)
            response_1 = (
                calculate_performance_base_scores(
                    metric_1, metric_value_mapping_copy[metric_1]
                )
                * performance_weights[metric_1]
                / 100
            )
            response_2 = (
                calculate_performance_base_scores(
                    metric_2, metric_value_mapping_copy[metric_2]
                )
                * performance_weights[metric_2]
                / 100
            )
            return (response_1 + response_2), f"{int(metric_value_mapping_copy[metric_1])}|{value} {metric_mappings[metric_1]}{metric_unit_mapping}"


    sum_of_pws = 0
    for skill, metric in skills_and_metrics_mapping.items():
        if skill == "Play Time":
            response[skill] = f'{metric_value_mapping["Corrected Play Time (min)"]} min'
        else:
            pws, value = calculate_pws(metric)
            response[skill] = value
            sum_of_pws += pws

    response["Football Skills"] = round(sum_of_pws, 1)

    return response


def get_gps_athletic_skills_metrics(user):
    try:
        metrics = GPSAthleticSkills.objects.filter(user=user).latest('updated_on')
        return metrics.metrics
    
    except:
        return {}


def get_gps_football_abilities_metrics(user):
    try:
        metrics = GPSFootballAbilities.objects.filter(user=user).latest('updated_on')
        return metrics.metrics
    
    except:
        return {}
