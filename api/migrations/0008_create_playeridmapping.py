from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_alter_playeridmapping_options'),  
    ]

    operations = [
        migrations.CreateModel(
            name='PlayerIDMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('player_id', models.CharField(max_length=255)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='player_ids', to='api.Wajouser')),
            ],
            options={
                'verbose_name': 'Player ID Mapping',
                'verbose_name_plural': 'Player ID Mappings',
            },
        ),
    ]
