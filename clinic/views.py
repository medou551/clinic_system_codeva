import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from functools import wraps
import json
import mimetypes
import os
from django.http import JsonResponse, FileResponse, Http404
from django.db.models import Q
from .models import (Specialite, Medecin, Service, RendezVous, Patient,
                     AdminClinique, Analyse, DemandeAnalyse,
                     FactureAnalyse, PaiementAnalyse,
                     FactureConsultation, PaiementConsultation,
                     Ordonnance, ListeAttente,
                     Notification, PlanningSemaine, JournalAudit,
                     PieceMedicale, PieceMedicaleAudit, DossierPartage, MedecinService)




def normalize_phone(phone):
    return ''.join(ch for ch in (phone or '') if ch.isdigit())


def ensure_unique_username(base):
    username = base
    idx = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}_{idx}"
        idx += 1
    return username


def create_staff_user_for_admin(admin_obj):
    if admin_obj.utilisateur_id:
        return admin_obj.utilisateur
    phone = normalize_phone(admin_obj.telephone) or str(admin_obj.pk)
    username = ensure_unique_username(f"staff_{phone}")
    user = User.objects.create_user(
        username=username,
        first_name=admin_obj.nom,
        last_name='',
        password=phone,
        is_staff=(admin_obj.role == 'admin'),
    )
    admin_obj.utilisateur = user
    admin_obj.must_change_password = True
    admin_obj.save(update_fields=['utilisateur', 'must_change_password'])
    return user


def get_active_dossier_share(patient, medecin):
    today = datetime.date.today()
    return DossierPartage.objects.filter(
        patient=patient,
        medecin_cible=medecin,
        actif=True
    ).filter(Q(date_fin__isnull=True) | Q(date_fin__gte=today)).order_by('-cree_le').first()


def get_allowed_services_for_medecin(medecin):
    return Service.objects.filter(
        actif=True,
        medecins_autorises__medecin=medecin,
        medecins_autorises__actif=True,
    ).distinct().order_by('nom')


def get_planning_for_date(medecin, target_date):
    jour_map = {0:'lun',1:'mar',2:'mer',3:'jeu',4:'ven',5:'sam',6:'dim'}
    jour = jour_map.get(target_date.weekday())
    if not jour:
        return None
    return PlanningSemaine.objects.filter(medecin=medecin, jour=jour, actif=True).first()


def compute_daily_capacity(medecin, target_date, service=None):
    planning = get_planning_for_date(medecin, target_date)
    if not planning:
        return 0
    start_minutes = planning.heure_debut.hour * 60 + planning.heure_debut.minute
    end_minutes = planning.heure_fin.hour * 60 + planning.heure_fin.minute
    total_minutes = max(end_minutes - start_minutes, 0)
    slot_minutes = planning.duree_rdv
    if service and getattr(service, 'duree', None):
        slot_minutes = service.duree
    slot_minutes = max(int(slot_minutes or 30), 5)
    return max(total_minutes // slot_minutes, 0)


def can_manage_patient_dossier(user, patient, action='view'):
    if not user.is_authenticated:
        return False
    ap = get_admin_profil(user)
    if ap and ap.role in ['admin', 'reception', 'laboratoire']:
        return True
    if patient.utilisateur_id == user.id:
        return action in ['view', 'upload']
    medecin = get_connected_medecin(user)
    if not medecin:
        return False
    if RendezVous.objects.filter(patient=patient.utilisateur, medecin=medecin).exists():
        return True
    share = get_active_dossier_share(patient, medecin)
    if not share:
        return False
    if action == 'view':
        return True
    if action == 'upload':
        return share.peut_ajouter_fichiers
    if action == 'note':
        return share.peut_ajouter_notes
    if action == 'ordonnance':
        return share.peut_creer_ordonnance
    return False



def get_connected_medecin(user):
    if not user or not user.is_authenticated:
        return None
    direct = Medecin.objects.filter(utilisateur=user).first()
    if direct:
        return direct
    ap = get_admin_profil(user)
    if not ap or not ap.nom:
        return None
    return (
        Medecin.objects.filter(telephone=ap.telephone).first() or
        Medecin.objects.filter(nom__iexact=ap.nom).first() or
        Medecin.objects.filter(nom__icontains=ap.nom.split()[0]).first()
    )


def can_access_medical_file(user, piece):
    if not user.is_authenticated or not piece.est_active:
        return False

    ap = get_admin_profil(user)
    if ap and ap.role in ["admin", "reception", "laboratoire"]:
        return True

    if piece.patient.utilisateur_id == user.id:
        return True

    medecin = get_connected_medecin(user)
    if medecin:
        if piece.rendez_vous and piece.rendez_vous.medecin_id == medecin.id:
            return True
        if RendezVous.objects.filter(patient=piece.patient.utilisateur, medecin=medecin).exists():
            return True
        if Ordonnance.objects.filter(patient=piece.patient, medecin=medecin).exists():
            return True
        if DemandeAnalyse.objects.filter(patient=piece.patient, medecin=medecin).exists():
            return True
        share = get_active_dossier_share(piece.patient, medecin)
        if share:
            return True

    return False


def resolve_source_role(user):
    ap = get_admin_profil(user)
    if ap:
        return ap.role
    return 'patient'


def can_access_patient_dossier(user, patient):
    if not user.is_authenticated:
        return False

    ap = get_admin_profil(user)
    if ap and ap.role in ["admin", "reception", "laboratoire"]:
        return True

    if patient.utilisateur_id == user.id:
        return True

    medecin = get_connected_medecin(user)
    if medecin:
        if RendezVous.objects.filter(patient=patient.utilisateur, medecin=medecin).exists():
            return True
        if get_active_dossier_share(patient, medecin):
            return True

    return False

def creer_notification(utilisateur, type_notif, titre, message, lien=''):
    try:
        Notification.objects.create(
            utilisateur=utilisateur, type_notif=type_notif,
            titre=titre, message=message, lien=lien,
        )
    except Exception:
        pass


def journaliser(request_or_user, action, modele, description, objet_id=None):
    try:
        user = getattr(request_or_user, 'user', request_or_user)
        ip = None
        if hasattr(request_or_user, 'META'):
            ip = request_or_user.META.get('REMOTE_ADDR')
        JournalAudit.objects.create(
            utilisateur=user if user and user.is_authenticated else None,
            action=action, modele=modele, objet_id=objet_id,
            description=description, ip_address=ip,
        )
    except Exception:
        pass


def get_admin_profil(user):
    try:
        return user.admin_profil
    except Exception:
        return None


def reception_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/connexion/?next=" + request.path)
        ap = get_admin_profil(request.user)
        if ap and ap.is_reception():
            return view_func(request, *args, **kwargs)
        messages.error(request, "غير مصرح لك بهذه الصفحة")
        return redirect("accueil")
    return wrapper


def laboratoire_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/connexion/?next=" + request.path)
        ap = get_admin_profil(request.user)
        if ap and ap.role in ["admin", "laboratoire"]:
            return view_func(request, *args, **kwargs)
        messages.error(request, "غير مصرح لك بهذه الصفحة")
        return redirect("accueil")
    return wrapper


def medecin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/connexion/?next=" + request.path)
        ap = get_admin_profil(request.user)
        if ap and ap.role in ["admin", "medecin"]:
            return view_func(request, *args, **kwargs)
        # Allow users with a direct Medecin.utilisateur link (no AdminClinique row needed)
        if Medecin.objects.filter(utilisateur=request.user).exists():
            return view_func(request, *args, **kwargs)
        messages.error(request, "غير مصرح لك بهذه الصفحة")
        return redirect("accueil")
    return wrapper


# Pages publiques
def accueil(request):
    return render(request, "accueil.html", {
        "medecins":         Medecin.objects.filter(disponible=True).select_related("specialite")[:4],
        "services":         Service.objects.all()[:6],
        "specialites":      Specialite.objects.all()[:6],
        "nb_medecins":      Medecin.objects.filter(disponible=True).count(),
        "nb_specialites":   Specialite.objects.count(),
        "analyses_accueil": Analyse.objects.filter(actif=True).order_by("nom")[:8],
        "nb_analyses":      Analyse.objects.filter(actif=True).count(),
    })

def liste_services(request):
    return render(request, "services.html", {"services": Service.objects.all()})

def liste_medecins(request):
    specialites = Specialite.objects.all()
    spec_id = request.GET.get("specialite")
    medecins = Medecin.objects.filter(disponible=True).select_related("specialite")
    if spec_id:
        medecins = medecins.filter(specialite_id=spec_id)
    return render(request, "medecins.html", {
        "medecins": medecins, "specialites": specialites, "spec_choisie": spec_id
    })

def liste_specialites(request):
    return render(request, "specialites.html", {
        "specialites": Specialite.objects.prefetch_related("medecins")
    })


# Auth
def inscription(request):
    if request.user.is_authenticated:
        return redirect("accueil")
    if request.method == "POST":
        nom = request.POST.get("nom", "").strip()
        prenom = request.POST.get("prenom", "").strip()
        telephone = request.POST.get("telephone", "").strip()
        genre = request.POST.get("genre", "")
        email = request.POST.get("email", "").strip()
        adresse = request.POST.get("adresse", "").strip()
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")

        if not nom or not telephone or not password or not password_confirm:
            messages.error(request, "الاسم والهاتف وكلمة المرور مطلوبة")
        elif password != password_confirm:
            messages.error(request, "تأكيد كلمة المرور غير مطابق")
        elif len(password) < 8:
            messages.error(request, "يجب أن تكون كلمة المرور 8 أحرف على الأقل")
        elif Patient.objects.filter(telephone=telephone).exists():
            messages.error(request, "رقم الهاتف مستخدم مسبقاً")
        else:
            base = "pat_" + (normalize_phone(telephone) or str(User.objects.count() + 1))
            username = ensure_unique_username(base)
            user = User.objects.create_user(username=username, first_name=prenom, last_name=nom, email=email, password=password)
            user.profil.telephone = telephone
            user.profil.genre = genre
            user.profil.adresse = adresse
            user.profil.save()
            journaliser(user, 'creation', 'Patient', f"إنشاء حساب مريض جديد: {nom}", user.profil.id)
            messages.success(request, "تم إنشاء الحساب بنجاح — يمكنك تسجيل الدخول الآن")
            return redirect("connexion")
    return render(request, "inscription.html")


def connexion(request):
    if request.user.is_authenticated:
        return redirect("accueil")

    if request.method == "POST":
        nom = request.POST.get("nom", "").strip()
        telephone = request.POST.get("telephone", "").strip()
        role = request.POST.get("role", "patient")
        password = request.POST.get("password", "").strip()
        if not telephone or not password:
            messages.error(request, "رقم الهاتف وكلمة المرور مطلوبان")
            return render(request, "connexion.html")

        if role == "staff":
            admin_obj = AdminClinique.objects.filter(telephone=telephone, actif=True).first()
            if not admin_obj:
                messages.error(request, "بيانات فريق العمل غير صحيحة")
                return render(request, "connexion.html")
            user = create_staff_user_for_admin(admin_obj)
            if nom and admin_obj.nom and nom.lower() not in admin_obj.nom.lower():
                messages.error(request, "الاسم لا يطابق الحساب")
                return render(request, "connexion.html")
            auth_user = authenticate(request, username=user.username, password=password)
            if not auth_user:
                messages.error(request, "كلمة المرور غير صحيحة")
                return render(request, "connexion.html")
            login(request, auth_user)
            if admin_obj.must_change_password:
                return redirect('set_password_first_login')
            journaliser(request, 'connexion', 'AdminClinique', f"دخول {admin_obj.nom} ({admin_obj.get_role_display()})", admin_obj.id)
            messages.success(request, f"مرحباً {admin_obj.nom} — {admin_obj.get_role_display()}")
            role_redirects = {
                'admin': 'admin_dashboard', 'reception': 'reception_dashboard',
                'medecin': 'medecin_dashboard', 'laboratoire': 'labo_dashboard'
            }
            return redirect(role_redirects.get(admin_obj.role, 'accueil'))

        patient = Patient.objects.filter(telephone=telephone).select_related('utilisateur').first()
        if not patient:
            messages.error(request, "الحساب غير موجود")
            return render(request, "connexion.html")
        if nom:
            full_name = (patient.utilisateur.get_full_name() or '').strip().lower()
            if nom.lower() not in full_name and nom.lower() not in patient.utilisateur.last_name.lower():
                messages.error(request, "الاسم لا يطابق الحساب")
                return render(request, "connexion.html")
        auth_user = authenticate(request, username=patient.utilisateur.username, password=password)
        if not auth_user:
            messages.error(request, "كلمة المرور غير صحيحة")
            return render(request, "connexion.html")
        login(request, auth_user)
        journaliser(request, 'connexion', 'Patient', f"دخول {patient}", patient.id)
        messages.success(request, f"مرحباً {patient}")
        return redirect(request.GET.get('next') or 'tableau_bord')

    return render(request, "connexion.html")

@login_required
def set_password_first_login(request):
    ap = get_admin_profil(request.user)
    if not ap:
        return redirect('accueil')
    if request.method == 'POST':
        password = request.POST.get('password', '').strip()
        confirm = request.POST.get('password_confirm', '').strip()
        if len(password) < 8:
            messages.error(request, 'يجب أن تكون كلمة المرور 8 أحرف على الأقل')
        elif password != confirm:
            messages.error(request, 'تأكيد كلمة المرور غير مطابق')
        else:
            request.user.set_password(password)
            request.user.save()
            ap.must_change_password = False
            ap.save(update_fields=['must_change_password'])
            auth_user = authenticate(request, username=request.user.username, password=password)
            if auth_user:
                login(request, auth_user)
            messages.success(request, 'تم تعيين كلمة المرور بنجاح')
            role_redirects = {'admin':'admin_dashboard','reception':'reception_dashboard','medecin':'medecin_dashboard','laboratoire':'labo_dashboard'}
            return redirect(role_redirects.get(ap.role, 'accueil'))
    return render(request, 'set_password_first_login.html')


def deconnexion(request):
    logout(request)
    messages.info(request, "تم تسجيل خروجك")
    return redirect("accueil")


@login_required
def profil(request):
    p = request.user.profil
    if request.method == "POST":
        u = request.user
        u.first_name = request.POST.get("prenom", "")
        u.last_name  = request.POST.get("nom", "")
        u.email      = request.POST.get("email", "")
        u.save()
        p.telephone = request.POST.get("telephone", "")
        p.adresse   = request.POST.get("adresse", "")
        p.genre     = request.POST.get("genre", "")
        dn = request.POST.get("date_naissance", "")
        if dn: p.date_naissance = dn
        p.save()
        messages.success(request, "تم تحديث ملفك الشخصي ✔")
        return redirect("profil")
    return render(request, "profil.html", {"patient": p})


@login_required
def prendre_rdv(request):
    specialites = Specialite.objects.all()
    services = Service.objects.filter(actif=True).order_by('nom')
    spec_id = request.GET.get("specialite")
    med_pres = request.GET.get("medecin")
    medecins = Medecin.objects.filter(disponible=True).select_related("specialite")
    if spec_id:
        medecins = medecins.filter(specialite_id=spec_id)

    if request.method == "POST":
        med_id = request.POST.get("medecin")
        service_id = request.POST.get("service")
        date_str = request.POST.get("date")
        heure_str = request.POST.get("heure")
        motif = request.POST.get("motif", "")
        if not med_id or not service_id or not date_str or not heure_str:
            messages.error(request, "يرجى ملء جميع الحقول")
        else:
            try:
                date_rdv = datetime.date.fromisoformat(date_str)
                if date_rdv < datetime.date.today():
                    raise ValueError
            except ValueError:
                messages.error(request, "التاريخ غير صالح أو في الماضي")
            else:
                medecin = get_object_or_404(Medecin, id=med_id, disponible=True)
                service = get_object_or_404(Service, id=service_id, actif=True)
                if not MedecinService.objects.filter(medecin=medecin, service=service, actif=True).exists():
                    messages.error(request, "هذا الطبيب غير مخول لهذه الخدمة")
                else:
                    try:
                        rdv_new = RendezVous.objects.create(
                            patient=request.user,
                            medecin=medecin,
                            service=service,
                            date=date_rdv,
                            heure=heure_str,
                            motif=motif,
                        )
                    except Exception as exc:
                        messages.error(request, f"تعذر حجز الموعد: {exc}")
                    else:
                        journaliser(request, 'creation', 'RendezVous', f"حجز موعد {service} مع {medecin} في {date_rdv} {heure_str}", rdv_new.id)
                        creer_notification(request.user, 'rdv_confirme',
                            f"تم حجز موعدك مع {medecin}",
                            f"الخدمة: {service.nom} — موعدك يوم {date_rdv} الساعة {heure_str}. سبب الزيارة: {motif or 'غير محدد'}",
                            lien='/مواعيدي/')
                        messages.success(request, f"تم حجز موعدك مع {medecin} — {service.nom} ✅")
                        return redirect("mes_rdv")

    creneaux_pris_js = {}
    rdvs_actifs = RendezVous.objects.filter(
        statut__in=["attente", "confirme"],
        medecin__in=medecins
    ).values("medecin_id", "date", "heure")
    for r in rdvs_actifs:
        mid = str(r["medecin_id"])
        dk = str(r["date"])
        if mid not in creneaux_pris_js:
            creneaux_pris_js[mid] = {}
        if dk not in creneaux_pris_js[mid]:
            creneaux_pris_js[mid][dk] = []
        creneaux_pris_js[mid][dk].append(str(r["heure"])[:5])

    services_by_medecin = {}
    disponibilites_resume = []
    today = datetime.date.today()
    for med in medecins[:12]:
        allowed = list(get_allowed_services_for_medecin(med).values('id', 'nom'))
        services_by_medecin[str(med.id)] = allowed
        capacity_today = compute_daily_capacity(med, today)
        booked_today = RendezVous.objects.filter(medecin=med, date=today, statut__in=["attente", "confirme"]).count()
        disponibilites_resume.append({
            "medecin": med,
            "booked": booked_today,
            "capacity": capacity_today,
            "remaining": max(capacity_today - booked_today, 0),
        })

    return render(request, "prendre_rdv.html", {
        "specialites": specialites,
        "services": services,
        "medecins": medecins,
        "spec_choisie": spec_id,
        "med_preselect": med_pres,
        "creneaux_pris_json": json.dumps(creneaux_pris_js),
        "services_by_medecin_json": json.dumps(services_by_medecin, ensure_ascii=False),
        "disponibilites_resume": disponibilites_resume,
    })


@login_required
def mes_rdv(request):
    rdvs = RendezVous.objects.filter(patient=request.user).select_related("medecin", "medecin__specialite")
    filtre = request.GET.get("statut")
    if filtre: rdvs = rdvs.filter(statut=filtre)
    return render(request, "mes_rdv.html", {"rdvs": rdvs, "filtre": filtre})


@login_required
def annuler_rdv(request, pk):
    rdv = get_object_or_404(RendezVous, pk=pk, patient=request.user)
    if rdv.statut in ["attente", "confirme"]:
        rdv.statut = "annule"
        rdv.save(update_fields=['statut'])
        journaliser(request, 'annulation', 'RendezVous', f"إلغاء الموعد #{rdv.id} مع {rdv.medecin}", rdv.id)
        messages.success(request, "تم إلغاء الموعد")
    else:
        messages.error(request, "لا يمكن إلغاء هذا الموعد")
    return redirect("mes_rdv")


@login_required
def tableau_bord(request):
    today = datetime.date.today()
    rdvs  = RendezVous.objects.filter(patient=request.user).select_related("medecin", "medecin__specialite")
    a_venir = rdvs.filter(date__gte=today, statut__in=["attente", "confirme"]).order_by("date", "heure")
    prochain = a_venir.first()
    dernier  = rdvs.filter(statut="termine").order_by("-date", "-heure").first()
    try:
        demandes = DemandeAnalyse.objects.filter(
            patient=request.user.profil
        ).select_related("analyse", "medecin").order_by("-cree_le")[:5]
    except Exception:
        demandes = []
    try:
        factures_consult = FactureConsultation.objects.filter(
            patient=request.user.profil
        ).select_related("medecin", "rdv").order_by("-cree_le")[:5]
        factures_analyse = FactureAnalyse.objects.filter(
            patient=request.user.profil
        ).select_related("demande__analyse").order_by("-cree_le")[:5]
        nb_impayes = (
            FactureConsultation.objects.filter(patient=request.user.profil, statut="non_payee").count() +
            FactureAnalyse.objects.filter(patient=request.user.profil, statut="non_payee").count()
        )
    except Exception:
        factures_consult = []
        factures_analyse = []
        nb_impayes = 0
    stats = {
        "total":   rdvs.count(),
        "attente": rdvs.filter(statut="attente").count(),
        "confirme":rdvs.filter(statut="confirme").count(),
        "termine": rdvs.filter(statut="termine").count(),
        "annule":  rdvs.filter(statut="annule").count(),
        "a_venir": a_venir.count(),
    }
    return render(request, "tableau_bord.html", {
        "a_venir": a_venir[:4], "prochain": prochain,
        "dernier": dernier, "stats": stats, "today": today, "demandes": demandes,
        "factures_consult": factures_consult,
        "factures_analyse": factures_analyse,
        "nb_impayes": nb_impayes,
    })


# RECEPTION
@reception_required
def reception_dashboard(request):
    today = datetime.date.today()
    rdvs_today = RendezVous.objects.filter(date=today).select_related(
        "patient", "medecin", "medecin__specialite").order_by("heure")
    rdvs_semaine = RendezVous.objects.filter(
        date__gte=today, statut__in=["attente", "confirme"]
    ).select_related("patient", "medecin").order_by("date", "heure")[:10]
    stats = {
        "rdv_today":       rdvs_today.count(),
        "rdv_attente":     RendezVous.objects.filter(statut="attente").count(),
        "rdv_confirme":    RendezVous.objects.filter(statut="confirme").count(),
        "nb_patients":     Patient.objects.count(),
        "nb_medecins":     Medecin.objects.filter(disponible=True).count(),
        "nb_rdv_total":    RendezVous.objects.count(),
        "factures_attente":FactureAnalyse.objects.filter(statut="non_payee").count(),
    }
    return render(request, "reception/dashboard.html", {
        "rdvs_today": rdvs_today, "rdvs_semaine": rdvs_semaine,
        "stats": stats, "today": today,
    })


@reception_required
def reception_rdv(request):
    rdvs = RendezVous.objects.all().select_related(
        "patient", "medecin", "medecin__specialite").order_by("-date", "-heure")
    filtre_statut = request.GET.get("statut", "")
    filtre_date   = request.GET.get("date", "")
    filtre_med    = request.GET.get("medecin", "")
    if filtre_statut: rdvs = rdvs.filter(statut=filtre_statut)
    if filtre_date:   rdvs = rdvs.filter(date=filtre_date)
    if filtre_med:    rdvs = rdvs.filter(medecin_id=filtre_med)
    medecins = Medecin.objects.all()
    return render(request, "reception/rdv_list.html", {
        "rdvs": rdvs, "medecins": medecins,
        "filtre_statut": filtre_statut, "filtre_date": filtre_date, "filtre_med": filtre_med,
    })


@reception_required
def reception_rdv_statut(request, pk):
    rdv = get_object_or_404(RendezVous, pk=pk)
    if request.method == "POST":
        nouveau = request.POST.get("statut")
        if nouveau in ["attente", "confirme", "checked_in", "annule", "termine"]:
            ancien = rdv.statut
            rdv.statut = nouveau
            rdv.notes  = request.POST.get("notes", rdv.notes)
            rdv.save(update_fields=['statut', 'notes'])
            journaliser(request, 'modification', 'RendezVous',
                f"تغيير حالة الموعد #{rdv.id} من {ancien} إلى {nouveau}", rdv.id)
            # Notifier le patient
            if nouveau == 'confirme':
                creer_notification(rdv.patient, 'rdv_confirme',
                    f"تم تأكيد موعدك مع {rdv.medecin}",
                    f"موعدك يوم {rdv.date} الساعة {rdv.heure} — مؤكد ✅",
                    lien='/مواعيدي/')
            elif nouveau == 'annule':
                creer_notification(rdv.patient, 'rdv_annule',
                    f"تم إلغاء موعدك مع {rdv.medecin}",
                    f"الموعد المقرر يوم {rdv.date} الساعة {rdv.heure} تم إلغاؤه",
                    lien='/حجز/')
            messages.success(request, f"تم تغيير الحالة إلى: {rdv.get_statut_display()}")
    return redirect("reception_rdv")


@reception_required
def reception_rdv_nouveau(request):
    medecins = Medecin.objects.filter(disponible=True).select_related("specialite")
    patients = Patient.objects.all().select_related("utilisateur").order_by("utilisateur__last_name")
    specialites = Specialite.objects.all()
    services = Service.objects.filter(actif=True).order_by('nom')
    services_by_medecin = {str(m.id): list(get_allowed_services_for_medecin(m).values('id', 'nom')) for m in medecins}
    if request.method == "POST":
        pat_id, med_id = request.POST.get("patient"), request.POST.get("medecin")
        service_id = request.POST.get('service')
        date_str, heure_str = request.POST.get("date"), request.POST.get("heure")
        motif, statut = request.POST.get("motif", ""), request.POST.get("statut", "confirme")
        if not all([pat_id, med_id, service_id, date_str, heure_str]):
            messages.error(request, "يرجى ملء جميع الحقول")
        else:
            patient_obj = get_object_or_404(Patient, pk=pat_id)
            medecin_obj = get_object_or_404(Medecin, pk=med_id, disponible=True)
            service_obj = get_object_or_404(Service, pk=service_id, actif=True)
            if not MedecinService.objects.filter(medecin=medecin_obj, service=service_obj, actif=True).exists():
                messages.error(request, 'هذا الطبيب غير مخول لهذه الخدمة')
            else:
                try:
                    RendezVous.objects.create(patient=patient_obj.utilisateur, medecin=medecin_obj, service=service_obj,
                                              date=date_str, heure=heure_str, motif=motif, statut=statut)
                except Exception as exc:
                    messages.error(request, f'تعذر إنشاء الموعد: {exc}')
                else:
                    messages.success(request, "تم إنشاء الموعد بنجاح ✅")
                    return redirect("reception_rdv")
    return render(request, "reception/rdv_nouveau.html", {
        "medecins": medecins, "patients": patients, "specialites": specialites,
        "services": services, "services_by_medecin_json": json.dumps(services_by_medecin, ensure_ascii=False)
    })


@reception_required
def reception_patients(request):
    q = request.GET.get("q", "")
    patients = Patient.objects.all().select_related("utilisateur").order_by("utilisateur__last_name")
    if q:
        from django.db.models import Q
        patients = patients.filter(
            Q(utilisateur__last_name__icontains=q) |
            Q(utilisateur__first_name__icontains=q) |
            Q(telephone__icontains=q)
        )
    return render(request, "reception/patients.html", {"patients": patients, "q": q})


@reception_required
def reception_patient_detail(request, pk):
    patient    = get_object_or_404(Patient, pk=pk)
    rdvs       = RendezVous.objects.filter(patient=patient.utilisateur).select_related("medecin").order_by("-date")
    demandes   = DemandeAnalyse.objects.filter(patient=patient).select_related("analyse", "medecin").order_by("-cree_le")
    ordonnances = Ordonnance.objects.filter(patient=patient).select_related("medecin", "rdv").order_by("-cree_le")
    return render(request, "reception/patient_detail.html", {
        "patient": patient, "rdvs": rdvs, "demandes": demandes, "ordonnances": ordonnances
    })


@reception_required
def reception_medecins(request):
    medecins    = Medecin.objects.all().select_related("specialite").order_by("nom")
    specialites = Specialite.objects.all()
    return render(request, "reception/medecins.html", {"medecins": medecins, "specialites": specialites})


@reception_required
def reception_medecin_toggle(request, pk):
    ap = get_admin_profil(request.user)
    if not ap or ap.role != "admin":
        messages.error(request, "للمدراء فقط")
        return redirect("reception_medecins")
    m = get_object_or_404(Medecin, pk=pk)
    m.disponible = not m.disponible; m.save()
    messages.success(request, f"{'تم تفعيل' if m.disponible else 'تم تعطيل'} {m}")
    return redirect("reception_medecins")


@reception_required
def reception_services(request):
    return render(request, "reception/services.html", {"services": Service.objects.all()})


@reception_required
def reception_equipe(request):
    ap = get_admin_profil(request.user)
    if not ap or ap.role != "admin":
        messages.error(request, "هذه الصفحة للمدراء فقط")
        return redirect("reception_dashboard")
    membres = AdminClinique.objects.all().order_by("role", "nom")
    return render(request, "reception/equipe.html", {"membres": membres})


@reception_required
def reception_equipe_ajouter(request):
    ap = get_admin_profil(request.user)
    if not ap or ap.role != "admin":
        return redirect("reception_dashboard")
    if request.method == "POST":
        nom, telephone = request.POST.get("nom", "").strip(), request.POST.get("telephone", "").strip()
        role = request.POST.get("role", "reception")
        if not nom or not telephone:
            messages.error(request, "الاسم والهاتف مطلوبان")
        elif AdminClinique.objects.filter(telephone=telephone).exists():
            messages.error(request, "رقم الهاتف موجود مسبقاً")
        else:
            membre = AdminClinique.objects.create(nom=nom, telephone=telephone, role=role)
            create_staff_user_for_admin(membre)
            messages.success(request, f"تمت إضافة {nom} بنجاح — كلمة المرور المؤقتة هي رقم الهاتف")
            return redirect("reception_equipe")
    return render(request, "reception/equipe_ajouter.html")


# Analyses publiques
def analyses_disponibles(request):
    analyses = Analyse.objects.filter(actif=True).order_by("nom")
    return render(request, "analyses/disponibles.html", {"analyses": analyses})


@login_required
def patient_analyses(request):
    patient  = request.user.profil
    demandes = DemandeAnalyse.objects.filter(patient=patient).select_related(
        "analyse", "medecin").order_by("-cree_le")
    analyses = Analyse.objects.filter(actif=True).order_by("nom")
    return render(request, "analyses/patient_analyses.html", {"demandes": demandes, "analyses": analyses})


# Reception : analyses + paiements
@reception_required
def reception_demande_analyse_nouveau(request):
    patients = Patient.objects.all().select_related("utilisateur").order_by(
        "utilisateur__last_name", "utilisateur__first_name")
    medecins = Medecin.objects.filter(disponible=True).select_related("specialite").order_by("nom")
    analyses = Analyse.objects.filter(actif=True).order_by("nom")
    if request.method == "POST":
        patient_id = request.POST.get("patient")
        medecin_id = request.POST.get("medecin")
        analyse_id = request.POST.get("analyse")
        if not patient_id or not medecin_id or not analyse_id:
            messages.error(request, "يرجى ملء جميع الحقول")
        else:
            patient = get_object_or_404(Patient, id=patient_id)
            medecin = get_object_or_404(Medecin, id=medecin_id)
            analyse = get_object_or_404(Analyse, id=analyse_id, actif=True)
            demande = DemandeAnalyse.objects.create(
                patient=patient, medecin=medecin, analyse=analyse, statut="attente"
            )
            FactureAnalyse.objects.create(demande=demande, patient=patient, montant=analyse.prix, statut="non_payee")
            messages.success(request, f"تم إنشاء طلب تحليل {analyse.nom} للمريض {patient} ✅")
            return redirect("reception_factures")
    return render(request, "reception/demande_analyse_nouveau.html", {
        "patients": patients, "medecins": medecins, "analyses": analyses
    })


@reception_required
def reception_factures(request):
    factures = FactureAnalyse.objects.select_related(
        "patient__utilisateur", "demande__analyse", "demande__medecin"
    ).all().order_by("-cree_le")
    filtre = request.GET.get("statut", "")
    if filtre:
        factures = factures.filter(statut=filtre)
    return render(request, "reception/factures_analyses.html", {"factures": factures, "filtre": filtre})


@reception_required
def reception_payer_facture(request, facture_id):
    """Paiement => demande visible au labo ET au médecin immédiatement"""
    facture = get_object_or_404(FactureAnalyse, id=facture_id)
    if facture.statut != "payee":
        mode      = request.POST.get("mode", "cash")
        reference = request.POST.get("reference", "")
        PaiementAnalyse.objects.create(facture=facture, montant=facture.montant, mode=mode, reference=reference)
        facture.statut = "payee"; facture.save()
        facture.demande.statut = "payee"; facture.demande.save()
        journaliser(request, 'paiement', 'FactureAnalyse',
            f"دفع فاتورة تحليل #{facture.id} — {facture.montant} MRU ({mode})", facture.id)
        messages.success(request,
            f"✅ تم تسجيل الدفع ({facture.montant} MRU) — "
            f"الطلب مرئي الآن للمختبر وللطبيب {facture.demande.medecin}")
    else:
        messages.info(request, "هذه الفاتورة مدفوعة مسبقاً")
    return redirect("reception_factures")


@reception_required
def facture_analyse_print(request, facture_id):
    facture = get_object_or_404(
        FactureAnalyse.objects.select_related("patient__utilisateur", "demande__analyse", "demande__medecin"),
        id=facture_id)
    return render(request, "reception/facture_analyse_print.html", {"facture": facture})


@reception_required
def creer_facture_consultation(request, rdv_id):
    rdv = get_object_or_404(RendezVous, id=rdv_id)
    facture, created = FactureConsultation.objects.get_or_create(
        rdv=rdv, defaults={"patient": rdv.patient.profil, "medecin": rdv.medecin, "montant": 800}
    )
    messages.success(request, "تم إنشاء فاتورة الاستشارة" if created else "فاتورة الاستشارة موجودة مسبقاً")
    return redirect("reception_rdv")


@reception_required
def payer_consultation(request, facture_id):
    facture = get_object_or_404(FactureConsultation, id=facture_id)
    if facture.statut != "payee":
        mode      = request.POST.get("mode", "cash")
        reference = request.POST.get("reference", "")
        PaiementConsultation.objects.create(facture=facture, montant=facture.montant, mode=mode, reference=reference)
        facture.statut = "payee"; facture.save()
        journaliser(request, 'paiement', 'FactureConsultation',
            f"دفع فاتورة استشارة #{facture.id} — {facture.montant} MRU ({mode})", facture.id)
        messages.success(request, f"✅ تم دفع استشارة {facture.medecin} — {facture.montant} MRU")
    return redirect("reception_rdv")


@reception_required
def facture_consultation_print(request, facture_id):
    facture = get_object_or_404(
        FactureConsultation.objects.select_related("patient__utilisateur", "medecin", "rdv"),
        id=facture_id)
    return render(request, "reception/facture_consultation_print.html", {"facture": facture})


# LABORATOIRE
@laboratoire_required
def labo_dashboard(request):
    filtre = request.GET.get("statut", "")
    demandes = DemandeAnalyse.objects.select_related(
        "patient__utilisateur", "analyse", "medecin"
    ).filter(statut__in=["payee", "en_cours", "prete"]).order_by("-cree_le")
    if filtre:
        demandes = demandes.filter(statut=filtre)
    stats = {
        "payees":   DemandeAnalyse.objects.filter(statut="payee").count(),
        "en_cours": DemandeAnalyse.objects.filter(statut="en_cours").count(),
        "pretes":   DemandeAnalyse.objects.filter(statut="prete").count(),
        "total":    DemandeAnalyse.objects.filter(statut__in=["payee","en_cours","prete"]).count(),
    }
    return render(request, "labo/dashboard.html", {"demandes": demandes, "stats": stats, "filtre": filtre})


@laboratoire_required
def labo_resultat(request, demande_id):
    demande = get_object_or_404(DemandeAnalyse, id=demande_id)
    if demande.statut == "payee":
        demande.statut = "en_cours"; demande.save()
    if request.method == "POST":
        demande.resultat   = request.POST.get("resultat", "")
        demande.notes_labo = request.POST.get("notes_labo", "")
        demande.statut     = "prete"; demande.save()
        journaliser(request, 'modification', 'DemandeAnalyse',
            f"نتيجة تحليل {demande.analyse.nom} للمريض {demande.patient}", demande.id)
        # Notifier le patient
        creer_notification(demande.patient.utilisateur, 'analyse_prete',
            f"نتيجة تحليل {demande.analyse.nom} جاهزة",
            f"يمكنك الآن الاطلاع على نتيجة تحليل {demande.analyse.nom}",
            lien='/تحاليل/')
        messages.success(request,
            f"✅ تم حفظ نتيجة {demande.analyse.nom} — مرئية الآن للطبيب {demande.medecin}")
        return redirect("labo_dashboard")
    return render(request, "labo/resultat.html", {"demande": demande})


@laboratoire_required
def labo_modifier_patient(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    if request.method == "POST":
        patient.utilisateur.first_name = request.POST.get("prenom", patient.utilisateur.first_name)
        patient.utilisateur.last_name  = request.POST.get("nom",    patient.utilisateur.last_name)
        patient.utilisateur.email      = request.POST.get("email",  patient.utilisateur.email)
        patient.utilisateur.save()
        patient.telephone = request.POST.get("telephone", patient.telephone)
        patient.adresse   = request.POST.get("adresse", patient.adresse)
        patient.genre     = request.POST.get("genre", patient.genre)
        patient.nni       = request.POST.get("nni", patient.nni)
        dn = request.POST.get("date_naissance", "")
        if dn: patient.date_naissance = dn
        patient.save()
        messages.success(request, "تم تحديث بيانات المريض ✔")
        return redirect("labo_dashboard")
    return render(request, "labo/patient.html", {"patient": patient})


# MEDECIN
@medecin_required
def medecin_dashboard(request):
    """
    Tableau de bord médecin — utilise get_connected_medecin() pour résoudre
    le compte connecté via lien direct ou AdminClinique.
    Affiche les analyses dès leur paiement à la réception (statut=payee/en_cours/prete)
    """
    medecin = get_connected_medecin(request.user)
    if not medecin:
        messages.error(request, "لم يُعثر على ملف الطبيب — يرجى مراجعة الإعدادات")
        return redirect("accueil")

    today = datetime.date.today()
    rdvs = RendezVous.objects.filter(medecin=medecin).select_related("patient").order_by("-date", "-heure")
    rdvs_today = rdvs.filter(date=today, statut__in=["attente", "confirme"])
    patient_ids = rdvs.values_list("patient", flat=True).distinct()
    patients = Patient.objects.filter(utilisateur_id__in=patient_ids).select_related("utilisateur")

    # Toutes les analyses pour ce médecin dès paiement à la réception
    demandes = DemandeAnalyse.objects.filter(
        medecin=medecin, statut__in=["payee", "en_cours", "prete"]
    ).select_related("patient__utilisateur", "analyse").order_by("-cree_le")

    stats = {
        "rdv_total":          rdvs.count(),
        "rdv_today":          rdvs_today.count(),
        "patients_total":     patients.count(),
        "analyses_nouvelles": demandes.filter(statut="payee").count(),
        "analyses_en_cours":  demandes.filter(statut="en_cours").count(),
        "analyses_pretes":    demandes.filter(statut="prete").count(),
    }
    return render(request, "medecin/dashboard.html", {
        "medecin": medecin, "rdvs": rdvs[:10], "rdvs_today": rdvs_today,
        "patients": patients[:10], "demandes": demandes[:15],
        "stats": stats, "today": today,
        "nb_nouvelles": stats["analyses_nouvelles"],
    })


@medecin_required
def medecin_analyses(request, medecin_id):
    medecin = get_object_or_404(Medecin, id=medecin_id)
    filtre  = request.GET.get("statut", "")
    demandes = DemandeAnalyse.objects.filter(
        medecin=medecin, statut__in=["payee", "en_cours", "prete"]
    ).select_related("patient__utilisateur", "analyse").order_by("-cree_le")
    if filtre:
        demandes = demandes.filter(statut=filtre)
    return render(request, "medecin/analyses.html", {
        "medecin": medecin, "demandes": demandes, "filtre": filtre
    })


# ── MEDECIN : notes + ordonnance ──────────────────────────────────────────

@medecin_required
def medecin_rdv_notes(request, rdv_id):
    """Médecin ajoute notes rapides + crée/modifie une ordonnance sur un RDV."""
    rdv = get_object_or_404(RendezVous, id=rdv_id)
    medecin = get_connected_medecin(request.user)
    if not medecin or rdv.medecin != medecin:
        messages.error(request, "لا يمكنك الوصول إلى هذا الموعد")
        return redirect("medecin_dashboard")
    patient_profile = getattr(rdv.patient, 'profil', None)

    ordonnance = getattr(rdv, 'ordonnance', None)

    if request.method == "POST":
        action = request.POST.get("action", "notes")
        if action == "notes":
            if patient_profile and not can_manage_patient_dossier(request.user, patient_profile, 'note'):
                messages.error(request, 'ليست لديك صلاحية إضافة ملاحظات لهذا الملف')
            else:
                rdv.notes = request.POST.get("notes", rdv.notes)
                rdv.save(update_fields=['notes'])
                messages.success(request, "تم حفظ الملاحظات ✔")
        elif action == "ordonnance":
            if patient_profile and not can_manage_patient_dossier(request.user, patient_profile, 'ordonnance'):
                messages.error(request, 'ليست لديك صلاحية إنشاء وصفة لهذا الملف')
                return redirect("medecin_rdv_notes", rdv_id=rdv.id)
            diag  = request.POST.get("diagnostic", "").strip()
            presc = request.POST.get("prescription", "").strip()
            notes_m = request.POST.get("notes_medecin", "").strip()
            if not diag or not presc:
                messages.error(request, "يرجى ملء التشخيص والوصفة")
            else:
                patient_obj = None
                try:
                    patient_obj = rdv.patient.profil
                except Exception:
                    pass
                if patient_obj:
                    if ordonnance:
                        ordonnance.diagnostic    = diag
                        ordonnance.prescription  = presc
                        ordonnance.notes_medecin = notes_m
                        ordonnance.save()
                    else:
                        ordonnance = Ordonnance.objects.create(
                            rdv=rdv, medecin=medecin, patient=patient_obj,
                            diagnostic=diag, prescription=presc, notes_medecin=notes_m
                        )
                    # Marquer RDV comme terminé
                    if rdv.statut not in ["annule", "termine"]:
                        rdv.statut = "termine"
                        rdv.save(update_fields=['statut'])
                    journaliser(request, 'creation', 'Ordonnance',
                        f"وصفة طبية للمريض {patient_obj} من {medecin}", ordonnance.id)
                    creer_notification(rdv.patient, 'ordonnance',
                        f"وصفة طبية جديدة من {medecin}",
                        f"التشخيص: {diag[:80]}",
                        lien='/تاريخي/')
                    messages.success(request, "تم حفظ الوصفة الطبية ✔")
                else:
                    messages.error(request, "لا يمكن إيجاد ملف المريض")
        return redirect("medecin_rdv_notes", rdv_id=rdv.id)

    return render(request, "medecin/rdv_notes.html", {
        "rdv": rdv, "medecin": medecin, "ordonnance": ordonnance
    })


@medecin_required
def medecin_ordonnances(request):
    """Liste des ordonnances du médecin connecté."""
    medecin = get_connected_medecin(request.user)
    if not medecin:
        return redirect("medecin_dashboard")
    ordonnances = Ordonnance.objects.filter(medecin=medecin).select_related(
        "patient__utilisateur", "rdv"
    ).order_by("-cree_le")
    return render(request, "medecin/ordonnances.html", {
        "medecin": medecin, "ordonnances": ordonnances
    })


# ── RECEPTION : liste d'attente ───────────────────────────────────────────

@reception_required
def reception_liste_attente(request):
    filtre = request.GET.get("statut", "en_attente")
    qs = ListeAttente.objects.select_related(
        "patient__utilisateur", "medecin__specialite"
    ).all()
    if filtre:
        qs = qs.filter(statut=filtre)
    stats = {
        "total":    ListeAttente.objects.count(),
        "attente":  ListeAttente.objects.filter(statut="en_attente").count(),
        "converti": ListeAttente.objects.filter(statut="converti").count(),
        "annule":   ListeAttente.objects.filter(statut="annule").count(),
    }
    return render(request, "reception/liste_attente.html", {
        "entrees": qs, "filtre": filtre, "stats": stats
    })


@reception_required
def reception_liste_attente_ajouter(request):
    patients    = Patient.objects.all().select_related("utilisateur").order_by("utilisateur__last_name")
    medecins    = Medecin.objects.filter(disponible=True).select_related("specialite").order_by("nom")
    if request.method == "POST":
        pat_id   = request.POST.get("patient")
        med_id   = request.POST.get("medecin")
        date_str = request.POST.get("date_souhaitee")
        notes    = request.POST.get("notes", "")
        if not pat_id or not med_id or not date_str:
            messages.error(request, "يرجى ملء جميع الحقول")
        else:
            patient = get_object_or_404(Patient, pk=pat_id)
            medecin = get_object_or_404(Medecin, pk=med_id)
            ListeAttente.objects.create(
                patient=patient, medecin=medecin,
                date_souhaitee=date_str, notes=notes
            )
            messages.success(request, f"تمت إضافة {patient} إلى قائمة الانتظار ✅")
            return redirect("reception_liste_attente")
    return render(request, "reception/liste_attente_ajouter.html", {
        "patients": patients, "medecins": medecins
    })


@reception_required
def reception_liste_attente_convertir(request, pk):
    """Convertit une entrée liste d'attente en rendez-vous confirmé."""
    entree = get_object_or_404(ListeAttente, pk=pk)
    if request.method == "POST":
        heure_str = request.POST.get("heure")
        date_str  = request.POST.get("date", str(entree.date_souhaitee))
        service_id = request.POST.get("service")
        if not heure_str or not service_id:
            messages.error(request, "يرجى تحديد الوقت والخدمة")
            return redirect("reception_liste_attente")
        service_obj = get_object_or_404(Service, pk=service_id, actif=True)
        if not MedecinService.objects.filter(medecin=entree.medecin, service=service_obj, actif=True).exists():
            messages.error(request, "هذا الطبيب غير مخول لهذه الخدمة")
            return redirect("reception_liste_attente")
        try:
            RendezVous.objects.create(
                patient=entree.patient.utilisateur,
                medecin=entree.medecin,
                service=service_obj,
                date=date_str,
                heure=heure_str,
                motif=entree.notes or "تحويل من قائمة الانتظار",
                statut="confirme"
            )
        except Exception as exc:
            messages.error(request, f"تعذر إنشاء الموعد: {exc}")
            return redirect("reception_liste_attente")
        entree.statut = "converti"; entree.save()
        messages.success(request, f"تم تحويل {entree.patient} إلى موعد مؤكد ✅")
    return redirect("reception_liste_attente")


@reception_required
def reception_liste_attente_annuler(request, pk):
    entree = get_object_or_404(ListeAttente, pk=pk)
    entree.statut = "annule"; entree.save()
    messages.info(request, "تم إلغاء إدخال قائمة الانتظار")
    return redirect("reception_liste_attente")


# ── RECEPTION : gestion des services ─────────────────────────────────────

@reception_required
def reception_service_modifier(request, pk):
    ap = get_admin_profil(request.user)
    if not ap or ap.role != "admin":
        messages.error(request, "هذه الصفحة للمدراء فقط")
        return redirect("reception_services")
    service = get_object_or_404(Service, pk=pk)
    if request.method == "POST":
        service.nom         = request.POST.get("nom", service.nom).strip()
        service.description = request.POST.get("description", service.description).strip()
        service.prix        = request.POST.get("prix", service.prix)
        service.duree       = request.POST.get("duree", service.duree)
        service.icone       = request.POST.get("icone", service.icone).strip()
        service.save()
        messages.success(request, f"تم تحديث خدمة «{service.nom}» ✔")
        return redirect("reception_services")
    return render(request, "reception/service_modifier.html", {"service": service})


# ── RECEPTION : toggle actif membre d'équipe ──────────────────────────────

@reception_required
def reception_equipe_toggle(request, pk):
    ap = get_admin_profil(request.user)
    if not ap or ap.role != "admin":
        messages.error(request, "للمدراء فقط")
        return redirect("reception_equipe")
    membre = get_object_or_404(AdminClinique, pk=pk)
    membre.actif = not membre.actif; membre.save()
    messages.success(request, f"{'تم تفعيل' if membre.actif else 'تم تعطيل'} حساب {membre.nom}")
    return redirect("reception_equipe")


# ── IMPRESSION ORDONNANCE ─────────────────────────────────────────────────

@medecin_required
def medecin_ordonnance_print(request, ordonnance_id):
    o = get_object_or_404(Ordonnance, id=ordonnance_id)
    medecin = get_connected_medecin(request.user)
    if not medecin or o.medecin != medecin:
        messages.error(request, "غير مصرح لك")
        return redirect("medecin_ordonnances")
    return render(request, "medecin/ordonnance_print.html", {"o": o})


# ── TRANSFERT PATIENT ─────────────────────────────────────────────────────

@medecin_required
def medecin_transfert(request, rdv_id):
    rdv = get_object_or_404(RendezVous, id=rdv_id)
    medecin = get_connected_medecin(request.user)
    if not medecin or rdv.medecin != medecin:
        messages.error(request, "غير مصرح لك")
        return redirect("medecin_dashboard")

    if request.method == "POST":
        new_med_id = request.POST.get("nouveau_medecin")
        motif_tr   = request.POST.get("motif_transfert", "").strip()
        if not new_med_id:
            messages.error(request, "يرجى اختيار الطبيب")
        else:
            nouveau   = get_object_or_404(Medecin, id=new_med_id)
            date_str  = request.POST.get("date", str(datetime.date.today()))
            heure_str = request.POST.get("heure", "09:00")
            if not rdv.service_id:
                messages.error(request, 'لا يمكن تحويل الموعد بدون خدمة مرتبطة')
                return redirect('medecin_transfert', rdv_id=rdv.id)
            if not MedecinService.objects.filter(medecin=nouveau, service=rdv.service, actif=True).exists():
                messages.error(request, 'الطبيب الجديد غير مخول لهذه الخدمة')
                return redirect('medecin_transfert', rdv_id=rdv.id)
            try:
                RendezVous.objects.create(
                    patient=rdv.patient,
                    medecin=nouveau,
                    service=rdv.service,
                    date=date_str,
                    heure=heure_str,
                    motif=f"تحويل من {medecin} — {motif_tr}",
                    statut="confirme",
                )
            except Exception as exc:
                messages.error(request, f'تعذر إنشاء الموعد الجديد: {exc}')
                return redirect('medecin_transfert', rdv_id=rdv.id)
            rdv.statut = "termine"
            rdv.notes  = (rdv.notes or "") + f"\n[تحويل إلى {nouveau} بتاريخ {date_str}]"
            rdv.save(update_fields=['statut', 'notes'])
            journaliser(request, 'transfert', 'RendezVous',
                f"تحويل المريض {rdv.patient.get_full_name()} من {medecin} إلى {nouveau}", rdv.id)
            creer_notification(rdv.patient, 'transfert',
                f"تم تحويلك إلى {nouveau}",
                f"قام {medecin} بتحويلك إلى {nouveau} — موعد جديد يوم {date_str} الساعة {heure_str}. السبب: {motif_tr or 'غير محدد'}",
                lien='/مواعيدي/')
            messages.success(request,
                f"تم تحويل المريض إلى {nouveau} ✅ — موعد جديد يوم {date_str}")
            return redirect("medecin_dashboard")

    autres_medecins = Medecin.objects.filter(disponible=True).exclude(id=medecin.id)
    return render(request, "medecin/transfert.html", {
        "rdv": rdv, "medecin": medecin, "autres_medecins": autres_medecins
    })


# ── DOSSIER PATIENT (médecin) ─────────────────────────────────────────────

@medecin_required
def medecin_patient_dossier(request, patient_id):
    patient  = get_object_or_404(Patient, id=patient_id)
    medecin = get_connected_medecin(request.user)
    if not medecin:
        return redirect("medecin_dashboard")
    has_direct_access = RendezVous.objects.filter(patient=patient.utilisateur, medecin=medecin).exists()
    share_access = get_active_dossier_share(patient, medecin)
    has_shared_access = bool(share_access)
    if not (has_direct_access or has_shared_access):
        messages.error(request, "لا يمكنك فتح ملف هذا المريض")
        return redirect("medecin_dashboard")

    rdvs = RendezVous.objects.filter(patient=patient.utilisateur).order_by("-date", "-heure")
    ordonnances = Ordonnance.objects.filter(patient=patient).order_by("-cree_le")
    demandes = DemandeAnalyse.objects.filter(patient=patient).select_related("analyse", "medecin").order_by("-cree_le")
    if has_direct_access and not has_shared_access:
        rdvs = rdvs.filter(medecin=medecin)
        ordonnances = ordonnances.filter(medecin=medecin)
        demandes = demandes.filter(medecin=medecin)

    pieces_medicales = PieceMedicale.objects.filter(patient=patient, est_active=True).select_related("cree_par", "rendez_vous").order_by("-cree_le")
    partages = DossierPartage.objects.filter(patient=patient, actif=True).select_related('medecin_source', 'medecin_cible')
    return render(request, "medecin/patient_dossier.html", {
        "patient": patient, "medecin": medecin,
        "rdvs": rdvs, "ordonnances": ordonnances, "demandes": demandes,
        "pieces_medicales": pieces_medicales,
        "partages": partages,
        "has_shared_access": has_shared_access,
        "share_access": share_access,
        "can_upload_files": can_manage_patient_dossier(request.user, patient, 'upload'),
        "can_add_note": can_manage_patient_dossier(request.user, patient, 'note'),
        "can_create_ordonnance": can_manage_patient_dossier(request.user, patient, 'ordonnance'),
    })


@login_required
def patient_liste_attente(request):
    patient = request.user.profil
    medecins = Medecin.objects.filter(disponible=True).select_related('specialite').order_by('nom')
    entrees = ListeAttente.objects.filter(patient=patient).select_related('medecin__specialite').order_by('-cree_le')

    if request.method == 'POST':
        med_id = request.POST.get('medecin')
        date_str = request.POST.get('date_souhaitee')
        notes = request.POST.get('notes', '').strip()
        if not med_id or not date_str:
            messages.error(request, 'يرجى اختيار الطبيب والتاريخ')
        else:
            medecin = get_object_or_404(Medecin, id=med_id, disponible=True)
            deja = ListeAttente.objects.filter(patient=patient, medecin=medecin, date_souhaitee=date_str, statut='en_attente').exists()
            if deja:
                messages.error(request, 'أنت مسجل بالفعل في قائمة الانتظار لهذا التاريخ')
            else:
                ListeAttente.objects.create(patient=patient, medecin=medecin, date_souhaitee=date_str, notes=notes)
                journaliser(request, 'creation', 'ListeAttente', f'إضافة {patient} إلى قائمة الانتظار مع {medecin}')
                messages.success(request, 'تمت إضافتك إلى قائمة الانتظار ✅')
                return redirect('patient_liste_attente')

    return render(request, 'attente/mes_attentes.html', {
        'medecins': medecins,
        'entrees': entrees,
    })


@login_required
def patient_liste_attente_annuler(request, pk):
    entree = get_object_or_404(ListeAttente, pk=pk, patient=request.user.profil)
    if entree.statut == 'en_attente':
        entree.statut = 'annule'
        entree.save(update_fields=['statut'])
        journaliser(request, 'annulation', 'ListeAttente', f'إلغاء انتظار #{entree.id}', entree.id)
        messages.success(request, 'تم إلغاء طلب الانتظار')
    return redirect('patient_liste_attente')


@login_required
def patient_paiements(request):
    patient = request.user.profil
    factures_consult = FactureConsultation.objects.filter(patient=patient).select_related('medecin', 'rdv', 'paiement').order_by('-cree_le')
    factures_analyse = FactureAnalyse.objects.filter(patient=patient).select_related('demande__analyse', 'paiement').order_by('-cree_le')
    total_impaye = sum([f.montant for f in factures_consult if f.statut == 'non_payee']) + sum([f.montant for f in factures_analyse if f.statut == 'non_payee'])
    return render(request, 'paiements/statut.html', {
        'factures_consult': factures_consult,
        'factures_analyse': factures_analyse,
        'total_impaye': total_impaye,
    })


@medecin_required
def medecin_profil(request):
    ap = get_admin_profil(request.user)
    medecin = get_connected_medecin(request.user)
    if not ap or not medecin:
        messages.error(request, 'تعذر إيجاد ملف الطبيب')
        return redirect('medecin_dashboard')

    if request.method == 'POST':
        ap.nom = request.POST.get('nom', ap.nom).strip()
        ap.telephone = request.POST.get('telephone', ap.telephone).strip()
        medecin.telephone = request.POST.get('telephone_professionnel', medecin.telephone).strip()
        medecin.email = request.POST.get('email', medecin.email).strip()
        medecin.bio = request.POST.get('bio', medecin.bio).strip()
        medecin.annees_experience = request.POST.get('annees_experience', medecin.annees_experience) or medecin.annees_experience
        ap.save(); medecin.save()
        journaliser(request, 'modification', 'Medecin', f'تحديث الملف الشخصي للطبيب {medecin}', medecin.id)
        messages.success(request, 'تم تحديث المعلومات الشخصية ✔')
        return redirect('medecin_profil')

    return render(request, 'medecin/profil.html', {'admin_obj': ap, 'medecin': medecin})


@reception_required
def reception_pression_travail(request):
    today = datetime.date.today()
    medecins = Medecin.objects.filter(disponible=True).select_related('specialite').order_by('nom')
    lignes = []
    for medecin in medecins:
        actifs = RendezVous.objects.filter(medecin=medecin, date=today, statut__in=['attente', 'confirme']).count()
        attente = ListeAttente.objects.filter(medecin=medecin, date_souhaitee=today, statut='en_attente').count()
        total_slots = compute_daily_capacity(medecin, today)
        saturation = round((actifs / total_slots) * 100, 1) if total_slots else 0
        if saturation >= 100:
            niveau = 'حرج'
        elif saturation >= 75:
            niveau = 'مرتفع'
        elif saturation >= 40:
            niveau = 'متوسط'
        else:
            niveau = 'منخفض'
        lignes.append({
            'medecin': medecin,
            'rdv': actifs,
            'attente': attente,
            'remaining': max(total_slots - actifs, 0),
            'saturation': saturation,
            'niveau': niveau,
        })

    return render(request, 'reception/pression_travail.html', {
        'today': today,
        'lignes': lignes,
        'total_rdv': sum(l['rdv'] for l in lignes),
        'total_attente': sum(l['attente'] for l in lignes),
    })


@medecin_required
def medecin_partager_dossier(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    medecin = get_connected_medecin(request.user)
    if not medecin or not RendezVous.objects.filter(patient=patient.utilisateur, medecin=medecin).exists():
        messages.error(request, 'لا يمكنك مشاركة ملف هذا المريض')
        return redirect('medecin_dashboard')

    autres_medecins = Medecin.objects.filter(disponible=True).exclude(id=medecin.id).order_by('nom')
    if request.method == 'POST':
        cible_id = request.POST.get('medecin_cible')
        date_fin = request.POST.get('date_fin') or None
        note = request.POST.get('note', '').strip()
        if not cible_id:
            messages.error(request, 'يرجى اختيار الطبيب المستفيد')
        else:
            cible = get_object_or_404(Medecin, id=cible_id)
            lecture_seule = request.POST.get('lecture_seule') == 'on'
            peut_ajouter_notes = request.POST.get('peut_ajouter_notes') == 'on'
            peut_ajouter_fichiers = request.POST.get('peut_ajouter_fichiers') == 'on'
            peut_creer_ordonnance = request.POST.get('peut_creer_ordonnance') == 'on'
            if lecture_seule:
                peut_ajouter_notes = False
                peut_ajouter_fichiers = False
                peut_creer_ordonnance = False
            DossierPartage.objects.create(patient=patient, medecin_source=medecin, medecin_cible=cible, cree_par=request.user, date_fin=date_fin, note=note, lecture_seule=lecture_seule, peut_ajouter_notes=peut_ajouter_notes, peut_ajouter_fichiers=peut_ajouter_fichiers, peut_creer_ordonnance=peut_creer_ordonnance)
            journaliser(request, 'transfert', 'DossierPartage', f'مشاركة ملف {patient} مع {cible}')
            messages.success(request, 'تمت مشاركة الملف الطبي بنجاح ✅')
            return redirect('medecin_patient_dossier', patient_id=patient.id)

    return render(request, 'medecin/partage_dossier.html', {
        'patient': patient,
        'medecin': medecin,
        'autres_medecins': autres_medecins,
    })


# ── ADMIN : AJOUTER / MODIFIER MÉDECIN ───────────────────────────────────

@reception_required
def reception_medecin_ajouter(request):
    ap = get_admin_profil(request.user)
    if not ap or ap.role != "admin":
        messages.error(request, "للمدراء فقط")
        return redirect("reception_medecins")
    specialites = Specialite.objects.all()
    if request.method == "POST":
        nom   = request.POST.get("nom", "").strip()
        spec  = request.POST.get("specialite") or None
        tel   = request.POST.get("telephone", "").strip()
        email = request.POST.get("email", "").strip()
        bio   = request.POST.get("bio", "").strip()
        exp   = request.POST.get("annees_experience", 1)
        dispo = request.POST.get("disponible") == "on"
        if not nom:
            messages.error(request, "الاسم مطلوب")
        else:
            medecin = Medecin.objects.create(
                nom=nom, specialite_id=spec, telephone=tel,
                email=email, bio=bio, annees_experience=exp, disponible=dispo
            )
            if tel:
                membre, created = AdminClinique.objects.get_or_create(telephone=tel, defaults={'nom': nom, 'role': 'medecin', 'actif': True})
                if not created:
                    membre.nom = nom
                    membre.role = 'medecin'
                    membre.actif = True
                    membre.save()
                user = create_staff_user_for_admin(membre)
                medecin.utilisateur = user
                medecin.save(update_fields=['utilisateur'])
            service_ids = request.POST.getlist('services_autorises')
            for idx, sid in enumerate(service_ids):
                if sid:
                    MedecinService.objects.get_or_create(medecin=medecin, service_id=sid, defaults={'actif': True, 'priorite': idx})
            messages.success(request, f"تمت إضافة {nom} ✅")
            return redirect("reception_medecins")
    return render(request, "reception/medecin_form.html", {
        "specialites": specialites, "services": Service.objects.filter(actif=True).order_by('nom'), "selected_service_ids": [], "action": "ajouter", "medecin": None
    })


@reception_required
def reception_medecin_modifier(request, pk):
    ap = get_admin_profil(request.user)
    if not ap or ap.role != "admin":
        messages.error(request, "للمدراء فقط")
        return redirect("reception_medecins")
    medecin     = get_object_or_404(Medecin, pk=pk)
    specialites = Specialite.objects.all()
    if request.method == "POST":
        medecin.nom               = request.POST.get("nom", medecin.nom).strip()
        medecin.specialite_id     = request.POST.get("specialite") or None
        medecin.telephone         = request.POST.get("telephone", medecin.telephone).strip()
        medecin.email             = request.POST.get("email", medecin.email).strip()
        medecin.bio               = request.POST.get("bio", medecin.bio).strip()
        medecin.annees_experience = request.POST.get("annees_experience", medecin.annees_experience)
        medecin.disponible        = request.POST.get("disponible") == "on"
        medecin.save()
        if medecin.telephone:
            membre = AdminClinique.objects.filter(telephone=medecin.telephone).first()
            if membre:
                membre.nom = medecin.nom
                membre.role = 'medecin'
                membre.actif = True
                if not membre.utilisateur_id:
                    create_staff_user_for_admin(membre)
                membre.save()
                if membre.utilisateur_id and medecin.utilisateur_id != membre.utilisateur_id:
                    medecin.utilisateur = membre.utilisateur
                    medecin.save(update_fields=['utilisateur'])
        service_ids = [int(s) for s in request.POST.getlist('services_autorises') if s]
        MedecinService.objects.filter(medecin=medecin).exclude(service_id__in=service_ids).update(actif=False)
        for idx, sid in enumerate(service_ids):
            MedecinService.objects.update_or_create(medecin=medecin, service_id=sid, defaults={'actif': True, 'priorite': idx})
        messages.success(request, f"تم تحديث بيانات {medecin} ✔")
        return redirect("reception_medecins")
    return render(request, "reception/medecin_form.html", {
        "specialites": specialites, "services": Service.objects.filter(actif=True).order_by('nom'), "selected_service_ids": list(MedecinService.objects.filter(medecin=medecin, actif=True).values_list('service_id', flat=True)), "action": "modifier", "medecin": medecin
    })


# ── ADMIN : AJOUTER SERVICE ───────────────────────────────────────────────

@reception_required
def reception_service_ajouter(request):
    ap = get_admin_profil(request.user)
    if not ap or ap.role != "admin":
        messages.error(request, "للمدراء فقط")
        return redirect("reception_services")
    if request.method == "POST":
        nom  = request.POST.get("nom", "").strip()
        desc = request.POST.get("description", "").strip()
        prix = request.POST.get("prix", 0)
        dur  = request.POST.get("duree", 30)
        icon = request.POST.get("icone", "fa-heartbeat").strip()
        if not nom:
            messages.error(request, "اسم الخدمة مطلوب")
        else:
            Service.objects.create(nom=nom, description=desc, prix=prix, duree=dur, icone=icon)
            messages.success(request, f"تمت إضافة الخدمة «{nom}» ✅")
            return redirect("reception_services")
    return render(request, "reception/service_modifier.html", {"service": None})


# ── ADMIN : GESTION ANALYSES ──────────────────────────────────────────────

@reception_required
def reception_analyses(request):
    ap = get_admin_profil(request.user)
    if not ap or ap.role != "admin":
        messages.error(request, "للمدراء فقط")
        return redirect("reception_dashboard")
    analyses = Analyse.objects.all().order_by("nom")
    return render(request, "reception/analyses.html", {"analyses": analyses})


@reception_required
def reception_analyse_form(request, pk=None):
    ap = get_admin_profil(request.user)
    if not ap or ap.role != "admin":
        return redirect("reception_dashboard")
    analyse = get_object_or_404(Analyse, pk=pk) if pk else None
    if request.method == "POST":
        nom   = request.POST.get("nom", "").strip()
        desc  = request.POST.get("description", "").strip()
        prix  = request.POST.get("prix", 0)
        actif = request.POST.get("actif") == "on"
        if not nom:
            messages.error(request, "اسم التحليل مطلوب")
        else:
            if analyse:
                analyse.nom = nom; analyse.description = desc
                analyse.prix = prix; analyse.actif = actif
                analyse.save()
                messages.success(request, f"تم تحديث «{nom}» ✔")
            else:
                Analyse.objects.create(nom=nom, description=desc, prix=prix, actif=actif)
                messages.success(request, f"تمت إضافة التحليل «{nom}» ✅")
            return redirect("reception_analyses")
    return render(request, "reception/analyse_form.html", {"analyse": analyse})


@reception_required
def reception_analyse_toggle(request, pk):
    ap = get_admin_profil(request.user)
    if not ap or ap.role != "admin":
        return redirect("reception_analyses")
    a = get_object_or_404(Analyse, pk=pk)
    a.actif = not a.actif; a.save()
    messages.success(request, f"{'تم تفعيل' if a.actif else 'تم إيقاف'} «{a.nom}»")
    return redirect("reception_analyses")


# ── RECEPTION : stats revenus (AJAX) ─────────────────────────────────────

@reception_required
def reception_stats_revenus(request):
    from django.db.models import Sum
    revenus_analyses = PaiementAnalyse.objects.aggregate(
        total=Sum("montant"))["total"] or 0
    revenus_consult  = PaiementConsultation.objects.aggregate(
        total=Sum("montant"))["total"] or 0
    return JsonResponse({
        "analyses":      float(revenus_analyses),
        "consultations": float(revenus_consult),
        "total":         float(revenus_analyses + revenus_consult),
        "factures_non_payees": FactureAnalyse.objects.filter(statut="non_payee").count() +
                               FactureConsultation.objects.filter(statut="non_payee").count(),
    })


# ══════════════════════════════════════════════════════════════════
# NOUVELLES FONCTIONNALITÉS V2
# ══════════════════════════════════════════════════════════════════

# ── 1. NOTIFICATIONS ─────────────────────────────────────────────

@login_required
def mes_notifications(request):
    notifs = Notification.objects.filter(utilisateur=request.user)
    nb_non_lues = notifs.filter(lue=False).count()
    notifs.filter(lue=False).update(lue=True)
    return render(request, 'notifications.html', {
        'notifications': notifs,
        'nb_non_lues': nb_non_lues,
    })


@login_required
def notif_marquer_lue(request, pk):
    notif = get_object_or_404(Notification, pk=pk, utilisateur=request.user)
    notif.lue = True; notif.save()
    return redirect(notif.lien or 'mes_notifications')


@login_required
def notif_supprimer(request, pk):
    notif = get_object_or_404(Notification, pk=pk, utilisateur=request.user)
    notif.delete()
    return redirect('mes_notifications')


def notif_count_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0})
    count = Notification.objects.filter(utilisateur=request.user, lue=False).count()
    return JsonResponse({'count': count})


# ── 2. HISTORIQUE DES VISITES (patient) ──────────────────────────

@login_required
def historique_visites(request):
    rdvs = RendezVous.objects.filter(
        patient=request.user
    ).select_related('medecin', 'medecin__specialite').order_by('-date', '-heure')

    # Filtres
    statut = request.GET.get('statut', '')
    medecin_id = request.GET.get('medecin', '')
    if statut:
        rdvs = rdvs.filter(statut=statut)
    if medecin_id:
        rdvs = rdvs.filter(medecin_id=medecin_id)

    medecins_vus = Medecin.objects.filter(
        rendez_vous__patient=request.user
    ).distinct()

    stats = {
        'total':    RendezVous.objects.filter(patient=request.user).count(),
        'termine':  RendezVous.objects.filter(patient=request.user, statut='termine').count(),
        'annule':   RendezVous.objects.filter(patient=request.user, statut='annule').count(),
        'a_venir':  RendezVous.objects.filter(
            patient=request.user, statut__in=['attente','confirme'],
            date__gte=datetime.date.today()
        ).count(),
    }

    ordonnances = Ordonnance.objects.filter(
        patient=request.user.profil
    ).select_related('medecin', 'rdv').order_by('-cree_le')

    return render(request, 'historique_visites.html', {
        'rdvs': rdvs,
        'stats': stats,
        'medecins_vus': medecins_vus,
        'filtre_statut': statut,
        'filtre_medecin': medecin_id,
        'ordonnances': ordonnances,
    })


# ── 3. PLANNING MÉDECIN ───────────────────────────────────────────

@medecin_required
def medecin_planning(request):
    medecin = get_connected_medecin(request.user)
    if not medecin:
        messages.error(request, "لا يوجد ملف طبيب مرتبط بهذا الحساب")
        return redirect('accueil')

    JOURS = ['lun','mar','mer','jeu','ven','sam','dim']
    JOURS_AR = {'lun':'الاثنين','mar':'الثلاثاء','mer':'الأربعاء',
                'jeu':'الخميس','ven':'الجمعة','sam':'السبت','dim':'الأحد'}

    if request.method == 'POST':
        journaliser(request, 'modification', 'PlanningSemaine',
            f"تعديل جدول عمل {medecin}")
        for jour in JOURS:
            actif = request.POST.get(f'actif_{jour}') == 'on'
            debut = request.POST.get(f'debut_{jour}', '08:00')
            fin   = request.POST.get(f'fin_{jour}', '17:00')
            duree = int(request.POST.get(f'duree_{jour}', 30))
            PlanningSemaine.objects.update_or_create(
                medecin=medecin, jour=jour,
                defaults={'heure_debut': debut, 'heure_fin': fin,
                          'actif': actif, 'duree_rdv': duree}
            )
        messages.success(request, "تم حفظ جدول العمل ✔")
        return redirect('medecin_planning')

    planning_dict = {p.jour: p for p in PlanningSemaine.objects.filter(medecin=medecin)}
    planning = []
    for jour in JOURS:
        p = planning_dict.get(jour)
        planning.append({
            'jour': jour,
            'nom': JOURS_AR[jour],
            'actif': p.actif if p else False,
            'debut': p.heure_debut.strftime('%H:%M') if p else '08:00',
            'fin':   p.heure_fin.strftime('%H:%M') if p else '17:00',
            'duree': p.duree_rdv if p else 30,
        })

    # RDV de la semaine en cours
    today = datetime.date.today()
    debut_semaine = today - datetime.timedelta(days=today.weekday())
    fin_semaine = debut_semaine + datetime.timedelta(days=6)
    rdvs_semaine = RendezVous.objects.filter(
        medecin=medecin,
        date__range=[debut_semaine, fin_semaine],
        statut__in=['attente','confirme']
    ).select_related('patient').order_by('date','heure')

    return render(request, 'medecin/planning.html', {
        'medecin': medecin,
        'planning': planning,
        'rdvs_semaine': rdvs_semaine,
        'debut_semaine': debut_semaine,
        'fin_semaine': fin_semaine,
    })


# ── 4. JOURNAL D'AUDIT (admin) ────────────────────────────────────

@reception_required
def journal_audit(request):
    ap = get_admin_profil(request.user)
    if not ap or ap.role != 'admin':
        messages.error(request, "هذه الصفحة للمدير فقط")
        return redirect('reception_dashboard')

    logs = JournalAudit.objects.select_related('utilisateur').order_by('-cree_le')

    # Filtres
    action   = request.GET.get('action', '')
    modele   = request.GET.get('modele', '')
    username = request.GET.get('user', '')
    if action:
        logs = logs.filter(action=action)
    if modele:
        logs = logs.filter(modele__icontains=modele)
    if username:
        logs = logs.filter(utilisateur__username__icontains=username)

    logs = logs[:300]

    actions_dispo  = JournalAudit.objects.values_list('action', flat=True).distinct()
    modeles_dispo  = JournalAudit.objects.values_list('modele', flat=True).distinct()

    return render(request, 'reception/journal_audit.html', {
        'logs': logs,
        'actions_dispo': actions_dispo,
        'modeles_dispo': modeles_dispo,
        'filtre_action': action,
        'filtre_modele': modele,
        'filtre_user': username,
        'total': JournalAudit.objects.count(),
    })


@login_required
def mes_fichiers_medicaux(request):
    try:
        patient = request.user.profil
    except Exception:
        messages.error(request, "لا يوجد ملف مريض مرتبط بحسابك")
        return redirect("accueil")

    pieces = PieceMedicale.objects.filter(patient=patient, est_active=True).select_related('cree_par', 'rendez_vous')
    return render(request, 'fichiers/mes_fichiers.html', {
        'patient': patient,
        'pieces': pieces,
    })


@login_required
def medical_file_upload(request, patient_id=None):
    ap = get_admin_profil(request.user)
    if patient_id:
        patient = get_object_or_404(Patient.objects.select_related('utilisateur'), id=patient_id)
    else:
        try:
            patient = request.user.profil
        except Exception:
            messages.error(request, "الرجاء تحديد المريض")
            return redirect('accueil')

    is_staff_like = bool(ap and ap.role in ['admin', 'reception', 'laboratoire', 'medecin'])
    if not is_staff_like and patient.utilisateur_id != request.user.id:
        messages.error(request, "غير مصرح لك بإضافة ملف لهذا المريض")
        return redirect('accueil')
    if ap and ap.role == 'medecin' and not can_manage_patient_dossier(request.user, patient, 'upload'):
        messages.error(request, 'هذه المشاركة لا تسمح لك برفع ملفات لهذا المريض')
        return redirect('medecin_patient_dossier', patient_id=patient.id)

    medecin = get_connected_medecin(request.user)
    patient_rdvs = RendezVous.objects.filter(patient=patient.utilisateur).select_related('medecin').order_by('-date', '-heure')
    if medecin and (not ap or ap.role == 'medecin'):
        patient_rdvs = patient_rdvs.filter(medecin=medecin)

    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        type_piece = request.POST.get('type_piece', 'document')
        description = request.POST.get('description', '').strip()
        fichier = request.FILES.get('fichier')
        rdv_id = request.POST.get('rendez_vous')
        rdv = None
        if rdv_id:
            rdv = get_object_or_404(RendezVous, id=rdv_id, patient=patient.utilisateur)
            if medecin and (ap and ap.role == 'medecin') and rdv.medecin_id != medecin.id:
                messages.error(request, 'لا يمكنك ربط الملف بموعد لا يخصك')
                return redirect(request.path)

        if not titre or not fichier:
            messages.error(request, 'العنوان والملف مطلوبان')
        else:
            try:
                piece = PieceMedicale.objects.create(
                    patient=patient,
                    rendez_vous=rdv,
                    cree_par=request.user,
                    titre=titre,
                    type_piece=type_piece,
                    fichier=fichier,
                    description=description,
                    source_role=resolve_source_role(request.user),
                )
                PieceMedicaleAudit.objects.create(piece=piece, utilisateur=request.user, action='upload')
                journaliser(request, 'creation', 'PieceMedicale', f'إضافة ملف طبي للمريض {patient}', piece.id)
                messages.success(request, 'تم رفع الملف الطبي بنجاح ✅')
                if ap and ap.role == 'medecin':
                    return redirect('medecin_patient_dossier', patient_id=patient.id)
                if ap and ap.role in ['admin', 'reception', 'laboratoire']:
                    return redirect('medical_file_upload_for_patient', patient_id=patient.id)
                return redirect('mes_fichiers_medicaux')
            except Exception as exc:
                messages.error(request, f'تعذر رفع الملف: {exc}')

    return render(request, 'fichiers/upload.html', {
        'patient': patient,
        'rdvs': patient_rdvs[:50],
        'source_role': resolve_source_role(request.user),
    })


@login_required
def medical_file_download(request, pk):
    piece = get_object_or_404(PieceMedicale.objects.select_related('patient__utilisateur', 'rendez_vous', 'cree_par'), pk=pk, est_active=True)
    if not can_access_medical_file(request.user, piece):
        messages.error(request, 'غير مصرح لك بالوصول إلى هذا الملف')
        return redirect('accueil')

    if not piece.fichier:
        raise Http404

    PieceMedicaleAudit.objects.create(piece=piece, utilisateur=request.user, action='download')
    journaliser(request, 'modification', 'PieceMedicale', f'تحميل ملف طبي #{piece.id}', piece.id)

    file_path = piece.fichier.path
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or 'application/octet-stream'
    return FileResponse(open(file_path, 'rb'), content_type=content_type, filename=os.path.basename(piece.nom_original or piece.fichier.name))


@login_required
def medical_file_delete(request, pk):
    piece = get_object_or_404(PieceMedicale.objects.select_related('patient__utilisateur'), pk=pk, est_active=True)
    ap = get_admin_profil(request.user)
    allowed = False
    if piece.cree_par_id == request.user.id:
        allowed = True
    if ap and ap.role in ['admin', 'reception', 'laboratoire']:
        allowed = True
    medecin = get_connected_medecin(request.user)
    if medecin and piece.rendez_vous and piece.rendez_vous.medecin_id == medecin.id:
        allowed = True

    if not allowed:
        messages.error(request, 'لا يمكنك حذف هذا الملف')
        return redirect('accueil')

    if request.method == 'POST':
        piece.est_active = False
        piece.save(update_fields=['est_active', 'modifie_le'])
        PieceMedicaleAudit.objects.create(piece=piece, utilisateur=request.user, action='delete')
        journaliser(request, 'suppression', 'PieceMedicale', f'حذف منطقي لملف طبي #{piece.id}', piece.id)
        messages.success(request, 'تم حذف الملف الطبي')

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    if ap and ap.role == 'medecin':
        return redirect('medecin_patient_dossier', patient_id=piece.patient_id)
    return redirect('mes_fichiers_medicaux')


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN CLINIQUE — Dashboard dédié (séparé de l'admin Django)
# ═══════════════════════════════════════════════════════════════════════════

def admin_required(view_func):
    """Décorateur : réservé au rôle 'admin' de AdminClinique uniquement."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/connexion/?next=" + request.path)
        ap = get_admin_profil(request.user)
        if ap and ap.role == "admin" and ap.actif:
            return view_func(request, *args, **kwargs)
        messages.error(request, "هذه الصفحة مخصصة للمدير فقط")
        return redirect("accueil")
    return wrapper


def admin_setup(request):
    """
    Page de création du premier compte admin clinique.
    Accessible sans connexion UNIQUEMENT si aucun admin clinique n'existe encore.
    """
    if AdminClinique.objects.filter(role="admin").exists():
        messages.info(request, "يوجد مدير مسجل بالفعل — الرجاء تسجيل الدخول")
        return redirect("connexion")

    if request.method == "POST":
        nom       = request.POST.get("nom", "").strip()
        telephone = request.POST.get("telephone", "").strip()
        password  = request.POST.get("password", "").strip()
        confirm   = request.POST.get("password_confirm", "").strip()

        if not nom or not telephone or not password:
            messages.error(request, "جميع الحقول مطلوبة")
        elif password != confirm:
            messages.error(request, "كلمة المرور غير متطابقة")
        elif len(password) < 8:
            messages.error(request, "كلمة المرور يجب أن تكون 8 أحرف على الأقل")
        elif AdminClinique.objects.filter(telephone=telephone).exists():
            messages.error(request, "رقم الهاتف مستخدم مسبقاً")
        else:
            admin_obj = AdminClinique.objects.create(
                nom=nom, telephone=telephone, role="admin",
                actif=True, must_change_password=False
            )
            phone_norm = normalize_phone(telephone) or str(admin_obj.pk)
            username   = ensure_unique_username(f"admin_{phone_norm}")
            user = User.objects.create_user(
                username=username,
                first_name=nom,
                password=password,
                is_staff=True,
            )
            admin_obj.utilisateur = user
            admin_obj.save(update_fields=["utilisateur"])
            auth_user = authenticate(request, username=username, password=password)
            if auth_user:
                login(request, auth_user)
            journaliser(request, "creation", "AdminClinique",
                        f"إنشاء أول حساب مدير: {nom}", admin_obj.id)
            messages.success(request, f"مرحباً {nom} — تم إنشاء حساب المدير بنجاح")
            return redirect("admin_dashboard")

    return render(request, "admin/setup.html")


@admin_required
def admin_dashboard(request):
    """Tableau de bord principal de l'admin clinique."""
    today = datetime.date.today()
    stats = {
        "nb_patients":   Patient.objects.count(),
        "nb_medecins":   Medecin.objects.count(),
        "nb_medecins_actifs": Medecin.objects.filter(disponible=True).count(),
        "nb_staff":      AdminClinique.objects.exclude(role="admin").count(),
        "nb_services":   Service.objects.filter(actif=True).count(),
        "nb_analyses":   Analyse.objects.filter(actif=True).count(),
        "rdv_today":     RendezVous.objects.filter(date=today).count(),
        "rdv_mois":      RendezVous.objects.filter(
                             date__year=today.year, date__month=today.month).count(),
        "nb_admins":     AdminClinique.objects.filter(role="admin").count(),
    }
    # Revenus du mois
    from django.db.models import Sum
    rev_consult = PaiementConsultation.objects.filter(
        date_paiement__year=today.year, date_paiement__month=today.month
    ).aggregate(t=Sum("montant"))["t"] or 0
    rev_analyse = PaiementAnalyse.objects.filter(
        date_paiement__year=today.year, date_paiement__month=today.month
    ).aggregate(t=Sum("montant"))["t"] or 0
    stats["rev_consult"] = rev_consult
    stats["rev_analyse"] = rev_analyse
    stats["rev_total"]   = rev_consult + rev_analyse

    medecins     = Medecin.objects.select_related("specialite").order_by("nom")
    staff        = AdminClinique.objects.exclude(role="admin").order_by("role", "nom")
    services     = Service.objects.order_by("nom")
    analyses     = Analyse.objects.order_by("nom")
    specialites  = Specialite.objects.order_by("nom")
    recent_rdvs  = RendezVous.objects.filter(date=today).select_related(
                       "patient__profil", "medecin").order_by("heure")[:10]
    recent_audit = JournalAudit.objects.select_related("utilisateur").order_by("-cree_le")[:15]

    return render(request, "admin/dashboard.html", {
        "stats": stats, "today": today,
        "medecins": medecins, "staff": staff,
        "services": services, "analyses": analyses,
        "specialites": specialites,
        "recent_rdvs": recent_rdvs,
        "recent_audit": recent_audit,
    })


@admin_required
def admin_medecin_ajouter(request):
    specialites = Specialite.objects.all().order_by("nom")
    if request.method == "POST":
        nom            = request.POST.get("nom", "").strip()
        telephone      = request.POST.get("telephone", "").strip()
        email          = request.POST.get("email", "").strip()
        specialite_id  = request.POST.get("specialite")
        experience     = request.POST.get("annees_experience", 1)
        bio            = request.POST.get("bio", "").strip()

        if not nom or not telephone:
            messages.error(request, "الاسم ورقم الهاتف مطلوبان")
        else:
            spec = Specialite.objects.filter(pk=specialite_id).first() if specialite_id else None
            medecin = Medecin.objects.create(
                nom=nom, telephone=telephone, email=email,
                specialite=spec, annees_experience=int(experience or 1),
                bio=bio, disponible=True
            )
            # Créer un compte AdminClinique + User pour le médecin
            phone_norm = normalize_phone(telephone) or str(medecin.pk)
            username   = ensure_unique_username(f"dr_{phone_norm}")
            user = User.objects.create_user(
                username=username, first_name=nom, password=phone_norm, is_staff=False
            )
            admin_obj = AdminClinique.objects.create(
                utilisateur=user, nom=nom, telephone=telephone,
                role="medecin", actif=True, must_change_password=True
            )
            medecin.utilisateur = user
            medecin.save(update_fields=["utilisateur"])
            journaliser(request, "creation", "Medecin",
                        f"إضافة طبيب: {medecin}", medecin.id)
            messages.success(request,
                f"تمت إضافة {medecin} — كلمة المرور المؤقتة: {phone_norm}")
            return redirect("admin_dashboard")

    return render(request, "admin/medecin_form.html", {"specialites": specialites})


@admin_required
def admin_staff_ajouter(request):
    ROLES_STAFF = [("reception", "استقبال"), ("laboratoire", "مختبر")]
    if request.method == "POST":
        nom       = request.POST.get("nom", "").strip()
        telephone = request.POST.get("telephone", "").strip()
        role      = request.POST.get("role", "reception")

        if not nom or not telephone:
            messages.error(request, "الاسم ورقم الهاتف مطلوبان")
        elif role not in ["reception", "laboratoire"]:
            messages.error(request, "الدور غير صالح")
        elif AdminClinique.objects.filter(telephone=telephone).exists():
            messages.error(request, "رقم الهاتف مستخدم مسبقاً")
        else:
            membre = AdminClinique.objects.create(
                nom=nom, telephone=telephone, role=role,
                actif=True, must_change_password=True
            )
            create_staff_user_for_admin(membre)
            journaliser(request, "creation", "AdminClinique",
                        f"إضافة موظف: {membre}", membre.id)
            messages.success(request,
                f"تمت إضافة {nom} — كلمة المرور المؤقتة: {normalize_phone(telephone)}")
            return redirect("admin_dashboard")

    return render(request, "admin/staff_form.html", {"roles": ROLES_STAFF})


@admin_required
def admin_membre_toggle(request, pk):
    membre = get_object_or_404(AdminClinique, pk=pk)
    if membre.role == "admin":
        messages.error(request, "لا يمكن تعطيل حساب مدير")
        return redirect("admin_dashboard")
    membre.actif = not membre.actif
    membre.save(update_fields=["actif"])
    if membre.utilisateur:
        membre.utilisateur.is_active = membre.actif
        membre.utilisateur.save(update_fields=["is_active"])
    journaliser(request, "modification", "AdminClinique",
                f"{'تفعيل' if membre.actif else 'تعطيل'} حساب {membre.nom}", membre.id)
    messages.success(request,
        f"{'تم تفعيل' if membre.actif else 'تم تعطيل'} حساب {membre.nom}")
    return redirect("admin_dashboard")


@admin_required
def admin_service_ajouter(request):
    if request.method == "POST":
        nom         = request.POST.get("nom", "").strip()
        description = request.POST.get("description", "").strip()
        prix        = request.POST.get("prix", 0)
        duree       = request.POST.get("duree", 30)
        icone       = request.POST.get("icone", "fa-heartbeat").strip()

        if not nom:
            messages.error(request, "اسم الخدمة مطلوب")
        else:
            svc = Service.objects.create(
                nom=nom, description=description,
                prix=prix, duree=duree, icone=icone, actif=True
            )
            journaliser(request, "creation", "Service",
                        f"إضافة خدمة: {svc.nom}", svc.id)
            messages.success(request, f"تمت إضافة خدمة «{svc.nom}»")
            return redirect("admin_dashboard")
    return render(request, "admin/service_form.html")


@admin_required
def admin_analyse_ajouter(request):
    if request.method == "POST":
        nom         = request.POST.get("nom", "").strip()
        description = request.POST.get("description", "").strip()
        prix        = request.POST.get("prix", 0)

        if not nom:
            messages.error(request, "اسم التحليل مطلوب")
        else:
            analyse = Analyse.objects.create(
                nom=nom, description=description, prix=prix, actif=True
            )
            journaliser(request, "creation", "Analyse",
                        f"إضافة تحليل: {analyse.nom}", analyse.id)
            messages.success(request, f"تمت إضافة تحليل «{analyse.nom}»")
            return redirect("admin_dashboard")
    return render(request, "admin/analyse_form.html")


@admin_required
def admin_specialite_ajouter(request):
    if request.method == "POST":
        nom         = request.POST.get("nom", "").strip()
        description = request.POST.get("description", "").strip()
        icone       = request.POST.get("icone", "fa-stethoscope").strip()

        if not nom:
            messages.error(request, "اسم التخصص مطلوب")
        else:
            spec = Specialite.objects.create(
                nom=nom, description=description, icone=icone
            )
            journaliser(request, "creation", "Specialite",
                        f"إضافة تخصص: {spec.nom}", spec.id)
            messages.success(request, f"تمت إضافة تخصص «{spec.nom}»")
            return redirect("admin_dashboard")
    return render(request, "admin/specialite_form.html")
