from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Specialite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100, verbose_name='التخصص')),
                ('icone', models.CharField(default='fa-stethoscope', max_length=60, verbose_name='الأيقونة')),
                ('description', models.TextField(blank=True, verbose_name='الوصف')),
            ],
            options={'verbose_name': 'تخصص', 'verbose_name_plural': 'التخصصات', 'ordering': ['nom']},
        ),
        migrations.CreateModel(
            name='Medecin',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100, verbose_name='الاسم الكامل')),
                ('telephone', models.CharField(blank=True, max_length=20, verbose_name='الهاتف')),
                ('email', models.EmailField(blank=True, verbose_name='البريد الإلكتروني')),
                ('bio', models.TextField(blank=True, verbose_name='نبذة')),
                ('annees_experience', models.PositiveIntegerField(default=1, verbose_name='سنوات الخبرة')),
                ('disponible', models.BooleanField(default=True, verbose_name='متاح للحجز')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                ('specialite', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='medecins', to='clinic.specialite', verbose_name='التخصص')),
            ],
            options={'verbose_name': 'طبيب', 'verbose_name_plural': 'الأطباء', 'ordering': ['nom']},
        ),
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100, verbose_name='اسم الخدمة')),
                ('description', models.TextField(verbose_name='الوصف')),
                ('icone', models.CharField(default='fa-heartbeat', max_length=60, verbose_name='الأيقونة')),
                ('prix', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='السعر (MRU)')),
            ],
            options={'verbose_name': 'خدمة', 'verbose_name_plural': 'الخدمات'},
        ),
        migrations.CreateModel(
            name='Patient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telephone', models.CharField(blank=True, max_length=20, verbose_name='الهاتف')),
                ('date_naissance', models.DateField(blank=True, null=True, verbose_name='تاريخ الميلاد')),
                ('genre', models.CharField(blank=True, choices=[('M', 'ذكر'), ('F', 'أنثى')], max_length=1, verbose_name='الجنس')),
                ('adresse', models.TextField(blank=True, verbose_name='العنوان')),
                ('utilisateur', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profil', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'مريض', 'verbose_name_plural': 'المرضى'},
        ),
        migrations.CreateModel(
            name='RendezVous',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='التاريخ')),
                ('heure', models.TimeField(verbose_name='الوقت')),
                ('motif', models.TextField(blank=True, verbose_name='سبب الزيارة')),
                ('statut', models.CharField(choices=[('attente', 'في الانتظار'), ('confirme', 'مؤكد'), ('annule', 'ملغي'), ('termine', 'مكتمل')], default='attente', max_length=20, verbose_name='الحالة')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات الطبيب')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                ('medecin', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rendez_vous', to='clinic.medecin', verbose_name='الطبيب')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rendez_vous', to=settings.AUTH_USER_MODEL, verbose_name='المريض')),
            ],
            options={'verbose_name': 'موعد', 'verbose_name_plural': 'المواعيد', 'ordering': ['-date', '-heure']},
        ),
    ]
