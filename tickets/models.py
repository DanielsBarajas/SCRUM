from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        SOLICITANTE = "SOLICITANTE", "Solicitante"
        AGENTE = "AGENTE", "Agente"
        COORDINADOR = "COORDINADOR", "Coordinador"
        AUDITOR = "AUDITOR", "Auditor"

    class Estado(models.TextChoices):
        ACTIVO = "ACTIVO", "Activo"
        INACTIVO = "INACTIVO", "Inactivo"

    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.SOLICITANTE)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)

    def __str__(self):
        return self.get_full_name() or self.username


class Solicitud(models.Model):
    class Prioridad(models.TextChoices):
        BAJA = "BAJA", "Baja"
        MEDIA = "MEDIA", "Media"
        ALTA = "ALTA", "Alta"

    class Estado(models.TextChoices):
        NUEVO = "NUEVO", "Nuevo"
        ASIGNADO = "ASIGNADO", "Asignado"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        RESUELTO = "RESUELTO", "Resuelto"
        CERRADO = "CERRADO", "Cerrado"
        REABIERTO = "REABIERTO", "Reabierto"

    titulo = models.CharField(max_length=180)
    descripcion = models.TextField()
    categoria = models.CharField(max_length=80)
    prioridad = models.CharField(max_length=10, choices=Prioridad.choices, default=Prioridad.MEDIA)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.NUEVO)
    justificacion_prioridad = models.TextField(blank=True)
    fecha_objetivo = models.DateField(null=True, blank=True)
    solicitante = models.ForeignKey(
        "tickets.Usuario",
        on_delete=models.PROTECT,
        related_name="solicitudes",
    )
    agente = models.ForeignKey(
        "tickets.Usuario",
        on_delete=models.SET_NULL,
        related_name="solicitudes_asignadas",
        null=True,
        blank=True,
        limit_choices_to={"rol": Usuario.Rol.AGENTE, "estado": Usuario.Estado.ACTIVO},
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_actualizacion"]

    def __str__(self):
        return f"#{self.pk} {self.titulo}"


class Comentario(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, related_name="comentarios")
    autor = models.ForeignKey("tickets.Usuario", on_delete=models.PROTECT, related_name="comentarios")
    texto = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha_creacion"]

    def __str__(self):
        return f"Comentario #{self.pk} en solicitud #{self.solicitud_id}"


class AuditLog(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, related_name="eventos_auditoria")
    actor_codificado = models.CharField(max_length=64)
    accion = models.CharField(max_length=80)
    campo_modificado = models.CharField(max_length=80, blank=True)
    valor_anterior = models.TextField(blank=True)
    valor_nuevo = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-pk"]

    def __str__(self):
        return f"{self.accion} en solicitud #{self.solicitud_id}"
