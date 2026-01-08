from django import forms
from sending_mail.models import Mailing, Message, Recipient


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"


class MessageForm(forms.ModelForm):
    """Форма для создания нового сообщения"""

    class Meta:
        model = Message
        fields = [
            "topik",
            "text",
        ]
        exclude = [
            "owner",
        ]

    def __init__(self, *args, **kwargs):
        super(MessageForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
        self.fields["topik"].widget.attrs.update(
            {
                "placeholder": "Тема письма",
            }
        )
        self.fields["text"].widget.attrs.update({"placeholder": "Текст письма"})


class RecipientForm(forms.ModelForm):
    """Форма для создания нового получателя рассылки"""

    class Meta:
        model = Recipient
        fields = [
            "email",
            "recipient_name",
            "comment",
        ]
        exclude = [
            "owner",
        ]

    def __init__(self, *args, **kwargs):
        super(RecipientForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
        self.fields["email"].widget.attrs.update(
            {
                "placeholder": "Почта получателя",
            }
        )
        self.fields["recipient_name"].widget.attrs.update({"placeholder": "ФИО получателя"})
        self.fields["comment"].widget.attrs.update({"placeholder": "Комментарий"})


class MailingForm(forms.ModelForm):
    """Форма для создания новой рассылки"""

    class Meta:
        model = Mailing
        fields = [
            "message",
            "recipients",
            "status",
            "started_at",
            "finished_at",
        ]
        exclude = []
        widgets = {
            "recipients": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)  # Получаем пользователя из view
        super(MailingForm, self).__init__(*args, **kwargs)

        if self.user:
            self.fields["message"].queryset = Message.objects.filter(owner=self.user)
            self.fields["recipients"].queryset = Recipient.objects.filter(owner=self.user)

        self.fields["message"].lable = "Сообщение"
        self.fields["started_at"].help_text = (
            "Обязательное поле! Введите дату и время начала рассылки в формате: ДД.ММ.ГГГГ ЧЧ:ММ:СС"
        )
        self.fields["finished_at"].help_text = (
            "Обязательное поле! Введите дату и время завершения рассылки в формате: ДД.ММ.ГГГГ ЧЧ:ММ:СС"
        )


class MailingManagerForm(forms.ModelForm):
    """Форма редактирования рассылки для менеджера"""

    class Meta:
        model = Mailing
        fields = [
            "status",
        ]
