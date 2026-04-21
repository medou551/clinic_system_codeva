from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import clinic.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('clinic', '0006_journalaudit_notification_planningsemaine'),
    ]

    operations = [
        migrations.CreateModel(
            name='PieceMedicale',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titre', models.CharField(max_length=255, verbose_name='العنوان')),
                ('type_piece', models.CharField(choices=[('ordonnance', 'وصفة طبية'), ('analyse', 'نتيجة تحليل'), ('radiologie', 'تصوير / أشعة'), ('rapport', 'تقرير طبي'), ('document', 'وثيقة طبية'), ('autre', 'أخرى')], default='document', max_length=20, verbose_name='نوع الملف')),
                ('fichier', models.FileField(upload_to=clinic.models.medical_file_upload_path, verbose_name='الملف')),
                ('nom_original', models.CharField(blank=True, max_length=255, verbose_name='اسم الملف الأصلي')),
                ('type_mime', models.CharField(blank=True, max_length=100, verbose_name='نوع MIME')),
                ('taille_octets', models.PositiveIntegerField(default=0, verbose_name='الحجم')),
                ('description', models.TextField(blank=True, verbose_name='الوصف')),
                ('source_role', models.CharField(choices=[('patient', 'مريض'), ('medecin', 'طبيب'), ('reception', 'استقبال'), ('laboratoire', 'مختبر'), ('admin', 'مدير')], default='patient', max_length=20, verbose_name='مصدر الإضافة')),
                ('est_active', models.BooleanField(default=True, verbose_name='نشط')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                ('modifie_le', models.DateTimeField(auto_now=True)),
                ('cree_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pieces_medicales_creees', to=settings.AUTH_USER_MODEL, verbose_name='أضيف من طرف')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pieces_medicales', to='clinic.patient', verbose_name='المريض')),
                ('rendez_vous', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pieces_medicales', to='clinic.rendezvous', verbose_name='الموعد')),
            ],
            options={
                'verbose_name': 'ملف طبي',
                'verbose_name_plural': 'الملفات الطبية',
                'ordering': ['-cree_le'],
            },
        ),
        migrations.CreateModel(
            name='PieceMedicaleAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('upload', 'رفع'), ('download', 'تحميل'), ('delete', 'حذف')], max_length=20, verbose_name='الإجراء')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                ('piece', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audits', to='clinic.piecemedicale', verbose_name='الملف')),
                ('utilisateur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_pieces_medicales', to=settings.AUTH_USER_MODEL, verbose_name='المستخدم')),
            ],
            options={
                'verbose_name': 'أثر ملف طبي',
                'verbose_name_plural': 'آثار الملفات الطبية',
                'ordering': ['-cree_le'],
            },
        ),
    ]
