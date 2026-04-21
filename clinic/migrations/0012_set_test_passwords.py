"""
Migration 0012 — Mots de passe standardisés pour les comptes de test.

Comptes patients  : mot de passe = "patient123"
Comptes staff     : mot de passe = numéro de téléphone (chiffres uniquement)
                    ex: +222 11 11 11 11  →  "222111111111"

Ces mots de passe sont UNIQUEMENT pour l'environnement de développement/test.
En production, utilisez des mots de passe forts et must_change_password=True.
"""
from django.db import migrations
from django.contrib.auth.hashers import make_password


def set_test_passwords(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    AdminClinique = apps.get_model('clinic', 'AdminClinique')
    Patient = apps.get_model('clinic', 'Patient')

    def normalize(phone):
        return ''.join(ch for ch in (phone or '') if ch.isdigit())

    # --- Comptes staff : mot de passe = numéro normalisé ---
    for admin in AdminClinique.objects.select_related('utilisateur').all():
        if not admin.utilisateur_id:
            continue
        pwd = normalize(admin.telephone) or 'clinic2024'
        User.objects.filter(pk=admin.utilisateur_id).update(
            password=make_password(pwd)
        )

    # --- Comptes patients : mot de passe = "patient123" ---
    # Identifier les users qui ont un profil Patient
    patient_user_ids = Patient.objects.exclude(utilisateur=None).values_list('utilisateur_id', flat=True)
    # Exclure les superusers
    User.objects.filter(pk__in=patient_user_ids, is_superuser=False).update(
        password=make_password('patient123')
    )


class Migration(migrations.Migration):

    dependencies = [
        ('clinic', '0011_fix_must_change_password'),
    ]

    operations = [
        migrations.RunPython(set_test_passwords, migrations.RunPython.noop),
    ]
