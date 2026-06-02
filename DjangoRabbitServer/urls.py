"""
URL configuration for DjangoRabbitServer project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/' , include('users.urls')),
    path('auth' , include('authentication.urls')),
    path('drivers-position' , include('driver_position.urls')),
    path('client-requests' , include('client_requests.urls')),
    path('driver-trip-offers' , include('driver_trip_offers.urls')),
    path('driver-bike-info' , include('driver_bike_info.urls')),
    path('firebase-notification' , include('firebase_notification.urls')),
]

urlpatterns +=  static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)