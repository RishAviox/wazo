# Generated manually on 2026-01-06 to fix phone_no NOT NULL constraint
# The model already allows null=True, but the database constraint was still NOT NULL
# This migration ensures the database matches the model definition

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_wajouser_language_metadata'),
    ]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE accounts_wajouser ALTER COLUMN phone_no DROP NOT NULL;",
            reverse_sql="ALTER TABLE accounts_wajouser ALTER COLUMN phone_no SET NOT NULL;",
        ),
    ]

