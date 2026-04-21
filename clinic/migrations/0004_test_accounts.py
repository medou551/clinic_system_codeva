from django.db import migrations

def seed(apps, schema_editor):
    AdminClinique = apps.get_model('clinic', 'AdminClinique')
    Analyse = apps.get_model('clinic', 'Analyse')

    # Comptes de test personnel
    staff = [
        ('أحمد ولد محمد',    '+222 11 11 11 11', 'medecin'),
        ('فاطمة بنت سيدي',   '+222 22 22 22 22', 'medecin'),
        ('محمد ولد عبدالله', '+222 33 33 33 33', 'medecin'),
        ('تكنيك المختبر',    '+222 44 44 44 44', 'laboratoire'),
        ('سارة المختبر',     '+222 55 55 55 55', 'laboratoire'),
    ]
    for nom, tel, role in staff:
        AdminClinique.objects.get_or_create(telephone=tel, defaults={'nom': nom, 'role': role, 'actif': True})

    # Analyses supplémentaires
    extra = [
        ('Vitamine D',       'قياس مستوى فيتامين د',             750),
        ('Ferritine',        'تحليل مخزون الحديد',               600),
        ('HbA1c',            'تحليل السكر التراكمي',              700),
        ('TP / INR',         'تحليل تخثر الدم',                  500),
        ('Ionogramme',       'تحليل الأملاح المعدنية',           650),
        ('PSA',              'تحليل بروستاتا',                   800),
        ('Beta HCG',         'تحليل الحمل',                      350),
        ('Sérologie HIV',    'تحليل فيروس نقص المناعة',         1000),
        ('Hépatite B',       'تحليل التهاب الكبد B',             900),
        ('Hépatite C',       'تحليل التهاب الكبد C',             900),
        ('ECBU',             'تحليل البول الكامل بمزرعة',        450),
        ('Spermiogramme',    'تحليل السائل المنوي',              1200),
        ('Frottis sanguin',  'فحص لطاخة الدم',                  400),
        ('Calcium / Phosphore', 'تحليل الكالسيوم والفسفور',     500),
        ('Acide urique',     'تحليل حمض اليوريك',               350),
        ('Albumine',         'تحليل الألبومين',                  400),
        ('Bilirubine',       'تحليل الصفراء',                   500),
        ('Progestérone',     'تحليل هرمون البروجسترون',          800),
        ('Testostérone',     'تحليل هرمون التستوستيرون',        800),
        ('Cortisol',         'تحليل هرمون الكورتيزول',          900),
    ]
    for nom, desc, prix in extra:
        Analyse.objects.get_or_create(nom=nom, defaults={'description': desc, 'prix': prix, 'actif': True})

class Migration(migrations.Migration):
    dependencies = [('clinic', '0003_seed_analyses')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
