from django.db import migrations


def fix_must_change_password(apps, schema_editor):
    """Reset must_change_password=False for all seeded/test staff accounts."""
    AdminClinique = apps.get_model('clinic', 'AdminClinique')
    AdminClinique.objects.all().update(must_change_password=False)


class Migration(migrations.Migration):

    dependencies = [
        ('clinic', '0010_auth_and_missing_features'),
    ]

    operations = [
        migrations.RunPython(fix_must_change_password, migrations.RunPython.noop),
    ]
