from django.db import migrations, models
import django.db.models.deletion
from django.contrib.auth.hashers import make_password


def forwards(apps, schema_editor):
    User = apps.get_model("auth", "User")
    AdminClinique = apps.get_model("clinic", "AdminClinique")
    Medecin = apps.get_model("clinic", "Medecin")

    def normalize(phone):
        return ''.join(ch for ch in (phone or '') if ch.isdigit())

    for admin in AdminClinique.objects.all():
        if admin.utilisateur_id:
            continue
        phone = normalize(admin.telephone) or str(admin.pk)
        base = f"staff_{phone}"
        username = base
        idx = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}_{idx}"
            idx += 1
        user = User.objects.create(
            username=username,
            first_name=admin.nom,
            last_name='',
            is_staff=admin.role == 'admin',
            password=make_password(phone),
        )
        admin.utilisateur_id = user.id
        admin.must_change_password = True
        admin.save(update_fields=['utilisateur', 'must_change_password'])

    for med in Medecin.objects.all():
        if med.utilisateur_id:
            continue
        linked = None
        if med.telephone:
            linked_admin = AdminClinique.objects.filter(telephone=med.telephone).exclude(utilisateur=None).first()
            if linked_admin:
                linked = linked_admin.utilisateur
        if not linked:
            linked_admin = AdminClinique.objects.filter(role='medecin', nom__iexact=med.nom).exclude(utilisateur=None).first()
            if linked_admin:
                linked = linked_admin.utilisateur
        if linked:
            med.utilisateur_id = linked.id
            med.save(update_fields=['utilisateur'])


class Migration(migrations.Migration):

    dependencies = [
        ('clinic', '0009_capacity_permissions_and_service_mapping'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='adminclinique',
            name='must_change_password',
            field=models.BooleanField(default=True, verbose_name='يجب تغيير كلمة المرور'),
        ),
        migrations.AddField(
            model_name='medecin',
            name='utilisateur',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='medecin_profil', to='auth.user', verbose_name='حساب الطبيب'),
        ),
        migrations.AlterField(
            model_name='rendezvous',
            name='statut',
            field=models.CharField(choices=[('attente', 'في الانتظار'), ('confirme', 'مؤكد'), ('checked_in', 'حضر إلى العيادة'), ('annule', 'ملغي'), ('termine', 'مكتمل')], default='attente', max_length=20, verbose_name='الحالة'),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
