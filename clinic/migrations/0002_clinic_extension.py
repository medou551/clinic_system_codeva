from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('clinic', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='AdminClinique',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100, verbose_name='الاسم الكامل')),
                ('telephone', models.CharField(max_length=20, unique=True, verbose_name='رقم الهاتف')),
                ('role', models.CharField(
                    choices=[('admin','مدير'),('reception','استقبال'),('medecin','طبيب'),('laboratoire','مختبر')],
                    default='reception', max_length=20, verbose_name='الدور')),
                ('actif', models.BooleanField(default=True, verbose_name='نشط')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                ('utilisateur', models.OneToOneField(blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='admin_profil', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'موظف', 'verbose_name_plural': 'فريق العمل'},
        ),
        migrations.AddField(
            model_name='patient', name='nni',
            field=models.CharField(blank=True, max_length=30, verbose_name='الرقم الوطني'),
        ),
        migrations.CreateModel(
            name='Analyse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=120, verbose_name='اسم التحليل')),
                ('description', models.TextField(blank=True, verbose_name='الوصف')),
                ('prix', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='السعر (MRU)')),
                ('actif', models.BooleanField(default=True, verbose_name='نشط')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
            ],
            options={'verbose_name': 'تحليل', 'verbose_name_plural': 'التحاليل', 'ordering': ['nom']},
        ),
        migrations.CreateModel(
            name='DemandeAnalyse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('resultat', models.TextField(blank=True, verbose_name='النتيجة')),
                ('notes_labo', models.TextField(blank=True, verbose_name='ملاحظات المختبر')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                ('modifie_le', models.DateTimeField(auto_now=True)),
                ('statut', models.CharField(
                    choices=[('attente','في الانتظار'),('payee','مدفوعة'),('en_cours','قيد الإنجاز'),('prete','جاهزة')],
                    default='attente', max_length=20, verbose_name='الحالة')),
                ('analyse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='demandes', to='clinic.analyse', verbose_name='التحليل')),
                ('medecin', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='demandes_analyses', to='clinic.medecin', verbose_name='الطبيب المعني')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='demandes_analyses', to='clinic.patient', verbose_name='المريض')),
            ],
            options={'verbose_name': 'طلب تحليل', 'verbose_name_plural': 'طلبات التحاليل', 'ordering': ['-cree_le']},
        ),
        migrations.CreateModel(
            name='FactureAnalyse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('montant', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='المبلغ')),
                ('statut', models.CharField(choices=[('non_payee','غير مدفوعة'),('payee','مدفوعة')], default='non_payee', max_length=20, verbose_name='الحالة')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                ('demande', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='facture', to='clinic.demandeanalyse', verbose_name='طلب التحليل')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='factures_analyses', to='clinic.patient', verbose_name='المريض')),
            ],
            options={'verbose_name': 'فاتورة تحليل', 'verbose_name_plural': 'فواتير التحاليل', 'ordering': ['-cree_le']},
        ),
        migrations.CreateModel(
            name='PaiementAnalyse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('montant', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='المبلغ')),
                ('mode', models.CharField(choices=[('cash','نقدا'),('bankily','بنكيلي'),('sedad','سداد'),('autre','أخرى')], default='cash', max_length=20, verbose_name='طريقة الدفع')),
                ('reference', models.CharField(blank=True, max_length=100, verbose_name='مرجع الدفع')),
                ('date_paiement', models.DateTimeField(auto_now_add=True)),
                ('facture', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='paiement', to='clinic.factureanalyse', verbose_name='الفاتورة')),
            ],
            options={'verbose_name': 'دفع تحليل', 'verbose_name_plural': 'مدفوعات التحاليل', 'ordering': ['-date_paiement']},
        ),
        migrations.CreateModel(
            name='FactureConsultation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('montant', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='المبلغ')),
                ('statut', models.CharField(choices=[('non_payee','غير مدفوعة'),('payee','مدفوعة')], default='non_payee', max_length=20, verbose_name='الحالة')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                ('medecin', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='factures_consultations', to='clinic.medecin', verbose_name='الطبيب')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='factures_consultations', to='clinic.patient', verbose_name='المريض')),
                ('rdv', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='facture_consultation', to='clinic.rendezvous', verbose_name='الموعد')),
            ],
            options={'verbose_name': 'فاتورة استشارة', 'verbose_name_plural': 'فواتير الاستشارات', 'ordering': ['-cree_le']},
        ),
        migrations.CreateModel(
            name='PaiementConsultation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('montant', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='المبلغ')),
                ('mode', models.CharField(choices=[('cash','نقدا'),('bankily','بنكيلي'),('sedad','سداد'),('autre','أخرى')], default='cash', max_length=20, verbose_name='طريقة الدفع')),
                ('reference', models.CharField(blank=True, max_length=100, verbose_name='مرجع الدفع')),
                ('date_paiement', models.DateTimeField(auto_now_add=True)),
                ('facture', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='paiement', to='clinic.factureconsultation', verbose_name='الفاتورة')),
            ],
            options={'verbose_name': 'دفع استشارة', 'verbose_name_plural': 'مدفوعات الاستشارات', 'ordering': ['-date_paiement']},
        ),
    ]
