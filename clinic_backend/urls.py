from django.urls import path

from . import views, api

urlpatterns = [
    path("", views.index, name="index"),
    path("book/", views.booking, name='booking opportunities'),
    path("book/call", views.call_booking, name='call booking'),
    path("book/online", views.online_booking, name='booking options'),
    path("book/online/choose_doctor", views.choose_doctor, name='doctor options'),
    path("book/online/choose_procedure", views.choose_procedure, name='service options'),
    path("book/online/doctor/<int:employee_id>", views.doctor_booking, name='doctor booking'),
    path("book/online/procedure/<int:procedure_id>", views.procedure_booking, name='procedure booking'),
    path("book/online/identification/", views.identification, name="identifications"),
    path("booking/info/<str:confirm_token>", views.booking_info, name='success'),
    path("api/doctor/<int:employee_id>/slots/", api.services_by_doctor, name="api_doctor_slots"),
    path("api/procedure/<int:procedure_id>/slots/", api.doctors_by_services, name="api_doctor_slots"),
    path("api/booking/add/", api.add_booking, name='api_add_booking'),
    path("api/call/add/", api.add_call, name="api_add_call"),
]
