from django.db import migrations
from django.contrib.auth.hashers import make_password
import os
from dotenv import load_dotenv

def create_default_employee(apps, schema_editor):
    Employee = apps.get_model("clinic_backend", "Employee")

    load_dotenv()

    if not Employee.objects.filter(id=1).exists():
        Employee.objects.create(
            username=str(os.getenv("SUPERUSER_USERNAME")),
            first_name="Default",
            last_name="Owner",
            role=0,  # Owner
            is_superuser=True,
            is_staff=True,
            password=make_password(str(os.getenv("SUPERUSER_PASSWORD")))
        )

def delete_default_employee(apps, schema_editor):
    Employee = apps.get_model("clinic_backend", "Employee")
    Employee.objects.filter(id=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("clinic_backend", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_employee, delete_default_employee)
    ]
