#!/usr/bin/env python3
"""
bootstrap_demo.py — إعداد كامل لقاعدة بيانات العيادة الطبية
يُنشئ: التخصصات، الخدمات، التحاليل، الأطباء، الموظفين، المرضى، المواعيد.
"""
import sys, os, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from clinic.models import (
    AdminClinique, Analyse, Medecin, MedecinService,
    Patient, PlanningSemaine, RendezVous, Service, Specialite,
)


def normalize(phone: str) -> str:
    return ''.join(ch for ch in (phone or '') if ch.isdigit())


# ──────────────────────────────────────────────
# 1. SPÉCIALITÉS
# ──────────────────────────────────────────────
SPECIALITES = [
    ("طب عام",           "fa-stethoscope",    "الرعاية الصحية الأولية والفحوصات العامة"),
    ("طب الأطفال",       "fa-baby",           "رعاية صحة الأطفال والرضع"),
    ("أمراض القلب",      "fa-heart",          "تشخيص وعلاج أمراض القلب والأوعية الدموية"),
    ("أمراض النساء",     "fa-venus",          "صحة المرأة والتوليد"),
    ("طب الأسنان",       "fa-tooth",          "علاج وتجميل الأسنان واللثة"),
    ("الجلدية",          "fa-hand-sparkles",  "تشخيص وعلاج أمراض الجلد والشعر"),
    ("العيون",           "fa-eye",            "فحص وعلاج أمراض العيون"),
    ("العظام",           "fa-bone",           "علاج إصابات وأمراض العظام والمفاصل"),
]

def seed_specialites():
    for nom, icone, desc in SPECIALITES:
        Specialite.objects.get_or_create(nom=nom, defaults={"icone": icone, "description": desc})
    print(f"  Specialites: {Specialite.objects.count()}")


# ──────────────────────────────────────────────
# 2. SERVICES
# ──────────────────────────────────────────────
SERVICES = [
    ("استشارة طبية عامة",      "فحص شامل وتشخيص طبي عام",                   "fa-stethoscope",   500, 30),
    ("فحص القلب",              "تخطيط القلب وقياس ضغط الدم",                "fa-heart",         800, 45),
    ("فحص الأطفال",            "فحص نمو الطفل والتطعيمات",                  "fa-baby",          600, 30),
    ("استشارة نسائية",         "متابعة صحة المرأة والحمل",                  "fa-venus",         700, 45),
    ("طب الأسنان",             "كشف وعلاج أمراض الأسنان",                   "fa-tooth",         600, 45),
    ("فحص العيون",             "قياس النظر وفحص شبكية العين",               "fa-eye",           700, 30),
    ("فحص العظام",             "فحص المفاصل والعظام والعمود الفقري",        "fa-bone",          750, 45),
    ("فحص الجلد",              "تشخيص وعلاج الأمراض الجلدية",               "fa-hand-sparkles", 650, 30),
    ("متابعة الأمراض المزمنة", "متابعة السكري وضغط الدم والكوليسترول",      "fa-notes-medical", 400, 20),
    ("شهادة طبية",             "إصدار شهادات طبية رسمية",                   "fa-file-medical",  300, 15),
]

def seed_services():
    for nom, desc, icone, prix, duree in SERVICES:
        Service.objects.get_or_create(nom=nom, defaults={
            "description": desc, "icone": icone,
            "prix": prix, "duree": duree, "actif": True,
        })
    print(f"  Services: {Service.objects.count()}")


# ──────────────────────────────────────────────
# 3. ANALYSES
# ──────────────────────────────────────────────
ANALYSES = [
    ("تحليل الدم الكامل CBC",        "قياس خلايا الدم الحمراء والبيضاء والصفائح",           350),
    ("سكر الصيام",                   "قياس مستوى الجلوكوز في الدم بعد الصيام",              200),
    ("هيموغلوبين السكري HbA1c",      "متابعة السكري على مدى 3 أشهر",                        450),
    ("وظائف الكلى — كرياتينين",      "قياس مستوى الكرياتينين واليوريا",                     300),
    ("وظائف الكبد ASAT / ALAT",      "تحليل إنزيمات الكبد",                                 350),
    ("بيليروبين",                    "تحليل الصفراء وتشخيص اليرقان",                        300),
    ("ألبومين",                      "تقييم البروتينات الكلية في الدم",                      300),
    ("أملاح الدم — صوديوم / بوتاسيوم","قياس الشوارد في الدم",                              300),
    ("كالسيوم / فوسفور",             "تقييم مستوى الكالسيوم والفوسفور",                    300),
    ("بروفيل الدهون",                "قياس الكوليسترول الكلي وHDL وLDL والدهون الثلاثية",  500),
    ("تحليل البول الكامل",           "فحص شامل للبول",                                      200),
    ("CRP",                          "مؤشر الالتهاب في الجسم",                              300),
    ("بيتا HCG — اختبار الحمل",      "تأكيد الحمل بدقة عالية",                              250),
    ("هرمونات الغدة الدرقية TSH",    "قياس وظائف الغدة الدرقية",                            500),
    ("T3 / T4",                      "تحليل هرمونات الثيروكسين",                            450),
    ("التهاب الكبد B",               "كشف الإصابة بفيروس التهاب الكبد B",                  400),
    ("التهاب الكبد C",               "كشف الإصابة بفيروس التهاب الكبد C",                  400),
    ("فيروس HIV",                    "فحص الإيدز بسرية تامة",                               400),
    ("مجموعة الدم",                  "تحديد فصيلة الدم والريزوس",                           200),
    ("وقت التخثر PT/APTT",           "قياس وقت تخثر الدم",                                  350),
    ("حمض اليوريك",                  "تشخيص النقرس وأمراض الكلى",                           250),
    ("الحديد والفيريتين",            "تشخيص فقر الدم بالحديد",                              400),
    ("فيتامين D",                    "قياس مستوى فيتامين د في الدم",                        500),
    ("فيتامين B12",                  "قياس مستوى فيتامين ب12",                              450),
    ("PSA — البروستاتا",             "فحص سرطان البروستاتا للرجال",                        600),
    ("CA-125",                       "تحليل علامات سرطان المبيض",                           650),
    ("AFP",                          "كشف سرطان الكبد والخلايا الجنينية",                   600),
    ("مسحة PCR كوفيد",               "كشف فيروس كوفيد بالـPCR",                             500),
    ("ثقافة بكتيرية — بول",          "زرع البول لتحديد البكتيريا والمضادات",                300),
    ("تحليل البراز",                 "فحص البراز للطفيليات والجراثيم",                      200),
]

def seed_analyses():
    for nom, desc, prix in ANALYSES:
        Analyse.objects.get_or_create(nom=nom, defaults={
            "description": desc, "prix": prix, "actif": True,
        })
    print(f"  Analyses: {Analyse.objects.count()}")


# ──────────────────────────────────────────────
# 4. MÉDECINS
# ──────────────────────────────────────────────
MEDECINS_DATA = [
    ("أحمد ولد محمد",       "+222 22 11 22 33", "طب عام",       10, "طبيب عام ذو خبرة واسعة في الرعاية الأولية"),
    ("فاطمة بنت سيدي",      "+222 22 33 44 55", "أمراض النساء",  8, "متخصصة في صحة المرأة والتوليد"),
    ("محمد ولد عبدالله",    "+222 22 55 66 77", "أمراض القلب",  12, "استشاري أمراض القلب والأوعية الدموية"),
    ("مريم بنت أحمد",       "+222 22 77 88 99", "طب الأطفال",    6, "طبيبة أطفال متخصصة في النمو والتطور"),
    ("عبدالله ولد إبراهيم", "+222 22 99 00 11", "طب الأسنان",    9, "طبيب أسنان وتجميل"),
    ("خديجة بنت محمود",     "+222 22 00 11 22", "الجلدية",       7, "متخصصة في أمراض الجلد والتجميل"),
]

def seed_medecins():
    for nom, tel, spec_nom, exp, bio in MEDECINS_DATA:
        spec = Specialite.objects.filter(nom=spec_nom).first() or Specialite.objects.first()
        med, _ = Medecin.objects.get_or_create(telephone=tel, defaults={
            "nom": nom, "specialite": spec,
            "annees_experience": exp, "bio": bio, "disponible": True,
        })
        med.disponible = True
        if not med.specialite_id:
            med.specialite = spec
        med.save()

        phone_norm = normalize(tel)
        ac = AdminClinique.objects.filter(telephone=tel).first()
        if not ac:
            ac = AdminClinique.objects.create(
                nom=nom, telephone=tel, role="medecin",
                actif=True, must_change_password=True,
            )
        if not ac.utilisateur_id:
            uname = f"dr_{phone_norm}"
            idx = 1
            while User.objects.filter(username=uname).exists():
                uname = f"dr_{phone_norm}_{idx}"; idx += 1
            user = User.objects.create(
                username=uname, first_name=nom,
                password=make_password(phone_norm),
            )
            ac.utilisateur = user
            ac.save(update_fields=["utilisateur"])

        if med.utilisateur_id != ac.utilisateur_id:
            med.utilisateur = ac.utilisateur
            med.save(update_fields=["utilisateur"])

        # Lier tous les services actifs
        for idx, svc in enumerate(Service.objects.filter(actif=True)):
            MedecinService.objects.get_or_create(
                medecin=med, service=svc,
                defaults={"actif": True, "priorite": idx},
            )
        # Planning lun-ven 8h-15h
        for jour in ["lun", "mar", "mer", "jeu", "ven"]:
            PlanningSemaine.objects.get_or_create(
                medecin=med, jour=jour,
                defaults={"heure_debut": datetime.time(8, 0),
                          "heure_fin": datetime.time(15, 0),
                          "actif": True, "duree_rdv": 30},
            )

    print(f"  Medecins: {Medecin.objects.count()} | Services liés: {MedecinService.objects.count()}")


# ──────────────────────────────────────────────
# 5. STAFF
# ──────────────────────────────────────────────
STAFF_DATA = [
    ("مدير النظام",    "+222 20 00 00 01", "admin"),
    ("موظف الاستقبال", "+222 20 00 00 02", "reception"),
    ("فني المختبر",    "+222 20 00 00 03", "laboratoire"),
]

def seed_staff():
    for nom, tel, role in STAFF_DATA:
        phone_norm = normalize(tel)
        ac = AdminClinique.objects.filter(telephone=tel).first()
        if not ac:
            ac = AdminClinique.objects.create(
                nom=nom, telephone=tel, role=role,
                actif=True, must_change_password=False,
            )
        else:
            ac.nom = nom; ac.role = role; ac.actif = True
            ac.must_change_password = False; ac.save()

        if not ac.utilisateur_id:
            uname = f"staff_{phone_norm}"
            idx = 1
            while User.objects.filter(username=uname).exists():
                uname = f"staff_{phone_norm}_{idx}"; idx += 1
            user = User.objects.create(
                username=uname, first_name=nom,
                is_staff=(role == "admin"),
                password=make_password(phone_norm),
            )
            ac.utilisateur = user
            ac.save(update_fields=["utilisateur"])
        else:
            u = ac.utilisateur
            u.first_name = nom; u.is_staff = (role == "admin")
            u.set_password(phone_norm); u.save()

    print(f"  Staff: {AdminClinique.objects.exclude(role='medecin').count()}")


# ──────────────────────────────────────────────
# 6. PATIENTS
# ──────────────────────────────────────────────
PATIENTS_DATA = [
    ("patient_mohamed", "patient123", "محمد",  "الأمين",  "+222 30 00 00 01", "M"),
    ("patient_aicha",   "patient123", "عائشة", "محمد",    "+222 30 00 00 02", "F"),
    ("patient_omar",    "patient123", "عمر",   "ولد سيد", "+222 30 00 00 03", "M"),
]

def seed_patients():
    for uname, pwd, first, last, tel, genre in PATIENTS_DATA:
        user, _ = User.objects.get_or_create(username=uname,
            defaults={"first_name": first, "last_name": last})
        user.first_name = first; user.last_name = last
        user.set_password(pwd); user.save()
        profil = getattr(user, "profil", None)
        if profil:
            profil.telephone = tel; profil.genre = genre; profil.save()
    print(f"  Patients: {Patient.objects.count()}")


# ──────────────────────────────────────────────
# 7. RENDEZ-VOUS DÉMO
# ──────────────────────────────────────────────
def seed_rdv():
    medecins = list(Medecin.objects.filter(disponible=True).order_by("id"))
    services = list(Service.objects.filter(actif=True).order_by("id"))
    patients = list(User.objects.filter(username__startswith="patient_"))
    today = datetime.date.today()
    if not (medecins and services and patients):
        return
    samples = [
        (patients[0], medecins[0], services[0], today + datetime.timedelta(days=1), datetime.time(9,  0), "استشارة أولية",  "confirme"),
        (patients[1], medecins[1 % len(medecins)], services[1 % len(services)], today + datetime.timedelta(days=2), datetime.time(10, 0), "متابعة دورية",   "attente"),
        (patients[0], medecins[2 % len(medecins)], services[2 % len(services)], today + datetime.timedelta(days=3), datetime.time(11, 0), "فحص عام",        "attente"),
    ]
    for pat, med, svc, date_v, heure_v, motif, statut in samples:
        RendezVous.objects.get_or_create(
            patient=pat, medecin=med, service=svc, date=date_v, heure=heure_v,
            defaults={"motif": motif, "statut": statut},
        )
    print(f"  Rendez-vous: {RendezVous.objects.count()}")


# ──────────────────────────────────────────────
# 8. SUPERUSER DJANGO
# ──────────────────────────────────────────────
def seed_superuser():
    u = User.objects.filter(username="superadmin").first()
    if not u:
        User.objects.create_superuser("superadmin", "superadmin@clinic.mr", "admin12345")
    else:
        u.is_superuser = True; u.is_staff = True
        u.set_password("admin12345"); u.save()
    print("  Superuser: superadmin / admin12345")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("\n=========================================")
    print("    إعداد قاعدة بيانات العيادة الطبية")
    print("=========================================\n")

    print("[1] التخصصات الطبية...")
    seed_specialites()

    print("[2] الخدمات الطبية...")
    seed_services()

    print("[3] التحاليل المخبرية...")
    seed_analyses()

    print("[4] الأطباء والحسابات...")
    seed_medecins()

    print("[5] فريق العمل...")
    seed_staff()

    print("[6] المرضى...")
    seed_patients()

    print("[7] مواعيد الديمو...")
    seed_rdv()

    print("[8] Django Admin...")
    seed_superuser()

    print("\n=========================================")
    print("تم الإعداد بنجاح!")
    print("=========================================")
    print()
    print("بيانات الدخول:")
    print("  مدير النظام   : +222 20 00 00 01  /  222200000001  (فريق العمل)")
    print("  الاستقبال     : +222 20 00 00 02  /  222200000002  (فريق العمل)")
    print("  المختبر       : +222 20 00 00 03  /  222200000003  (فريق العمل)")
    print("  طبيب أحمد     : +222 22 11 22 33  /  22222112233   (فريق العمل)")
    print("  طبيب فاطمة    : +222 22 33 44 55  /  22222334455   (فريق العمل)")
    print("  مريض          : +222 30 00 00 01  /  patient123    (مريض)")
    print("  Django Admin  : superadmin        /  admin12345    (/admin/)")
    print()
    print("تشغيل الخادم:")
    print("  python manage.py runserver")
    print("  http://127.0.0.1:8000")
    print()


if __name__ == "__main__":
    main()
