from django.urls import path
from .admin_linea_views import (
    admin_linea_drivers,
    deactivate_driver_by_admin_linea,
    delete_driver_by_admin_linea,
    update_admin_linea_profile,
)

urlpatterns = [
    path('drivers', admin_linea_drivers),
    path('drivers/', admin_linea_drivers),
    path('drivers/<int:id_driver>/deactivate', deactivate_driver_by_admin_linea),
    path('drivers/<int:id_driver>/deactivate/', deactivate_driver_by_admin_linea),
    path('drivers/<int:id_driver>', delete_driver_by_admin_linea),
    path('drivers/<int:id_driver>/', delete_driver_by_admin_linea),
    path('profile', update_admin_linea_profile),
    path('profile/', update_admin_linea_profile),
]
