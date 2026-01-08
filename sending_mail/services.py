from django.core.mail import send_mail
from django.utils import timezone

from config.settings import EMAIL_HOST_USER


def send_message(pk, request=None):
    """
    Отправляет рассылку по требованию.

    Функция выполняет отправку email-рассылки с проверкой прав доступа,
    временных ограничений и статуса рассылки. Результат каждой попытки
    логируется в модели SendAttempt.
    """

    from sending_mail.models import Mailing, SendAttempt

    # Получение объекта рассылки
    mailing = Mailing.objects.get(pk=pk)
    now = timezone.now()

    # Проверка прав доступа (если передан request)
    if request and mailing.owner != request.user:
        attempt = SendAttempt.objects.create(
            mailing=mailing,
            status=SendAttempt.STATUS_UNSUCCES,
            server_response=f"ошибка отправки, вы не являетесь владельцем: {request.user.email}",
            attempt_datetime=now,
            owner=request.user,
        )
        return False, attempt

    # Подготовка данных для отправки
    topik = mailing.message.topik
    message = mailing.message.text
    recipient_list = [recipient.email for recipient in mailing.recipients.all()]

    # Проверка статуса рассылки
    if mailing.status == Mailing.STATUS_FINISHED:
        attempt = SendAttempt.objects.create(
            mailing=mailing,
            status=SendAttempt.STATUS_UNSUCCES,
            server_response="Рассылка уже завершена",
            attempt_datetime=now,
            owner=request.user if request else mailing.owner,
        )
        return False, attempt

    # Проверка временных ограничений
    elif now < mailing.started_at:
        attempt = SendAttempt.objects.create(
            mailing=mailing,
            status=SendAttempt.STATUS_UNSUCCES,
            server_response=f"Время рассылки еще не наступило (начало - {mailing.started_at}, сейчас - {now})",
            attempt_datetime=now,
            owner=request.user if request else mailing.owner,
        )
        return False, attempt

    elif now > mailing.finished_at:
        mailing.status = Mailing.STATUS_FINISHED
        mailing.save()
        attempt = SendAttempt.objects.create(
            mailing=mailing,
            status=SendAttempt.STATUS_UNSUCCES,
            server_response=f"Время рассылки уже прошло (конец - {mailing.finished_at}, сейчас - {now})",
            attempt_datetime=now,
            owner=request.user if request else mailing.owner,
        )
        return False, attempt

    # Проверка наличия получателей
    if not recipient_list:
        attempt = SendAttempt.objects.create(
            mailing=mailing,
            status=SendAttempt.STATUS_UNSUCCES,
            server_response="Нет получателей рассылки",
            attempt_datetime=now,
            owner=request.user if request else mailing.owner,
        )
        return False, attempt

    # Отправка email
    try:
        send_mail(
            subject=topik,
            message=message,
            from_email=EMAIL_HOST_USER,
            recipient_list=recipient_list,
            fail_silently=False,
        )

        # Логирование успешной попытки
        attempt = SendAttempt.objects.create(
            mailing=mailing,
            status=SendAttempt.STATUS_SUCCESS,
            server_response="Рассылка отправлена",
            attempt_datetime=now,
            owner=request.user if request else mailing.owner,
        )

        # Обновление статуса рассылки, если она только что запущена
        if mailing.status == Mailing.STATUS_CREATED:
            mailing.status = Mailing.STATUS_STARTED
            mailing.save()

        return True, attempt

    except Exception as e:
        # Логирование ошибки отправки
        attempt = SendAttempt.objects.create(
            mailing=mailing,
            status=SendAttempt.STATUS_UNSUCCES,
            server_response=str(e),
            attempt_datetime=now,
            owner=request.user if request else mailing.owner,
        )
        return False, attempt
