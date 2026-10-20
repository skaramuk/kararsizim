from django import forms
from django.core.exceptions import ValidationError

from . import services
from .models import Poll


class PollCreateForm(forms.ModelForm):
    """Soru + açıklama alanları ModelForm'dan; seçenekler aynı adlı (`choices`) tekrarlı
    girdilerden gelir, böylece JS'in eklediği/çıkardığı alanlar sıralamayı bozmaz."""

    class Meta:
        model = Poll
        fields = ("question", "description")
        labels = {"question": "Sorun nedir?", "description": "Açıklama (isteğe bağlı)"}
        widgets = {
            "question": forms.TextInput(attrs={"placeholder": "Bugün sinemaya mı gitsem, restorana mı?"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        error_messages = {
            "question": {"required": "Soru yazmalısın."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["question"].widget.attrs["autofocus"] = True
        self.fields["description"].max_length = 500
        self.fields["description"].widget.attrs["maxlength"] = 500
        self.choice_values = (
            [value.strip() for value in self.data.getlist("choices")] if self.is_bound else []
        )

    @property
    def choice_rows(self):
        """Şablonun çizeceği 5 seçenek alanı (JS kapalıyken hepsi görünür)."""
        values = list(self.choice_values)[: services.MAX_CHOICES]
        return values + [""] * (services.MAX_CHOICES - len(values))

    def clean(self):
        cleaned = super().clean()
        try:
            self.cleaned_choices = services.clean_choices(self.choice_values)
        except ValidationError as error:
            self.add_error(None, error)
        return cleaned

    def save(self, author):
        return services.create_poll(
            author,
            self.cleaned_data["question"],
            self.cleaned_data.get("description", ""),
            self.cleaned_choices,
        )
