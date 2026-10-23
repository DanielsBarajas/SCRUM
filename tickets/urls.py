from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("solicitudes/nueva/", views.crear_solicitud, name="crear_solicitud"),
    path("solicitudes/<int:pk>/", views.detalle_ticket, name="detalle_ticket"),
    path("solicitudes/<int:pk>/gestionar/", views.gestionar_solicitud, name="gestionar_solicitud"),
    path("solicitudes/<int:pk>/estado-agente/", views.cambiar_estado_agente, name="estado_agente"),
    path("solicitudes/<int:pk>/comentarios/", views.agregar_comentario, name="agregar_comentario"),
    path("solicitudes/<int:pk>/estado/", views.cambiar_estado_solicitante, name="cambiar_estado"),
    path("auditoria/", views.auditoria, name="auditoria"),
    path("reportes/solicitudes.csv", views.exportar_csv, name="exportar_csv"),
]
