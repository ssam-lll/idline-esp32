import base64
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import LecturaSensor, EstadoRobot, ComandoPendiente, PistaReferencia
from .serializers import (
    LecturaSensorSerializer,
    EstadoRobotSerializer,
    ComandoPendienteSerializer,
    ComandoCreateInputSerializer
)
from .odometry import reconstruct_trajectory
from .vision_ai import (
    extract_track_polyline,
    VisionAIConfigError,
    VisionAIError,
)

class LecturaSensorListCreateAPIView(APIView):
    """
    GET /api/datos/ -> returns last 50 readings (or filtered by ?track_id=...)
    POST /api/datos/ -> saves telemetry from ESP32, checks oldest unexecuted command,
                       marks it executed and returns it in 201 response.
    """
    def get(self, request):
        dispositivo_id = request.query_params.get('dispositivo_id', 'idline_esp32')
        track_id = request.query_params.get('track_id')
        limit = int(request.query_params.get('limit', 50))
        limit = max(1, min(limit, 500))

        queryset = LecturaSensor.objects.filter(dispositivo_id=dispositivo_id)
        if track_id:
            try:
                queryset = queryset.filter(track_id=int(track_id))
            except ValueError:
                pass

        readings = queryset.order_by('-id')[:limit]
        serializer = LecturaSensorSerializer(readings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        dispositivo_id = data.get('dispositivo_id') or 'idline_esp32'
        data['dispositivo_id'] = dispositivo_id

        # Resolve or initialize robot state & track_id with minimal DB roundtrips
        if not data.get('track_id'):
            active_track_id = (
                EstadoRobot.objects.filter(dispositivo_id=dispositivo_id)
                .values_list('active_track_id', flat=True)
                .first()
            )
            if active_track_id is None:
                estado, _ = EstadoRobot.objects.get_or_create(
                    dispositivo_id=dispositivo_id,
                    defaults={'active_track_id': 1}
                )
                active_track_id = estado.active_track_id
            data['track_id'] = active_track_id

        batch_cmds = bool(data.get('batch_cmds'))

        serializer = LecturaSensorSerializer(data=data)
        if serializer.is_valid():
            lectura = serializer.save()

            pending_qs = ComandoPendiente.objects.filter(
                dispositivo_id=dispositivo_id,
                ejecutado=False
            ).order_by('creado')

            if batch_cmds:
                comandos = list(pending_qs[:5])
                if comandos:
                    ComandoPendiente.objects.filter(
                        id__in=[c.id for c in comandos]
                    ).update(ejecutado=True)
                comandos_data = [
                    {'id': c.id, 'cmd': c.cmd, 'payload': c.payload}
                    for c in comandos
                ]
                comando_data = comandos_data[0] if comandos_data else None
                return Response({
                    'status': 'success',
                    'id': lectura.id,
                    'track_id': lectura.track_id,
                    'dispositivo_id': lectura.dispositivo_id,
                    'comando': comando_data,
                    'comandos': comandos_data,
                }, status=status.HTTP_201_CREATED)

            # Default: pop oldest unexecuted pending command for this device
            comando = pending_qs.first()
            comando_data = None
            if comando:
                comando.ejecutado = True
                comando.save(update_fields=['ejecutado'])
                comando_data = {
                    'id': comando.id,
                    'cmd': comando.cmd,
                    'payload': comando.payload
                }

            return Response({
                'status': 'success',
                'id': lectura.id,
                'track_id': lectura.track_id,
                'dispositivo_id': lectura.dispositivo_id,
                'comando': comando_data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ComandoCreateAPIView(APIView):
    """
    POST /api/comando/ -> queues a ComandoPendiente.
                          If cmd == 'new_track', increments active_track_id in EstadoRobot
                          and queues new_track for the ESP32.
    GET /api/comando/ -> lists recent pending or executed commands.
    """
    def get(self, request):
        dispositivo_id = request.query_params.get('dispositivo_id', 'idline_esp32')
        ejecutado = request.query_params.get('ejecutado')
        queryset = ComandoPendiente.objects.filter(dispositivo_id=dispositivo_id)
        if ejecutado is not None:
            is_exec = ejecutado.lower() in ['true', '1']
            queryset = queryset.filter(ejecutado=is_exec)
        comandos = queryset.order_by('-creado')[:20]
        serializer = ComandoPendienteSerializer(comandos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        input_serializer = ComandoCreateInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(input_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        dispositivo_id = input_serializer.validated_data.get('dispositivo_id', 'idline_esp32')
        cmd = input_serializer.validated_data.get('cmd')
        payload = input_serializer.validated_data.get('payload', {})
        if not isinstance(payload, dict):
            payload = {'value': payload}

        estado, _ = EstadoRobot.objects.get_or_create(
            dispositivo_id=dispositivo_id,
            defaults={'active_track_id': 1}
        )

        active_track_id = estado.active_track_id
        if cmd == 'new_track':
            estado.active_track_id += 1
            estado.save(update_fields=['active_track_id', 'actualizado'])
            active_track_id = estado.active_track_id
            payload['new_track_id'] = active_track_id

        comando = ComandoPendiente.objects.create(
            dispositivo_id=dispositivo_id,
            cmd=cmd,
            payload=payload,
            ejecutado=False
        )

        return Response({
            'status': 'queued',
            'id': comando.id,
            'cmd': comando.cmd,
            'payload': comando.payload,
            'dispositivo_id': comando.dispositivo_id,
            'active_track_id': active_track_id
        }, status=status.HTTP_201_CREATED)


class PistaOdometriaAPIView(APIView):
    """
    GET /api/pista/?track_id=... -> returns reconstructed (x, y) trajectory
    points computed from high-freq muestras or telemetry sensor readings
    using differential-drive odometry with vbat_mv voltage compensation.
    """
    def get(self, request):
        dispositivo_id = request.query_params.get('dispositivo_id', 'idline_esp32')
        track_id_param = request.query_params.get('track_id')

        if track_id_param:
            try:
                track_id = int(track_id_param)
            except ValueError:
                return Response({'error': 'track_id invalido'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            estado = EstadoRobot.objects.filter(dispositivo_id=dispositivo_id).first()
            if estado:
                track_id = estado.active_track_id
            else:
                latest = LecturaSensor.objects.filter(dispositivo_id=dispositivo_id).first()
                track_id = latest.track_id if latest else 1

        readings = list(
            LecturaSensor.objects.filter(
                dispositivo_id=dispositivo_id,
                track_id=track_id
            )
            .only('id', 'm1', 'm2', 'vbat_mv', 'posicion', 'timestamp', 'muestras')
            .order_by('id')
        )

        reconstruction = reconstruct_trajectory(readings)
        reconstruction['track_id'] = track_id
        reconstruction['dispositivo_id'] = dispositivo_id
        return Response(reconstruction, status=status.HTTP_200_OK)


class EstadoRobotAPIView(APIView):
    """
    GET /api/estado/?dispositivo_id=... -> returns active track and robot status.
    """
    def get(self, request):
        dispositivo_id = request.query_params.get('dispositivo_id', 'idline_esp32')
        estado, _ = EstadoRobot.objects.get_or_create(
            dispositivo_id=dispositivo_id,
            defaults={'active_track_id': 1}
        )
        latest = LecturaSensor.objects.filter(dispositivo_id=dispositivo_id).first()
        pending_count = ComandoPendiente.objects.filter(dispositivo_id=dispositivo_id, ejecutado=False).count()

        return Response({
            'dispositivo_id': estado.dispositivo_id,
            'active_track_id': estado.active_track_id,
            'actualizado': estado.actualizado,
            'comandos_pendientes': pending_count,
            'ultima_lectura': LecturaSensorSerializer(latest).data if latest else None
        }, status=status.HTTP_200_OK)


class PistaReferenciaAPIView(APIView):
    """
    GET /api/pista/referencia/?device_id=...&track_id=... -> returns PistaReferencia for (device_id, track_id).
    POST /api/pista/referencia/ -> accepts JSON `images` (list of 2-4 dicts/base64, or
        single `image_base64` for compat) or multipart `images`/`image` files, calls
        Gemini Vision AI, saves/updates PistaReferencia per (device_id, track_id), and
        returns normalized polyline.
    """
    @staticmethod
    def _resolve_track_id(raw_track_id, device_id: str) -> int:
        if raw_track_id is not None and str(raw_track_id).strip() != '':
            return int(raw_track_id)
        active_track_id = (
            EstadoRobot.objects.filter(dispositivo_id=device_id)
            .values_list('active_track_id', flat=True)
            .first()
        )
        return active_track_id if active_track_id is not None else 1

    def get(self, request):
        device_id = (
            request.query_params.get('device_id')
            or request.query_params.get('dispositivo_id')
            or 'idline_esp32'
        )
        try:
            track_id = self._resolve_track_id(
                request.query_params.get('track_id'),
                device_id,
            )
        except (TypeError, ValueError):
            return Response(
                {'ok': False, 'error': 'track_id invalido'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ref = PistaReferencia.objects.filter(
            device_id=device_id,
            track_id=track_id,
        ).first()
        if not ref:
            return Response(
                {
                    'ok': False,
                    'device_id': device_id,
                    'track_id': track_id,
                    'points': [],
                    'closed': False,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                'ok': True,
                'device_id': ref.device_id,
                'track_id': ref.track_id,
                'photo_count': ref.photo_count,
                'points': ref.points_json,
                'closed': ref.closed,
                'updated_at': ref.updated_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        device_id = (
            request.data.get('device_id')
            or request.data.get('dispositivo_id')
            or 'idline_esp32'
        )
        raw_track_id = request.data.get('track_id')
        if raw_track_id is None:
            raw_track_id = request.query_params.get('track_id')
        try:
            track_id = self._resolve_track_id(raw_track_id, device_id)
        except (TypeError, ValueError):
            return Response(
                {'ok': False, 'error': 'track_id invalido'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_files = request.FILES.getlist('images') or request.FILES.getlist('image')
        images_payload = []

        if uploaded_files:
            if len(uploaded_files) < 1 or len(uploaded_files) > 4:
                return Response(
                    {
                        'ok': False,
                        'error': 'Se permiten entre 1 y 4 archivos de imagen (2 a 4 recomendados).',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for image_file in uploaded_files:
                raw_bytes = image_file.read()
                if not raw_bytes:
                    return Response(
                        {'ok': False, 'error': 'Uno de los archivos de imagen esta vacio.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                images_payload.append({
                    'image_base64': base64.b64encode(raw_bytes).decode('ascii'),
                    'mime_type': getattr(image_file, 'content_type', None) or 'image/jpeg',
                })
        elif 'images' in request.data:
            raw_images = request.data.get('images')
            if not isinstance(raw_images, list):
                return Response(
                    {'ok': False, 'error': "El campo 'images' debe ser una lista."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if len(raw_images) < 1 or len(raw_images) > 4:
                return Response(
                    {
                        'ok': False,
                        'error': 'Se requieren entre 1 y 4 imagenes en "images" (2 a 4 recomendadas).',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for item in raw_images:
                if isinstance(item, dict):
                    images_payload.append({
                        'image_base64': item.get('image_base64') or item.get('data') or '',
                        'mime_type': item.get('mime_type') or 'image/jpeg',
                    })
                elif isinstance(item, str):
                    images_payload.append({'image_base64': item, 'mime_type': None})
                else:
                    return Response(
                        {'ok': False, 'error': 'Formato invalido en lista "images".'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        else:
            image_base64 = request.data.get('image_base64')
            if image_base64:
                images_payload.append({
                    'image_base64': image_base64,
                    'mime_type': request.data.get('mime_type') or 'image/jpeg',
                })

        if not images_payload:
            return Response(
                {
                    'ok': False,
                    'error': 'Se requiere images (1-4 fotos), image_base64 o archivos multipart images/image.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            extracted = extract_track_polyline(images_payload)
        except VisionAIConfigError as exc:
            return Response(
                {'ok': False, 'error': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ValueError as exc:
            return Response(
                {'ok': False, 'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except VisionAIError as exc:
            return Response(
                {'ok': False, 'error': str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        photo_count = len(images_payload)
        ref, _ = PistaReferencia.objects.update_or_create(
            device_id=device_id,
            track_id=track_id,
            defaults={
                'points_json': extracted['points'],
                'closed': extracted['closed'],
                'photo_count': photo_count,
                'metadata': {
                    'photo_count': photo_count,
                    'mode': 'multi_view' if photo_count >= 2 else 'single_view',
                },
            },
        )

        return Response(
            {
                'ok': True,
                'device_id': ref.device_id,
                'track_id': ref.track_id,
                'photo_count': ref.photo_count,
                'points': ref.points_json,
                'closed': ref.closed,
                'updated_at': ref.updated_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
