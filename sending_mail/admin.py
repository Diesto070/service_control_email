from django.contrib import admin

from .models import Mailing, Message, Recipient, SendAttempt


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "recipient_name",
    )
    search_fields = (
        "email",
        "recipient_name",
        "comment",
    )
    list_filter = ("owner",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "topik",
        "owner",
    )
    search_fields = (
        "topik",
        "text",
        "owner",
    )
    list_filter = ("owner",)


@admin.register(Mailing)
class MailingAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "message",
        "owner",
    )
    search_fields = (
        "message",
        "owner",
        "status",
    )
    list_filter = (
        "owner",
        "status",
    )


@admin.register(SendAttempt)
class SendAttemptAdmin(admin.ModelAdmin):
    list_display = ("pk", "mailing", "attempt_datetime", "status", "owner")
    search_fields = (
        "mailing",
        "attempt_datetime",
    )
    list_filter = (
        "owner",
        "status",
    )
