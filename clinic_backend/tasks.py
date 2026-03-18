from celery import shared_task

from clinic_backend.models import Booking

from django.utils import timezone
import logging
logger = logging.getLogger(__name__)

@shared_task
def booking_link_deactivation():
    now = timezone.now()

    logger.info(f"Started booking link deactivation at {now}")

    expired = Booking.objects.filter(
        date__lt=now.date()
    ) | Booking.objects.filter(
        date=now.date(),
        time__lt=now.time()
    )

    expired.update(confirm_token=None)

    logger.info(f"Finished booking link deactivation")