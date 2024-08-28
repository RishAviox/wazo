
STATUS_METRIC_WEIGHTS = {
    "Athlete Status": {
        "Overall Wellness": 0.3,
        "Readiness": 0.3,
        "Subjective Performance Index (SPI)": 0.25,
        "Recovery": 0.15
    },
    "Overall Wellness": {
        "Mood": 0.15,
        "Sleep Quality": 0.2,
        "Energy Level": 0.15,
        "Muscle Soreness": 0.1,
        "Diet": 0.1,
        "Stress Level": 0.15,
        "Pain Level": 0.1,
        "Hydration Status": 0.05
    },
    "RPE": {
        "RPE": 1.0
    },
    "Readiness": {
        "Muscle Soreness": 0.15,
        "Stress Level": 0.15,
        "Pain Level": 0.1,
        "Fatigue": 0.15,
        "Recovery": 0.15,
        "Mood": 0.1,
        "Sleep Quality": 0.1,
        "Performance": 0.5,
        "Satisfaction": 0.3,
        "Intensity": 0.2
    },
    "Recovery": {
        "Sleep Quality": 0.3,
        "Muscle Soreness": 0.25,
        "Fatigue": 0.25,
        "Recovery": 0.2
    },
    "Subjective Performance Index": {
        "Performance": 0.5,
        "Satisfaction": 0.3,
        "Intensity": 0.2
    },
    "sRPE": {
        "SRPE": 1.0
    }
}


WPI_WEIGHTS = {
    'Overall Score': {
        'Pace': 0.15,
        'Shooting': 0.2,
        'Passing': 0.15,
        'Dribbling': 0.1,
        'Defending': 0.2,
        'Physicality': 0.1,
        'Game Intelligence': 0.05,
        'Composure': 0.05,
        'Goal Keeping': 0.02,  # for only goal keepers otherwise 0
    },
    'Position Specific': {
        'CAM': {
            'Pace': 1.1,
            'Shooting': 1.2,
            'Passing': 1.4,
            'Dribbling': 1.3,
            'Defending': 0.8,
            'Physicality': 1,
            'Game Intelligence': 1.3,
            'Composure': 1.2,
        },
        'CM' : {
            'Pace': 1,
            'Shooting': 1.1,
            'Passing': 1.4,
            'Dribbling': 1.2,
            'Defending': 1.1,
            'Physicality': 1.1,
            'Game Intelligence': 1.3,
            'Composure': 1.1,
        },
        'CDM' : {
            'Pace': 0.9,
            'Shooting': 0.8,
            'Passing': 1.2,
            'Dribbling': 1,
            'Defending': 1.5,
            'Physicality': 1.3,
            'Game Intelligence': 1.4,
            'Composure': 1.2,
        },
        'CB' : {
            'Pace': 1,
            'Shooting': 0.6,
            'Passing': 1,
            'Dribbling': 0.8,
            'Defending': 1.5,
            'Physicality': 1.4,
            'Game Intelligence': 1.3,
            'Composure': 1.3,
        },
        'RB/LB' : {
            'Pace': 1.3,
            'Shooting': 0.7,
            'Passing': 1.2,
            'Dribbling': 1.1,
            'Defending': 1.3,
            'Physicality': 1.2,
            'Game Intelligence': 1.2,
            'Composure': 1.1,
        },
        'RW/LW' : {
            'Pace': 1.4,
            'Shooting': 1.3,
            'Passing': 1.2,
            'Dribbling': 1.4,
            'Defending': 0.9,
            'Physicality': 1.1,
            'Game Intelligence': 1.3,
            'Composure': 1.2,
        },
        'ST/CF' : {
            'Pace': 1.3,
            'Shooting': 1.5,
            'Passing': 1,
            'Dribbling': 1.2,
            'Defending': 0.8,
            'Physicality': 1.3,
            'Game Intelligence': 1.4,
            'Composure': 1.3,
        },
        'GK' : {
            'Pace': 0.6,
            'Shooting': 0.5,
            'Passing': 1.1,
            'Dribbling': 0.7,
            'Defending': 1.4,
            'Physicality': 1.3,
            'Game Intelligence': 1.5,
            'Composure': 1.4,
        },
    },
    'Metric Specific': {
        'Pace': {
            'Top Speed': 0.45,
            'High Intensity Run': 0.35,
            'Max Intensity Run': 0.1,
            'Max Intensity Acceleration': 0.07,
            'High Intensity Acceleration': 0.03
        },
        'Shooting': {
            'Goal': 0.4,
            'Shot on Target': 0.3,
            'Shot in PA': 0.15,
            'Shot outside PA': 0.05,
            'Shot Blocked': -0.03,
            'Shot Off Target': -0.07,
            'Kick Power': 0.03,
        },
        'Passing': {
            'Pass Succeeded': 0.35,
            'Key Pass': 0.3,
            'Long Pass Succeeded': 0.15,
            'Cross Succeeded': 0.1,
            'Final Third Area Pass Succeeded': 0.1,
            'Pass Failed': -0.05,
            'Intercept': 0.05,
            'Backward Pass Succeeded': 0.05,
        },
        'Dribbling': {
            'Take-On Succeeded': 0.5,
            'Dribbling Count': 0.15,
            'Dribbling Distance': 0.15,
            'High Intensity Runs': 0.1,
            'Take-On Failed': -0.05,
        },
        'Defending': {
            'Tackle Succeeded': 0.35,
            'Intercept': 0.25,
            'Clearance': 0.15,
            'Block': 0.1,
            'Defensive Line Support Succeeded': 0.1,
            'Loose Ball Duel Succeeded': 0.1,
            'Tackle Failed': -0.03,
        },
        'Physicality': {
            'Aerial Duel Succeeded': 0.35,
            'Ground Duel Succeeded': 0.3,
            'Recovery': 0.2,
            'High Intensity Acceleration': 0.08,
            'High Intensity Deceleration': 0.07,
        },
        'Game Intelligence': {
            'Key Pass': 0.25,
            'Mistake': -0.2,
            'Offside': -0.08,
            'Own Goal': -0.25,
            'Intervention': 0.15,
            'Assist': 0.15,
        }
    },
    'Position Modifiers': {
        'ST': {
            'SHO': 1.2,
            'PHY': 1.05
        },
        'LW': {
            'SHO': 1.15,
            'DRI': 1.1
        },
        'RW': {
            'SHO': 1.15,
            'DRI': 1.1
        },
        'CAM': {
            'PAS': 1.1,
            'DRI': 1.1
        },
        'CDM': {
            'DEF': 1.1,
        },
        'CB': {
            'DEF': 1.2,
            'PHY': 1.1
        },
        'LB': {
            'DEF': 1.15,
            'PAC': 1.05
        },
        'RB': {
            'DEF': 1.15,
            'PAC': 1.05
        },
        'CF': {
            'SHO': 1.2,
            'DRI': 1.1
        },
        'CM': {
            'PAS': 1.1,
        },
        'RM': {
            'PAS': 1.1,
            'DRI': 1.05
        },
        'LM': {
            'PAS': 1.1,
            'DRI': 1.05
        },
        'GK': {
            'GK': 1.3,
        },
    },
    'Injury History': {
        'No Injuries': 1,
        'Minor Injuries': 0.98,
        'Moderate Injuries': 0.95,
        'Major Injuries': 0.9,
        'Chronic Injuries': 0.85
    },
    'Training Load': {
        'Optimal Load': 1,
        'High Load': 0.97,
        'Low Load': 0.98,
        'Overload': 0.95,
        'Underload': 0.95
    },
    'Decline Rate': {
        'Pace': {
            'Peak Age': 25,
            'Decline Rate': 0.05
        },
        'Shooting': {
            'Peak Age': 28,
            'Decline Rate': 0.03
        },
        'Passing': {
            'Peak Age': 30,
            'Decline Rate': 0.02
        },
        'Dribbling': {
            'Peak Age': 26,
            'Decline Rate': 0.04
        },
        'Defending': {
            'Peak Age': 29,
            'Decline Rate': 0.03
        },
        'Phisicality': {
            'Peak Age': 28,
            'Decline Rate': 0.03
        },
        'Game Intelligence': {
            'Peak Age': 32,
            'Decline Rate': 0.01
        },
        'Composure': {
            'Peak Age': 30,
            'Decline Rate': 0.02
        },
        'Goalkeeping': {
            'Peak Age': 30,
            'Decline Rate': 0.02
        },
    },
}
