import csv
import json
from datetime import timedelta
from io import StringIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import DetailView, ListView, TemplateView
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from sending_mail.forms import MailingForm, MailingManagerForm, MessageForm, RecipientForm
from sending_mail.models import Mailing, Message, Recipient, SendAttempt
from sending_mail.services import send_message
from user.models import User


@require_GET
def check_email_duplicate(request):
    """Проверяет, существует ли email в базе данных."""
    email = request.GET.get('email', '')
    exclude_id = request.GET.get('exclude', '')

    if not email:
        return JsonResponse({'exists': False})

    queryset = Recipient.objects.filter(email=email)

    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)

    exists = queryset.exists()

    return JsonResponse({
        'exists': exists,
        'count': queryset.count()
    })


@method_decorator(login_required, name='dispatch')
class HomeView(TemplateView):
    template_name = 'sending_mail/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Основная статистика
        mailings_qs = Mailing.objects.all()
        recipients_qs = Recipient.objects.values('email').distinct()

        # Фильтрация для обычных пользователей
        if not self.request.user.is_superuser:
            mailings_qs = mailings_qs.filter(owner=self.request.user)
            recipients_qs = recipients_qs.filter(owner=self.request.user)

        context['mailings'] = mailings_qs.count()
        context['started_mailings'] = mailings_qs.filter(
            status=Mailing.STATUS_STARTED
        ).count()
        context['recipients'] = recipients_qs.count()

        # Рассчитать процент успешных отправок
        send_attempts_qs = SendAttempt.objects.all()
        if not self.request.user.is_superuser:
            send_attempts_qs = send_attempts_qs.filter(owner=self.request.user)

        total_attempts = send_attempts_qs.count()
        successful_attempts = send_attempts_qs.filter(
            status=SendAttempt.STATUS_SUCCESS
        ).count()

        if total_attempts > 0:
            context['success_rate'] = round((successful_attempts / total_attempts) * 100)
        else:
            context['success_rate'] = 0

        # Недавняя активность (последние 5 действий)
        if self.request.user.is_authenticated:
            recent_activity = []

            # Последние рассылки пользователя
            user_mailings = Mailing.objects.filter(owner=self.request.user).order_by('-created_at')[:3]
            for mailing in user_mailings:
                recent_activity.append({
                    'title': f'Рассылка "{mailing.message.topik[:30]}"',
                    'description': f'Статус: {mailing.get_status_display()}',
                    'time': mailing.created_at.strftime('%H:%M'),
                    'icon': 'fas fa-paper-plane',
                    'color': '#4361ee'
                })

            # Последние попытки отправки
            recent_attempts = SendAttempt.objects.filter(
                owner=self.request.user
            ).order_by('-attempt_datetime')[:2]

            for attempt in recent_attempts:
                recent_activity.append({
                    'title': 'Отправка письма',
                    'description': f'Статус: {attempt.get_status_display()}',
                    'time': attempt.attempt_datetime.strftime('%H:%M'),
                    'icon': 'fas fa-envelope',
                    'color': attempt.status == SendAttempt.STATUS_SUCCESS and '#2ecc71' or '#e74c3c'
                })

            context['recent_activity'] = recent_activity

        return context


class MessageCreateView(LoginRequiredMixin, CreateView):
    """Контроллер для создания сообщения"""

    model = Message
    form_class = MessageForm
    template_name = "sending_mail/message_form.html"
    success_url = reverse_lazy("sending_mail:message_list")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class MessageDetailView(LoginRequiredMixin, DetailView):
    """Контроллер для просмотра сообщения"""

    model = Message
    template_name = "sending_mail/message_form.html"
    context_object_name = "message"

    def get_queryset(self):
        """Фильтруем сообщения по владельцу для обычных пользователей"""
        queryset = Message.objects.all()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(owner=self.request.user)
        return queryset


class MessageListView(LoginRequiredMixin, ListView):
    """Контроллер для просмотра списка сообщений"""

    model = Message
    template_name = "sending_mail/message_list.html"
    context_object_name = "messages"

    def get_queryset(self):
        """Фильтруем сообщения по владельцу для обычных пользователей"""
        queryset = Message.objects.all()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(owner=self.request.user)
        return queryset.order_by('-id')


class MessageUpdateView(LoginRequiredMixin, UpdateView):
    """Контроллер для редактирования сообщения"""

    model = Message
    form_class = MessageForm
    template_name = "sending_mail/message_form.html"
    success_url = reverse_lazy("sending_mail:message_list")

    def get_queryset(self):
        """Фильтруем сообщения по владельцу для обычных пользователей"""
        queryset = Message.objects.all()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(owner=self.request.user)
        return queryset

    def form_valid(self, form):
        # Сохраняем текущего владельца
        form.instance.owner = self.object.owner  # Сохраняем оригинального владельца
        return super().form_valid(form)


class MessageDeleteView(LoginRequiredMixin, DeleteView):
    """Контроллер для удаления сообщения"""

    model = Message
    template_name = "sending_mail/message_confirm_delete.html"
    success_url = reverse_lazy("sending_mail:message_list")

    def get_queryset(self):
        """Фильтруем сообщения по владельцу для обычных пользователей"""
        queryset = Message.objects.all()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(owner=self.request.user)
        return queryset

    def post(self, request, *args, **kwargs):
        message = get_object_or_404(Message, id=kwargs.get("pk"))
        user = self.request.user
        if user != message.owner and not user.is_superuser:  # Разрешаем суперпользователям
            return HttpResponseForbidden("У вас нет прав для удаления сообщения")
        message.delete()
        return redirect("sending_mail:message_list")

    def form_valid(self, form):
        return super().form_valid(form)


class RecipientListView(LoginRequiredMixin, ListView):
    model = Recipient
    template_name = 'sending_mail/recipient_list.html'
    context_object_name = 'recipients'
    paginate_by = 20

    def get_queryset(self):
        queryset = Recipient.objects.all()

        # Фильтрация для обычных пользователей
        if not self.request.user.is_superuser and not self.request.user.has_perm('sending_mail.can_view_recipient'):
            queryset = queryset.filter(owner=self.request.user)

        # Фильтрация по email
        email = self.request.GET.get('email')
        if email:
            queryset = queryset.filter(email__icontains=email)

        # Фильтрация по имени
        name = self.request.GET.get('name')
        if name:
            queryset = queryset.filter(recipient_name__icontains=name)

        # Фильтрация по владельцу (только для суперпользователей)
        if self.request.user.is_superuser:
            owner_id = self.request.GET.get('owner')
            if owner_id:
                queryset = queryset.filter(owner_id=owner_id)

        return queryset.select_related('owner').order_by('-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Статистика
        context['recipients_count'] = self.get_queryset().count()

        # Для обычных пользователей считаем только своих получателей
        if not self.request.user.is_superuser:
            context['active_recipients'] = Recipient.objects.filter(
                owner=self.request.user
            ).count()
        else:
            context['active_recipients'] = Recipient.objects.count()

        # Уникальные владельцы для фильтра
        if self.request.user.is_superuser:
            context['owners'] = User.objects.filter(
                recipient__isnull=False
            ).distinct().annotate(
                recipient_count=Count('recipient')
            ).order_by('username')
            context['unique_owners'] = context['owners'].count()

        return context


class RecipientCreateView(LoginRequiredMixin, CreateView):
    """Контроллер для создания профиля нового получателя рассылки"""

    model = Recipient
    form_class = RecipientForm
    template_name = "sending_mail/recipient_form.html"
    success_url = reverse_lazy("sending_mail:recipient_list")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class RecipientDetailView(LoginRequiredMixin, DetailView):
    """Контроллер для просмотра профиля получателя рассылки"""

    model = Recipient
    template_name = "sending_mail/recipient.html"
    context_object_name = "recipient"

    def get_queryset(self):
        """Фильтруем получателей по владельцу для обычных пользователей"""
        queryset = Recipient.objects.all()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(owner=self.request.user)
        return queryset


class RecipientUpdateView(LoginRequiredMixin, UpdateView):
    """Контроллер для редактирования профиля получателя рассылки"""

    model = Recipient
    form_class = RecipientForm
    template_name = "sending_mail/recipient_form.html"
    success_url = reverse_lazy("sending_mail:recipient_list")

    def get_queryset(self):
        """Фильтруем получателей по владельцу для обычных пользователей"""
        queryset = Recipient.objects.all()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(owner=self.request.user)
        return queryset

    def form_valid(self, form):
        # Сохраняем текущего владельца
        form.instance.owner = self.object.owner  # Сохраняем оригинального владельца
        return super().form_valid(form)


class RecipientDeleteView(LoginRequiredMixin, DeleteView):
    """Контроллер для удаления профиля получателя рассылки"""

    model = Recipient
    template_name = "sending_mail/recipient_confirm_delete.html"
    success_url = reverse_lazy("sending_mail:recipient_list")

    def get_queryset(self):
        """Фильтруем получателей по владельцу для обычных пользователей"""
        queryset = Recipient.objects.all()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(owner=self.request.user)
        return queryset

    def post(self, request, *args, **kwargs):
        recipient = get_object_or_404(Recipient, id=kwargs.get("pk"))
        user = self.request.user
        if user != recipient.owner and not user.is_superuser:  # Разрешаем суперпользователям
            return HttpResponseForbidden("У вас нет прав для удаления профиля получателя рассылки")
        recipient.delete()
        return redirect("sending_mail:recipient_list")

    def form_valid(self, form):
        return super().form_valid(form)


class MailingListView(LoginRequiredMixin, ListView):
    model = Mailing
    template_name = 'sending_mail/mailing_template_list.html'
    context_object_name = 'mailings'
    paginate_by = 12

    def get_queryset(self):
        queryset = Mailing.objects.all()

        # Фильтрация для обычных пользователей
        if not self.request.user.is_superuser and not self.request.user.has_perm('sending_mail.can_view_mailing'):
            queryset = queryset.filter(owner=self.request.user)

        # Поиск по теме сообщения
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(message__topik__icontains=search)

        # Фильтрация по статусу
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Фильтрация по дате
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if start_date:
            queryset = queryset.filter(started_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(finished_at__date__lte=end_date)

        # Фильтрация по владельцу (только для суперпользователей)
        if self.request.user.is_superuser:
            owner_id = self.request.GET.get('owner')
            if owner_id:
                queryset = queryset.filter(owner_id=owner_id)

        return queryset.select_related('message', 'owner').prefetch_related('recipients').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Статистика
        queryset = self.get_queryset()
        context['total_mailings'] = queryset.count()
        context['created_mailings'] = queryset.filter(status='создана').count()
        context['started_mailings'] = queryset.filter(status='запущена').count()
        context['finished_mailings'] = queryset.filter(status='завершена').count()

        # Уникальные владельцы для фильтра
        if self.request.user.is_superuser:
            context['owners'] = User.objects.filter(
                mailing__isnull=False
            ).distinct().annotate(
                mailing_count=Count('mailing')
            ).order_by('username')

        return context


class MailingDetailView(LoginRequiredMixin, DetailView):
    """Контроллер для просмотра рассылки"""

    model = Mailing
    template_name = "sending_mail/mailing.html"
    context_object_name = "mailing"

    def get_queryset(self):
        """Фильтруем рассылки по владельцу для обычных пользователей"""
        queryset = Mailing.objects.all()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(owner=self.request.user)
        return queryset


class MailingCreateView(LoginRequiredMixin, CreateView):
    """Контроллер для создания рассылки"""

    model = Mailing
    form_class = MailingForm
    template_name = "sending_mail/mailing_form.html"
    success_url = reverse_lazy("sending_mail:mailing_list")

    def get_form_kwargs(self):
        """Передаем пользователя в форму"""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class MailingUpdateView(LoginRequiredMixin, UpdateView):
    """Контроллер для редактирования рассылки"""

    model = Mailing
    form_class = MailingForm
    template_name = "sending_mail/mailing_form.html"
    context_object_name = "mailing"
    success_url = reverse_lazy("sending_mail:mailing_list")

    def get_queryset(self):
        """Фильтруем рассылки по владельцу для обычных пользователей"""
        queryset = Mailing.objects.all()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(owner=self.request.user)
        return queryset

    def get_form_class(self):
        user = self.request.user
        if user == self.object.owner or user.is_superuser:  # Разрешаем суперпользователям
            return MailingForm
        if user.has_perm("mailing.can_finished_mailing"):
            return MailingManagerForm
        else:
            raise PermissionDenied("У вас нет прав для редактирования этой рассылки")

    def form_valid(self, form):
        # Сохраняем текущего владельца
        form.instance.owner = self.object.owner  # Сохраняем оригинального владельца
        return super().form_valid(form)


class MailingDeleteView(LoginRequiredMixin, DeleteView):
    """Контроллер для удаления рассылки"""

    model = Mailing
    template_name = "sending_mail/mailing_confirm_delete.html"
    success_url = reverse_lazy("sending_mail:mailing_list")

    def get_queryset(self):
        """Фильтруем рассылки по владельцу для обычных пользователей"""
        queryset = Mailing.objects.all()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(owner=self.request.user)
        return queryset

    def post(self, request, *args, **kwargs):
        mailing = get_object_or_404(Mailing, id=kwargs.get("pk"))
        user = self.request.user
        if user != mailing.owner and not user.is_superuser:  # Разрешаем суперпользователям
            return HttpResponseForbidden("У вас нет прав для удаления рассылки")
        mailing.delete()
        return redirect("sending_mail:mailing_list")

    def form_valid(self, form):
        return super().form_valid(form)


class SendAttemptListView(LoginRequiredMixin, ListView):
    """Контроллер для отображения списка попыток рассылки"""

    model = SendAttempt
    template_name = "sending_mail/send_attempt_list.html"
    context_object_name = "attempts"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attempts = self.get_queryset()
        context["total_attempts"] = attempts.count()
        context["successful_attempts"] = attempts.filter(status="успешно").count()
        context["unsucessful_attempts"] = attempts.filter(status="не успешно").count()
        context["sending_mails"] = 0
        context["sending_mails"] = sum(
            attempt.mailing.recipients.count() for attempt in attempts.filter(status="успешно")
        )
        return context

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Вы не авторизованы")

        cache_key = f"mailings_attempts_user_{self.request.user.pk}"
        queryset = cache.get(cache_key)
        if not queryset:
            queryset = SendAttempt.objects.filter(owner=self.request.user).order_by("attempt_datetime")
            cache.set(cache_key, queryset, 60 * 15)
        return queryset


class SendAttemptDetailView(LoginRequiredMixin, DetailView):
    """Контроллер для отображения информации о попытке рассылки"""

    model = SendAttempt
    template_name = "sending_mail/send_attempt.html"
    context_object_name = "attempt"

    def get_queryset(self):
        """Фильтруем попытки отправки по владельцу для обычных пользователей"""
        queryset = SendAttempt.objects.all()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(owner=self.request.user)
        return queryset


class SendMailingView(View):
    """Контроллер для отправки рассылки"""

    def get(self, request, pk):
        # Фильтруем рассылки по владельцу
        mailing_qs = Mailing.objects.all()
        if not request.user.is_superuser:
            mailing_qs = mailing_qs.filter(owner=request.user)

        mailing = get_object_or_404(mailing_qs, pk=pk)

        success, attempt = send_message(mailing.pk, request)

        if success:
            messages.success(request, "Рассылка успешно отправлена!")
        else:
            messages.error(request, "Рассылка не отправлена. Проверьте детали.")

        context = {
            "success": success,
            "mailing": mailing,
            "attempt": attempt,
        }

        return render(request, "sending_mail/send_mailing.html", context)


@login_required
@require_GET
def recipient_stats(request):
    """Возвращает статистику получателей в JSON формате."""
    try:
        # Для обычных пользователей считаем только своих получателей
        if not request.user.is_superuser:
            total = Recipient.objects.filter(owner=request.user).count()
            active = total
            unique_owners = 1  # Только текущий пользователь
        else:
            total = Recipient.objects.count()
            active = total
            unique_owners = User.objects.filter(
                recipient__isnull=False
            ).distinct().count()

        return JsonResponse({
            'success': True,
            'total': total,
            'active': active,
            'unique_owners': unique_owners
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_GET
def export_recipients_csv(request):
    """Экспорт получателей в CSV формате."""
    try:
        # Получаем IDs из запроса
        ids_param = request.GET.get('ids', '')
        if ids_param:
            ids = [int(id) for id in ids_param.split(',') if id.isdigit()]
            recipients = Recipient.objects.filter(id__in=ids)
        else:
            # Экспорт всех получателей
            if request.user.is_superuser:
                recipients = Recipient.objects.all()
            else:
                recipients = Recipient.objects.filter(owner=request.user)

        # Создаем HTTP ответ с CSV
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="recipients.csv"'

        # Создаем CSV writer
        writer = csv.writer(response, delimiter=';')

        # Записываем заголовки
        headers = ['Email', 'ФИО', 'Комментарий', 'Владелец', 'Дата создания']
        if request.user.is_superuser:
            headers.append('ID')
        writer.writerow(headers)

        # Записываем данные
        for recipient in recipients.select_related('owner'):
            row = [
                recipient.email,
                recipient.recipient_name or '',
                recipient.comment or '',
                recipient.owner.username if recipient.owner else '',
                recipient.owner.email if recipient.owner else ''
            ]

            if request.user.is_superuser:
                row.append(str(recipient.id))

            writer.writerow(row)

        return response

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def bulk_delete_recipients(request):
    """Массовое удаление получателей."""
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])

        if not ids:
            return JsonResponse({
                'success': False,
                'error': 'Не указаны ID получателей'
            })

        # Получаем получателей
        recipients = Recipient.objects.filter(id__in=ids)

        # Проверяем права
        if not request.user.is_superuser:
            # Проверяем, что все получатели принадлежат пользователю
            for recipient in recipients:
                if recipient.owner != request.user:
                    return JsonResponse({
                        'success': False,
                        'error': 'Нет прав на удаление некоторых получателей'
                    })

        # Удаляем
        deleted_count = recipients.count()
        recipients.delete()

        return JsonResponse({
            'success': True,
            'deleted': deleted_count,
            'message': f'Удалено {deleted_count} получателей'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат JSON'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def bulk_change_owner(request):
    """Массовое изменение владельца получателей."""
    try:
        if not request.user.is_superuser:
            return JsonResponse({
                'success': False,
                'error': 'Только администраторы могут изменять владельца'
            })

        data = json.loads(request.body)
        ids = data.get('ids', [])
        new_owner_username = data.get('owner', '')

        if not ids:
            return JsonResponse({
                'success': False,
                'error': 'Не указаны ID получателей'
            })

        if not new_owner_username:
            return JsonResponse({
                'success': False,
                'error': 'Не указан новый владелец'
            })

        # Находим нового владельца
        try:
            new_owner = User.objects.get(username=new_owner_username)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Пользователь {new_owner_username} не найден'
            })

        # Получаем получателей
        recipients = Recipient.objects.filter(id__in=ids)

        # Обновляем владельца
        updated_count = recipients.count()

        with transaction.atomic():
            recipients.update(owner=new_owner)

        return JsonResponse({
            'success': True,
            'updated': updated_count,
            'message': f'Изменен владелец для {updated_count} получателей'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат JSON'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_GET
def mailing_stats(request):
    """Возвращает статистику рассылок в JSON формате."""
    try:
        queryset = Mailing.objects.all()

        if not request.user.is_superuser:
            queryset = queryset.filter(owner=request.user)

        return JsonResponse({
            'success': True,
            'total': queryset.count(),
            'created': queryset.filter(status='создана').count(),
            'started': queryset.filter(status='запущена').count(),
            'finished': queryset.filter(status='завершена').count(),
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_GET
def check_expiring(request):
    """Проверяет рассылки, которые скоро завершатся."""
    try:
        queryset = Mailing.objects.filter(
            status='запущена',
            finished_at__isnull=False
        )

        if not request.user.is_superuser:
            queryset = queryset.filter(owner=request.user)

        # Рассылки, которые завершатся в ближайшие 24 часа
        now = timezone.now()
        next_24_hours = now + timedelta(hours=24)

        expiring = queryset.filter(
            finished_at__range=[now, next_24_hours]
        ).count()

        return JsonResponse({
            'success': True,
            'expiring_count': expiring,
            'next_check': (now + timedelta(minutes=5)).isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def message_duplicate(request, pk):
    """Дублирование шаблона сообщения."""
    try:
        # Фильтруем сообщения по владельцу
        messages_qs = Message.objects.all()
        if not request.user.is_superuser:
            messages_qs = messages_qs.filter(owner=request.user)

        original = messages_qs.get(pk=pk)

        # Проверка прав
        if original.owner != request.user and not request.user.is_superuser:
            return JsonResponse({
                'success': False,
                'error': 'Нет прав на дублирование этого шаблона'
            })

        # Создание копии
        copy = Message.objects.create(
            topik=f"{original.topik} (копия)",
            text=original.text,
            owner=request.user,  # Новый владелец - текущий пользователь
            category=original.category,
            tags=original.tags
        )

        return JsonResponse({
            'success': True,
            'new_id': copy.pk,
            'message': 'Шаблон успешно скопирован'
        })

    except Message.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Шаблон не найден'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def import_templates(request):
    """Импорт шаблонов из файла."""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'Файл не загружен'
            })

        file = request.FILES['file']
        category = request.POST.get('category', '')

        imported_count = 0
        errors = []

        # Обработка JSON файла
        if file.name.endswith('.json'):
            data = json.loads(file.read().decode('utf-8'))

            if not isinstance(data, list):
                data = [data]

            for item in data:
                try:
                    Message.objects.create(
                        topik=item.get('topik', 'Без названия'),
                        text=item.get('text', ''),
                        owner=request.user,
                        category=category or item.get('category', ''),
                        tags=item.get('tags', '')
                    )
                    imported_count += 1
                except Exception as e:
                    errors.append(str(e))

        # Обработка CSV файла
        elif file.name.endswith('.csv'):
            content = file.read().decode('utf-8-sig')
            reader = csv.DictReader(StringIO(content), delimiter=';')

            for row in reader:
                try:
                    Message.objects.create(
                        topik=row.get('topik', row.get('title', 'Без названия')),
                        text=row.get('text', row.get('content', '')),
                        owner=request.user,
                        category=category or row.get('category', ''),
                        tags=row.get('tags', '')
                    )
                    imported_count += 1
                except Exception as e:
                    errors.append(str(e))

        else:
            return JsonResponse({
                'success': False,
                'error': 'Неподдерживаемый формат файла'
            })

        return JsonResponse({
            'success': True,
            'count': imported_count,
            'errors': errors if errors else None
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def import_templates_text(request):
    """Импорт шаблонов из текста."""
    try:
        data = json.loads(request.body)
        text = data.get('text', '')
        category = data.get('category', '')

        if not text:
            return JsonResponse({
                'success': False,
                'error': 'Текст для импорта пуст'
            })

        imported_count = 0

        # Попробуем распарсить как JSON
        try:
            templates = json.loads(text)
            if not isinstance(templates, list):
                templates = [templates]

            for item in templates:
                Message.objects.create(
                    topik=item.get('topik', 'Без названия'),
                    text=item.get('text', ''),
                    owner=request.user,
                    category=category or item.get('category', ''),
                    tags=item.get('tags', '')
                )
                imported_count += 1

        # Если не JSON, пробуем CSV
        except json.JSONDecodeError:
            reader = csv.DictReader(StringIO(text), delimiter=';')

            for row in reader:
                Message.objects.create(
                    topik=row.get('topik', row.get('title', 'Без названия')),
                    text=row.get('text', row.get('content', '')),
                    owner=request.user,
                    category=category or row.get('category', ''),
                    tags=row.get('tags', '')
                )
                imported_count += 1

        return JsonResponse({
            'success': True,
            'count': imported_count
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def message_stats(request):
    """Статистика по шаблонам."""
    try:
        total = Message.objects.count()
        my_templates = Message.objects.filter(owner=request.user).count()

        # Подсчет использования (если есть связь с рассылками)
        from django.db.models import Count
        used_count = Message.objects.filter(
            mailings__isnull=False
        ).distinct().count()

        return JsonResponse({
            'success': True,
            'total': total,
            'my_templates': my_templates,
            'used_count': used_count
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })