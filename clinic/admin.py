
from django.contrib import admin
from .models import *

for model in [Specialite, Medecin, Service, Patient, RendezVous, AdminClinique,
              Analyse, DemandeAnalyse, FactureAnalyse, PaiementAnalyse,
              FactureConsultation, PaiementConsultation]:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass


from .models import PieceMedicale, PieceMedicaleAudit

@admin.register(PieceMedicale)
class PieceMedicaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'titre', 'patient', 'type_piece', 'source_role', 'est_active', 'cree_le')
    list_filter = ('type_piece', 'source_role', 'est_active', 'cree_le')
    search_fields = ('titre', 'patient__utilisateur__first_name', 'patient__utilisateur__last_name', 'nom_original')

@admin.register(PieceMedicaleAudit)
class PieceMedicaleAuditAdmin(admin.ModelAdmin):
    list_display = ('id', 'piece', 'utilisateur', 'action', 'cree_le')
    list_filter = ('action', 'cree_le')
