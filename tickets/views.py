import csv
import hashlib
import hmac
from statistics import median

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ComentarioForm, GestionSolicitudForm, MotivoForm, SolicitudForm
from .models import AuditLog, Comentario, Solicitud, Usuario


def _actor_codificado(usuario):
    return hmac.new(
        settings.SECRET_KEY.encode(),
        str(usuario.pk).encode(),
        hashlib.sha256,
    ).hexdigest()


def _registrar_evento(solicitud, usuario, accion, campo="", anterior="", nuevo=""):
    AuditLog.objects.create(
        solicitud=solicitud,
        actor_codificado=_actor_codificado(usuario),
        accion=accion,
        campo_modificado=campo,
        valor_anterior=str(anterior),
        valor_nuevo=str(nuevo),
    )


def _destino_por_rol(usuario):
    if usuario.rol == Usuario.Rol.AUDITOR:
        return "auditoria"
    return "dashboard"


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_destino_por_rol(request.user))
    error = ""
    if request.method == "POST":
        usuario = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )
        if usuario is not None and usuario.estado == Usuario.Estado.ACTIVO:
            login(request, usuario)
            return redirect(_destino_por_rol(usuario))
        error = "Usuario o contraseña inválidos, o cuenta inactiva."
    return render(request, "tickets/login.html", {"error": error})


@require_POST
@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


def _solicitudes_visibles(usuario):
    solicitudes = Solicitud.objects.select_related("solicitante", "agente")
    if usuario.rol == Usuario.Rol.SOLICITANTE:
        return solicitudes.filter(solicitante=usuario)
    if usuario.rol == Usuario.Rol.AGENTE:
        return solicitudes.filter(agente=usuario)
    if usuario.rol == Usuario.Rol.COORDINADOR:
        return solicitudes
    return solicitudes.none()


def _filtrar_solicitudes(request, solicitudes):
    termino = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    prioridad = request.GET.get("prioridad", "").strip()
    categoria = request.GET.get("categoria", "").strip()
    if termino:
        solicitudes = solicitudes.filter(
            Q(titulo__icontains=termino)
            | Q(descripcion__icontains=termino)
            | Q(categoria__icontains=termino)
        )
    if estado in Solicitud.Estado.values:
        solicitudes = solicitudes.filter(estado=estado)
    if prioridad in Solicitud.Prioridad.values:
        solicitudes = solicitudes.filter(prioridad=prioridad)
    if categoria:
        solicitudes = solicitudes.filter(categoria__icontains=categoria)
    return solicitudes, {
        "q": termino,
        "estado_seleccionado": estado,
        "prioridad_seleccionada": prioridad,
        "categoria": categoria,
    }


@login_required
def dashboard(request):
    if request.user.rol == Usuario.Rol.AUDITOR:
        return redirect("auditoria")
    if request.user.rol not in {
        Usuario.Rol.SOLICITANTE,
        Usuario.Rol.AGENTE,
        Usuario.Rol.COORDINADOR,
    }:
        return HttpResponseForbidden("Rol no autorizado.")

    solicitudes, filtros = _filtrar_solicitudes(request, _solicitudes_visibles(request.user))
    contexto = {
        **filtros,
        "solicitudes": solicitudes,
        "estados": Solicitud.Estado.choices,
        "prioridades": Solicitud.Prioridad.choices,
        "puede_crear": request.user.rol == Usuario.Rol.SOLICITANTE,
        "es_coordinador": request.user.rol == Usuario.Rol.COORDINADOR,
    }
    if request.user.rol == Usuario.Rol.COORDINADOR:
        conteos_estado = {
            item["estado"]: item["total"]
            for item in Solicitud.objects.values("estado").annotate(total=Count("id"))
        }
        contexto["estado_metricas"] = [
            {"etiqueta": etiqueta, "total": conteos_estado.get(codigo, 0)}
            for codigo, etiqueta in Solicitud.Estado.choices
        ]
        eventos_resolucion = AuditLog.objects.filter(
            campo_modificado="estado",
            valor_nuevo=Solicitud.Estado.RESUELTO,
        ).select_related("solicitud").order_by("fecha")
        primera_resolucion = {}
        for evento in eventos_resolucion:
            primera_resolucion.setdefault(evento.solicitud_id, evento)
        tiempos_ciclo = [
            (evento.fecha - evento.solicitud.fecha_creacion).total_seconds() / 3600
            for evento in primera_resolucion.values()
            if evento.fecha >= evento.solicitud.fecha_creacion
        ]
        contexto["mediana_ciclo_horas"] = median(tiempos_ciclo) if tiempos_ciclo else None

    if request.headers.get("HX-Request") == "true":
        return render(request, "tickets/partials/lista_solicitudes.html", contexto)
    contexto["formulario_solicitud"] = SolicitudForm()
    return render(request, "tickets/dashboard.html", contexto)


@login_required
@require_POST
def crear_solicitud(request):
    if request.user.rol != Usuario.Rol.SOLICITANTE:
        return HttpResponseForbidden("Solo los solicitantes pueden crear solicitudes.")
    formulario = SolicitudForm(request.POST)
    if formulario.is_valid():
        solicitud = formulario.save(commit=False)
        solicitud.solicitante = request.user
        solicitud.estado = Solicitud.Estado.NUEVO
        solicitud.save()
        _registrar_evento(solicitud, request.user, "Solicitud creada", "estado", "", solicitud.estado)
        messages.success(request, "La solicitud fue creada.")
    else:
        detalle_errores = "; ".join(
            f"{campo}: {', '.join(errores)}"
            for campo, errores in formulario.errors.items()
        )
        messages.error(request, f"No se pudo crear la solicitud. {detalle_errores}")
    return redirect("dashboard")


def _obtener_solicitud_visible(request, pk):
    return get_object_or_404(_solicitudes_visibles(request.user), pk=pk)


@login_required
def detalle_ticket(request, pk):
    solicitud = _obtener_solicitud_visible(request, pk)
    puede_gestionar = request.user.rol == Usuario.Rol.COORDINADOR
    puede_comentar = request.user.rol == Usuario.Rol.AGENTE and solicitud.agente_id == request.user.pk
    puede_responder = (
        request.user.rol == Usuario.Rol.SOLICITANTE
        and solicitud.solicitante_id == request.user.pk
    )
    formulario_gestion = GestionSolicitudForm(
        initial={
            "agente": solicitud.agente_id,
            "prioridad": solicitud.prioridad,
            "justificacion_prioridad": solicitud.justificacion_prioridad,
            "fecha_objetivo": solicitud.fecha_objetivo,
            "estado": solicitud.estado,
        }
    ) if puede_gestionar else None
    return render(
        request,
        "tickets/detalle_ticket.html",
        {
            "solicitud": solicitud,
            "comentarios": solicitud.comentarios.select_related("autor"),
            "eventos": solicitud.eventos_auditoria.all(),
            "formulario_gestion": formulario_gestion,
            "formulario_comentario": ComentarioForm(),
            "formulario_motivo": MotivoForm(),
            "puede_gestionar": puede_gestionar,
            "puede_comentar": puede_comentar,
            "puede_responder": puede_responder,
        },
    )


@login_required
@require_POST
@transaction.atomic
def gestionar_solicitud(request, pk):
    if request.user.rol != Usuario.Rol.COORDINADOR:
        return HttpResponseForbidden("Solo el coordinador puede gestionar solicitudes.")
    solicitud = get_object_or_404(Solicitud.objects.select_for_update(), pk=pk)
    formulario = GestionSolicitudForm(request.POST)
    if not formulario.is_valid():
        messages.error(request, "Datos de gestión inválidos. La prioridad alta requiere justificación y fecha.")
        return redirect("detalle_ticket", pk=pk)

    datos = formulario.cleaned_data
    estados_coordinador = {
        Solicitud.Estado.NUEVO: {
            Solicitud.Estado.NUEVO,
            Solicitud.Estado.ASIGNADO,
        },
        Solicitud.Estado.ASIGNADO: {
            Solicitud.Estado.ASIGNADO,
            Solicitud.Estado.EN_PROCESO,
        },
        Solicitud.Estado.EN_PROCESO: {
            Solicitud.Estado.EN_PROCESO,
            Solicitud.Estado.RESUELTO,
        },
        Solicitud.Estado.RESUELTO: {Solicitud.Estado.RESUELTO},
        Solicitud.Estado.REABIERTO: {
            Solicitud.Estado.REABIERTO,
            Solicitud.Estado.ASIGNADO,
        },
    }
    if datos["estado"] not in estados_coordinador.get(solicitud.estado, set()):
        messages.error(request, "La transición de estado seleccionada no está permitida.")
        return redirect("detalle_ticket", pk=pk)
    cambios = [
        ("agente", solicitud.agente, datos["agente"]),
        ("prioridad", solicitud.prioridad, datos["prioridad"]),
        (
            "justificacion_prioridad",
            solicitud.justificacion_prioridad,
            datos["justificacion_prioridad"] if datos["prioridad"] == Solicitud.Prioridad.ALTA else "",
        ),
        (
            "fecha_objetivo",
            solicitud.fecha_objetivo,
            datos["fecha_objetivo"] if datos["prioridad"] == Solicitud.Prioridad.ALTA else None,
        ),
        ("estado", solicitud.estado, datos["estado"]),
    ]
    for campo, anterior, nuevo in cambios:
        anterior_valor = getattr(anterior, "pk", anterior)
        nuevo_valor = getattr(nuevo, "pk", nuevo)
        if str(anterior_valor or "") != str(nuevo_valor or ""):
            setattr(solicitud, campo, nuevo)
            _registrar_evento(
                solicitud,
                request.user,
                f"{campo.capitalize()} actualizado",
                campo,
                getattr(anterior, "username", anterior),
                getattr(nuevo, "username", nuevo),
            )
    solicitud.save()
    messages.success(request, "La solicitud fue actualizada.")
    return redirect("detalle_ticket", pk=pk)


@login_required
@require_POST
@transaction.atomic
def cambiar_estado_agente(request, pk):
    if request.user.rol != Usuario.Rol.AGENTE:
        return HttpResponseForbidden("Solo el agente asignado puede actualizar el estado.")
    solicitud = get_object_or_404(
        Solicitud.objects.select_for_update(),
        pk=pk,
        agente=request.user,
    )
    siguiente_estado = request.POST.get("estado")
    transiciones = {
        Solicitud.Estado.ASIGNADO: {Solicitud.Estado.EN_PROCESO},
        Solicitud.Estado.REABIERTO: {Solicitud.Estado.EN_PROCESO},
        Solicitud.Estado.EN_PROCESO: {Solicitud.Estado.RESUELTO},
    }
    if siguiente_estado not in transiciones.get(solicitud.estado, set()):
        messages.error(request, "La transición de estado seleccionada no está permitida.")
        return redirect("detalle_ticket", pk=pk)
    anterior = solicitud.estado
    solicitud.estado = siguiente_estado
    solicitud.save(update_fields=["estado", "fecha_actualizacion"])
    _registrar_evento(solicitud, request.user, "Estado actualizado", "estado", anterior, siguiente_estado)
    messages.success(request, "El estado de la solicitud fue actualizado.")
    return redirect("detalle_ticket", pk=pk)


@login_required
@require_POST
def agregar_comentario(request, pk):
    if request.user.rol != Usuario.Rol.AGENTE:
        return HttpResponseForbidden("Solo los agentes asignados pueden comentar.")
    solicitud = get_object_or_404(Solicitud, pk=pk, agente=request.user)
    formulario = ComentarioForm(request.POST)
    if formulario.is_valid():
        Comentario.objects.create(
            solicitud=solicitud,
            autor=request.user,
            texto=formulario.cleaned_data["texto"],
        )
        _registrar_evento(solicitud, request.user, "Comentario agregado")
        messages.success(request, "Comentario agregado.")
    else:
        messages.error(request, "El comentario no puede estar vacío y debe tener como máximo 5000 caracteres.")
    return redirect("detalle_ticket", pk=pk)


@login_required
@require_POST
@transaction.atomic
def cambiar_estado_solicitante(request, pk):
    if request.user.rol != Usuario.Rol.SOLICITANTE:
        return HttpResponseForbidden("Solo el solicitante puede cerrar o reabrir la solicitud.")
    solicitud = get_object_or_404(Solicitud.objects.select_for_update(), pk=pk, solicitante=request.user)
    formulario = MotivoForm(request.POST)
    siguiente_estado = request.POST.get("estado")
    transiciones = {
        Solicitud.Estado.RESUELTO: Solicitud.Estado.CERRADO,
        Solicitud.Estado.CERRADO: Solicitud.Estado.REABIERTO,
    }
    if not formulario.is_valid() or transiciones.get(solicitud.estado) != siguiente_estado:
        messages.error(request, "La acción no está permitida o debes indicar un motivo válido.")
        return redirect("detalle_ticket", pk=pk)
    anterior = solicitud.estado
    solicitud.estado = siguiente_estado
    solicitud.save(update_fields=["estado", "fecha_actualizacion"])
    Comentario.objects.create(
        solicitud=solicitud,
        autor=request.user,
        texto=f"{'Cierre' if siguiente_estado == Solicitud.Estado.CERRADO else 'Reapertura'}: "
        f"{formulario.cleaned_data['motivo']}",
    )
    _registrar_evento(solicitud, request.user, "Estado actualizado", "estado", anterior, siguiente_estado)
    messages.success(request, "El estado de la solicitud fue actualizado.")
    return redirect("detalle_ticket", pk=pk)


@login_required
def auditoria(request):
    if request.user.rol not in {Usuario.Rol.COORDINADOR, Usuario.Rol.AUDITOR}:
        return HttpResponseForbidden("No tienes acceso a la auditoría.")
    eventos = AuditLog.objects.select_related("solicitud")
    termino = request.GET.get("q", "").strip()
    if termino.isdigit():
        eventos = eventos.filter(solicitud_id=int(termino))
    elif termino:
        eventos = eventos.filter(
            Q(accion__icontains=termino)
            | Q(campo_modificado__icontains=termino)
            | Q(valor_anterior__icontains=termino)
            | Q(valor_nuevo__icontains=termino)
        )
    return render(request, "tickets/auditoria.html", {"eventos": eventos, "q": termino})


@login_required
def exportar_csv(request):
    if request.user.rol not in {Usuario.Rol.COORDINADOR, Usuario.Rol.AUDITOR}:
        return HttpResponseForbidden("No tienes permiso para exportar reportes.")
    solicitudes, _ = _filtrar_solicitudes(request, Solicitud.objects.select_related("solicitante", "agente"))
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="reporte_solicitudes.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        ["ID", "Título", "Categoría", "Prioridad", "Estado", "Solicitante", "Agente", "Fecha de creación", "Fecha objetivo"]
    )

    def texto_csv_seguro(valor):
        texto = str(valor or "")
        if texto.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
            return f"'{texto}"
        return texto

    for solicitud in solicitudes:
        writer.writerow(
            [
                solicitud.pk,
                texto_csv_seguro(solicitud.titulo),
                texto_csv_seguro(solicitud.categoria),
                solicitud.get_prioridad_display(),
                solicitud.get_estado_display(),
                texto_csv_seguro(solicitud.solicitante.username),
                texto_csv_seguro(solicitud.agente.username) if solicitud.agente else "",
                timezone.localtime(solicitud.fecha_creacion).isoformat(),
                solicitud.fecha_objetivo.isoformat() if solicitud.fecha_objetivo else "",
            ]
        )
    return response
