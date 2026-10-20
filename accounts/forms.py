from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .models import RESERVED_USERNAMES

User = get_user_model()


class SignUpForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Parola",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="En az 8 karakter; çok yaygın veya sadece rakamlardan oluşan parolalar kabul edilmez.",
    )
    password2 = forms.CharField(
        label="Parola (tekrar)",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ("username", "email")
        labels = {"username": "Kullanıcı adı", "email": "E-posta"}
        help_texts = {
            "username": "3–20 karakter; harf, rakam, _ ve . kullanabilirsin. Anketlerde bu ad görünür.",
            "email": "Sadece giriş için kullanılır, kimseye gösterilmez.",
        }
        error_messages = {
            "email": {"invalid": "Geçerli bir e-posta adresi gir."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"autocomplete": "username", "autocapitalize": "none", "spellcheck": "false"}
        )
        self.fields["email"].widget.attrs.update({"autocomplete": "email"})
        for field in self.fields.values():
            field.error_messages["required"] = "Bu alan zorunludur."

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if username.lower() in RESERVED_USERNAMES:
            raise ValidationError("Bu kullanıcı adı kullanılamaz.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Bu kullanıcı adı zaten alınmış.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Bu e-posta adresiyle zaten bir hesap var.")
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2:
            if password1 != password2:
                self.add_error("password2", "Parolalar eşleşmiyor.")
            else:
                candidate = User(username=cleaned.get("username", ""), email=cleaned.get("email", ""))
                try:
                    password_validation.validate_password(password2, candidate)
                except ValidationError as error:
                    self.add_error("password2", error)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "E-posta veya parola hatalı.",
        "inactive": "Bu hesap devre dışı.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "E-posta"
        self.fields["username"].widget = forms.EmailInput(
            attrs={"autocomplete": "email", "autofocus": True}
        )
        self.fields["password"].label = "Parola"
        for field in self.fields.values():
            field.error_messages["required"] = "Bu alan zorunludur."

    def clean_username(self):
        # E-postalar küçük harfle saklanır; girişte büyük/küçük harf fark etmesin.
        return self.cleaned_data["username"].strip().lower()
