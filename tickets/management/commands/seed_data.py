from datetime import timedelta
import hashlib
import hmac

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from tickets.models import AuditLog, Solicitud, Usuario


class Command(BaseCommand):
    help = "Crea las cuentas de prueba y ocho solicitudes de ejemplo."

    def handle(self, *args, **options):
        cuentas = [
            ("solicitante", Usuario.Rol.SOLICITANTE, "Sofía Solicitante"),
            ("agente", Usuario.Rol.AGENTE, "Andrés Agente"),
            ("coordinador", Usuario.Rol.COORDINADOR, "Camila Coordinadora"),
            ("auditor", Usuario.Rol.AUDITOR, "Ariel Auditor"),
        ]
        usuarios = {}
        for username, rol, nombre in cuentas:
            usuario, creado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "rol": rol,
                    "estado": Usuario.Estado.ACTIVO,
                    "first_name": nombre.split()[0],
                    "last_name": " ".join(nombre.split()[1:]),
                },
            )
            if creado:
                usuario.set_password("MarzDemo2026!")
            usuario.rol = rol
            usuario.estado = Usuario.Estado.ACTIVO
            usuario.is_active = True
            usuario.first_name = nombre.split()[0]
            usuario.last_name = " ".join(nombre.split()[1:])
            usuario.save()
            usuarios[rol] = usuario

        if not Solicitud.objects.exists():
            ahora = timezone.now()
            filas = [
                ("Acceso a correo", "No puedo iniciar sesión en el correo corporativo.", "Accesos", Solicitud.Prioridad.ALTA, Solicitud.Estado.RESUELTO),
                ("Equipo lento", "El equipo tarda varios minutos en iniciar.", "Hardware", Solicitud.Prioridad.MEDIA, Solicitud.Estado.EN_PROCESO),
                ("Permisos de carpeta", "Solicito acceso al repositorio del área.", "Accesos", Solicitud.Prioridad.BAJA, Solicitud.Estado.ASIGNADO),
                ("Impresora sin conexión", "La impresora del piso no aparece disponible.", "Impresión", Solicitud.Prioridad.MEDIA, Solicitud.Estado.NUEVO),
                ("VPN intermitente", "La conexión remota se desconecta varias veces al día.", "Redes", Solicitud.Prioridad.ALTA, Solicitud.Estado.CERRADO),
                ("Actualización de software", "Necesito la versión vigente de la herramienta de diseño.", "Software", Solicitud.Prioridad.BAJA, Solicitud.Estado.REABIERTO),
                ("Pantalla externa", "La pantalla externa no detecta la señal.", "Hardware", Solicitud.Prioridad.MEDIA, Solicitud.Estado.RESUELTO),
                ("Cuenta bloqueada", "La cuenta se bloqueó después de varios intentos.", "Accesos", Solicitud.Prioridad.ALTA, Solicitud.Estado.ASIGNADO),
            ]
            for indice, (titulo, descripcion, categoria, prioridad, estado) in enumerate(filas):
                solicitud = Solicitud.objects.create(
                    titulo=titulo,
                    descripcion=descripcion,
                    categoria=categoria,
                    prioridad=prioridad,
                    estado=estado,
                    justificacion_prioridad="Interrumpe una actividad crítica del área." if prioridad == Solicitud.Prioridad.ALTA else "",
                    fecha_objetivo=(ahora + timedelta(days=2)).date() if prioridad == Solicitud.Prioridad.ALTA else None,
                    solicitante=usuarios[Usuario.Rol.SOLICITANTE],
                    agente=usuarios[Usuario.Rol.AGENTE] if estado != Solicitud.Estado.NUEVO else None,
                )
                creada = ahora - timedelta(days=indice + 1)
                Solicitud.objects.filter(pk=solicitud.pk).update(
                    fecha_creacion=creada,
                    fecha_actualizacion=creada,
                )
                if estado == Solicitud.Estado.RESUELTO:
                    AuditLog.objects.create(
                        solicitud=solicitud,
                        actor_codificado=hmac.new(
                            settings.SECRET_KEY.encode(),
                            str(usuarios[Usuario.Rol.AGENTE].pk).encode(),
                            hashlib.sha256,
                        ).hexdigest(),
                        accion="Estado actualizado",
                        campo_modificado="estado",
                        valor_anterior=Solicitud.Estado.EN_PROCESO,
                        valor_nuevo=Solicitud.Estado.RESUELTO,
                    )
                    AuditLog.objects.filter(solicitud=solicitud, campo_modificado="estado").update(
                        fecha=creada + timedelta(hours=indice + 3)
                    )
            self.stdout.write(self.style.SUCCESS("Se crearon ocho solicitudes de ejemplo."))
        else:
            self.stdout.write("Ya existen solicitudes; se conservaron sin cambios.")
        self.stdout.write(self.style.SUCCESS("Usuarios de prueba listos. Contraseña para cuentas nuevas: MarzDemo2026!"))
