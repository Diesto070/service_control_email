from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.views.generic import DetailView, ListView
from django.views.generic.edit import FormView, UpdateView

from .forms import (
    FormUserCreation,
    UserForm,
    UserManagerForm,
    UserPasswordChangeForm,
)
from .models import User


class RegisterView(FormView):
    """Регистрация нового пользователя."""

    form_class = FormUserCreation
    template_name = "registration/register.html"
    success_url = reverse_lazy("sending_mail:home")

    def get(self, request, *args, **kwargs):
        """GET запрос - отображаем пустую форму."""
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """POST запрос - обрабатываем форму."""
        form = self.get_form()
        if not form.is_valid():
            for field, errors in form.errors.items():
                for error in errors:
                    print(f"  {field}: {error}")

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Создает пользователя и выполняет автоматический вход."""
        try:
            # Сохраняем пользователя
            user = form.save()
            # Автоматический вход
            login(self.request, user)

            messages.success(self.request, f"Добро пожаловать, {user.username}! Регистрация прошла успешно.")

            return super().form_valid(form)

        except Exception as e:
            # Сохраняем ошибку в сообщениях Django
            messages.error(self.request, mark_safe(
                f"Ошибка при регистрации:<br>"
                f"<strong>{type(e).__name__}:</strong> {str(e)}<br>"
                f"<small>Проверьте консоль сервера для подробностей</small>"
            ))

            # Возвращаем невалидную форму с ошибками
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Обработка невалидной формы."""
        error_list = []
        for field, errors in form.errors.items():
            field_name = form.fields[field].label if field in form.fields else field
            for error in errors:
                error_list.append(f"<strong>{field_name}:</strong> {error}")

        if error_list:
            messages.error(self.request, mark_safe(
                "Пожалуйста, исправьте ошибки:<br>" + "<br>".join(error_list)
            ))

        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        """Добавляем отладочную информацию в контекст."""
        context = super().get_context_data(**kwargs)

        # Для отладки в шаблоне
        if self.request.method == 'POST':
            context['posted_data'] = self.request.POST
            context['form_errors'] = self.get_form().errors if hasattr(self, 'get_form') else None

        return context

class UserDetailView(DetailView):
    """Контроллер для просмотра информации о пользователе"""

    model = User
    template_name = "user/user_info.html"
    context_object_name = "user"

    def get_object(self, queryset=None):
        pk = self.kwargs.get("pk")
        user = get_object_or_404(User, pk=pk)
        return user


class UserUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование профиля пользователя с проверкой прав доступа."""

    model = User
    template_name = "user/user_form.html"
    context_object_name = "user"
    success_url = reverse_lazy("sending_mail:home")

    def form_valid(self, form):
        """Привязывает форму к текущему пользователю."""
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_form_class(self):
        """Возвращает форму в зависимости от прав пользователя."""
        user = self.request.user
        target_user = self.get_object()
        if user == target_user:
            return UserForm
        if user.has_perm("users.can_blocked_user"):
            return UserManagerForm
        else:
            raise PermissionDenied("У вас нет прав для редактирования этого профиля пользователя")

    def get_object(self, queryset=None):
        """Возвращает редактируемого пользователя или текущего пользователя."""
        pk = self.kwargs.get("pk")
        if pk:
            return get_object_or_404(User, pk=pk)
        return self.request.user

    def get_context_data(self, **kwargs):
        """Добавляет флаг is_owner в контекст шаблона."""
        context = super().get_context_data(**kwargs)
        context["is_owner"] = self.request.user == self.object
        return context


class UserPasswordChange(PasswordChangeView):
    """Изменение пароля пользователя."""

    form_class = UserPasswordChangeForm
    success_url = reverse_lazy("users:password_change_done")
    template_name = "user/password_change.html"
    extra_context = {"title": "Изменение пароля"}


class UserListView(ListView):
    """Список всех пользователей."""

    model = User
    template_name = "user/user_list.html"
    context_object_name = "users"
