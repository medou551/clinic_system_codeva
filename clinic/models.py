import datetime
import os
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Specialite(models.Model):
    nom         = models.CharField(max_length=100, verbose_name="التخصص")
    icone       = models.CharField(max_length=60, default="fa-stethoscope", verbose_name="الأيقونة")
    description = models.TextField(blank=True, verbose_name="الوصف")

    class Meta:
        verbose_name = "تخصص"
        verbose_name_plural = "التخصصات"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Medecin(models.Model):
    utilisateur       = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='medecin_profil', verbose_name="حساب الطبيب")
    nom               = models.CharField(max_length=100, verbose_name="الاسم الكامل")
    specialite        = models.ForeignKey(Specialite, on_delete=models.SET_NULL, null=True, blank=True, related_name='medecins', verbose_name="التخصص")
    telephone         = models.CharField(max_length=20, blank=True, verbose_name="الهاتف")
    email             = models.EmailField(blank=True, verbose_name="البريد الإلكتروني")
    bio               = models.TextField(blank=True, verbose_name="نبذة")
    annees_experience = models.PositiveIntegerField(default=1, verbose_name="سنوات الخبرة")
    disponible        = models.BooleanField(default=True, verbose_name="متاح للحجز")
    cree_le           = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "طبيب"
        verbose_name_plural = "الأطباء"
        ordering = ['nom']

    def __str__(self):
        return f"د. {self.nom}"


class Service(models.Model):
    nom         = models.CharField(max_length=100, verbose_name="اسم الخدمة")
    description = models.TextField(verbose_name="الوصف")
    icone       = models.CharField(max_length=60, default="fa-heartbeat", verbose_name="الأيقونة")
    prix        = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="السعر (MRU)")
    duree       = models.PositiveIntegerField(default=30, verbose_name="المدة (دقائق)")
    capacite_par_creneau = models.PositiveIntegerField(default=1, verbose_name="السعة لكل فترة")
    actif = models.BooleanField(default=True, verbose_name="نشط")

    class Meta:
        verbose_name = "خدمة"
        verbose_name_plural = "الخدمات"

    def __str__(self):
        return self.nom


class MedecinService(models.Model):
    medecin = models.ForeignKey(Medecin, on_delete=models.CASCADE, related_name='services_autorises', verbose_name="الطبيب")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='medecins_autorises', verbose_name="الخدمة")
    actif = models.BooleanField(default=True, verbose_name="نشط")
    priorite = models.PositiveIntegerField(default=0, verbose_name="الأولوية")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "خدمة مسموحة لطبيب"
        verbose_name_plural = "الخدمات المسموحة للأطباء"
        unique_together = ('medecin', 'service')
        ordering = ['medecin', 'priorite', 'service__nom']

    def __str__(self):
        return f"{self.medecin} ← {self.service}"


class Patient(models.Model):
    GENRE = [('M', 'ذكر'), ('F', 'أنثى')]
    utilisateur    = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil')
    telephone      = models.CharField(max_length=20, blank=True, verbose_name="الهاتف")
    date_naissance = models.DateField(null=True, blank=True, verbose_name="تاريخ الميلاد")
    genre          = models.CharField(max_length=1, choices=GENRE, blank=True, verbose_name="الجنس")
    adresse        = models.TextField(blank=True, verbose_name="العنوان")
    nni            = models.CharField(max_length=30, blank=True, verbose_name="الرقم الوطني")

    class Meta:
        verbose_name = "مريض"
        verbose_name_plural = "المرضى"

    def __str__(self):
        return self.utilisateur.get_full_name() or self.utilisateur.username

    def age(self):
        if self.date_naissance:
            today = datetime.date.today()
            return today.year - self.date_naissance.year - (
                (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
            )
        return None


@receiver(post_save, sender=User)
def creer_profil(sender, instance, created, **kwargs):
    if created:
        Patient.objects.create(utilisateur=instance)

@receiver(post_save, sender=User)
def sauvegarder_profil(sender, instance, **kwargs):
    if hasattr(instance, 'profil'):
        instance.profil.save()


class RendezVous(models.Model):
    STATUTS = [
        ('attente',  'في الانتظار'),
        ('confirme', 'مؤكد'),
        ('checked_in', 'حضر إلى العيادة'),
        ('annule',   'ملغي'),
        ('termine',  'مكتمل'),
    ]
    patient  = models.ForeignKey(User,    on_delete=models.CASCADE, related_name='rendez_vous', verbose_name="المريض")
    medecin  = models.ForeignKey(Medecin, on_delete=models.CASCADE, related_name='rendez_vous', verbose_name="الطبيب")
    service  = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True, related_name='rendez_vous', verbose_name="الخدمة")
    date     = models.DateField(verbose_name="التاريخ")
    heure    = models.TimeField(verbose_name="الوقت")
    motif    = models.TextField(blank=True, verbose_name="سبب الزيارة")
    statut   = models.CharField(max_length=20, choices=STATUTS, default='attente', verbose_name="الحالة")
    notes    = models.TextField(blank=True, verbose_name="ملاحظات الطبيب")
    cree_le  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "موعد"
        verbose_name_plural = "المواعيد"
        ordering = ['-date', '-heure']

    def __str__(self):
        return f"{self.patient} ← {self.medecin} | {self.date}"

    def clean(self):
        super().clean()
        if not self.service_id:
            raise ValidationError("الخدمة مطلوبة لهذا الموعد")

        if not MedecinService.objects.filter(medecin=self.medecin, service=self.service, actif=True).exists():
            raise ValidationError("هذا الطبيب غير مخول لهذه الخدمة")

        jour_map = {0:'lun',1:'mar',2:'mer',3:'jeu',4:'ven',5:'sam',6:'dim'}
        jour = jour_map.get(self.date.weekday()) if self.date else None
        planning = None
        if jour:
            planning = PlanningSemaine.objects.filter(medecin=self.medecin, jour=jour, actif=True).first()
        if planning:
            if self.heure < planning.heure_debut or self.heure >= planning.heure_fin:
                raise ValidationError("وقت الموعد خارج ساعات عمل الطبيب")
            slot_minutes = self.service.duree if self.service and self.service.duree else planning.duree_rdv
            total_minutes = ((planning.heure_fin.hour * 60 + planning.heure_fin.minute) - (planning.heure_debut.hour * 60 + planning.heure_debut.minute))
            capacity = max(total_minutes // max(slot_minutes, 5), 0)
            if capacity <= 0:
                raise ValidationError("لا توجد سعة متاحة في جدول هذا الطبيب")

        qs = RendezVous.objects.filter(
            medecin=self.medecin,
            date=self.date,
            heure=self.heure,
            statut__in=['attente', 'confirme']
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if self.service_id:
            same_slot = qs.filter(service=self.service).count()
            if same_slot >= max(self.service.capacite_par_creneau, 1):
                raise ValidationError("هذه الفترة ممتلئة لهذه الخدمة")

    def save(self, *args, **kwargs):
        # Skip full_clean for partial updates (e.g. notes/statut only)
        # Callers pass update_fields=[...] to bypass validation on legacy data
        if not kwargs.get('update_fields'):
            self.full_clean()
        super().save(*args, **kwargs)

    def badge(self):
        return {'attente':'warning','confirme':'success','checked_in':'info','annule':'danger','termine':'secondary'}.get(self.statut,'secondary')


class AdminClinique(models.Model):
    ROLES = [
        ('admin',      'مدير'),
        ('reception',  'استقبال'),
        ('medecin',    'طبيب'),
        ('laboratoire','مختبر'),
    ]
    utilisateur = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='admin_profil',
        null=True, blank=True
    )
    nom       = models.CharField(max_length=100, verbose_name="الاسم الكامل")
    telephone = models.CharField(max_length=20, verbose_name="رقم الهاتف", unique=True)
    role      = models.CharField(max_length=20, choices=ROLES, default='reception', verbose_name="الدور")
    actif     = models.BooleanField(default=True, verbose_name="نشط")
    must_change_password = models.BooleanField(default=True, verbose_name="يجب تغيير كلمة المرور")
    cree_le   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "موظف"
        verbose_name_plural = "فريق العمل"

    def __str__(self):
        return f"{self.nom} ({self.get_role_display()})"

    def is_admin(self):
        return self.role == 'admin'

    def is_reception(self):
        return self.role in ['admin', 'reception']


# ==== Extensions laboratoire / facturation ====

class Analyse(models.Model):
    nom = models.CharField(max_length=120, verbose_name="اسم التحليل")
    description = models.TextField(blank=True, verbose_name="الوصف")
    prix = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="السعر (MRU)")
    actif = models.BooleanField(default=True, verbose_name="نشط")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "تحليل"
        verbose_name_plural = "التحاليل"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class DemandeAnalyse(models.Model):
    STATUTS = [
        ('attente', 'في الانتظار'),
        ('payee', 'مدفوعة'),
        ('en_cours', 'قيد الإنجاز'),
        ('prete', 'جاهزة'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='demandes_analyses', verbose_name="المريض")
    medecin = models.ForeignKey(Medecin, on_delete=models.SET_NULL, null=True, blank=True, related_name='demandes_analyses', verbose_name="الطبيب المعني")
    analyse = models.ForeignKey(Analyse, on_delete=models.CASCADE, related_name='demandes', verbose_name="التحليل")
    resultat = models.TextField(blank=True, verbose_name="النتيجة")
    notes_labo = models.TextField(blank=True, verbose_name="ملاحظات المختبر")
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)
    statut = models.CharField(max_length=20, choices=STATUTS, default='attente', verbose_name="الحالة")

    class Meta:
        verbose_name = "طلب تحليل"
        verbose_name_plural = "طلبات التحاليل"
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.patient} - {self.analyse}"


class FactureAnalyse(models.Model):
    STATUTS = [('non_payee', 'غير مدفوعة'), ('payee', 'مدفوعة')]
    demande = models.OneToOneField(DemandeAnalyse, on_delete=models.CASCADE, related_name='facture', verbose_name="طلب التحليل")
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='factures_analyses', verbose_name="المريض")
    montant = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="المبلغ")
    statut = models.CharField(max_length=20, choices=STATUTS, default='non_payee', verbose_name="الحالة")
    cree_le = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = "فاتورة تحليل"
        verbose_name_plural = "فواتير التحاليل"
        ordering = ['-cree_le']
    def __str__(self):
        return f"فاتورة تحليل #{self.id}"


class PaiementAnalyse(models.Model):
    MODES = [('cash', 'نقدا'), ('bankily', 'بنكيلي'), ('sedad', 'سداد'), ('autre', 'أخرى')]
    facture = models.OneToOneField(FactureAnalyse, on_delete=models.CASCADE, related_name='paiement', verbose_name="الفاتورة")
    montant = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="المبلغ")
    mode = models.CharField(max_length=20, choices=MODES, default='cash', verbose_name="طريقة الدفع")
    reference = models.CharField(max_length=100, blank=True, verbose_name="مرجع الدفع")
    date_paiement = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = "دفع تحليل"
        verbose_name_plural = "مدفوعات التحاليل"
        ordering = ['-date_paiement']
    def __str__(self):
        return f"دفع تحليل #{self.facture.id}"


class FactureConsultation(models.Model):
    STATUTS = [('non_payee', 'غير مدفوعة'), ('payee', 'مدفوعة')]
    rdv = models.OneToOneField(RendezVous, on_delete=models.CASCADE, related_name='facture_consultation', verbose_name="الموعد")
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='factures_consultations', verbose_name="المريض")
    medecin = models.ForeignKey(Medecin, on_delete=models.CASCADE, related_name='factures_consultations', verbose_name="الطبيب")
    montant = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="المبلغ")
    statut = models.CharField(max_length=20, choices=STATUTS, default='non_payee', verbose_name="الحالة")
    cree_le = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = "فاتورة استشارة"
        verbose_name_plural = "فواتير الاستشارات"
        ordering = ['-cree_le']
    def __str__(self):
        return f"فاتورة استشارة #{self.id}"


class PaiementConsultation(models.Model):
    MODES = [('cash', 'نقدا'), ('bankily', 'بنكيلي'), ('sedad', 'سداد'), ('autre', 'أخرى')]
    facture = models.OneToOneField(FactureConsultation, on_delete=models.CASCADE, related_name='paiement', verbose_name="الفاتورة")
    montant = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="المبلغ")
    mode = models.CharField(max_length=20, choices=MODES, default='cash', verbose_name="طريقة الدفع")
    reference = models.CharField(max_length=100, blank=True, verbose_name="مرجع الدفع")
    date_paiement = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = "دفع استشارة"
        verbose_name_plural = "مدفوعات الاستشارات"
        ordering = ['-date_paiement']
    def __str__(self):
        return f"دفع استشارة #{self.facture.id}"


class Ordonnance(models.Model):
    rdv           = models.OneToOneField(RendezVous, on_delete=models.CASCADE, related_name='ordonnance', verbose_name="الموعد")
    medecin       = models.ForeignKey(Medecin,  on_delete=models.CASCADE, related_name='ordonnances', verbose_name="الطبيب")
    patient       = models.ForeignKey(Patient,  on_delete=models.CASCADE, related_name='ordonnances', verbose_name="المريض")
    diagnostic    = models.TextField(verbose_name="التشخيص")
    prescription  = models.TextField(verbose_name="الوصفة الطبية")
    notes_medecin = models.TextField(blank=True, verbose_name="ملاحظات إضافية")
    cree_le       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "وصفة طبية"
        verbose_name_plural = "الوصفات الطبية"
        ordering = ['-cree_le']

    def __str__(self):
        return f"وصفة {self.patient} — {self.cree_le.strftime('%Y/%m/%d')}"


class Notification(models.Model):
    TYPES = [
        ('rdv_confirme',   'موعد مؤكد'),
        ('rdv_annule',     'موعد ملغي'),
        ('rdv_rappel',     'تذكير بموعد'),
        ('analyse_prete',  'تحليل جاهز'),
        ('ordonnance',     'وصفة طبية جديدة'),
        ('transfert',      'تحويل إلى طبيب'),
        ('general',        'إشعار عام'),
    ]
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name="المستخدم")
    type_notif  = models.CharField(max_length=30, choices=TYPES, default='general', verbose_name="نوع الإشعار")
    titre       = models.CharField(max_length=200, verbose_name="العنوان")
    message     = models.TextField(verbose_name="الرسالة")
    lue         = models.BooleanField(default=False, verbose_name="مقروءة")
    lien        = models.CharField(max_length=200, blank=True, verbose_name="الرابط")
    cree_le     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "إشعار"
        verbose_name_plural = "الإشعارات"
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.titre} → {self.utilisateur.username}"


class PlanningSemaine(models.Model):
    JOURS = [
        ('lun', 'الاثنين'),
        ('mar', 'الثلاثاء'),
        ('mer', 'الأربعاء'),
        ('jeu', 'الخميس'),
        ('ven', 'الجمعة'),
        ('sam', 'السبت'),
        ('dim', 'الأحد'),
    ]
    medecin       = models.ForeignKey(Medecin, on_delete=models.CASCADE, related_name='planning', verbose_name="الطبيب")
    jour          = models.CharField(max_length=3, choices=JOURS, verbose_name="اليوم")
    heure_debut   = models.TimeField(verbose_name="بداية العمل")
    heure_fin     = models.TimeField(verbose_name="نهاية العمل")
    actif         = models.BooleanField(default=True, verbose_name="يعمل هذا اليوم")
    duree_rdv     = models.PositiveIntegerField(default=30, verbose_name="مدة الموعد (دقائق)")

    class Meta:
        verbose_name = "يوم عمل"
        verbose_name_plural = "جدول العمل الأسبوعي"
        unique_together = ('medecin', 'jour')
        ordering = ['medecin', 'jour']

    def __str__(self):
        return f"{self.medecin} — {self.get_jour_display()} {self.heure_debut}-{self.heure_fin}"


class JournalAudit(models.Model):
    ACTIONS = [
        ('creation',     'إنشاء'),
        ('modification', 'تعديل'),
        ('suppression',  'حذف'),
        ('connexion',    'دخول'),
        ('deconnexion',  'خروج'),
        ('paiement',     'دفع'),
        ('transfert',    'تحويل'),
        ('annulation',   'إلغاء'),
    ]
    utilisateur  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='journal', verbose_name="المستخدم")
    action       = models.CharField(max_length=20, choices=ACTIONS, verbose_name="الإجراء")
    modele       = models.CharField(max_length=50, verbose_name="الجدول")
    objet_id     = models.PositiveIntegerField(null=True, blank=True, verbose_name="معرف الكائن")
    description  = models.TextField(verbose_name="التفاصيل")
    ip_address   = models.GenericIPAddressField(null=True, blank=True, verbose_name="عنوان IP")
    cree_le      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "سجل مراقبة"
        verbose_name_plural = "سجل المراقبة"
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.utilisateur} — {self.action} — {self.modele} — {self.cree_le.strftime('%d/%m/%Y %H:%M')}"


class ListeAttente(models.Model):
    STATUTS = [
        ('en_attente', 'في الانتظار'),
        ('converti',   'تحول لموعد'),
        ('annule',     'ملغي'),
    ]
    patient        = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='liste_attente', verbose_name="المريض")
    medecin        = models.ForeignKey(Medecin, on_delete=models.CASCADE, related_name='liste_attente', verbose_name="الطبيب")
    date_souhaitee = models.DateField(verbose_name="التاريخ المرغوب")
    notes          = models.TextField(blank=True, verbose_name="ملاحظات")
    statut         = models.CharField(max_length=20, choices=STATUTS, default='en_attente', verbose_name="الحالة")
    cree_le        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "قائمة انتظار"
        verbose_name_plural = "قائمة الانتظار"
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.patient} — {self.medecin} | {self.date_souhaitee}"


ALLOWED_MEDICAL_FILE_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MEDICAL_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}
MAX_MEDICAL_FILE_SIZE = 10 * 1024 * 1024


def medical_file_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    ext = ext if ext in ALLOWED_MEDICAL_FILE_EXTENSIONS else ".bin"
    return f"private_medical/patient_{instance.patient_id}/{uuid.uuid4().hex}{ext}"


class PieceMedicaleType(models.TextChoices):
    ORDONNANCE = "ordonnance", "وصفة طبية"
    ANALYSE = "analyse", "نتيجة تحليل"
    RADIOLOGIE = "radiologie", "تصوير / أشعة"
    RAPPORT = "rapport", "تقرير طبي"
    DOCUMENT = "document", "وثيقة طبية"
    AUTRE = "autre", "أخرى"


class PieceMedicale(models.Model):
    SOURCE_ROLES = [
        ('patient', 'مريض'),
        ('medecin', 'طبيب'),
        ('reception', 'استقبال'),
        ('laboratoire', 'مختبر'),
        ('admin', 'مدير'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='pieces_medicales', verbose_name="المريض")
    rendez_vous = models.ForeignKey(RendezVous, on_delete=models.SET_NULL, null=True, blank=True, related_name='pieces_medicales', verbose_name="الموعد")
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pieces_medicales_creees', verbose_name="أضيف من طرف")
    titre = models.CharField(max_length=255, verbose_name="العنوان")
    type_piece = models.CharField(max_length=20, choices=PieceMedicaleType.choices, default=PieceMedicaleType.DOCUMENT, verbose_name="نوع الملف")
    fichier = models.FileField(upload_to=medical_file_upload_path, verbose_name="الملف")
    nom_original = models.CharField(max_length=255, blank=True, verbose_name="اسم الملف الأصلي")
    type_mime = models.CharField(max_length=100, blank=True, verbose_name="نوع MIME")
    taille_octets = models.PositiveIntegerField(default=0, verbose_name="الحجم")
    description = models.TextField(blank=True, verbose_name="الوصف")
    source_role = models.CharField(max_length=20, choices=SOURCE_ROLES, default='patient', verbose_name="مصدر الإضافة")
    est_active = models.BooleanField(default=True, verbose_name="نشط")
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ملف طبي"
        verbose_name_plural = "الملفات الطبية"
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.titre} — {self.patient}"

    def clean(self):
        if not self.fichier:
            raise ValidationError("الملف مطلوب")

        ext = os.path.splitext(self.fichier.name)[1].lower()
        if ext not in ALLOWED_MEDICAL_FILE_EXTENSIONS:
            raise ValidationError("صيغة الملف غير مسموح بها")

        file_size = getattr(self.fichier, 'size', 0) or 0
        if file_size > MAX_MEDICAL_FILE_SIZE:
            raise ValidationError("حجم الملف يتجاوز 10MB")

        content_type = getattr(self.fichier, 'content_type', '') or ''
        if content_type and content_type not in ALLOWED_MEDICAL_MIME_TYPES:
            raise ValidationError("نوع الملف غير مسموح")

        if self.rendez_vous and self.rendez_vous.patient_id != self.patient.utilisateur_id:
            raise ValidationError("الموعد المحدد لا يعود لهذا المريض")

    def save(self, *args, **kwargs):
        if self.fichier:
            self.nom_original = self.nom_original or os.path.basename(self.fichier.name)
            self.taille_octets = getattr(self.fichier, 'size', 0) or 0
            self.type_mime = getattr(self.fichier, 'content_type', '') or self.type_mime
        self.full_clean()
        super().save(*args, **kwargs)


class PieceMedicaleAudit(models.Model):
    ACTIONS = [
        ('upload', 'رفع'),
        ('download', 'تحميل'),
        ('delete', 'حذف'),
    ]

    piece = models.ForeignKey(PieceMedicale, on_delete=models.CASCADE, related_name='audits', verbose_name="الملف")
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_pieces_medicales', verbose_name="المستخدم")
    action = models.CharField(max_length=20, choices=ACTIONS, verbose_name="الإجراء")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "أثر ملف طبي"
        verbose_name_plural = "آثار الملفات الطبية"
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.get_action_display()} — {self.piece_id}"


class DossierPartage(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="partages_dossier", verbose_name="المريض")
    medecin_source = models.ForeignKey(Medecin, on_delete=models.SET_NULL, null=True, blank=True, related_name='partages_envoyes', verbose_name="الطبيب المصدر")
    medecin_cible = models.ForeignKey(Medecin, on_delete=models.CASCADE, related_name='partages_recus', verbose_name="الطبيب المستفيد")
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='partages_crees', verbose_name="أنشئ بواسطة")
    lecture_seule = models.BooleanField(default=True, verbose_name="قراءة فقط")
    peut_ajouter_notes = models.BooleanField(default=False, verbose_name="يمكنه إضافة ملاحظات")
    peut_ajouter_fichiers = models.BooleanField(default=False, verbose_name="يمكنه رفع ملفات")
    peut_creer_ordonnance = models.BooleanField(default=False, verbose_name="يمكنه إنشاء وصفة")
    actif = models.BooleanField(default=True, verbose_name="نشط")
    date_debut = models.DateField(auto_now_add=True, verbose_name="تاريخ البداية")
    date_fin = models.DateField(null=True, blank=True, verbose_name="تاريخ النهاية")
    note = models.TextField(blank=True, verbose_name="ملاحظات")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "مشاركة ملف طبي"
        verbose_name_plural = "مشاركات الملف الطبي"
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.patient} → {self.medecin_cible}"

    def est_valide(self):
        if not self.actif:
            return False
        if self.date_fin and self.date_fin < datetime.date.today():
            return False
        return True
