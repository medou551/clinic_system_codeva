from django.db import migrations, models
import django.db.models.deletion


def seed_medecin_services(apps, schema_editor):
    Medecin = apps.get_model('clinic', 'Medecin')
    Service = apps.get_model('clinic', 'Service')
    MedecinService = apps.get_model('clinic', 'MedecinService')

    services = list(Service.objects.all())
    for medecin in Medecin.objects.all():
        for idx, service in enumerate(services):
            MedecinService.objects.get_or_create(
                medecin=medecin,
                service=service,
                defaults={'actif': True, 'priorite': idx},
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('clinic', '0008_commercial_features'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='capacite_par_creneau',
            field=models.PositiveIntegerField(default=1, verbose_name='السعة لكل فترة'),
        ),
        migrations.AddField(
            model_name='service',
            name='actif',
            field=models.BooleanField(default=True, verbose_name='نشط'),
        ),
        migrations.CreateModel(
            name='MedecinService',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('actif', models.BooleanField(default=True, verbose_name='نشط')),
                ('priorite', models.PositiveIntegerField(default=0, verbose_name='الأولوية')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                ('medecin', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='services_autorises', to='clinic.medecin', verbose_name='الطبيب')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='medecins_autorises', to='clinic.service', verbose_name='الخدمة')),
            ],
            options={
                'verbose_name': 'خدمة مسموحة لطبيب',
                'verbose_name_plural': 'الخدمات المسموحة للأطباء',
                'ordering': ['medecin', 'priorite', 'service__nom'],
                'unique_together': {('medecin', 'service')},
            },
        ),
        migrations.AddField(
            model_name='rendezvous',
            name='service',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rendez_vous', to='clinic.service', verbose_name='الخدمة'),
        ),
        migrations.AddField(
            model_name='dossierpartage',
            name='peut_ajouter_fichiers',
            field=models.BooleanField(default=False, verbose_name='يمكنه رفع ملفات'),
        ),
        migrations.AddField(
            model_name='dossierpartage',
            name='peut_ajouter_notes',
            field=models.BooleanField(default=False, verbose_name='يمكنه إضافة ملاحظات'),
        ),
        migrations.AddField(
            model_name='dossierpartage',
            name='peut_creer_ordonnance',
            field=models.BooleanField(default=False, verbose_name='يمكنه إنشاء وصفة'),
        ),
        migrations.RunPython(seed_medecin_services, noop_reverse),
    ]
