import json
from django.test import TestCase, Client as DjangoClient
from django.urls import reverse
from werkzeug.test import Client as WerkzeugClient

from .models import LecturaSensor, EstadoRobot, ComandoPendiente, PistaReferencia
from .odometry import (
    calculate_odometry_point,
    reconstruct_trajectory,
    align_trajectory_to_reference,
)
from dashboard.app import (
    app as dash_app,
    handle_commands,
    handle_track_photo_upload,
    build_track_map_figure,
    update_telemetry,
    update_fast_telemetry,
    update_charts_telemetry,
    vbat_mv_to_percent,
    format_vbat_badge,
)
from wsgi_pythonanywhere import application as wsgi_application


class TelemetriaAPITests(TestCase):
    def setUp(self):
        self.client = DjangoClient()
        self.dispositivo_id = "idline_esp32"
        self.estado = EstadoRobot.objects.create(
            dispositivo_id=self.dispositivo_id,
            active_track_id=1
        )

    def test_01_post_datos_saves_and_piggybacks_track_id(self):
        """Verify POST /api/datos/ saves reading with active_track_id when omitted."""
        payload = {
            "dispositivo_id": self.dispositivo_id,
            "sensores": [300, 310, 450, 2200, 2100, 420, 290, 280],
            "m1": 680,
            "m2": 670,
            "error": 5,
            "modo": "RUNNING",
            "posicion": 35,
            "vbat_mv": 8150
        }
        response = self.client.post(
            reverse('datos'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["track_id"], 1)
        self.assertIsNone(data["comando"])

        # Check in database
        lectura = LecturaSensor.objects.get(id=data["id"])
        self.assertEqual(lectura.track_id, 1)
        self.assertEqual(lectura.vbat_mv, 8150)
        self.assertEqual(lectura.m1, 680)

    def test_02_post_datos_executes_and_returns_oldest_pending_command(self):
        """Verify POST /api/datos/ pops oldest ComandoPendiente and marks ejecutado=True."""
        # Create two pending commands
        cmd1 = ComandoPendiente.objects.create(
            dispositivo_id=self.dispositivo_id,
            cmd="start_pid",
            payload={"speed": 680},
            ejecutado=False
        )
        cmd2 = ComandoPendiente.objects.create(
            dispositivo_id=self.dispositivo_id,
            cmd="set_motores",
            payload={"m1": 180, "m2": 180},
            ejecutado=False
        )

        # Robot sends telemetry
        payload = {
            "dispositivo_id": self.dispositivo_id,
            "sensores": [200] * 8,
            "m1": 0,
            "m2": 0,
            "modo": "IDLE",
            "vbat_mv": 7900
        }
        res1 = self.client.post(
            reverse('datos'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 201)
        data1 = res1.json()
        self.assertIsNotNone(data1["comando"])
        self.assertEqual(data1["comando"]["id"], cmd1.id)
        self.assertEqual(data1["comando"]["cmd"], "start_pid")

        # Verify cmd1 is now executed
        cmd1.refresh_from_db()
        self.assertTrue(cmd1.ejecutado)

        # Robot sends next telemetry -> gets cmd2
        res2 = self.client.post(
            reverse('datos'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        data2 = res2.json()
        self.assertEqual(data2["comando"]["id"], cmd2.id)
        self.assertEqual(data2["comando"]["cmd"], "set_motores")

        # Third telemetry -> no pending commands
        res3 = self.client.post(
            reverse('datos'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        data3 = res3.json()
        self.assertIsNone(data3["comando"])

    def test_03_get_datos_returns_readings_filtered_by_track(self):
        """Verify GET /api/datos/ returns last readings and filters by ?track_id."""
        LecturaSensor.objects.create(dispositivo_id=self.dispositivo_id, track_id=1, m1=100)
        LecturaSensor.objects.create(dispositivo_id=self.dispositivo_id, track_id=2, m1=200)

        # All for device
        res = self.client.get(reverse('datos'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 2)

        # Filtered by track_id=2
        res_t2 = self.client.get(reverse('datos') + '?track_id=2')
        self.assertEqual(res_t2.status_code, 200)
        items = res_t2.json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["m1"], 200)

    def test_04_post_comando_standard_and_new_track(self):
        """Verify POST /api/comando/ queues commands and handles 'new_track' logic."""
        # 1. Standard command
        cmd_payload = {
            "dispositivo_id": self.dispositivo_id,
            "cmd": "set_pid",
            "payload": {"kp": 0.58, "kd": 4.0, "speed": 680}
        }
        res1 = self.client.post(
            reverse('comando'),
            data=json.dumps(cmd_payload),
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 201)
        self.assertEqual(res1.json()["status"], "queued")
        self.assertEqual(res1.json()["cmd"], "set_pid")

        # 2. 'new_track' command
        new_track_payload = {
            "dispositivo_id": self.dispositivo_id,
            "cmd": "new_track"
        }
        res2 = self.client.post(
            reverse('comando'),
            data=json.dumps(new_track_payload),
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 201)
        self.assertEqual(res2.json()["cmd"], "new_track")
        self.assertEqual(res2.json()["active_track_id"], 2)

        # Verify EstadoRobot was updated in DB
        self.estado.refresh_from_db()
        self.assertEqual(self.estado.active_track_id, 2)

        # Verify a new POST /api/datos/ now inherits track_id=2
        res_data = self.client.post(
            reverse('datos'),
            data=json.dumps({"dispositivo_id": self.dispositivo_id, "sensores": [0]*8}),
            content_type='application/json'
        )
        self.assertEqual(res_data.json()["track_id"], 2)

    def test_05_get_pista_odometry_reconstruction(self):
        """Verify GET /api/pista/ computes trajectory with voltage compensation."""
        # Create a series of readings for track 1
        for i in range(10):
            LecturaSensor.objects.create(
                dispositivo_id=self.dispositivo_id,
                track_id=1,
                m1=600,
                m2=600 if i < 5 else 400, # Straight then right turn
                vbat_mv=7800,
                posicion=0 if i < 5 else 50
            )

        res = self.client.get(reverse('pista') + '?track_id=1')
        self.assertEqual(res.status_code, 200)
        pista_data = res.json()
        self.assertEqual(pista_data["track_id"], 1)
        self.assertGreater(pista_data["total_points"], 5)
        self.assertGreater(pista_data["total_distance_m"], 0.0)
        self.assertIn("trajectory", pista_data)
        self.assertIn("bounds", pista_data)

        # Check trajectory point structure
        p0 = pista_data["trajectory"][0]
        self.assertEqual(p0["x"], 0.0)
        self.assertEqual(p0["y"], 0.0)

    def test_06_get_pista_with_burst_muestras(self):
        """Verify odometry reconstruction using high-rate burst memory samples."""
        muestras_burst = [
            [0, 0, 500, 500, 7400],
            [20, 5, 520, 500, 7390],
            [40, 10, 550, 480, 7380],
            [60, 20, 580, 450, 7370],
            [80, 30, 600, 400, 7360],
        ]
        LecturaSensor.objects.create(
            dispositivo_id=self.dispositivo_id,
            track_id=3,
            m1=500,
            m2=500,
            vbat_mv=7400,
            muestras=muestras_burst
        )
        res = self.client.get(reverse('pista') + '?track_id=3')
        self.assertEqual(res.status_code, 200)
        pista_data = res.json()
        self.assertEqual(pista_data["track_id"], 3)
        self.assertGreaterEqual(pista_data["total_points"], len(muestras_burst))


class DashAndWSGIIntegrationTests(TestCase):
    def setUp(self):
        self.dispositivo_id = "idline_esp32"
        EstadoRobot.objects.get_or_create(
            dispositivo_id=self.dispositivo_id,
            defaults={'active_track_id': 1}
        )

    def test_07_dash_layout_renders_without_errors(self):
        """Verify Dash app layout compiles and produces a valid component tree."""
        layout = dash_app.layout
        self.assertIsNotNone(layout)
        # Check that children container is rendered
        self.assertTrue(hasattr(layout, 'children'))

    def test_08_dash_telemetry_update_callback(self):
        """Verify Dash update_telemetry callback produces valid figures and badges."""
        LecturaSensor.objects.create(
            dispositivo_id=self.dispositivo_id,
            track_id=1,
            m1=580,
            m2=580,
            vbat_mv=8200,
            sensores=[500, 1200, 2500, 3000, 1800, 900, 400, 350],
            posicion=20,
            modo="RUNNING"
        )
        outputs = update_telemetry(n_intervals=1, selected_track_id=1)
        (
            status_text, status_color, vbat_text, modo_text,
            motores_text, track_text, track_opts, view_track,
            fig_map, fig_sens, fig_hist,
            reticle_pos_text, reticle_pointer_style
        ) = outputs

        self.assertIn("ONLINE", status_text)
        self.assertIn("8.20 V", vbat_text)
        self.assertIn("RUNNING", modo_text)
        self.assertIn("M1: 580 | M2: 580", motores_text)
        self.assertIn("PISTA ACTIVA #1", track_text)
        self.assertEqual(view_track, 1)
        self.assertIsNotNone(fig_map)
        self.assertIsNotNone(fig_sens)
        self.assertIsNotNone(fig_hist)
        self.assertEqual(reticle_pos_text, "+20")
        self.assertIn("left", reticle_pointer_style)

    def test_10_dash_command_handlers(self):
        """Verify Dash queue_command and command dispatch."""
        from unittest.mock import patch
        from dashboard.app import queue_command

        # Test queue_command directly
        msg_start = queue_command(self.dispositivo_id, "start_pid")
        self.assertIn("start_pid", msg_start)

        cmd_db = ComandoPendiente.objects.filter(dispositivo_id=self.dispositivo_id, cmd="start_pid").first()
        self.assertIsNotNone(cmd_db)
        self.assertFalse(cmd_db.ejecutado)

        # Test new_track increments active_track_id
        msg_track = queue_command(self.dispositivo_id, "new_track")
        self.assertIn("Pista #2", msg_track)

        estado = EstadoRobot.objects.get(dispositivo_id=self.dispositivo_id)
        self.assertEqual(estado.active_track_id, 2)

    def test_09_wsgi_dispatcher_middleware_routes_cleanly(self):
        """
        Verify Werkzeug DispatcherMiddleware routing:
        - '/' redirects to '/dashboard/'
        - '/dashboard/' serves Dash UI
        - '/api/datos/' serves DRF API
        - '/api/pista/' serves odometry API
        """
        client = WerkzeugClient(wsgi_application)

        # 1. Root redirect
        res_root = client.get('/')
        self.assertIn(res_root.status_code, [301, 302])
        self.assertEqual(res_root.headers.get('Location'), '/dashboard/')

        # 2. Dash UI
        res_dash = client.get('/dashboard/')
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b"<!DOCTYPE html>", res_dash.data)

        # 3. API Datos
        res_api = client.get('/api/datos/')
        self.assertEqual(res_api.status_code, 200)
        self.assertIn('application/json', res_api.headers.get('Content-Type', ''))

        # 4. API Pista
        res_pista = client.get('/api/pista/')
        self.assertEqual(res_pista.status_code, 200)
        self.assertIn('application/json', res_pista.headers.get('Content-Type', ''))

    def test_11_battery_percentage_mapping_and_badge(self):
        """Verify 2S Li-Ion 6400-8400 mV percentage mapping and badge formatting."""
        self.assertIsNone(vbat_mv_to_percent(None))
        self.assertIsNone(vbat_mv_to_percent(0))
        self.assertEqual(vbat_mv_to_percent(6000), 0)
        self.assertEqual(vbat_mv_to_percent(6400), 0)
        self.assertEqual(vbat_mv_to_percent(7400), 50)
        self.assertEqual(vbat_mv_to_percent(8400), 100)
        self.assertEqual(vbat_mv_to_percent(8600), 100)

        text_none, _ = format_vbat_badge(None)
        self.assertEqual(text_none, "--% · --.- V")

        text_full, style_full = format_vbat_badge(8200)
        self.assertEqual(text_full, "90% · 8.20 V")
        self.assertEqual(style_full["color"], "#1D4ED8")

        text_low, style_low = format_vbat_badge(6600)
        self.assertEqual(text_low, "10% · 6.60 V")
        self.assertEqual(style_low["color"], "#B91C1C")

    def test_12_fast_and_charts_callbacks_short_circuit(self):
        """Verify split Dash callbacks update on new reading and short-circuit when idle."""
        from dash import no_update

        r = LecturaSensor.objects.create(
            dispositivo_id=self.dispositivo_id,
            track_id=1,
            m1=400,
            m2=420,
            vbat_mv=7900,
            sensores=[200, 300, 2100, 2500, 300, 200, 150, 100],
            posicion=-15,
            modo="RUNNING"
        )

        fast_out = update_fast_telemetry(1, None)
        self.assertEqual(fast_out[0], "ONLINE")
        self.assertEqual(fast_out[2], "75% · 7.90 V")
        self.assertEqual(fast_out[8], "-15")
        fast_state = fast_out[10]
        self.assertEqual(fast_state["id"], r.id)

        # Second tick with same state must short-circuit with no_update
        fast_idle = update_fast_telemetry(2, fast_state)
        self.assertTrue(all(x is no_update for x in fast_idle))

        charts_out = update_charts_telemetry(1, 1, None)
        self.assertEqual(charts_out[1], 1)
        charts_state = charts_out[4]
        self.assertEqual(charts_state["id"], r.id)

        charts_idle = update_charts_telemetry(2, 1, charts_state)
        self.assertTrue(all(x is no_update for x in charts_idle))

    def test_13_post_datos_batch_cmds(self):
        """Verify POST /api/datos/ with batch_cmds=True pops multiple pending commands."""
        ComandoPendiente.objects.create(dispositivo_id=self.dispositivo_id, cmd="set_pid", payload={"speed": 680})
        ComandoPendiente.objects.create(dispositivo_id=self.dispositivo_id, cmd="start_pid", payload={})

        res = self.client.post(
            reverse('datos'),
            data=json.dumps({
                "dispositivo_id": self.dispositivo_id,
                "sensores": [200] * 8,
                "vbat_mv": 8000,
                "batch_cmds": True,
            }),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertEqual(len(body["comandos"]), 2)
        self.assertEqual(body["comandos"][0]["cmd"], "set_pid")
        self.assertEqual(body["comandos"][1]["cmd"], "start_pid")
        self.assertEqual(body["comando"]["cmd"], "set_pid")
        self.assertEqual(
            ComandoPendiente.objects.filter(dispositivo_id=self.dispositivo_id, ejecutado=False).count(),
            0
        )

    def test_14_odometry_skips_leading_idle_points(self):
        """Verify leading stationary points are skipped and WHEELBASE_M is 0.128."""
        from .odometry import WHEELBASE_M
        self.assertEqual(WHEELBASE_M, 0.128)

        # Sequential readings with 2 leading idle points
        idle1 = LecturaSensor.objects.create(dispositivo_id=self.dispositivo_id, track_id=10, m1=0, m2=0, vbat_mv=7400)
        idle2 = LecturaSensor.objects.create(dispositivo_id=self.dispositivo_id, track_id=10, m1=20, m2=-30, vbat_mv=7400)
        move1 = LecturaSensor.objects.create(dispositivo_id=self.dispositivo_id, track_id=10, m1=500, m2=500, vbat_mv=7400)
        res_seq = reconstruct_trajectory([idle1, idle2, move1])
        self.assertEqual(res_seq["total_points"], 2)  # origin + move1
        self.assertEqual(res_seq["trajectory"][0]["m1"], 500)

        # All-stationary readings keep at least 1 point
        res_all_idle = reconstruct_trajectory([idle1, idle2])
        self.assertGreaterEqual(res_all_idle["total_points"], 1)
        self.assertEqual(res_all_idle["total_distance_m"], 0.0)

        # Burst muestras with leading idle samples
        burst = LecturaSensor.objects.create(
            dispositivo_id=self.dispositivo_id,
            track_id=11,
            m1=0,
            m2=0,
            vbat_mv=7400,
            muestras=[
                [0, 0, 0, 0, 7400],
                [20, 0, 15, -10, 7400],
                [40, 5, 500, 500, 7400],
            ],
        )
        res_burst = reconstruct_trajectory([burst])
        self.assertEqual(res_burst["total_points"], 2)  # origin + moving sample
        self.assertEqual(res_burst["trajectory"][0]["m1"], 500)

    def test_15_delete_track_command(self):
        """Verify btn-delete-track deletes readings and updates active_track_id."""
        from unittest.mock import patch, MagicMock
        LecturaSensor.objects.create(dispositivo_id=self.dispositivo_id, track_id=1, m1=500, m2=500)
        LecturaSensor.objects.create(dispositivo_id=self.dispositivo_id, track_id=2, m1=500, m2=500)
        LecturaSensor.objects.create(dispositivo_id=self.dispositivo_id, track_id=2, m1=520, m2=520)
        estado, _ = EstadoRobot.objects.get_or_create(
            dispositivo_id=self.dispositivo_id, defaults={'active_track_id': 2}
        )
        estado.active_track_id = 2
        estado.save()

        mock_ctx = MagicMock()
        mock_ctx.triggered_id = "btn-delete-track"
        with patch("dashboard.app.ctx", mock_ctx):
            # Delete active track 2 -> should fall back to max remaining track (1)
            msg, color = handle_commands(*([None] * 16), 0, 0, 2)
            self.assertIn("PISTA #2 eliminada (2 lecturas)", msg)
            self.assertEqual(LecturaSensor.objects.filter(dispositivo_id=self.dispositivo_id, track_id=2).count(), 0)
            estado.refresh_from_db()
            self.assertEqual(estado.active_track_id, 1)

            # Delete last remaining track 1 -> should reset active_track_id to 1
            msg2, _ = handle_commands(*([None] * 16), 0, 0, 1)
            self.assertIn("PISTA #1 eliminada (1 lecturas)", msg2)
            estado.refresh_from_db()
            self.assertEqual(estado.active_track_id, 1)


class VisionAndAlignmentTests(TestCase):
    def setUp(self):
        self.client = DjangoClient()
        self.device_id = "idline_esp32"
        self.sample_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="

    def _mock_gemini_response(self, text_payload):
        from unittest.mock import MagicMock
        body = json.dumps({
            "candidates": [
                {"content": {"parts": [{"text": text_payload}]}}
            ]
        }).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        return mock_resp

    def test_16_get_pista_referencia_not_found(self):
        """GET /api/pista/referencia/ returns 404 with empty points when none exists."""
        res = self.client.get(reverse('pista_referencia') + f'?device_id={self.device_id}')
        self.assertEqual(res.status_code, 404)
        body = res.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["points"], [])
        self.assertFalse(body["closed"])

    def test_17_post_pista_referencia_missing_api_key(self):
        """POST /api/pista/referencia/ returns 503 when GEMINI_API_KEY is missing."""
        import os
        from unittest.mock import patch

        env_without_key = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env_without_key, clear=True):
            res = self.client.post(
                reverse('pista_referencia'),
                data=json.dumps({
                    "image_base64": self.sample_b64,
                    "mime_type": "image/png",
                    "device_id": self.device_id,
                }),
                content_type='application/json',
            )
        self.assertEqual(res.status_code, 503)
        body = res.json()
        self.assertFalse(body["ok"])
        self.assertIn("GEMINI_API_KEY", body["error"])

    def test_18_post_and_get_pista_referencia_multiview_and_per_track(self):
        """POST /api/pista/referencia/ (2-4 images + per-track_id) and GET with mocked urlopen."""
        import os
        from unittest.mock import patch
        from django.core.files.uploadedfile import SimpleUploadedFile

        gemini_t1 = json.dumps({
            "points": [[-0.1, 0.2], [0.5, 0.2], [1.2, 0.8], [0.2, 0.8]],
            "closed": True,
        })

        # 1. Multi-view JSON (3 opposite-corner images) for track_id=1
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-fake-key"}):
            with patch("urllib.request.urlopen", return_value=self._mock_gemini_response(gemini_t1)) as mock_open:
                res_post = self.client.post(
                    reverse('pista_referencia'),
                    data=json.dumps({
                        "device_id": self.device_id,
                        "track_id": 1,
                        "images": [
                            {"image_base64": f"data:image/png;base64,{self.sample_b64}", "mime_type": "image/png"},
                            {"image_base64": self.sample_b64, "mime_type": "image/jpeg"},
                            {"image_base64": self.sample_b64, "mime_type": "image/jpeg"},
                        ],
                    }),
                    content_type='application/json',
                )
        self.assertEqual(res_post.status_code, 200)
        self.assertEqual(mock_open.call_count, 1)

        # Verify all 3 images were sent as inline_data parts in a single Gemini payload
        sent_req = mock_open.call_args[0][0]
        sent_payload = json.loads(sent_req.data.decode("utf-8"))
        parts = sent_payload["contents"][0]["parts"]
        inline_parts = [p for p in parts if "inline_data" in p]
        self.assertEqual(len(inline_parts), 3)

        body = res_post.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["track_id"], 1)
        self.assertEqual(body["photo_count"], 3)
        self.assertTrue(body["closed"])
        # Coordinates must be clamped to [0.0, 1.0]
        self.assertEqual(body["points"][0], [0.0, 0.2])
        self.assertEqual(body["points"][2], [1.0, 0.8])

        ref_t1 = PistaReferencia.objects.get(device_id=self.device_id, track_id=1)
        self.assertEqual(ref_t1.photo_count, 3)
        self.assertEqual(len(ref_t1.points_json), 4)

        # 2. Multipart 2-image upload for track_id=2 stores a separate PistaReferencia
        gemini_t2 = json.dumps({
            "points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]],
            "closed": False,
        })
        files = [
            SimpleUploadedFile("corner1.png", b"\x89PNG\r\n\x1a\nfake1", content_type="image/png"),
            SimpleUploadedFile("corner2.png", b"\x89PNG\r\n\x1a\nfake2", content_type="image/png"),
        ]
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-fake-key"}):
            with patch("urllib.request.urlopen", return_value=self._mock_gemini_response(gemini_t2)) as mock_open_mp:
                res_mp = self.client.post(
                    reverse('pista_referencia'),
                    data={"images": files, "device_id": self.device_id, "track_id": 2},
                )
        self.assertEqual(res_mp.status_code, 200)
        self.assertEqual(mock_open_mp.call_count, 1)
        mp_payload = json.loads(mock_open_mp.call_args[0][0].data.decode("utf-8"))
        mp_inline = [p for p in mp_payload["contents"][0]["parts"] if "inline_data" in p]
        self.assertEqual(len(mp_inline), 2)
        self.assertEqual(res_mp.json()["track_id"], 2)
        self.assertEqual(res_mp.json()["photo_count"], 2)
        self.assertFalse(res_mp.json()["closed"])

        # Both track_id=1 and track_id=2 exist independently
        self.assertEqual(PistaReferencia.objects.filter(device_id=self.device_id).count(), 2)

        # GET per track_id returns the matching reference or 404
        res_get_1 = self.client.get(reverse('pista_referencia') + f'?device_id={self.device_id}&track_id=1')
        self.assertEqual(res_get_1.status_code, 200)
        self.assertEqual(res_get_1.json()["track_id"], 1)
        self.assertEqual(res_get_1.json()["points"], body["points"])

        res_get_2 = self.client.get(reverse('pista_referencia') + f'?device_id={self.device_id}&track_id=2')
        self.assertEqual(res_get_2.status_code, 200)
        self.assertEqual(res_get_2.json()["track_id"], 2)
        self.assertEqual(len(res_get_2.json()["points"]), 3)

        res_get_99 = self.client.get(reverse('pista_referencia') + f'?device_id={self.device_id}&track_id=99')
        self.assertEqual(res_get_99.status_code, 404)

    def test_19_post_pista_referencia_validation_errors(self):
        """POST /api/pista/referencia/ rejects missing payload, >4 images (400), and invalid Gemini JSON."""
        import os
        from unittest.mock import patch

        res_empty = self.client.post(
            reverse('pista_referencia'),
            data=json.dumps({"device_id": self.device_id}),
            content_type='application/json',
        )
        self.assertEqual(res_empty.status_code, 400)

        # > 4 images must be rejected with 400 without calling Gemini
        too_many = [{"image_base64": self.sample_b64, "mime_type": "image/png"} for _ in range(5)]
        res_too_many = self.client.post(
            reverse('pista_referencia'),
            data=json.dumps({"device_id": self.device_id, "track_id": 1, "images": too_many}),
            content_type='application/json',
        )
        self.assertEqual(res_too_many.status_code, 400)
        self.assertFalse(res_too_many.json()["ok"])

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-fake-key"}):
            with patch("urllib.request.urlopen", return_value=self._mock_gemini_response('{"points": [[0.5, 0.5]]}')):
                res_bad_pts = self.client.post(
                    reverse('pista_referencia'),
                    data=json.dumps({"image_base64": self.sample_b64}),
                    content_type='application/json',
                )
        self.assertEqual(res_bad_pts.status_code, 502)

    def test_20_align_trajectory_to_reference_normal_and_edge_cases(self):
        """Verify 2D similarity alignment and edge cases in align_trajectory_to_reference."""
        import math

        # Edge cases: empty, <2 points, degenerate zero-variance
        self.assertEqual(align_trajectory_to_reference([], [[0.0, 0.0], [1.0, 1.0]]), [])
        single = [{"x": 1.0, "y": 2.0, "m1": 500}]
        aligned_single = align_trajectory_to_reference(single, [[0.0, 0.0], [1.0, 1.0]])
        self.assertEqual(aligned_single, single)
        self.assertIsNot(aligned_single[0], single[0])

        traj_few_ref = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}]
        self.assertEqual(align_trajectory_to_reference(traj_few_ref, [[0.5, 0.5]]), traj_few_ref)

        # Degenerate (all identical points) should translate centroid without NaN/ZeroDivisionError
        degen = [{"x": 2.0, "y": 3.0}, {"x": 2.0, "y": 3.0}, {"x": 2.0, "y": 3.0}]
        ref_line = [[0.2, 0.4], [0.6, 0.8]]
        aligned_degen = align_trajectory_to_reference(degen, ref_line)
        self.assertAlmostEqual(aligned_degen[0]["x"], 0.4, places=5)
        self.assertAlmostEqual(aligned_degen[0]["y"], 0.6, places=5)

        # Normal similarity transform: scale=2.5, rotate 90 deg, translate (1.0, -0.5)
        ref_square = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
        traj_dicts = []
        for idx, (rx, ry) in enumerate(ref_square):
            # Rotate +90 deg: (x, y) -> (-y, x), scale 2.5, shift (+1.0, -0.5)
            tx = 1.0 + 2.5 * (-ry)
            ty = -0.5 + 2.5 * rx
            traj_dicts.append({"x": tx, "y": ty, "m1": 600 + idx, "t": idx * 0.1})

        aligned = align_trajectory_to_reference(traj_dicts, ref_square)
        for pt, (rx, ry) in zip(aligned, ref_square):
            self.assertAlmostEqual(pt["x"], rx, places=4)
            self.assertAlmostEqual(pt["y"], ry, places=4)
        # Preserves extra keys and does not mutate input
        self.assertEqual(aligned[2]["m1"], 602)
        self.assertNotAlmostEqual(traj_dicts[0]["x"], ref_square[0][0], places=2)

        # Tuple format and different point counts (arc-length resampling)
        traj_tuples = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (2.0, 1.0), (2.0, 2.0)]
        ref_l = [[0.1, 0.1], [0.1, 0.5], [0.5, 0.5]]
        aligned_tuples = align_trajectory_to_reference(traj_tuples, ref_l)
        self.assertIsInstance(aligned_tuples[0], tuple)
        self.assertEqual(len(aligned_tuples), len(traj_tuples))
        self.assertTrue(all(math.isfinite(x) and math.isfinite(y) for x, y in aligned_tuples))

    def test_21_dash_upload_and_track_map_overlay(self):
        """Verify Dash multi-view upload validation (2-4 photos) and per-track_id Pista Real (IA) overlay."""
        import os
        from unittest.mock import patch
        from dash import no_update

        EstadoRobot.objects.get_or_create(dispositivo_id=self.device_id, defaults={"active_track_id": 1})
        r1_a = LecturaSensor.objects.create(dispositivo_id=self.device_id, track_id=1, m1=500, m2=500, vbat_mv=7800)
        r1_b = LecturaSensor.objects.create(dispositivo_id=self.device_id, track_id=1, m1=500, m2=350, vbat_mv=7800)
        r2_a = LecturaSensor.objects.create(dispositivo_id=self.device_id, track_id=2, m1=600, m2=600, vbat_mv=7900)
        r2_b = LecturaSensor.objects.create(dispositivo_id=self.device_id, track_id=2, m1=600, m2=400, vbat_mv=7900)

        data_uri = f"data:image/png;base64,{self.sample_b64}"

        # 1. < 2 photos returns warning alert and no_update without calling Gemini
        with patch("urllib.request.urlopen") as mock_open_lt2:
            alert_lt2, map_lt2 = handle_track_photo_upload(
                [data_uri],
                ["corner1.png"],
                1,
            )
        self.assertEqual(alert_lt2.color, "warning")
        self.assertIn("2 y 4", alert_lt2.children)
        self.assertIs(map_lt2, no_update)
        self.assertEqual(mock_open_lt2.call_count, 0)

        # 2. > 4 photos returns warning alert and no_update without calling Gemini
        with patch("urllib.request.urlopen") as mock_open_gt4:
            alert_gt4, map_gt4 = handle_track_photo_upload(
                [data_uri] * 5,
                [f"c{i}.png" for i in range(5)],
                1,
            )
        self.assertEqual(alert_gt4.color, "warning")
        self.assertIn("2 y 4", alert_gt4.children)
        self.assertIs(map_gt4, no_update)
        self.assertEqual(mock_open_gt4.call_count, 0)

        # 3. Missing GEMINI_API_KEY with 2 photos returns warning alert and no_update without crashing
        env_without_key = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env_without_key, clear=True):
            alert_err, map_err = handle_track_photo_upload(
                [data_uri, data_uri],
                ["c1.png", "c2.png"],
                1,
            )
        self.assertEqual(alert_err.color, "warning")
        self.assertIn("GEMINI_API_KEY", alert_err.children)
        self.assertIs(map_err, no_update)

        # 4. Successful 2-photo upload for track 1 overlays 'Pista Real (IA)' on graph-track-map
        gemini_t1 = json.dumps({
            "points": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
            "closed": True,
        })
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-fake-key"}):
            with patch("urllib.request.urlopen", return_value=self._mock_gemini_response(gemini_t1)):
                alert_ok, fig_map_1 = handle_track_photo_upload(
                    [data_uri, data_uri],
                    ["c1.png", "c2.png"],
                    1,
                )
        self.assertEqual(alert_ok.color, "success")
        self.assertIn("Pista #1", alert_ok.children)
        self.assertIn("2 fotos", alert_ok.children)
        self.assertIn("4 puntos", alert_ok.children)
        trace_names_1 = [t.name for t in fig_map_1.data]
        self.assertIn("Pista Real (IA)", trace_names_1)
        self.assertIn("Trayectoria del Robot", trace_names_1)

        # 5. Per-track_id isolation: track 2 does NOT show track 1's Pista Real (IA)
        fig_map_2_before = build_track_map_figure([r2_a, r2_b], 2)
        self.assertNotIn("Pista Real (IA)", [t.name for t in fig_map_2_before.data])

        # Uploading 2 photos for track 2 shows Pista Real (IA) only for track 2
        gemini_t2 = json.dumps({
            "points": [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]],
            "closed": True,
        })
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-fake-key"}):
            with patch("urllib.request.urlopen", return_value=self._mock_gemini_response(gemini_t2)):
                alert_ok_2, fig_map_2_after = handle_track_photo_upload(
                    [data_uri, data_uri],
                    ["t2_a.png", "t2_b.png"],
                    2,
                )
        self.assertEqual(alert_ok_2.color, "success")
        self.assertIn("Pista #2", alert_ok_2.children)
        self.assertIn("3 puntos", alert_ok_2.children)
        self.assertIn("Pista Real (IA)", [t.name for t in fig_map_2_after.data])
        self.assertEqual(PistaReferencia.objects.filter(device_id=self.device_id).count(), 2)
        # Track 1 still has its 4-point reference (4 + 1 closing point = 5 in Plotly trace)
        fig_map_1_check = build_track_map_figure([r1_a, r1_b], 1)
        ia_trace_1 = [t for t in fig_map_1_check.data if t.name == "Pista Real (IA)"][0]
        self.assertEqual(len(ia_trace_1.x), 5)
