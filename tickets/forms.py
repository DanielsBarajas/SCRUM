from django import forms

from .models import Solicitud, Usuario


class SolicitudForm(forms.ModelForm):
    class Meta:
        model = Solicitud
        fields = ["titulo", "descripcion", "categoria"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-input", "maxlength": 180}),
            "descripcion": forms.Textarea(attrs={"class": "form-input", "rows": 5}),
            "categoria": forms.TextInput(attrs={"class": "form-input", "maxlength": 80}),
        }


class GestionSolicitudForm(forms.Form):
    agente = forms.ModelChoiceField(
        queryset=Usuario.objects.none(),
        required=False,
        empty_label="Sin asignar",
        widget=forms.Select(attrs={"class": "form-input"}),
    )
    prioridad = forms.ChoiceField(
        choices=Solicitud.Prioridad.choices,
        widget=forms.Select(attrs={"class": "form-input"}),
    )
    justificacion_prioridad = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-input", "rows": 2}),
    )
    fecha_objetivo = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )
    estado = forms.ChoiceField(
        choices=[
            (Solicitud.Estado.NUEVO, "Nuevo"),
            (Solicitud.Estado.ASIGNADO, "Asignado"),
            (Solicitud.Estado.EN_PROCESO, "En proceso"),
            (Solicitud.Estado.RESUELTO, "Resuelto"),
        ],
        widget=forms.Select(attrs={"class": "form-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["agente"].queryset = Usuario.objects.filter(
            rol=Usuario.Rol.AGENTE,
            estado=Usuario.Estado.ACTIVO,
            is_active=True,
        ).order_by("username")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("prioridad") == Solicitud.Prioridad.ALTA:
            if not cleaned_data.get("justificacion_prioridad"):
                self.add_error("justificacion_prioridad", "La prioridad alta requiere una justificación.")
            if not cleaned_data.get("fecha_objetivo"):
                self.add_error("fecha_objetivo", "La prioridad alta requiere una fecha objetivo.")
        return cleaned_data


class ComentarioForm(forms.Form):
    texto = forms.CharField(
        min_length=1,
        max_length=5000,
        widget=forms.Textarea(attrs={"class": "form-input", "rows": 3}),
    )


class MotivoForm(forms.Form):
    motivo = forms.CharField(
        min_length=3,
        max_length=2000,
        widget=forms.Textarea(attrs={"class": "form-input", "rows": 3}),
    )
