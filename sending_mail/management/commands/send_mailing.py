from django.core.management import BaseCommand
from django.utils import timezone

from sending_mail.services import send_message


class Command(BaseCommand):
    help = "Send current mailings"

    def handle(self, *args, **options):
        from mailing.models import Mailing

        now = timezone.now()
        success_count = 0
        error_count = 0

        try:
            mailings = Mailing.objects.filter(
                started_at__lte=now,
                finished_at__gte=now,
                status__in=[Mailing.STATUS_CREATED, Mailing.STATUS_STARTED],
            )

            for mailing in mailings:
                success, attempt = send_message(mailing.pk)

                if success:
                    success_count += 1
                    if mailing.status == Mailing.STATUS_CREATED:
                        mailing.status = Mailing.STATUS_STARTED
                        mailing.save()
                else:
                    error_count += 1

            self.stdout.write(
                self.style.SUCCESS(f"Рассылки отправлены. Успешно: {success_count}, Ошибок: {error_count}")
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка: {str(e)}"))
