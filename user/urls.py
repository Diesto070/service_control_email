from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.urls import path, reverse_lazy

from user import views
from user.apps import UserConfig
from user.forms import CustomAuthenticationForm

app_name = UserConfig.name

urlpatterns = [
    # Регистрация и аутентификация
    path("register/", views.RegisterView.as_view(), name="register"),
    path(
        "login/",
        LoginView.as_view(form_class=CustomAuthenticationForm, template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", LogoutView.as_view(next_page="sending_mail:home"), name="logout"),
    # Профиль пользователя
    path("user_info/<int:pk>/", views.UserDetailView.as_view(), name="user_info"),
    path("user_form/<int:pk>/", views.UserUpdateView.as_view(), name="user_form"),
    # Управление паролем
    path("user_form/password/", views.UserPasswordChange.as_view(), name="password"),
    path("password_change/", views.UserPasswordChange.as_view(), name="password_change"),
    path(
        "password_change/done/",
        PasswordChangeDoneView.as_view(template_name="user/password_change_done.html"),
        name="password_change_done",
    ),
    # Сброс пароля
    path(
        "password_reset/",
        PasswordResetView.as_view(
            template_name="user/password_reset_form.html",
            email_template_name="user/password_reset_email.html",
            success_url=reverse_lazy("user:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password_reset_done/",
        PasswordResetDoneView.as_view(template_name="user/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "password_reset/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(
            template_name="users/password_reset_confirm.html",
            success_url=reverse_lazy("user:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password_reset/complete/",
        PasswordResetCompleteView.as_view(template_name="user/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    # Список пользователей
    path("user_list/", views.UserListView.as_view(), name="user_list"),
]
