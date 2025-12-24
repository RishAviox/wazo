# Generated manually for adding language fields to TraceSession and TracePlayer models

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracevision', '0006_remove_tracesession_unique_video_url_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tracesession',
            name='language_metadata',
            field=models.JSONField(blank=True, default=dict, help_text="Multilingual match data with 'en' and 'he' sections containing match summary, lineups, replacements, bench, coaches, and referees", null=True),
        ),
        migrations.AddField(
            model_name='traceplayer',
            name='language_data',
            field=models.JSONField(blank=True, default=dict, help_text="Multilingual player data: {'en': {'name': 'Player Name', 'role': 'GK'}, 'he': {'name': 'שם שחקן', 'role': 'שוער'}}", null=True),
        ),
    ]

