# Generated manually for adding language_metadata field to Game model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('games', '0013_remove_gameuserrole_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='language_metadata',
            field=models.JSONField(blank=True, default=dict, help_text="Multilingual match data with 'en' and 'he' sections containing match summary, lineups, replacements, bench, coaches, and referees", null=True),
        ),
    ]

