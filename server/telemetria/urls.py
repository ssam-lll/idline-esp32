from django.urls import path
from .views import (
    LecturaSensorListCreateAPIView,
    ComandoCreateAPIView,
    PistaOdometriaAPIView,
    EstadoRobotAPIView,
    PistaReferenciaAPIView,
)

urlpatterns = [
    path('datos/', LecturaSensorListCreateAPIView.as_view(), name='datos'),
    path('comando/', ComandoCreateAPIView.as_view(), name='comando'),
    path('pista/', PistaOdometriaAPIView.as_view(), name='pista'),
    path('pista/referencia/', PistaReferenciaAPIView.as_view(), name='pista_referencia'),
    path('estado/', EstadoRobotAPIView.as_view(), name='estado'),
]
