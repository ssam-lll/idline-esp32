from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='root_redirect'),
    path('admin/', admin.site.urls),
    path('api/', include('telemetria.urls')),
]
