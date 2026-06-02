from django.urls import path
from .views import create, get_nearby_drivers, get_driver_position,delete
urlpatterns =  [
    path('', create),
    path('/nearby/<client_lat>/<client_lng>', get_nearby_drivers),
    path('/<id_driver>', get_driver_position),
    path('/delete/<id_driver>', delete),
]