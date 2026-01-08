import os
import json
from cryptography.fernet import Fernet

from django.conf import settings
from django.db import models
from django.http import JsonResponse
from django.urls import path
from django.core.management import execute_from_command_line

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = "django-secret-key"

settings.configure(
    DEBUG=True,
    SECRET_KEY=SECRET_KEY,
    ROOT_URLCONF=__name__,
    INSTALLED_APPS=["__main__"],
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": "hashst",
            "USER": "root",
            "PASSWORD": "Vimal05",
            "HOST": "mysql",
            "PORT": "3306",
        }
    },
)

import django
django.setup()

import base64
import hashlib

key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
FERNET_KEY = base64.urlsafe_b64encode(key)
cipher = Fernet(FERNET_KEY)

class HashStore(models.Model):
    data = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = "hashstore"
        managed = False 

def encode_data(data_list):
    json_data = json.dumps(data_list)
    return cipher.encrypt(json_data.encode()).decode()

from cryptography.fernet import InvalidToken

def decode_data(encoded):
    if not encoded:
        return []

    try:
        return json.loads(cipher.decrypt(encoded.encode()).decode())
    except InvalidToken:
        return []
    
def add_value(request):
    new_value = request.GET.get("value")

    obj, _ = HashStore.objects.get_or_create(id=1)

    if obj.data:
        data_list = decode_data(obj.data)
    else:
        data_list = []

    data_list.append(new_value)
    if len(data_list) > 3:
        data_list.pop(0)

    obj.data = encode_data(data_list)
    obj.save()

    return JsonResponse({
        "stored_json": data_list,
        "hashed_value": obj.data
    })

def read_value(request):
    obj = HashStore.objects.get(id=1)
    return JsonResponse({
        "decoded_json": decode_data(obj.data)
    })

urlpatterns = [
    path("add/", add_value),
    path("read/", read_value),
]

if __name__ == "__main__":
    execute_from_command_line()
