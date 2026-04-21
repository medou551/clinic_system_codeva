
from django.db import migrations

def seed(apps, schema_editor):
    Analyse = apps.get_model('clinic', 'Analyse')
    data = [
        ('NFS', 'تعداد الدم الكامل', 500),
        ('Glycémie', 'تحليل السكر في الدم', 300),
        ('Créatinine', 'تحليل وظائف الكلى', 400),
        ('Urée', 'تحليل اليوريا', 350),
        ('Bilan lipidique', 'تحليل الدهون', 800),
        ('ASAT / ALAT', 'تحليل الكبد', 700),
        ('CRP', 'مؤشر الالتهاب', 450),
        ('Groupage sanguin', 'فصيلة الدم', 600),
        ('Examen d’urines', 'تحليل البول', 300),
        ('TSH', 'تحليل الغدة الدرقية', 900),
    ]
    for nom, description, prix in data:
        Analyse.objects.get_or_create(nom=nom, defaults={'description': description, 'prix': prix, 'actif': True})

class Migration(migrations.Migration):
    dependencies = [('clinic', '0002_clinic_extension')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
