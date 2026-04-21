from django.urls import path
from . import views

urlpatterns = [
    # ── Pages publiques ──
    path('',                views.accueil,          name='accueil'),
    path('خدمات/',          views.liste_services,   name='services'),
    path('اطباء/',          views.liste_medecins,   name='medecins'),
    path('تخصصات/',         views.liste_specialites,name='specialites'),

    # ── Auth nom + téléphone ──
    path('تسجيل/',          views.inscription,      name='inscription'),
    path('دخول/',           views.connexion,        name='connexion'),
    path('connexion/',      views.connexion,        name='connexion_ascii'),
    path('خروج/',           views.deconnexion,      name='deconnexion'),
    path('اول-دخول/كلمة-المرور/', views.set_password_first_login, name='set_password_first_login'),

    # ── Patient ──
    path('ملفي/',           views.profil,           name='profil'),
    path('حجز/',            views.prendre_rdv,      name='prendre_rdv'),
    path('مواعيدي/',        views.mes_rdv,          name='mes_rdv'),
    path('الغاء/<int:pk>/', views.annuler_rdv,      name='annuler_rdv'),
    path('لوحتي/',          views.tableau_bord,     name='tableau_bord'),

    # ── Patient : liste d'attente + paiements ──
    path('انتظاري/',                               views.patient_liste_attente,              name='patient_liste_attente'),
    path('انتظاري/<int:pk>/الغاء/',               views.patient_liste_attente_annuler,      name='patient_liste_attente_annuler'),
    path('مدفوعاتي/',                             views.patient_paiements,                  name='patient_paiements'),
    path('ملفاتي-الطبية/',    views.mes_fichiers_medicaux, name='mes_fichiers_medicaux'),
    path('ملف-طبي/رفع/',      views.medical_file_upload, name='medical_file_upload'),
    path('ملف-طبي/رفع/<int:patient_id>/', views.medical_file_upload, name='medical_file_upload_for_patient'),
    path('ملف-طبي/<int:pk>/تحميل/', views.medical_file_download, name='medical_file_download'),
    path('ملف-طبي/<int:pk>/حذف/',   views.medical_file_delete, name='medical_file_delete'),

    # ── Réception / Admin ──
    path('استقبال/',                       views.reception_dashboard,      name='reception_dashboard'),
    path('استقبال/مواعيد/',               views.reception_rdv,            name='reception_rdv'),
    path('استقبال/مواعيد/جديد/',          views.reception_rdv_nouveau,    name='reception_rdv_nouveau'),
    path('استقبال/مواعيد/<int:pk>/حالة/', views.reception_rdv_statut,     name='reception_rdv_statut'),
    path('استقبال/مرضى/',                 views.reception_patients,       name='reception_patients'),
    path('استقبال/مرضى/<int:pk>/',        views.reception_patient_detail, name='reception_patient_detail'),
    path('استقبال/اطباء/',                views.reception_medecins,       name='reception_medecins'),
    path('استقبال/اطباء/<int:pk>/تفعيل/', views.reception_medecin_toggle, name='reception_medecin_toggle'),
    path('استقبال/خدمات/',                views.reception_services,       name='reception_services'),
    path('استقبال/فريق/',                 views.reception_equipe,         name='reception_equipe'),
    path('استقبال/فريق/اضافة/',           views.reception_equipe_ajouter, name='reception_equipe_ajouter'),

    # ── Analyses publiques / patient ──
    path('تحاليل-متاحة/',                views.analyses_disponibles,            name='analyses_disponibles'),
    path('تحاليل/',                      views.patient_analyses,                 name='patient_analyses'),

    # ── Réception : analyses + paiements ──
    path('استقبال/تحاليل/جديد/',         views.reception_demande_analyse_nouveau, name='reception_demande_analyse_nouveau'),
    path('استقبال/تحاليل/فواتير/',       views.reception_factures,               name='reception_factures'),
    path('استقبال/تحاليل/دفع/<int:facture_id>/', views.reception_payer_facture,  name='reception_payer_facture'),
    path('استقبال/تحاليل/فاتورة/<int:facture_id>/', views.facture_analyse_print, name='facture_analyse_print'),
    path('استقبال/استشارة/انشاء-فاتورة/<int:rdv_id>/', views.creer_facture_consultation, name='creer_facture_consultation'),
    path('استقبال/استشارة/دفع/<int:facture_id>/', views.payer_consultation,      name='payer_consultation'),
    path('استقبال/استشارة/فاتورة/<int:facture_id>/', views.facture_consultation_print, name='facture_consultation_print'),

    # ── Laboratoire ──
    path('مختبر/',                        views.labo_dashboard,                   name='labo_dashboard'),
    path('مختبر/نتيجة/<int:demande_id>/', views.labo_resultat,                   name='labo_resultat'),
    path('مختبر/مريض/<int:patient_id>/',  views.labo_modifier_patient,           name='labo_modifier_patient'),

    # ── Médecin ──
    path('طبيب/لوحة/',                            views.medecin_dashboard,             name='medecin_dashboard'),
    path('طبيب/<int:medecin_id>/تحاليل/',          views.medecin_analyses,              name='medecin_analyses'),
    path('طبيب/ملاحظات/<int:rdv_id>/',            views.medecin_rdv_notes,             name='medecin_rdv_notes'),
    path('طبيب/وصفاتي/',                           views.medecin_ordonnances,           name='medecin_ordonnances'),
    path('طبيب/وصفة/<int:ordonnance_id>/طباعة/',  views.medecin_ordonnance_print,      name='medecin_ordonnance_print'),
    path('طبيب/تحويل/<int:rdv_id>/',              views.medecin_transfert,             name='medecin_transfert'),
    path('طبيب/مريض/<int:patient_id>/دوسيه/',     views.medecin_patient_dossier,       name='medecin_patient_dossier'),

    # ── Réception : liste d'attente ──
    path('استقبال/انتظار/',                         views.reception_liste_attente,           name='reception_liste_attente'),
    path('استقبال/انتظار/اضافة/',                   views.reception_liste_attente_ajouter,   name='reception_liste_attente_ajouter'),
    path('استقبال/انتظار/<int:pk>/تحويل/',          views.reception_liste_attente_convertir, name='reception_liste_attente_convertir'),
    path('استقبال/انتظار/<int:pk>/الغاء/',          views.reception_liste_attente_annuler,   name='reception_liste_attente_annuler'),

    # ── Réception : gestion services ──
    path('استقبال/خدمات/جديد/',                    views.reception_service_ajouter,         name='reception_service_ajouter'),
    path('استقبال/خدمات/<int:pk>/تعديل/',          views.reception_service_modifier,        name='reception_service_modifier'),

    # ── Réception : gestion médecins ──
    path('استقبال/اطباء/جديد/',                    views.reception_medecin_ajouter,         name='reception_medecin_ajouter'),
    path('استقبال/اطباء/<int:pk>/تعديل/',          views.reception_medecin_modifier,        name='reception_medecin_modifier'),

    # ── Réception : gestion analyses ──
    path('استقبال/ادارة-تحاليل/',                  views.reception_analyses,                name='reception_analyses'),
    path('استقبال/ادارة-تحاليل/جديد/',             views.reception_analyse_form,            name='reception_analyse_ajouter'),
    path('استقبال/ادارة-تحاليل/<int:pk>/تعديل/',   views.reception_analyse_form,            name='reception_analyse_modifier'),
    path('استقبال/ادارة-تحاليل/<int:pk>/تفعيل/',   views.reception_analyse_toggle,          name='reception_analyse_toggle'),

    # ── Réception : toggle équipe ──
    path('استقبال/فريق/<int:pk>/تفعيل/',            views.reception_equipe_toggle,           name='reception_equipe_toggle'),

    # ── Réception : stats revenus ──
    path('استقبال/api/revenus/',                    views.reception_stats_revenus,           name='reception_stats_revenus'),

    # ── Notifications ──
    path('إشعاراتي/',                              views.mes_notifications,                  name='mes_notifications'),
    path('إشعار/<int:pk>/حذف/',                    views.notif_supprimer,                    name='notif_supprimer'),
    path('api/notifs/count/',                       views.notif_count_api,                    name='notif_count_api'),

    # ── Historique visites (patient) ──
    path('تاريخي/',                                views.historique_visites,                  name='historique_visites'),

    # ── Planning médecin ──
    path('طبيب/جدولي/',                            views.medecin_planning,                   name='medecin_planning'),
    path('طبيب/ملفي/',                              views.medecin_profil,                     name='medecin_profil'),
    path('طبيب/مريض/<int:patient_id>/مشاركة/',      views.medecin_partager_dossier,          name='medecin_partager_dossier'),

    # ── Journal audit (admin) ──
    path('استقبال/سجل-المراقبة/',                  views.journal_audit,                      name='journal_audit'),
    path('استقبال/ضغط-العمل/',                      views.reception_pression_travail,         name='reception_pression_travail'),

    # ── Admin Clinique — Dashboard dédié ──
    path('setup/',                                  views.admin_setup,                        name='admin_setup'),
    path('admin-clinique/',                         views.admin_dashboard,                    name='admin_dashboard'),
    path('admin-clinique/medecin/ajouter/',         views.admin_medecin_ajouter,              name='admin_medecin_ajouter'),
    path('admin-clinique/staff/ajouter/',           views.admin_staff_ajouter,                name='admin_staff_ajouter'),
    path('admin-clinique/staff/<int:pk>/toggle/',   views.admin_membre_toggle,                name='admin_membre_toggle'),
    path('admin-clinique/service/ajouter/',         views.admin_service_ajouter,              name='admin_service_ajouter'),
    path('admin-clinique/analyse/ajouter/',         views.admin_analyse_ajouter,              name='admin_analyse_ajouter'),
    path('admin-clinique/specialite/ajouter/',      views.admin_specialite_ajouter,           name='admin_specialite_ajouter'),
]
