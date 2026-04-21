from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clinic', '0007_medical_files'),
    ]

    operations = [
        migrations.CreateModel(
            name='DossierPartage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lecture_seule', models.BooleanField(default=True, verbose_name='قراءة فقط')),
                ('actif', models.BooleanField(default=True, verbose_name='نشط')),
                ('date_debut', models.DateField(auto_now_add=True, verbose_name='تاريخ البداية')),
                ('date_fin', models.DateField(blank=True, null=True, verbose_name='تاريخ النهاية')),
                ('note', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                ('cree_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='partages_crees', to='auth.user', verbose_name='أنشئ بواسطة')),
                ('medecin_cible', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='partages_recus', to='clinic.medecin', verbose_name='الطبيب المستفيد')),
                ('medecin_source', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='partages_envoyes', to='clinic.medecin', verbose_name='الطبيب المصدر')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='partages_dossier', to='clinic.patient', verbose_name='المريض')),
            ],
            options={'verbose_name': 'مشاركة ملف طبي', 'verbose_name_plural': 'مشاركات الملف الطبي', 'ordering': ['-cree_le']},
        ),
    ]
