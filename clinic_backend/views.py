import json

from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import Employee, Booking, Procedure


def index(request):
    employees = Employee.objects.filter(is_visible=True)
    procedures = Procedure.objects.filter(is_visible=True)
    return render(request, "index.html",
                  {"employees": employees,
                   "procedures": procedures})


def booking(request):
    return HttpResponse("There will be buttons for booking opportunities soon")


def call_booking(request):
    return render(request, "call_booking.html")


def online_booking(request):
    return render(request, "online_booking.html")


def booking_info(request, confirm_token):

    booking_object = get_object_or_404(Booking, confirm_token=Booking.hash_confirm_token(confirm_token))

    if request.method == "POST":
        booking_object.delete()
        return redirect("/")

    return render(
        request,
        "booking_info.html",
        {
            "booking": booking_object,
            "doctor": booking_object.doctor_id,
            "procedure": booking_object.procedure_id,
        },
    )


def choose_doctor(request):
    doctors = Employee.objects.filter(role=2, is_visible=True)
    return render(request, "choose_doctor.html", {"doctors": doctors})


def choose_procedure(request):
    procedures = Procedure.objects.filter(is_visible=True)
    return render(request, "choose_service.html", {"services": procedures})


def doctor_booking(request, employee_id):
    doctor = get_object_or_404(Employee, id=employee_id)
    return render(request, "doctor.html", {"doctor": doctor})


def procedure_booking(request, procedure_id):
    procedure = get_object_or_404(Procedure, id=procedure_id)
    return render(request, "procedure.html", {"procedure": procedure})


@ensure_csrf_cookie
def identification(request):
    doctor_id = request.GET.get("doctor")
    procedure_id = request.GET.get("service")
    doctor = get_object_or_404(Employee, id=doctor_id)
    procedure = get_object_or_404(Procedure, id=procedure_id)
    return render(request, "identification.html",
                  {"doctor": doctor, "procedure": procedure})
