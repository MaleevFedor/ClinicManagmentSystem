from datetime import datetime, time, timedelta

from django import forms
from django.contrib import admin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from .api import appointment_slots
from .models import Employee, Service, Booking, Timetable, Exception, Procedure, Call, Client


class ClinicAdminSite(admin.AdminSite):
    site_header = "Clinic Management"
    site_title = "Clinic Admin"
    index_title = "Обзор"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("overview/", self.admin_view(self.overview_view), name="overview"),
            path("add-booking/", self.admin_view(self.add_booking_view), name="add_booking"),
            path(
                "add-booking/procedures/",
                self.admin_view(self.booking_procedures_feed),
                name="add_booking_procedures",
            ),
            path(
                "add-booking/slots/",
                self.admin_view(self.booking_slots_feed),
                name="add_booking_slots",
            ),
            path("overview/calls/", self.admin_view(self.calls_feed), name="overview_calls"),
            path(
                "overview/calls/<int:call_id>/complete/",
                self.admin_view(self.complete_call),
                name="overview_call_complete",
            ),
        ]
        return custom_urls + urls

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        overview_app = {
            "name": "Обзор",
            "app_label": "overview",
            "app_url": reverse("admin:overview"),
            "has_module_perms": True,
            "models": [
                {
                    "name": "Обзор",
                    "object_name": "Overview",
                    "admin_url": reverse("admin:overview"),
                    "add_url": None,
                    "view_only": True,
                }
            ],
        }
        add_booking_app = {
            "name": "Добавить запись",
            "app_label": "add_booking",
            "app_url": reverse("admin:add_booking"),
            "has_module_perms": True,
            "models": [
                {
                    "name": "Добавить запись",
                    "object_name": "AddBooking",
                    "admin_url": reverse("admin:add_booking"),
                    "add_url": None,
                    "view_only": True,
                }
            ],
        }
        return [overview_app, add_booking_app, *app_list]

    def add_booking_view(self, request):
        selected_doctor = request.user if request.user.role == 2 else None
        doctors = Employee.objects.filter(role=2, is_active=True).order_by("last_name", "first_name")
        context = {
            **self.each_context(request),
            "title": "Добавить запись",
            "doctors": doctors,
            "selected_doctor": selected_doctor,
            "procedures_url": reverse("admin:add_booking_procedures"),
            "slots_url": reverse("admin:add_booking_slots"),
            "booking_add_url": reverse("admin:clinic_backend_booking_add"),
        }
        return TemplateResponse(request, "admin/add_booking.html", context)

    def _resolve_doctor(self, request):
        if request.user.role == 2:
            return request.user
        doctor_id = request.GET.get("doctor_id")
        if not doctor_id:
            return None
        return Employee.objects.filter(pk=doctor_id, role=2, is_active=True).first()

    def booking_procedures_feed(self, request):
        doctor = self._resolve_doctor(request)
        if doctor is None:
            return JsonResponse({"procedures": []})

        services = (
            Service.objects
            .select_related("procedure_id")
            .filter(doctor_id=doctor, procedure_id__is_visible=True)
        )
        procedures = []
        seen = set()
        for service in services:
            procedure = service.procedure_id
            if not procedure or procedure.pk in seen:
                continue
            seen.add(procedure.pk)
            procedures.append({"id": procedure.pk, "name": procedure.name})

        return JsonResponse({"procedures": procedures})

    def booking_slots_feed(self, request):
        doctor = self._resolve_doctor(request)
        procedure_id = request.GET.get("procedure_id")
        date_value = request.GET.get("date")
        weekday_value = request.GET.get("weekday")
        if doctor is None or not procedure_id or not date_value or weekday_value is None:
            return HttpResponseBadRequest("Missing doctor, procedure, date, or weekday")

        procedure = Procedure.objects.filter(pk=procedure_id, is_visible=True).first()
        if procedure is None:
            return HttpResponseBadRequest("Invalid procedure")

        try:
            selected_date = datetime.strptime(date_value, "%Y-%m-%d").date()
            weekday = int(weekday_value)
        except ValueError:
            return HttpResponseBadRequest("Invalid date or weekday")

        slots = []
        for dt_value, is_available in appointment_slots(doctor, procedure, selected_date, weekday):
            slots.append(
                {
                    "time": dt_value.strftime("%H:%M"),
                    "is_available": is_available,
                }
            )

        return JsonResponse(
            {
                "doctor": {
                    "id": doctor.pk,
                    "name": doctor.build_username(),
                },
                "procedure": {
                    "id": procedure.pk,
                    "name": procedure.name,
                },
                "date": selected_date.isoformat(),
                "date_label": selected_date.strftime("%d.%m.%Y"),
                "weekday": weekday,
                "slots": slots,
            }
        )

    def overview_view(self, request):
        user = request.user
        today = timezone.localdate()
        now = timezone.now()
        limit = int(request.GET.get("limit", 20))
        limit = max(1, min(limit, 200))

        bookings = Booking.objects.select_related("doctor_id", "procedure_id")
        show_edit_button = False
        show_calls = False
        calls = []
        if user.role in {0, 1}:
            bookings = bookings.filter(date__gte=today)
            show_edit_button = True
            show_calls = True
            calls = self.get_overview_calls(now, today)
            bookings = bookings.order_by("date", "time")
            items = list(bookings[: limit + 1])
            has_more = len(items) > limit
            sliced_bookings = items[:limit]
        else:
            bookings = bookings.filter(doctor_id=user)
            bookings = bookings.order_by("date", "time")
            sliced_bookings = list(bookings)
            has_more = False

        context = {
            **self.each_context(request),
            "title": "Обзор",
            "bookings": sliced_bookings,
            "has_more": has_more,
            "next_limit": limit + 20,
            "show_edit_button": show_edit_button,
            "show_calls": show_calls,
            "calls": calls,
            "limit": limit,
        }
        return self.render_overview(request, context)

    def render_overview(self, request, context):
        return TemplateResponse(request, "admin/overview.html", context)

    def get_overview_calls(self, now, today):
        time_window = now - timedelta(minutes=20)
        return list(
            Call.objects.filter(added__date=today).filter(
                Q(status=0) | Q(status=1, added__gte=time_window)
            ).order_by("-added")
        )

    def calls_feed(self, request):
        user = request.user
        if user.role not in {0, 1}:
            raise PermissionDenied
        now = timezone.now()
        today = timezone.localdate()
        calls = self.get_overview_calls(now, today)
        payload = [
            {
                "id": call.id,
                "phone_number": call.phone_number,
                "status": call.status,
                "added": call.added.isoformat(),
            }
            for call in calls
        ]
        return JsonResponse({"calls": payload})

    def complete_call(self, request, call_id):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        user = request.user
        if user.role not in {0, 1}:
            raise PermissionDenied
        call = get_object_or_404(Call, pk=call_id)
        call.status = 1
        call.save(update_fields=["status"])
        return JsonResponse({"status": "ok"})


class EmployeeCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Подтверждение пароля", widget=forms.PasswordInput)

    class Meta:
        model = Employee
        fields = ("first_name", "last_name", "fathers_name", "role", "is_active", "is_visible", "description", "image")

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Пароли не совпадают.")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.username = user.build_username()
        if commit:
            user.save()
            self.save_m2m()
        return user


class EmployeeChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(label="Пароль")

    class Meta:
        model = Employee
        fields = ("first_name", "last_name", "fathers_name", "role", "is_active", "is_visible", "description",
                  "image", "password")

    def clean_password(self):
        return self.initial["password"]


class EmployeeAdmin(UserAdmin):
    form = EmployeeChangeForm
    add_form = EmployeeCreationForm
    model = Employee
    list_display = ("username", "first_name", "last_name", "role", "week_schedule", "services_list", "is_active")
    list_filter = ("role",)
    search_fields = ("first_name", "last_name")
    ordering = ("last_name", "first_name")

    fieldsets = (
        (None, {"fields": ("first_name", "last_name", "fathers_name", "role", "is_active", "is_visible")}),
        ("Дополнительно", {"fields": ("description", "image", "password")}),
    )
    add_fieldsets = (
        (None, {"fields": ("first_name", "last_name", "fathers_name", "role", "is_active", "is_visible")}),
        ("Дополнительно", {"fields": ("description", "image", "password1", "password2")}),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.prefetch_related("timetable_set", "service_set__procedure_id")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:employee_id>/timetable/<int:weekday>/",
                self.admin_site.admin_view(self.open_or_create_timetable),
                name="clinic_backend_employee_timetable",
            ),
        ]
        return custom_urls + urls

    def open_or_create_timetable(self, request, employee_id, weekday):
        if not self.has_change_permission(request):
            raise PermissionDenied

        employee = get_object_or_404(Employee, pk=employee_id)
        timetable = Timetable.objects.filter(worker_id=employee, weekday=weekday).first()
        if timetable is None:
            timetable = Timetable.objects.create(
                worker_id=employee,
                weekday=weekday,
                start_time=time(9, 0),
                end_time=time(18, 0),
            )
        return redirect("admin:clinic_backend_timetable_change", timetable.pk)

    def week_schedule(self, obj):
        timetables = {item.weekday: item.pk for item in obj.timetable_set.all()}
        days = [
            (0, "Пн", "Понедельник"),
            (1, "Вт", "Вторник"),
            (2, "Ср", "Среда"),
            (3, "Чт", "Четверг"),
            (4, "Пт", "Пятница"),
            (5, "Сб", "Суббота"),
            (6, "Вс", "Воскресенье"),
        ]
        return format_html(
            '<div class="timetable-widget">{}</div>',
            format_html_join(
                "",
                '<a class="timetable-day {}" href="{}" title="{}">{}</a>',
                (
                    (
                        "is-working" if weekday in timetables else "is-off",
                        reverse("admin:clinic_backend_employee_timetable", args=[obj.pk, weekday]),
                        title,
                        label,
                    )
                    for weekday, label, title in days
                ),
            ),
        )

    week_schedule.short_description = "Расписание"

    def services_list(self, obj):
        services = obj.service_set.all()
        if not services:
            return "—"
        service_items = [
            (service.pk, service.procedure_id.name)
            for service in services
            if service.procedure_id_id and service.procedure_id.name
        ]
        if not service_items:
            return "—"
        return format_html(
            '<details class="timetable-services">'
            '<summary>Услуги ({})</summary>'
            "<ul>{}</ul>"
            "</details>",
            len(service_items),
            format_html_join(
                "",
                '<li><a href="{}">{}</a></li>',
                (
                    (reverse("admin:clinic_backend_service_change", args=[service_id]), name)
                    for service_id, name in service_items
                ),
            ),
        )

    services_list.short_description = "Услуги"

    class Media:
        css = {"all": ("clinic_backend/admin.css",)}



class ClientAdmin(admin.ModelAdmin):
    list_display = ("display_label", "ads_consent", "ads_consent_given")
    search_fields = ("name", "phone_number", "email")

    @admin.display(description="Клиент")
    def display_label(self, obj):
        return str(obj)


class BookingAdmin(admin.ModelAdmin):
    exclude = ("confirm_token",)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        for key in ("doctor_id", "procedure_id", "date", "time", "name", "phone", "email"):
            value = request.GET.get(key)
            if value:
                initial[key] = value
        return initial


admin_site = ClinicAdminSite(name="admin")

admin_site.register(Employee, EmployeeAdmin)
admin_site.register(Procedure)
admin_site.register(Service)
admin_site.register(Booking, BookingAdmin)
admin_site.register(Timetable)
admin_site.register(Exception)
admin_site.register(Client, ClientAdmin)
