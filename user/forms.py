from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserChangeForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError

from .models import User


class FormUserCreation(UserCreationForm):
    """Форма регистрации нового пользователя."""

    email = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите ваш email',
            'autocomplete': 'email',
            'required': 'required'
        })
    )

    username = forms.CharField(
        label="Имя пользователя",
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите имя пользователя',
            'autocomplete': 'username',
            'required': 'required'
        })
    )

    phone = forms.CharField(
        label="Телефон",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 999-99-99',
            'autocomplete': 'tel'
        })
    )

    country = forms.CharField(
        label="Страна",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например: Россия',
            'autocomplete': 'country-name'
        })
    )

    class Meta:
        model = User
        fields = ("email", "username", "phone", "country", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Устанавливаем обязательные поля
        self.fields['email'].required = True
        self.fields['username'].required = True
        self.fields['password1'].required = True
        self.fields['password2'].required = True

        # Настройка виджетов паролей
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Введите пароль',
            'autocomplete': 'new-password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Повторите пароль',
            'autocomplete': 'new-password'
        })

    def clean_email(self):
        """Проверка уникальности email."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Пользователь с таким email уже существует.")
        return email

    def clean_username(self):
        """Проверка уникальности username."""
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("Пользователь с таким именем уже существует.")
        return username

    def clean(self):
        """Дополнительная валидация всей формы."""
        cleaned_data = super().clean()

        # Проверка, что username не пустой
        username = cleaned_data.get('username')
        if username and len(username.strip()) < 3:
            self.add_error('username', 'Имя пользователя должно содержать минимум 3 символа.')

        return cleaned_data

    def save(self, commit=True):
        """Сохраняет пользователя."""
        print("=== СРАБОТАЛ МЕТОД save() ФОРМЫ ===")

        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['username']
        user.phone = self.cleaned_data.get('phone', '')
        user.country = self.cleaned_data.get('country', '')

        # Устанавливаем is_active по умолчанию
        user.is_active = True

        print(f"Пользователь перед сохранением:")
        print(f"  Email: {user.email}")
        print(f"  Username: {user.username}")
        print(f"  Phone: {user.phone}")
        print(f"  Country: {user.country}")

        if commit:
            try:
                user.save()
                print(f"Пользователь сохранен с ID: {user.id}")
                # Сохраняем ManyToMany отношения, если они есть
                self.save_m2m()
            except Exception as e:
                print(f"Ошибка при сохранении пользователя: {e}")
                raise

        return user

class CustomAuthenticationForm(AuthenticationForm):
    """Кастомная форма аутентификации с добавлением CSS-классов."""

    def __init__(self, *args, **kwargs):
        """Инициализирует форму, добавляя CSS-классы ко всем полям."""
        super(CustomAuthenticationForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"


class UserForm(UserChangeForm):
    """Форма редактирования профиля пользователя."""

    class Meta:
        model = User
        fields = ["username", "email", "phone", "country", "avatar"]
        exclude = ["password"]
        widgets = {
            "avatar": forms.ClearableFileInput(attrs={"class": "form-control-file"}),
        }

    def __init__(self, *args, **kwargs):
        """
        Настраивает форму:
        - Удаляет поле password
        - Добавляет CSS-классы и placeholder'ы к полям
        """
        super().__init__(*args, **kwargs)
        if "password" in self.fields:
            del self.fields["password"]

        for field_name, field in self.fields.items():
            if field_name != "avatar":
                field.widget.attrs["class"] = "form-control"

        self.fields["username"].widget.attrs.update({"placeholder": "Имя пользователя"})
        self.fields["phone"].widget.attrs.update({"placeholder": "Телефон пользователя"})
        self.fields["country"].widget.attrs.update({"placeholder": "Страна проживания"})


class UserManagerForm(UserChangeForm):
    """Форма блокировки/разблокировки пользователя (для менеджеров)."""

    class Meta:
        model = User
        fields = ["is_active"]

    def __init__(self, *args, **kwargs):
        """Настраивает форму, добавляя подсказку для поля is_active."""
        super().__init__(*args, **kwargs)
        if "password" in self.fields:
            del self.fields["password"]

        self.fields["is_active"].widget.attrs["class"] = "form-check-input"
        self.fields["is_active"].help_text = "Для блокировки пользователя уберите галочку"


class UserPasswordChangeForm(PasswordChangeForm):
    """Форма изменения пароля пользователя."""

    old_password = forms.CharField(label="Старый пароль", widget=forms.PasswordInput(attrs={"class": "form-input"}))
    new_password1 = forms.CharField(label="Новый пароль", widget=forms.PasswordInput(attrs={"class": "form-input"}))
    new_password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput(attrs={"class": "form-input"}),
    )
