from datetime import datetime
import hashlib
import secrets

from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.contrib.auth.hashers import make_password
from django.utils import timezone


def generate_hashed_confirm_token():
    return hashlib.sha256(secrets.token_urlsafe(32).encode("utf-8")).hexdigest()


class Employee(AbstractUser):
    username = models.CharField("Имя пользователя", max_length=150, unique=True)
    first_name = models.CharField("Имя", max_length=150, blank=True)
    last_name = models.CharField("Фамилия", max_length=150, blank=True)
    email = models.EmailField("Адрес электронной почты", blank=True)
    fathers_name = models.CharField("Отчество", max_length=100, blank=True)
    description = models.TextField("Описание", max_length=1000, blank=True)
    is_visible = models.BooleanField("Видимость", default=True)

    image = models.ImageField(
        "Изображение",
        upload_to='profile_pictures/',
        null=True,
        blank=True,
        default='profile_pictures/default/default.jpg'
    )

    ROLE_CHOICES = [
        (0, 'Владелец'),
        (1, 'Администратор'),
        (2, 'Доктор')
    ]
    role = models.IntegerField("Роль", choices=ROLE_CHOICES, default=2)

    def build_username(self):
        return f"{self.first_name}_{self.last_name}#{self.id}".strip()

    def save(self, *args, **kwargs):
        if self.password and not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)

        self.username = self.build_username()
        self.is_staff = True
        self.is_active = True
        self.is_superuser = self.role == 0
        if not self.date_joined:
            self.date_joined = timezone.now()

        super().save(*args, **kwargs)
        group_name = dict(self.ROLE_CHOICES).get(self.role)
        if group_name:
            group, _ = Group.objects.get_or_create(name=group_name)
            self.groups.clear()
            self.groups.add(group)

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"


class Procedure(models.Model):
    name = models.TextField("Название", max_length=70, blank=True)
    description = models.TextField("Описание", max_length=1000, blank=True)
    duration = models.IntegerField("Длительность (минуты)", default=30)
    is_visible = models.BooleanField("Видимость", default=True)

    def __str__(self):
        return self.name or "Процедура"

    class Meta:
        verbose_name = "Процедура"
        verbose_name_plural = "Процедуры"


class Service(models.Model):
    doctor_id = models.ForeignKey(Employee, verbose_name="Доктор", on_delete=models.CASCADE)
    procedure_id = models.ForeignKey(Procedure, verbose_name="Процедура", on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"


class Booking(models.Model):
    doctor_id = models.ForeignKey(Employee, verbose_name="Доктор", default=1, on_delete=models.SET_DEFAULT)
    procedure_id = models.ForeignKey(Procedure, verbose_name="Процедура", on_delete=models.CASCADE)
    date = models.DateField("Дата")
    time = models.TimeField("Время")
    name = models.CharField("Имя", max_length=50)
    phone = models.CharField("Телефон", max_length=20)
    email = models.CharField("Email", max_length=100)
    confirm_token = models.CharField("Токен подтверждения",
                                     max_length=64,
                                     unique=True,
                                     null=True,
                                     default=generate_hashed_confirm_token)

    @staticmethod
    def hash_confirm_token(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def generate_confirm_token_pair(cls):
        raw_token = secrets.token_urlsafe(32)
        return raw_token, cls.hash_confirm_token(raw_token)
    #ToDo add booking status

    def __str__(self):
        return f"{self.date} {self.time}"

    class Meta:
        verbose_name = "Запись"
        verbose_name_plural = "Записи"


class Timetable(models.Model):
    worker_id = models.ForeignKey(Employee, verbose_name="Сотрудник", on_delete=models.CASCADE)
    weekday = models.IntegerField("День недели", choices=[
        (0, 'Понедельник'),
        (1, 'Вторник'),
        (2, 'Среда'),
        (3, 'Четверг'),
        (4, 'Пятница'),
        (5, 'Суббота'),
        (6, 'Воскресенье')
    ])
    start_time = models.TimeField("Начало")
    end_time = models.TimeField("Окончание")

    class Meta:
        verbose_name = "Расписание"
        verbose_name_plural = "Расписания"


class Exception(models.Model):
    worker_id = models.ForeignKey(Employee, verbose_name="Сотрудник", on_delete=models.CASCADE)
    is_working = models.BooleanField("Рабочий день")
    date = models.DateField("Дата")
    start_time = models.TimeField("Начало")
    end_time = models.TimeField("Окончание")
    reason = models.TextField("Причина", max_length=1000)
    # ToDo check for overlapping exceptions

    class Meta:
        verbose_name = "Отгулы/Доп. Часы"
        verbose_name_plural = "Отгулы/Доп. Часы"


class Call(models.Model):
    name = models.CharField("Имя", max_length=50, blank=True)
    phone_number = models.TextField("Телефон", max_length=20)
    added = models.DateTimeField("Добавлен", default=timezone.now)
    status = models.IntegerField("Статус", choices=[
        (0, 'Открытый'),
        (1, 'Выполнен')
    ], default=0)

    class Meta:
        verbose_name = "Звонок"
        verbose_name_plural = "Звонки"


class Client(models.Model):
    name = models.CharField("Имя", max_length=100)
    email = models.EmailField("Email", unique=True, null=True, blank=True)
    phone_number = models.CharField("Телефон", max_length=20, unique=True, null=True, blank=True)
    ads_consent = models.BooleanField("Согласие на рекламу", default=False)
    ads_consent_given = models.DateTimeField("Согласие дано", null=True, blank=True)

    def __str__(self):
        phone = self.phone_number or "—"
        email = self.email or "—"
        return f"{self.name} <{phone}> {email}"

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"
