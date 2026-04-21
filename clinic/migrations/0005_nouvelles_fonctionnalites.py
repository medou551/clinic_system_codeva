from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clinic', '0004_test_accounts'),
    ]

    operations = [
        # Ajouter duree à Service
        migrations.AddField(
            model_name='service',
            name='duree',
            field=models.PositiveIntegerField(default=30, verbose_name='المدة (دقائق)'),
        ),
        # Créer Ordonnance
        migrations.CreateModel(
            name='Ordonnance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('diagnostic',    models.TextField(verbose_name='التشخيص')),
                ('prescription',  models.TextField(verbose_name='الوصفة الطبية')),
                ('notes_medecin', models.TextField(blank=True, verbose_name='ملاحظات إضافية')),
                ('cree_le',       models.DateTimeField(auto_now_add=True)),
                ('rdv',     models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='ordonnance', to='clinic.rendezvous', verbose_name='الموعد')),
                ('medecin', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ordonnances', to='clinic.medecin', verbose_name='الطبيب')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ordonnances', to='clinic.patient', verbose_name='المريض')),
            ],
            options={'verbose_name': 'وصفة طبية', 'verbose_name_plural': 'الوصفات الطبية', 'ordering': ['-cree_le']},
        ),
        # Créer ListeAttente
        migrations.CreateModel(
            name='ListeAttente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_souhaitee', models.DateField(verbose_name='التاريخ المرغوب')),
                ('notes',  models.TextField(blank=True, verbose_name='ملاحظات')),
                ('statut', models.CharField(choices=[('en_attente', 'في الانتظار'), ('converti', 'تحول لموعد'), ('annule', 'ملغي')], default='en_attente', max_length=20, verbose_name='الحالة')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='liste_attente', to='clinic.patient', verbose_name='المريض')),
                ('medecin', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='liste_attente', to='clinic.medecin', verbose_name='الطبيب')),
            ],
            options={'verbose_name': 'قائمة انتظار', 'verbose_name_plural': 'قائمة الانتظار', 'ordering': ['-cree_le']},
        ),
    ]
