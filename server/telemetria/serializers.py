from rest_framework import serializers
from .models import LecturaSensor, EstadoRobot, ComandoPendiente

class LecturaSensorSerializer(serializers.ModelSerializer):
    class Meta:
        model = LecturaSensor
        fields = [
            'id',
            'dispositivo_id',
            'sensores',
            'm1',
            'm2',
            'error',
            'modo',
            'posicion',
            'vbat_mv',
            'track_id',
            'muestras',
            'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']


class EstadoRobotSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoRobot
        fields = ['id', 'dispositivo_id', 'active_track_id', 'actualizado']
        read_only_fields = ['id', 'actualizado']


class ComandoPendienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComandoPendiente
        fields = ['id', 'dispositivo_id', 'cmd', 'payload', 'ejecutado', 'creado']
        read_only_fields = ['id', 'creado']


class ComandoCreateInputSerializer(serializers.Serializer):
    dispositivo_id = serializers.CharField(max_length=64, required=False, default="idline_esp32")
    cmd = serializers.CharField(max_length=64, required=True)
    payload = serializers.JSONField(required=False, default=dict)
