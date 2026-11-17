from django.contrib import admin
from .models import LecturaSensor, EstadoRobot, ComandoPendiente

@admin.register(LecturaSensor)
class LecturaSensorAdmin(admin.ModelAdmin):
    list_display = ('id', 'dispositivo_id', 'track_id', 'modo', 'vbat_mv', 'm1', 'm2', 'posicion', 'timestamp')
    list_filter = ('dispositivo_id', 'track_id', 'modo')
    search_fields = ('dispositivo_id',)
    readonly_fields = ('timestamp',)


@admin.register(EstadoRobot)
class EstadoRobotAdmin(admin.ModelAdmin):
    list_display = ('id', 'dispositivo_id', 'active_track_id', 'actualizado')
    search_fields = ('dispositivo_id',)


@admin.register(ComandoPendiente)
class ComandoPendienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'dispositivo_id', 'cmd', 'ejecutado', 'creado')
    list_filter = ('dispositivo_id', 'cmd', 'ejecutado')
    search_fields = ('dispositivo_id', 'cmd')
    readonly_fields = ('creado',)
