from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from celery import shared_task
import logging
logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def send_booking_created_email(to_email, confirm_url, *, date, time, doctor, procedure):
    subject = "Подтверждение записи"

    text = (
        f"Ваша запись создана.\n\n"
        f"Дата: {date}\n"
        f"Время: {time}\n"
        f"Врач: {doctor}\n"
        f"Услуга: {procedure}\n\n"
        f"Детали: {confirm_url}\n"
    )

    html = f"""
    <h2>Подтверждение записи</h2>
    <p><b>Дата:</b> {date}</p>
    <p><b>Время:</b> {time}</p>
    <p><b>Врач:</b> {doctor}</p>
    <p><b>Услуга:</b> {procedure}</p>
    <br>
    <a href="{confirm_url}" style="padding:12px 20px;background:#2563eb;color:white;text-decoration:none;border-radius:6px;">
        Открыть запись
    </a>
    """

    msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to_email])
    msg.attach_alternative(html, "text/html")
    try:
        msg.send()
    except Exception:
        logger.exception("SMTP send failed")