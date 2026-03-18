import json
from datetime import timedelta, datetime

from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from .models import Employee, Service, Booking, Timetable, Exception, Procedure, Call, Client
from .utils.email import send_booking_created_email


def services_by_doctor(request, employee_id):
    doctor = get_object_or_404(Employee, id=employee_id)

    date_str = request.GET.get("date")
    weekday = request.GET.get("weekday")

    if not date_str or not weekday:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        weekday = int(weekday)
    except ValueError:
        return JsonResponse({"error": "Invalid date or parameter format"}, status=400)

    services = (
        Service.objects
        .select_related("doctor_id")
        .filter(doctor_id=doctor, procedure_id__is_visible=True)
    )

    result = []
    for service in services:
        procedure = service.procedure_id
        slots = appointment_slots(doctor, procedure, selected_date, weekday)
        if len(slots) != 0:
            json_service = {"id": procedure.id, "name": f"Услуга {procedure.name}",
                            "slots": slots}
            result.append(json_service)
    return JsonResponse({"services": result},
                        status=200)


def doctors_by_services(request, procedure_id):
    procedure = get_object_or_404(Procedure, id=procedure_id)

    date_str = request.GET.get("date")
    weekday = request.GET.get("weekday")

    if not date_str or not weekday:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        weekday = int(weekday)
    except ValueError:
        return JsonResponse({"error": "Invalid date or parameter format"}, status=400)

    services = (
        Service.objects
        .select_related("procedure_id")
        .filter(procedure_id=procedure, doctor_id__is_active=True)
    )
    result = []
    for service in services:
        doctor = service.doctor_id
        json_service = {"id": doctor.id, "name": f"{doctor.last_name} {doctor.first_name} {doctor.fathers_name}",
                        "picture": doctor.image.url if doctor.image else None,
                        "slots": appointment_slots(doctor, procedure, selected_date, weekday)}
        result.append(json_service)
    return JsonResponse({"services": result},
                        status=200)


def appointment_slots(doctor, procedure, selected_date, weekday):
    slots = []

    # ToDO false behavior when there is no timetable for the day but there is a exception
    timetable = Timetable.objects.filter(worker_id=doctor, weekday=weekday).first()
    if timetable is None:
        return slots

    timetable = get_object_or_404(Timetable, worker_id=doctor, weekday=weekday)

    start, end = timetable.start_time, timetable.end_time

    period = timedelta(minutes=procedure.duration)

    start_dt = datetime.combine(selected_date, start)
    end_dt = datetime.combine(selected_date, end)
    cur_time = start_dt
    now = datetime.now()

    while cur_time + period <= end_dt:
        slots.append([cur_time, True])
        cur_time += period

    for exc in Exception.objects.filter(worker_id=doctor, date=selected_date, is_working=True):
        exc_start = datetime.combine(selected_date, exc.start_time)
        exc_end = datetime.combine(selected_date, exc.end_time)
        if exc_start < start_dt:
            cur_time = start_dt
            while cur_time - period >= exc_start:
                cur_time -= period
                slots.insert(0, [cur_time, True])
        if exc_end > end_dt:
            cur_time = end_dt
            while cur_time + period <= exc_end:
                slots.append([cur_time, True])
                cur_time += period
                # ToDo fix next day overlaping

    for exc in Exception.objects.filter(worker_id=doctor, date=selected_date, is_working=False):
        exc_start = datetime.combine(selected_date, exc.start_time)
        exc_end = datetime.combine(selected_date, exc.end_time)
        for i, (slot_time, _) in enumerate(slots):
            if exc_start - period <= slot_time < exc_end:
                slots[i][1] = False

    for booking in Booking.objects.filter(doctor_id=doctor, date=selected_date):
        book_start = datetime.combine(selected_date, booking.time)
        book_end = book_start + timedelta(minutes=booking.procedure_id.duration)
        for i, (slot_time, _) in enumerate(slots):
            if book_start <= slot_time < book_end:
                slots[i][1] = False

    for slot in slots:
        if slot[0] < now:
            slot[1] = False
        else:
            break

    return slots


@require_POST
@csrf_protect
def add_booking(request):
    data = json.loads(request.body)

    time = data.get("time")
    date = data.get("date")
    doctor_id = int(data.get("doctor"))
    procedure_id = int(data.get("service"))
    client_email = (data.get("client_email") or "").strip()
    client_name = (data.get("client_name") or "").strip()
    ads_consent = bool(data.get("ads_consent", False))

    doctor = get_object_or_404(Employee, id=doctor_id)
    procedure = get_object_or_404(Procedure, id=procedure_id)

    exists = Booking.objects.filter(
        doctor_id=doctor,
        date=date,
        time=time
    ).exists()

    if exists:
        return JsonResponse({"error": "Время уже занято"}, status=400)

    raw_confirm_token, hashed_confirm_token = Booking.generate_confirm_token_pair()

    Booking.objects.create(
        doctor_id=doctor,
        procedure_id=procedure,
        date=date,
        time=time,
        name=client_name,
        email=client_email,
        confirm_token=hashed_confirm_token,
    )

    if client_email:
        defaults = {"name": client_name}
        #if ads_consent:
        #    defaults["ads_consent"] = True
        #    defaults["ads_consent_given"] = timezone.now()
        defaults["ads_consent"] = False
        Client.objects.update_or_create(email=client_email, defaults=defaults)

    confirm_url = "/booking/info/" + raw_confirm_token

    send_booking_created_email.delay(
        client_email,
        "https://sventus.ru" + confirm_url,
        date=date,
        time=time,
        doctor=str(doctor),
        procedure=str(procedure),
    )

    return JsonResponse(
        {"redirect_url": confirm_url},
        status=200
    )


@require_POST
@csrf_protect
def add_call(request):
    phone_number = request.POST.get("client_phone", "").strip()
    client_name = request.POST.get("client_name", "").strip()

    if not phone_number:
        return JsonResponse({"error": "Телефон обязателен"}, status=400)

    Call.objects.create(name=client_name, phone_number=phone_number)
    Client.objects.update_or_create(
        phone_number=phone_number,
        defaults={"name": client_name},
    )

    return redirect("/book/call")
