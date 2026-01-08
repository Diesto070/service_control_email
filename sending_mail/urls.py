from django.urls import path

from sending_mail import views
from sending_mail.apps import SendingMailConfig

app_name = SendingMailConfig.name

urlpatterns = [
    # Главная страница
    path("", views.HomeView.as_view(), name="home"),
    # Маршруты для работы с сообщениями
    path('check-email-duplicate/', views.check_email_duplicate, name='check_email_duplicate'),
    path("message_new/", views.MessageCreateView.as_view(), name="message_new"),
    path("message/<int:pk>/", views.MessageDetailView.as_view(), name="message"),
    path("message_list/", views.MessageListView.as_view(), name="message_list"),
    path("message_edit/<int:pk>/", views.MessageUpdateView.as_view(), name="message_edit"),
    path("message_delete/<int:pk>/", views.MessageDeleteView.as_view(), name="message_delete"),
    # API для шаблонов
    path('message/<int:pk>/duplicate/', views.message_duplicate, name='message_duplicate'),
    path('message/import/', views.import_templates, name='import_templates'),
    path('message/import-text/', views.import_templates_text, name='import_templates_text'),
    path('message/stats/', views.message_stats, name='message_stats'),

    # Маршруты для работы с получателями
    path("recipient_list/", views.RecipientListView.as_view(), name="recipient_list"),
    path("recipient_new/", views.RecipientCreateView.as_view(), name="recipient_new"),
    path("recipient/<int:pk>/", views.RecipientDetailView.as_view(), name="recipient"),
    path("recipient_edit/<int:pk>/", views.RecipientUpdateView.as_view(), name="recipient_edit"),
    path("recipient_delete/<int:pk>/", views.RecipientDeleteView.as_view(), name="recipient_delete"),
    path('recipient/stats/', views.recipient_stats, name='recipient_stats'),
    path('recipient/export-csv/', views.export_recipients_csv, name='export_recipients_csv'),
    path('recipient/bulk-delete/', views.bulk_delete_recipients, name='bulk_delete_recipients'),
    path('recipient/bulk-change-owner/', views.bulk_change_owner, name='bulk_change_owner'),
    # Маршруты для работы с рассылками
    path("mailing_list/", views.MailingListView.as_view(), name="mailing_list"),
    path("mailing/<int:pk>/", views.MailingDetailView.as_view(), name="mailing"),
    path("mailing_new/", views.MailingCreateView.as_view(), name="mailing_new"),
    path("mailing_edit/<int:pk>/", views.MailingUpdateView.as_view(), name="mailing_edit"),
    path("mailing_delete/<int:pk>/", views.MailingDeleteView.as_view(), name="mailing_delete"),
    path('mailing_list/', views.MailingListView.as_view(), name='mailing_list'),
    path('api/mailing/stats/', views.mailing_stats, name='mailing_stats'),
    path('api/mailing/check-expiring/', views.check_expiring, name='check_expiring'),
    # Маршруты для работы с попытками отправки
    path("send_attempt_list/", views.SendAttemptListView.as_view(), name="send_attempt_list"),
    path("send_attempt/<int:pk>/", views.SendAttemptDetailView.as_view(), name="send_attempt"),
    # Отправка рассылки по требованию
    path("send_mailing/<int:pk>/", views.SendMailingView.as_view(), name="send_mailing"),
]
