# Nexo — Soporte interno

Nexo es una aplicación web para registrar y atender solicitudes de soporte dentro de una organización. Cada persona ve las herramientas que necesita según su rol, desde el seguimiento de sus propios tickets hasta la asignación de agentes, la auditoría y los reportes.

La aplicación está construida con Django y plantillas HTML. HTMX se usa para actualizar los resultados de búsqueda y Tailwind CSS para los estilos; ambos se cargan desde CDN, así que el navegador necesita conexión a internet para obtenerlos.

## Qué puedes hacer

- Crear solicitudes con título, descripción y categoría.
- Consultar solicitudes con filtros combinables por texto, estado, prioridad y categoría.
- Asignar solicitudes a agentes activos, ajustar la prioridad y dar seguimiento al estado.
- Solicitar una justificación y una fecha objetivo cuando se asigna prioridad alta.
- Agregar comentarios a la conversación del ticket. Los comentarios no tienen opciones para editarse ni eliminarse desde la aplicación.
- Cerrar una solicitud resuelta o reabrir una cerrada; en ambos casos se debe indicar el motivo.
- Revisar el resumen de solicitudes por estado y la mediana del tiempo hasta su primera resolución.
- Consultar un historial de auditoría con identificadores de actor anonimizados.
- Descargar un CSV con datos de seguimiento, sin incluir descripciones ni comentarios.

## Roles

| Rol | Acceso principal |
| --- | --- |
| Solicitante | Crear solicitudes y consultar únicamente las propias. Puede cerrar una solicitud resuelta o reabrir una cerrada. |
| Agente | Ver las solicitudes que tiene asignadas, actualizar su progreso y agregar comentarios. |
| Coordinador | Consultar y filtrar todas las solicitudes, asignar agentes, cambiar prioridad y estado, y consultar métricas y auditoría. |
| Auditor | Consultar la auditoría y exportar el reporte CSV. No puede abrir el detalle de los tickets. |

El flujo habitual es: una solicitud nueva se asigna a un agente, pasa a «En proceso» y luego a «Resuelto». El solicitante puede cerrarla o reabrirla si el problema persiste.

## Cómo iniciar el proyecto en Windows

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Si todavía no tienes un entorno virtual en `venv`, créalo antes de activarlo:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Al iniciar Django, abre [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/) en el navegador. Para detener el servidor, vuelve a la terminal y presiona `Ctrl+C`.

## Cuentas de prueba

El comando `seed_data` prepara una cuenta por rol:

| Usuario | Rol |
| --- | --- |
| `solicitante` | Solicitante |
| `agente` | Agente |
| `coordinador` | Coordinador |
| `auditor` | Auditor |

La contraseña inicial de las cuentas que el comando crea es `MarzDemo2026!`. Estas credenciales son solo para desarrollo y demostración: no las uses en un entorno real.

El comando crea ocho solicitudes de ejemplo si la base todavía no contiene solicitudes. Puedes ejecutarlo de nuevo sin duplicar esos tickets. Si las cuentas ya existen, el comando conserva sus contraseñas actuales; no las restablece.

## Datos y estructura

El proyecto usa SQLite y guarda la base en `db.sqlite3`, dentro de la carpeta principal. Las migraciones de la aplicación están en `tickets/migrations/`.

- `tickets/models.py`: usuarios, solicitudes, comentarios y eventos de auditoría.
- `tickets/views.py` y `tickets/urls.py`: autenticación, permisos, flujos de trabajo, búsqueda y exportación.
- `tickets/templates/tickets/`: páginas de inicio de sesión, solicitudes, detalle y auditoría.
- `tickets/management/commands/seed_data.py`: cuentas y solicitudes de demostración.

La exportación CSV está disponible para coordinadores y auditores en `/reportes/solicitudes.csv`. El panel de auditoría se encuentra en `/auditoria/`.

## Consideraciones antes de publicar

- La configuración predeterminada es para desarrollo: `DEBUG` está activado y la clave secreta tiene un valor local de respaldo. No publiques la aplicación con esos valores.
- Antes de desplegar, define `DJANGO_SECRET_KEY` con una clave privada, `DJANGO_DEBUG=false` y `DJANGO_ALLOWED_HOSTS` con los dominios autorizados, separados por comas. Por ejemplo, en PowerShell:

  ```powershell
  $env:DJANGO_SECRET_KEY = "reemplaza-por-una-clave-segura"
  $env:DJANGO_DEBUG = "false"
  $env:DJANGO_ALLOWED_HOSTS = "soporte.ejemplo.com"
  ```

- Tailwind CSS y HTMX se descargan desde CDN al abrir las páginas. Si la red bloquea esos servicios, las interacciones o los estilos pueden no estar disponibles.
- La mediana del ciclo se calcula en horas para las solicitudes con un evento de auditoría de primera resolución. Mantener los eventos de auditoría es importante para que la métrica refleje correctamente la actividad.
- Las cuentas de demostración son activas y conocidas. Desactívalas, elimínalas o cambia sus contraseñas antes de exponer una instalación fuera de un entorno local.
