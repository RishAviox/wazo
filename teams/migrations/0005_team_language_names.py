# Generated manually for adding language_names field to Team model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0004_team_jersey_color'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='language_names',
            field=models.JSONField(blank=True, default=dict, help_text="Multilingual team names: {'en': 'Team Name', 'he': 'שם הקבוצה'}", null=True),
        ),
    ]

