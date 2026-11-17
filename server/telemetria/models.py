from django.db import models

class LecturaSensor(models.Model):
    dispositivo_id = models.CharField(max_length=64, default="idline_esp32", db_index=True)
    sensores = models.JSONField(default=list)
    m1 = models.IntegerField(default=0)
    m2 = models.IntegerField(default=0)
    error = models.IntegerField(default=0)
    modo = models.CharField(max_length=32, default="IDLE")
    posicion = models.IntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    vbat_mv = models.IntegerField(null=True, blank=True)
    track_id = models.IntegerField(default=1, db_index=True)
    muestras = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Lectura de Sensor'
        verbose_name_plural = 'Lecturas de Sensores'
        indexes = [
            models.Index(fields=['dispositivo_id', '-id'], name='idx_lectura_disp_id_desc'),
            models.Index(fields=['dispositivo_id', 'track_id', 'id'], name='idx_lectura_disp_track_id'),
        ]

    def __str__(self):
        return f"[{self.timestamp}] {self.dispositivo_id} (Track #{self.track_id}) - {self.modo} - Pos: {self.posicion}"


class EstadoRobot(models.Model):
    dispositivo_id = models.CharField(max_length=64, unique=True)
    active_track_id = models.IntegerField(default=1)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Estado del Robot'
        verbose_name_plural = 'Estados de Robots'

    def __str__(self):
        return f"{self.dispositivo_id} | Track Activo: #{self.active_track_id}"


class ComandoPendiente(models.Model):
    dispositivo_id = models.CharField(max_length=64, db_index=True)
    cmd = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    ejecutado = models.BooleanField(default=False, db_index=True)
    creado = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['creado']
        verbose_name = 'Comando Pendiente'
        verbose_name_plural = 'Comandos Pendientes'
        indexes = [
            models.Index(fields=['dispositivo_id', 'ejecutado', 'creado'], name='idx_cmd_disp_exec_creado'),
        ]

    def __str__(self):
        return f"{self.dispositivo_id} -> {self.cmd} (Ejecutado: {self.ejecutado}) @ {self.creado}"


class PistaReferencia(models.Model):
    device_id = models.CharField(max_length=64, default="idline_esp32", db_index=True)
    track_id = models.IntegerField(default=1, db_index=True)
    points_json = models.JSONField(default=list)
    closed = models.BooleanField(default=True)
    photo_count = models.PositiveSmallIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Pista de Referencia'
        verbose_name_plural = 'Pistas de Referencia'
        constraints = [
            models.UniqueConstraint(
                fields=['device_id', 'track_id'],
                name='uniq_pista_ref_device_track',
            ),
        ]

    def __str__(self):
        return (
            f"{self.device_id} (Track #{self.track_id}, "
            f"{len(self.points_json)} pts, {self.photo_count} fotos, closed={self.closed}) "
            f"@ {self.updated_at}"
        )
