import json
import os
import sys
from datetime import datetime, timezone

# Ensure Django settings are available
server_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'API.settings')
import django
try:
    django.setup()
except RuntimeError:
    pass

import dash
from dash import dcc, html, Input, Output, State, ctx, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from telemetria.models import LecturaSensor, EstadoRobot, ComandoPendiente
from telemetria.odometry import reconstruct_trajectory

try:
    from telemetria import odometry as _odometry_mod
    align_trajectory_to_reference = getattr(_odometry_mod, 'align_trajectory_to_reference', None)
except ImportError:
    align_trajectory_to_reference = None

# Initialize Dash application with BOOTSTRAP (Light Theme)
app = dash.Dash(
    __name__,
    requests_pathname_prefix='/dashboard/',
    routes_pathname_prefix='/',
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="IDLine ESP32 — Telemetria & Odometria"
)

server = app.server

# ---------------------------------------------------------
# APPLE HIG WHITE & BLUE DESIGN SYSTEM CONSTANTS
# ---------------------------------------------------------
FONT_FAMILY = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", Roboto, Helvetica, Arial, sans-serif'

# Palette
BG_PAGE = "#F5F5F7"
BG_CARD = "#FFFFFF"
BG_SUBTLE = "#F8FAFC"
BORDER_LIGHT = "#E2E8F0"
BORDER_DARK = "#CBD5E1"
TEXT_MAIN = "#0F172A"
TEXT_MUTED = "#64748B"
BLUE_PRIMARY = "#2563EB"
BLUE_DARK = "#1D4ED8"
BLUE_BG = "#EFF6FF"
BLUE_BORDER = "#BFDBFE"
RED_STOP = "#DC2626"

STYLE_CONTAINER = {
    "backgroundColor": BG_PAGE,
    "minHeight": "100vh",
    "padding": "16px 22px",
    "fontFamily": FONT_FAMILY,
    "color": TEXT_MAIN,
}

STYLE_CARD = {
    "backgroundColor": BG_CARD,
    "border": f"1px solid {BORDER_LIGHT}",
    "borderRadius": "12px",
    "boxShadow": "0 1px 3px rgba(0, 0, 0, 0.04)",
    "overflow": "hidden",
}

STYLE_CARD_HEADER = {
    "backgroundColor": BG_CARD,
    "borderBottom": f"1px solid {BORDER_LIGHT}",
    "padding": "11px 16px",
    "color": TEXT_MUTED,
    "fontSize": "11px",
    "fontWeight": "700",
    "letterSpacing": "0.06em",
    "textTransform": "uppercase",
    "display": "flex",
    "alignItems": "center",
    "justifyContent": "space-between",
}

STYLE_CARD_BODY = {
    "backgroundColor": BG_CARD,
    "padding": "15px 16px",
    "color": TEXT_MAIN,
}

STYLE_BTN_START = {
    "backgroundColor": BLUE_PRIMARY,
    "borderColor": BLUE_PRIMARY,
    "color": "#FFFFFF",
    "fontWeight": "600",
    "fontSize": "13px",
    "letterSpacing": "0.02em",
    "borderRadius": "8px",
}

STYLE_BTN_STOP = {
    "backgroundColor": RED_STOP,
    "borderColor": RED_STOP,
    "color": "#FFFFFF",
    "fontWeight": "600",
    "fontSize": "13px",
    "letterSpacing": "0.02em",
    "borderRadius": "8px",
}

STYLE_BTN_SECONDARY = {
    "backgroundColor": "#F1F5F9",
    "border": f"1px solid {BORDER_DARK}",
    "color": TEXT_MAIN,
    "fontWeight": "600",
    "fontSize": "12px",
    "borderRadius": "8px",
}

STYLE_BTN_PROFILE = {
    "backgroundColor": BLUE_BG,
    "border": f"1px solid {BLUE_BORDER}",
    "color": BLUE_DARK,
    "fontWeight": "600",
    "fontSize": "11px",
    "borderRadius": "8px",
    "padding": "6px 2px",
    "textAlign": "center",
    "width": "100%",
}

STYLE_BTN_DPAD = {
    "backgroundColor": BG_SUBTLE,
    "border": f"1px solid {BORDER_DARK}",
    "color": TEXT_MAIN,
    "fontWeight": "600",
    "fontSize": "11px",
    "letterSpacing": "0.02em",
    "borderRadius": "8px",
    "padding": "7px 4px",
}

STYLE_BADGE_PILL = {
    "fontFamily": FONT_FAMILY,
    "fontWeight": "600",
    "fontSize": "12px",
    "letterSpacing": "0.02em",
    "padding": "6px 12px",
    "borderRadius": "999px",
    "border": f"1px solid {BORDER_DARK}",
    "backgroundColor": BG_SUBTLE,
    "color": TEXT_MAIN,
    "display": "inline-flex",
    "alignItems": "center",
    "justifyContent": "center",
    "textDecoration": "none",
}


# 2S Li-Ion battery range (GEMINI.md: 7.4V nominal, 8.4V max; config.h: 6.4V cutoff)
VBAT_MIN_MV = 6400
VBAT_MAX_MV = 8400


def vbat_mv_to_percent(vbat_mv) -> int | None:
    """Convert 2S Li-Ion battery voltage in mV to 0-100%."""
    if vbat_mv is None or vbat_mv <= 0:
        return None
    pct = round((float(vbat_mv) - VBAT_MIN_MV) * 100.0 / (VBAT_MAX_MV - VBAT_MIN_MV))
    return max(0, min(100, int(pct)))


def format_vbat_badge(vbat_mv) -> tuple[str, dict]:
    """Return (badge_text, badge_style) with live % and voltage for 2S Li-Ion."""
    base_style = {
        **STYLE_BADGE_PILL,
        "backgroundColor": BLUE_BG,
        "color": BLUE_DARK,
        "border": f"1px solid {BLUE_BORDER}",
    }
    pct = vbat_mv_to_percent(vbat_mv)
    if pct is None:
        return "--% · --.- V", base_style

    text = f"{pct}% · {vbat_mv / 1000.0:.2f} V"
    if pct < 20:
        style = {
            **STYLE_BADGE_PILL,
            "backgroundColor": "#FEE2E2",
            "color": "#B91C1C",
            "border": "1px solid #FECACA",
        }
    elif pct < 50:
        style = {
            **STYLE_BADGE_PILL,
            "backgroundColor": "#FEF3C7",
            "color": "#B45309",
            "border": "1px solid #FDE68A",
        }
    else:
        style = base_style
    return text, style


# Helper function to queue commands in SQLite
def queue_command(dispositivo_id: str, cmd: str, payload: dict = None) -> str:
    if payload is None:
        payload = {}
    estado, _ = EstadoRobot.objects.get_or_create(
        dispositivo_id=dispositivo_id,
        defaults={'active_track_id': 1}
    )
    if cmd == 'new_track':
        estado.active_track_id += 1
        estado.save(update_fields=['active_track_id', 'actualizado'])
        payload['new_track_id'] = estado.active_track_id

    comando = ComandoPendiente.objects.create(
        dispositivo_id=dispositivo_id,
        cmd=cmd,
        payload=payload,
        ejecutado=False
    )
    if cmd == 'new_track':
        return f"Pista #{estado.active_track_id} creada y comando 'new_track' encolado (ID: {comando.id})"
    return f"Comando '{cmd}' encolado exitosamente (ID: {comando.id})"


def build_sensors_figure(sensor_vals):
    fig_sens = go.Figure()
    channel_labels = [f"C{i}" for i in range(4, 12)]

    fig_sens.add_trace(go.Bar(
        x=channel_labels,
        y=[4095] * 8,
        marker=dict(
            color="#F1F5F9",
            line=dict(color=BORDER_DARK, width=1)
        ),
        hoverinfo="none",
        showlegend=False,
        name="Slot"
    ))

    fig_sens.add_trace(go.Bar(
        x=channel_labels,
        y=sensor_vals,
        marker=dict(
            color=[BLUE_PRIMARY if v > 1500 else "#0284C7" for v in sensor_vals],
            line=dict(color=BLUE_DARK, width=1)
        ),
        text=[f"{v}" if v > 0 else "" for v in sensor_vals],
        textposition="outside",
        textfont=dict(color=TEXT_MAIN, size=9, family=FONT_FAMILY),
        hoverinfo="x+y",
        showlegend=False,
        name="ADC Raw"
    ))

    fig_sens.update_layout(
        template='plotly_white',
        paper_bgcolor=BG_CARD,
        plot_bgcolor=BG_SUBTLE,
        barmode='overlay',
        margin=dict(l=38, r=16, t=14, b=24),
        showlegend=False,
        yaxis=dict(
            range=[0, 4300],
            title=dict(text="ADC Raw", font=dict(color=TEXT_MUTED, size=9, family=FONT_FAMILY)),
            showgrid=True,
            gridcolor=BORDER_LIGHT,
            tickfont=dict(color=TEXT_MUTED, size=8, family=FONT_FAMILY)
        ),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(color=TEXT_MAIN, size=10, family=FONT_FAMILY)
        )
    )
    return fig_sens


# DASH LAYOUT (Apple HIG White & Blue - Studio Workspace)
app.layout = dbc.Container([
    # Split intervals: fast (800ms) for live badges/reticle/sensors; charts rebuild reactively on state change
    dcc.Interval(id='interval-fast', interval=800, n_intervals=0),
    dcc.Interval(id='interval-charts', interval=4000, n_intervals=0, disabled=True),
    dcc.Store(id='store-fast-state', data=None),
    dcc.Store(id='store-charts-state', data=None),

    # 1. SLEEK TOP BAR (HEADER)
    dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span("IDLINE ESP32", style={
                            "fontWeight": "800",
                            "fontSize": "18px",
                            "color": TEXT_MAIN,
                            "letterSpacing": "-0.01em"
                        }),
                        html.Span("STUDIO TELEMETRIA & ODOMETRIA", style={
                            "fontSize": "11px",
                            "fontWeight": "600",
                            "color": TEXT_MUTED,
                            "marginLeft": "12px",
                            "letterSpacing": "0.06em",
                            "textTransform": "uppercase"
                        }),
                    ], className="d-flex align-items-center"),
                ], md=4, xs=12, className="d-flex align-items-center mb-2 mb-md-0"),
                dbc.Col([
                    html.Div([
                        dbc.Badge("OFFLINE", id="badge-status", color="secondary", style={
                            **STYLE_BADGE_PILL,
                            "border": f"1px solid {BORDER_DARK}",
                        }),
                        dbc.Badge("--% · --.- V", id="badge-vbat", color="light", style={
                            **STYLE_BADGE_PILL,
                            "backgroundColor": BLUE_BG,
                            "color": BLUE_DARK,
                            "border": f"1px solid {BLUE_BORDER}",
                        }),
                        dbc.Badge("MODO: --", id="badge-modo", color="light", style=STYLE_BADGE_PILL),
                        dbc.Badge("M1: 0 | M2: 0", id="badge-motores", color="light", style=STYLE_BADGE_PILL),
                        dbc.Badge("PISTA #1", id="badge-track", color="light", style={
                            **STYLE_BADGE_PILL,
                            "backgroundColor": BLUE_BG,
                            "color": BLUE_DARK,
                            "border": f"1px solid {BLUE_BORDER}",
                        }),
                    ], className="d-flex flex-wrap gap-2 justify-content-md-end align-items-center"),
                ], md=8, xs=12),
            ], className="align-items-center"),
        ], style={"padding": "12px 18px", "backgroundColor": BG_CARD}),
    ], style={**STYLE_CARD, "marginBottom": "16px"}),

    # 2. MAIN 2-COLUMN STUDIO WORKSPACE
    dbc.Row([
        # -------------------------------------------------------------
        # LEFT COLUMN (lg=4, md=12) — UNIFIED CONTROL SIDEBAR
        # -------------------------------------------------------------
        dbc.Col([
            # CARD 1: CONTROL DE CARRERA Y PISTA
            dbc.Card([
                dbc.CardHeader(html.Div("CONTROL DE CARRERA Y PISTA", style=STYLE_CARD_HEADER), style={"padding": 0, "border": "none"}),
                dbc.CardBody([
                    dbc.Button("ARRANCAR (START)", id="btn-start", style={**STYLE_BTN_START, "width": "100%", "padding": "10px", "marginBottom": "8px"}),
                    dbc.Row([
                        dbc.Col([
                            dbc.Button("PARAR", id="btn-stop", style={**STYLE_BTN_STOP, "width": "100%", "padding": "9px"}),
                        ], xs=6),
                        dbc.Col([
                            dbc.Button("CALIBRAR", id="btn-calib", style={**STYLE_BTN_SECONDARY, "width": "100%", "padding": "9px"}),
                        ], xs=6),
                    ], className="mb-3 g-2"),
                    html.Div("PERFILES DE COMPETICION PID", style={
                        "color": TEXT_MUTED,
                        "fontSize": "10px",
                        "fontWeight": "700",
                        "letterSpacing": "0.08em",
                        "marginBottom": "6px"
                    }),
                    dbc.Row([
                        dbc.Col([
                            dbc.Button(["CARRERA", html.Br(), html.Span("680 PWM", style={"fontSize": "9px", "color": "inherit", "opacity": "0.85", "fontWeight": "500"})], id="btn-prof-carrera", style=STYLE_BTN_PROFILE),
                        ], xs=3),
                        dbc.Col([
                            dbc.Button(["SEGURO", html.Br(), html.Span("580 PWM", style={"fontSize": "9px", "color": "inherit", "opacity": "0.85", "fontWeight": "500"})], id="btn-prof-seguro", style=STYLE_BTN_PROFILE),
                        ], xs=3),
                        dbc.Col([
                            dbc.Button(["ATAQUE", html.Br(), html.Span("750 PWM", style={"fontSize": "9px", "color": "inherit", "opacity": "0.85", "fontWeight": "500"})], id="btn-prof-ataque", style=STYLE_BTN_PROFILE),
                        ], xs=3),
                        dbc.Col([
                            dbc.Button(["ARQUITEC", html.Br(), html.Span("500 PWM", style={"fontSize": "9px", "color": "inherit", "opacity": "0.85", "fontWeight": "500"})], id="btn-prof-arquitec", style=STYLE_BTN_PROFILE),
                        ], xs=3),
                    ], className="g-1 mb-2"),
                    html.Hr(style={"borderColor": BORDER_LIGHT, "margin": "12px 0 10px 0"}),
                    html.Div("SESION DE PISTA & MEMORIA", style={
                        "color": TEXT_MUTED,
                        "fontSize": "10px",
                        "fontWeight": "700",
                        "letterSpacing": "0.08em",
                        "marginBottom": "6px"
                    }),
                    dbc.Row([
                        dbc.Col([
                            dbc.Button("NUEVA PISTA", id="btn-new-track", style={**STYLE_BTN_START, "width": "100%", "padding": "8px", "fontSize": "12px"}),
                        ], xs=6),
                        dbc.Col([
                            dbc.Button("CARGAR MEMORIA", id="btn-upload-memory", style={**STYLE_BTN_SECONDARY, "width": "100%", "padding": "8px", "fontSize": "12px"}),
                        ], xs=6),
                    ], className="g-2 mb-2"),
                    dcc.Upload(
                        id="upload-track-photo",
                        children=html.Div([
                            html.Div("SUBIR 2-4 FOTOS DE PISTA", style={"fontWeight": "700", "fontSize": "12px"}),
                            html.Div(
                                "Selecciona 2 a 4 fotos desde esquinas opuestas del tablero blanco para triangular la pista",
                                style={"fontSize": "10px", "color": TEXT_MUTED, "marginTop": "2px"},
                            ),
                        ]),
                        accept="image/*",
                        multiple=True,
                        style={
                            "width": "100%",
                            "padding": "9px 12px",
                            "borderWidth": "1px",
                            "borderStyle": "dashed",
                            "borderColor": BLUE_BORDER,
                            "borderRadius": "8px",
                            "textAlign": "center",
                            "backgroundColor": BLUE_BG,
                            "color": BLUE_DARK,
                            "cursor": "pointer",
                            "marginBottom": "8px",
                            "transition": "all 0.15s ease",
                        },
                    ),
                    dcc.Loading(
                        id="loading-upload-track",
                        type="dot",
                        color=BLUE_PRIMARY,
                        children=html.Div(id="upload-track-feedback", style={"marginBottom": "6px"}),
                    ),
                    dbc.Button(
                        "BORRAR REFERENCIA IA",
                        id="btn-clear-ref-track",
                        style={
                            "backgroundColor": "#FFFFFF",
                            "border": "1px solid #E2E8F0",
                            "color": TEXT_MUTED,
                            "fontWeight": "600",
                            "fontSize": "11px",
                            "letterSpacing": "0.04em",
                            "borderRadius": "8px",
                            "padding": "5px 10px",
                            "width": "100%",
                            "marginBottom": "10px",
                        },
                    ),
                    html.Div("HISTORIAL DE PISTAS", style={
                        "color": TEXT_MUTED,
                        "fontSize": "10px",
                        "fontWeight": "700",
                        "letterSpacing": "0.08em",
                        "marginBottom": "4px"
                    }),
                    dcc.Dropdown(
                        id="dropdown-track-id",
                        options=[{"label": "Pista #1 (Activa)", "value": 1}],
                        value=1,
                        clearable=False,
                        style={"color": TEXT_MAIN, "borderRadius": "8px", "fontSize": "13px"}
                    ),
                    dbc.Button(
                        "ELIMINAR PISTA",
                        id="btn-delete-track",
                        style={
                            "backgroundColor": "#FEF2F2",
                            "border": "1px solid #FECACA",
                            "color": RED_STOP,
                            "fontWeight": "600",
                            "fontSize": "11px",
                            "letterSpacing": "0.04em",
                            "borderRadius": "8px",
                            "padding": "6px 10px",
                            "width": "100%",
                            "marginTop": "8px",
                        },
                    ),
                ], style=STYLE_CARD_BODY),
            ], style={**STYLE_CARD, "marginBottom": "16px"}),

            # CARD 2: CONTROL MANUAL DE MOTORES
            dbc.Card([
                dbc.CardHeader(html.Div("CONTROL MANUAL DE MOTORES", style=STYLE_CARD_HEADER), style={"padding": 0, "border": "none"}),
                dbc.CardBody([
                    # Direction Pad
                    dbc.Row([
                        dbc.Col(
                            dbc.Button("AVANZAR", id="btn-fwd", style={**STYLE_BTN_DPAD, "width": "100%"}),
                            width={"size": 6, "offset": 3},
                            className="mb-1"
                        ),
                    ]),
                    dbc.Row([
                        dbc.Col(dbc.Button("GIRO IZQ", id="btn-left", style={**STYLE_BTN_DPAD, "width": "100%"}), width=4),
                        dbc.Col(dbc.Button("TEST", id="btn-test", style={**STYLE_BTN_DPAD, "width": "100%", "borderColor": BLUE_BORDER, "color": BLUE_PRIMARY, "fontWeight": "700"}), width=4),
                        dbc.Col(dbc.Button("GIRO DER", id="btn-right", style={**STYLE_BTN_DPAD, "width": "100%"}), width=4),
                    ], className="g-1 mb-1"),
                    dbc.Row([
                        dbc.Col(
                            dbc.Button("REVERSA", id="btn-rev", style={**STYLE_BTN_DPAD, "width": "100%"}),
                            width={"size": 6, "offset": 3},
                            className="mb-2"
                        ),
                    ]),
                    # Motor Sliders
                    html.Small("SLIDER M1 (MOTOR IZQUIERDO)", style={"color": TEXT_MUTED, "fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.05em", "display": "block", "marginTop": "4px"}),
                    dcc.Slider(
                        id="slider-m1",
                        min=-255,
                        max=255,
                        step=5,
                        value=0,
                        marks={
                            -255: {"label": "-255", "style": {"color": TEXT_MUTED, "fontSize": "10px", "fontWeight": "600"}},
                            0: {"label": "0", "style": {"color": TEXT_MUTED, "fontSize": "10px", "fontWeight": "600"}},
                            255: {"label": "255", "style": {"color": TEXT_MUTED, "fontSize": "10px", "fontWeight": "600"}},
                        }
                    ),
                    html.Small("SLIDER M2 (MOTOR DERECHO)", style={"color": TEXT_MUTED, "fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.05em", "display": "block", "marginTop": "6px"}),
                    dcc.Slider(
                        id="slider-m2",
                        min=-255,
                        max=255,
                        step=5,
                        value=0,
                        marks={
                            -255: {"label": "-255", "style": {"color": TEXT_MUTED, "fontSize": "10px", "fontWeight": "600"}},
                            0: {"label": "0", "style": {"color": TEXT_MUTED, "fontSize": "10px", "fontWeight": "600"}},
                            255: {"label": "255", "style": {"color": TEXT_MUTED, "fontSize": "10px", "fontWeight": "600"}},
                        }
                    ),
                    dbc.Button("APLICAR PWM MANUAL", id="btn-send-sliders", style={
                        **STYLE_BTN_SECONDARY,
                        "width": "100%",
                        "marginTop": "10px",
                        "padding": "7px",
                        "fontSize": "11px",
                        "backgroundColor": BLUE_BG,
                        "color": BLUE_DARK,
                        "borderColor": BLUE_BORDER
                    }),
                    dcc.Loading(
                        id="loading-cmd-status",
                        type="dot",
                        color=BLUE_PRIMARY,
                        children=dbc.Alert("Listo para recibir telemetria o enviar ordenes.", id="alert-cmd-status", color="light", style={
                            "backgroundColor": BG_SUBTLE,
                            "border": f"1px solid {BORDER_LIGHT}",
                            "color": "#334155",
                            "borderRadius": "8px",
                            "fontSize": "12px",
                            "padding": "8px 12px",
                            "marginTop": "10px",
                            "marginBottom": "0"
                        }),
                    ),
                ], style=STYLE_CARD_BODY),
            ], style=STYLE_CARD),
        ], lg=4, md=12, className="mb-3"),

        # -------------------------------------------------------------
        # RIGHT COLUMN (lg=8, md=12) — LIVE TELEMETRY & ODOMETRY CANVAS
        # -------------------------------------------------------------
        dbc.Col([
            # TOP ROW: MAPA DE PISTA + SENSORES & POSICION
            dbc.Row([
                # 1. Reconstructed Track Map
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.Div("MAPA DE PISTA RECONSTRUIDO", style=STYLE_CARD_HEADER), style={"padding": 0, "border": "none"}),
                        dbc.CardBody([
                            dcc.Graph(id="graph-track-map", style={"height": "340px"}, config={"displayModeBar": True, "responsive": True}),
                        ], style={"padding": "4px", "backgroundColor": BG_CARD}),
                    ], style={**STYLE_CARD, "marginBottom": "16px"}),
                ], lg=7, xs=12),

                # 2. Sensor Bar Chart (C4-C11) + Position Reticle
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.Div("SENSORES C4–C11 & POSICION", style=STYLE_CARD_HEADER), style={"padding": 0, "border": "none"}),
                        dbc.CardBody([
                            dcc.Graph(id="graph-sensors", figure=build_sensors_figure([0] * 8), style={"height": "245px"}, config={"displayModeBar": False, "responsive": True}),
                            html.Div([
                                html.Div([
                                    html.Span("POSICION DE LINEA", style={"fontSize": "10px", "fontWeight": "700", "color": TEXT_MUTED, "letterSpacing": "0.06em"}),
                                    html.Span("+0", id="reticle-pos-text", style={
                                        "fontSize": "12px", "fontWeight": "700", "color": BLUE_DARK,
                                        "backgroundColor": BLUE_BG, "border": f"1px solid {BLUE_BORDER}",
                                        "borderRadius": "999px", "padding": "2px 10px"
                                    }),
                                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "8px"}),
                                html.Div([
                                    html.Div(style={
                                        "position": "absolute", "left": "50%", "top": "0", "bottom": "0",
                                        "width": "2px", "backgroundColor": BORDER_DARK, "transform": "translateX(-50%)"
                                    }),
                                    html.Div(id="reticle-pointer", style={
                                        "position": "absolute", "left": "50%", "top": "50%",
                                        "width": "18px", "height": "18px", "borderRadius": "50%",
                                        "backgroundColor": BLUE_PRIMARY, "border": "2px solid #FFFFFF",
                                        "boxShadow": "0 1px 4px rgba(37, 99, 235, 0.45)",
                                        "transform": "translate(-50%, -50%)", "transition": "left 0.12s ease-out"
                                    }),
                                ], style={
                                    "position": "relative", "height": "28px", "backgroundColor": "#F1F5F9",
                                    "border": f"1px solid {BORDER_DARK}", "borderRadius": "999px", "overflow": "hidden"
                                }),
                                html.Div([
                                    html.Span("-1000 (IZQ)"),
                                    html.Span("0 (CENTRO)"),
                                    html.Span("+1000 (DER)"),
                                ], style={
                                    "display": "flex", "justifyContent": "space-between",
                                    "fontSize": "10px", "fontWeight": "600", "color": TEXT_MUTED, "marginTop": "4px"
                                }),
                            ], style={"padding": "10px 12px 6px 12px", "borderTop": f"1px solid {BORDER_LIGHT}"}),
                        ], style={"padding": "4px", "backgroundColor": BG_CARD}),
                    ], style={**STYLE_CARD, "marginBottom": "16px"}),
                ], lg=5, xs=12),
            ]),

            # BOTTOM ROW: TELEMETRY HISTORY
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.Div("HISTORIAL DE MOTORES Y LINEA", style=STYLE_CARD_HEADER), style={"padding": 0, "border": "none"}),
                        dbc.CardBody([
                            dcc.Graph(id="graph-telemetry-history", style={"height": "230px"}, config={"displayModeBar": True, "responsive": True}),
                        ], style={"padding": "4px", "backgroundColor": BG_CARD}),
                    ], style=STYLE_CARD),
                ], xs=12),
            ]),
        ], lg=8, md=12),
    ], className="g-3"),
], fluid=True, style=STYLE_CONTAINER)


# DASH CALLBACK: COMMAND HANDLING
@app.callback(
    Output("alert-cmd-status", "children"),
    Output("alert-cmd-status", "color"),
    [
        Input("btn-start", "n_clicks"),
        Input("btn-stop", "n_clicks"),
        Input("btn-calib", "n_clicks"),
        Input("btn-prof-carrera", "n_clicks"),
        Input("btn-prof-seguro", "n_clicks"),
        Input("btn-prof-ataque", "n_clicks"),
        Input("btn-prof-arquitec", "n_clicks"),
        Input("btn-fwd", "n_clicks"),
        Input("btn-rev", "n_clicks"),
        Input("btn-left", "n_clicks"),
        Input("btn-right", "n_clicks"),
        Input("btn-test", "n_clicks"),
        Input("btn-send-sliders", "n_clicks"),
        Input("btn-new-track", "n_clicks"),
        Input("btn-upload-memory", "n_clicks"),
        Input("btn-delete-track", "n_clicks"),
    ],
    [
        State("slider-m1", "value"),
        State("slider-m2", "value"),
        State("dropdown-track-id", "value"),
    ],
    prevent_initial_call=True
)
def handle_commands(*args):
    trig = ctx.triggered_id
    if not trig:
        return "Sin cambios.", "light"

    slider_m1 = args[-3] or 0
    slider_m2 = args[-2] or 0
    selected_track_id = args[-1]
    disp_id = "idline_esp32"

    if trig == "btn-start":
        msg = queue_command(disp_id, "start_pid")
        return f"START: {msg}", "primary"
    elif trig == "btn-stop":
        msg = queue_command(disp_id, "stop")
        return f"STOP: {msg}", "danger"
    elif trig == "btn-calib":
        msg = queue_command(disp_id, "calibrate")
        return f"CALIBRAR: {msg}", "primary"
    elif trig == "btn-prof-carrera":
        msg = queue_command(disp_id, "set_pid", {"speed": 680, "kp": 0.58, "ki": 0.0, "kd": 4.0})
        return f"PERFIL CARRERA (680): {msg}", "primary"
    elif trig == "btn-prof-seguro":
        msg = queue_command(disp_id, "set_pid", {"speed": 580, "kp": 0.62, "ki": 0.0, "kd": 3.6})
        return f"PERFIL SEGURO (580): {msg}", "primary"
    elif trig == "btn-prof-ataque":
        msg = queue_command(disp_id, "set_pid", {"speed": 750, "kp": 0.48, "ki": 0.0, "kd": 4.4})
        return f"PERFIL ATAQUE (750): {msg}", "primary"
    elif trig == "btn-prof-arquitec":
        msg = queue_command(disp_id, "set_pid", {"speed": 500, "kp": 0.55, "ki": 0.0, "kd": 3.5})
        return f"PERFIL ARQUITEC (500): {msg}", "primary"
    elif trig == "btn-fwd":
        msg = queue_command(disp_id, "set_motores", {"m1": 180, "m2": 180})
        return f"AVANZAR: {msg}", "primary"
    elif trig == "btn-rev":
        msg = queue_command(disp_id, "set_motores", {"m1": -180, "m2": -180})
        return f"REVERSA: {msg}", "primary"
    elif trig == "btn-left":
        msg = queue_command(disp_id, "set_motores", {"m1": -150, "m2": 150})
        return f"GIRO IZQ: {msg}", "primary"
    elif trig == "btn-right":
        msg = queue_command(disp_id, "set_motores", {"m1": 150, "m2": -150})
        return f"GIRO DER: {msg}", "primary"
    elif trig == "btn-test":
        msg = queue_command(disp_id, "test")
        return f"TEST: {msg}", "primary"
    elif trig == "btn-send-sliders":
        msg = queue_command(disp_id, "set_motores", {"m1": int(slider_m1), "m2": int(slider_m2)})
        return f"SLIDERS M1={slider_m1}, M2={slider_m2}: {msg}", "primary"
    elif trig == "btn-new-track":
        msg = queue_command(disp_id, "new_track")
        return f"NUEVA PISTA: {msg}", "primary"
    elif trig == "btn-upload-memory":
        msg = queue_command(disp_id, "upload_memory")
        return f"VOLCADO MEMORIA: {msg}", "primary"
    elif trig == "btn-delete-track":
        if selected_track_id is None:
            return "Selecciona una pista válida para eliminar.", "warning"
        track_id = int(selected_track_id)
        deleted_count, _ = LecturaSensor.objects.filter(
            dispositivo_id=disp_id, track_id=track_id
        ).delete()
        try:
            from telemetria.models import PistaReferencia
            PistaReferencia.objects.filter(device_id=disp_id, track_id=track_id).delete()
        except Exception:
            pass
        remaining_qs = LecturaSensor.objects.filter(dispositivo_id=disp_id)
        estado, _ = EstadoRobot.objects.get_or_create(
            dispositivo_id=disp_id, defaults={'active_track_id': 1}
        )
        if not remaining_qs.exists():
            if estado.active_track_id != 1:
                estado.active_track_id = 1
                estado.save(update_fields=['active_track_id', 'actualizado'])
        elif estado.active_track_id == track_id:
            max_track = (
                remaining_qs.order_by('-track_id')
                .values_list('track_id', flat=True)
                .first()
                or 1
            )
            estado.active_track_id = max_track
            estado.save(update_fields=['active_track_id', 'actualizado'])
        return f"PISTA #{track_id} eliminada ({deleted_count} lecturas).", "warning"

    return "Listo.", "light"


# CLIENTSIDE CALLBACKS: 0ms INSTANT VISUAL FEEDBACK
app.clientside_callback(
    """
    function() {
        const ctx = window.dash_clientside.callback_context;
        if (!ctx || !ctx.triggered || ctx.triggered.length === 0) {
            return Array(4).fill(window.dash_clientside.no_update);
        }
        const trig = ctx.triggered[0].prop_id.split('.')[0];
        const baseStyle = {
            backgroundColor: "#EFF6FF",
            border: "1px solid #BFDBFE",
            color: "#1D4ED8",
            fontWeight: "600",
            fontSize: "11px",
            borderRadius: "8px",
            padding: "6px 2px",
            textAlign: "center",
            width: "100%"
        };
        const activeStyle = {
            backgroundColor: "#2563EB",
            border: "1px solid #1D4ED8",
            color: "#FFFFFF",
            fontWeight: "700",
            fontSize: "11px",
            borderRadius: "8px",
            padding: "6px 2px",
            textAlign: "center",
            width: "100%",
            boxShadow: "0 2px 6px rgba(37, 99, 235, 0.35)"
        };
        const ids = ["btn-prof-carrera", "btn-prof-seguro", "btn-prof-ataque", "btn-prof-arquitec"];
        return ids.map(id => (id === trig ? activeStyle : baseStyle));
    }
    """,
    Output("btn-prof-carrera", "style"),
    Output("btn-prof-seguro", "style"),
    Output("btn-prof-ataque", "style"),
    Output("btn-prof-arquitec", "style"),
    Input("btn-prof-carrera", "n_clicks"),
    Input("btn-prof-seguro", "n_clicks"),
    Input("btn-prof-ataque", "n_clicks"),
    Input("btn-prof-arquitec", "n_clicks"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function() {
        const ctx = window.dash_clientside.callback_context;
        if (!ctx || !ctx.triggered || ctx.triggered.length === 0) {
            return Array(6).fill(window.dash_clientside.no_update);
        }
        const trig = ctx.triggered[0].prop_id.split('.')[0];
        const dpadBase = {
            backgroundColor: "#F8FAFC",
            border: "1px solid #CBD5E1",
            color: "#0F172A",
            fontWeight: "600",
            fontSize: "11px",
            letterSpacing: "0.02em",
            borderRadius: "8px",
            padding: "7px 4px",
            width: "100%"
        };
        const testBase = Object.assign({}, dpadBase, {
            borderColor: "#BFDBFE",
            color: "#2563EB",
            fontWeight: "700"
        });
        const slidersBase = {
            backgroundColor: "#EFF6FF",
            border: "1px solid #BFDBFE",
            color: "#1D4ED8",
            fontWeight: "600",
            fontSize: "11px",
            borderRadius: "8px",
            width: "100%",
            marginTop: "10px",
            padding: "7px"
        };
        const activeDpad = Object.assign({}, dpadBase, {
            backgroundColor: "#DBEAFE",
            border: "2px solid #0284C7",
            color: "#1D4ED8",
            fontWeight: "700",
            boxShadow: "0 0 0 2px rgba(2, 132, 199, 0.18)"
        });
        const activeSliders = Object.assign({}, slidersBase, {
            backgroundColor: "#DBEAFE",
            border: "2px solid #0284C7",
            color: "#1D4ED8",
            fontWeight: "700",
            boxShadow: "0 0 0 2px rgba(2, 132, 199, 0.18)"
        });

        const ids = ["btn-fwd", "btn-rev", "btn-left", "btn-right", "btn-test", "btn-send-sliders"];
        const bases = [dpadBase, dpadBase, dpadBase, dpadBase, testBase, slidersBase];
        if (trig === "btn-stop" || trig === "btn-start") {
            return bases;
        }
        return ids.map((id, idx) => {
            if (id === trig) {
                return id === "btn-send-sliders" ? activeSliders : activeDpad;
            }
            return bases[idx];
        });
    }
    """,
    Output("btn-fwd", "style"),
    Output("btn-rev", "style"),
    Output("btn-left", "style"),
    Output("btn-right", "style"),
    Output("btn-test", "style"),
    Output("btn-send-sliders", "style"),
    Input("btn-fwd", "n_clicks"),
    Input("btn-rev", "n_clicks"),
    Input("btn-left", "n_clicks"),
    Input("btn-right", "n_clicks"),
    Input("btn-test", "n_clicks"),
    Input("btn-send-sliders", "n_clicks"),
    Input("btn-stop", "n_clicks"),
    Input("btn-start", "n_clicks"),
    prevent_initial_call=True,
)


app.clientside_callback(
    """
    function() {
        const ctx = window.dash_clientside.callback_context;
        if (!ctx || !ctx.triggered || ctx.triggered.length === 0) {
            return Array(6).fill(window.dash_clientside.no_update);
        }
        const trig = ctx.triggered[0].prop_id.split('.')[0];
        const styles = {
            "btn-start": {
                backgroundColor: "#2563EB", borderColor: "#2563EB", color: "#FFFFFF",
                fontWeight: "600", fontSize: "13px", letterSpacing: "0.02em",
                borderRadius: "8px", width: "100%", padding: "10px", marginBottom: "8px",
                transition: "all 0.15s ease"
            },
            "btn-stop": {
                backgroundColor: "#DC2626", borderColor: "#DC2626", color: "#FFFFFF",
                fontWeight: "600", fontSize: "13px", letterSpacing: "0.02em",
                borderRadius: "8px", width: "100%", padding: "9px",
                transition: "all 0.15s ease"
            },
            "btn-calib": {
                backgroundColor: "#F1F5F9", border: "1px solid #CBD5E1", color: "#0F172A",
                fontWeight: "600", fontSize: "12px", borderRadius: "8px",
                width: "100%", padding: "9px", transition: "all 0.15s ease"
            },
            "btn-new-track": {
                backgroundColor: "#2563EB", borderColor: "#2563EB", color: "#FFFFFF",
                fontWeight: "600", fontSize: "12px", letterSpacing: "0.02em",
                borderRadius: "8px", width: "100%", padding: "8px",
                transition: "all 0.15s ease"
            },
            "btn-upload-memory": {
                backgroundColor: "#F1F5F9", border: "1px solid #CBD5E1", color: "#0F172A",
                fontWeight: "600", fontSize: "12px", borderRadius: "8px",
                width: "100%", padding: "8px", transition: "all 0.15s ease"
            },
            "btn-delete-track": {
                backgroundColor: "#FEF2F2", border: "1px solid #FECACA", color: "#DC2626",
                fontWeight: "600", fontSize: "11px", letterSpacing: "0.04em",
                borderRadius: "8px", padding: "6px 10px", width: "100%", marginTop: "8px",
                transition: "all 0.15s ease"
            }
        };
        const ids = ["btn-start", "btn-stop", "btn-calib", "btn-new-track", "btn-upload-memory", "btn-delete-track"];
        return ids.map(id => {
            const base = Object.assign({}, styles[id]);
            if (id === trig) {
                if (id === "btn-stop" || id === "btn-delete-track") {
                    base.boxShadow = "0 0 0 3px rgba(220, 38, 38, 0.28)";
                    base.borderColor = "#991B1B";
                } else {
                    base.boxShadow = "0 0 0 3px rgba(37, 99, 235, 0.28)";
                    base.borderColor = "#1D4ED8";
                }
            }
            return base;
        });
    }
    """,
    Output("btn-start", "style"),
    Output("btn-stop", "style"),
    Output("btn-calib", "style"),
    Output("btn-new-track", "style"),
    Output("btn-upload-memory", "style"),
    Output("btn-delete-track", "style"),
    Input("btn-start", "n_clicks"),
    Input("btn-stop", "n_clicks"),
    Input("btn-calib", "n_clicks"),
    Input("btn-new-track", "n_clicks"),
    Input("btn-upload-memory", "n_clicks"),
    Input("btn-delete-track", "n_clicks"),
    prevent_initial_call=True,
)


def _get_latest_reference_track(dispositivo_id: str = "idline_esp32", track_id=None):
    """Fetch the latest AI-extracted reference track for (dispositivo_id, track_id), if available."""
    try:
        from telemetria.models import PistaReferencia
    except ImportError:
        return None

    try:
        field_names = {f.name for f in PistaReferencia._meta.get_fields()}
        filter_kwargs = {}
        if "device_id" in field_names:
            filter_kwargs["device_id"] = dispositivo_id
        elif "dispositivo_id" in field_names:
            filter_kwargs["dispositivo_id"] = dispositivo_id

        if track_id is not None and "track_id" in field_names:
            filter_kwargs["track_id"] = int(track_id)

        order_field = "-updated_at" if "updated_at" in field_names else "-id"
        try:
            ref = PistaReferencia.objects.filter(**filter_kwargs).order_by(order_field).first()
        except Exception:
            if "track_id" in filter_kwargs:
                filter_kwargs.pop("track_id", None)
                ref = PistaReferencia.objects.filter(**filter_kwargs).order_by(order_field).first()
            else:
                raise
        if not ref:
            return None

        points = getattr(ref, "points_json", None)
        if points is None:
            points = getattr(ref, "points", None)
        if not isinstance(points, list) or len(points) < 2:
            return None

        closed = bool(getattr(ref, "closed", False))
        updated_at = getattr(ref, "updated_at", None) or getattr(ref, "created_at", None)
        return {
            "points": points,
            "closed": closed,
            "track_id": getattr(ref, "track_id", track_id),
            "photo_count": getattr(ref, "photo_count", 1),
            "updated_at": updated_at.isoformat() if updated_at else str(ref.pk),
        }
    except Exception:
        return None


def _extract_ref_xy(points, closed=False):
    """Extract (xs, ys) lists from normalized [[x, y], ...] or [{'x':..., 'y':...}] points."""
    xs, ys = [], []
    for pt in points:
        if isinstance(pt, dict):
            x, y = pt.get("x"), pt.get("y")
        elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
            x, y = pt[0], pt[1]
        else:
            continue
        if x is not None and y is not None:
            xs.append(float(x))
            ys.append(float(y))
    if closed and len(xs) >= 2 and (xs[0] != xs[-1] or ys[0] != ys[-1]):
        xs.append(xs[0])
        ys.append(ys[0])
    return xs, ys


def build_track_map_figure(track_readings, current_view_track):
    """Build the reconstructed trajectory figure for the selected track."""
    rec = reconstruct_trajectory(track_readings)
    traj = rec.get("trajectory", [])
    ref = _get_latest_reference_track("idline_esp32", track_id=current_view_track)

    fig_map = go.Figure()
    has_ref = bool(ref and len(ref.get("points", [])) >= 2)

    if has_ref:
        ref_xs, ref_ys = _extract_ref_xy(ref["points"], closed=ref.get("closed", False))
        if len(ref_xs) >= 2:
            fig_map.add_trace(go.Scatter(
                x=ref_xs, y=ref_ys,
                mode='lines',
                name='Pista Real (IA)',
                line=dict(color='#10B981', width=2.5, dash='dash'),
                opacity=0.85,
            ))
            if traj and align_trajectory_to_reference is not None:
                try:
                    traj = align_trajectory_to_reference(traj, ref["points"])
                except Exception:
                    pass
        else:
            has_ref = False

    if traj:
        xs = [p["x"] for p in traj]
        ys = [p["y"] for p in traj]

        fig_map.add_trace(go.Scatter(
            x=xs, y=ys,
            mode='lines',
            name='Trayectoria del Robot',
            line=dict(color=BLUE_PRIMARY, width=3)
        ))
        fig_map.add_trace(go.Scatter(
            x=[xs[0]], y=[ys[0]],
            mode='markers+text',
            name='Inicio',
            marker=dict(color='#0284C7', size=11, symbol='circle'),
            text=['INICIO'],
            textposition='top right',
            textfont=dict(color='#0284C7', size=9, family=FONT_FAMILY)
        ))
        fig_map.add_trace(go.Scatter(
            x=[xs[-1]], y=[ys[-1]],
            mode='markers+text',
            name='Robot',
            marker=dict(color=TEXT_MAIN, size=13, symbol='circle', line=dict(color=BLUE_PRIMARY, width=2)),
            text=['ROBOT'],
            textposition='top center',
            textfont=dict(color=TEXT_MAIN, size=9, family=FONT_FAMILY)
        ))

        tot_dist = rec.get("total_distance_m", 0.0)
        dur = rec.get("duration_s", 0.0)
        align_tag = " | Alineada a IA" if has_ref else ""
        map_subtitle = f"Pista #{current_view_track} | Distancia: {tot_dist:.2f} m | Duración: {dur:.1f} s | {len(traj)} pts{align_tag}"
        fig_map.update_layout(
            title=dict(text=map_subtitle, font=dict(size=10, color=TEXT_MUTED, family=FONT_FAMILY), x=0.03, y=0.97)
        )
    elif has_ref:
        map_subtitle = f"Pista #{current_view_track} | Pista Real (IA): {len(ref['points'])} pts — Esperando telemetría"
        fig_map.update_layout(
            title=dict(text=map_subtitle, font=dict(size=10, color=TEXT_MUTED, family=FONT_FAMILY), x=0.03, y=0.97)
        )
    else:
        fig_map.add_annotation(
            text="Sin datos de trayectoria en esta pista",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(color=TEXT_MUTED, size=12, family=FONT_FAMILY)
        )
        fig_map.update_xaxes(range=[-1, 1])
        fig_map.update_yaxes(range=[-1, 1])

    fig_map.update_layout(
        template='plotly_white',
        paper_bgcolor=BG_CARD,
        plot_bgcolor=BG_SUBTLE,
        margin=dict(l=35, r=20, t=28, b=28),
        xaxis=dict(
            title=dict(text="X (metros)", font=dict(color=TEXT_MUTED, size=9, family=FONT_FAMILY)),
            showgrid=True, gridcolor=BORDER_LIGHT, zeroline=True, zerolinecolor=BORDER_DARK,
            tickfont=dict(color=TEXT_MUTED, size=9, family=FONT_FAMILY)
        ),
        yaxis=dict(
            title=dict(text="Y (metros)", font=dict(color=TEXT_MUTED, size=9, family=FONT_FAMILY)),
            showgrid=True, gridcolor=BORDER_LIGHT, zeroline=True, zerolinecolor=BORDER_DARK,
            scaleanchor="x", scaleratio=1,
            tickfont=dict(color=TEXT_MUTED, size=9, family=FONT_FAMILY)
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1, font=dict(size=9, color=TEXT_MUTED, family=FONT_FAMILY))
    )
    return fig_map


def build_history_figure(recent_readings):
    """Build the motor & line position history figure."""
    fig_hist = go.Figure()
    if recent_readings:
        indices = list(range(len(recent_readings)))
        m1_vals = [r.m1 for r in recent_readings]
        m2_vals = [r.m2 for r in recent_readings]
        pos_vals = [r.posicion for r in recent_readings]

        fig_hist.add_trace(go.Scatter(
            x=indices, y=m1_vals,
            mode='lines',
            name='M1 (Izq)',
            line=dict(color=BLUE_PRIMARY, width=2)
        ))
        fig_hist.add_trace(go.Scatter(
            x=indices, y=m2_vals,
            mode='lines',
            name='M2 (Der)',
            line=dict(color='#0EA5E9', width=2)
        ))
        fig_hist.add_trace(go.Scatter(
            x=indices, y=pos_vals,
            mode='lines',
            name='Posicion',
            line=dict(color=TEXT_MUTED, width=1.5, dash='dot')
        ))
    else:
        fig_hist.add_annotation(
            text="Sin historial de lecturas.",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(color=TEXT_MUTED, size=12, family=FONT_FAMILY)
        )

    fig_hist.update_layout(
        template='plotly_white',
        paper_bgcolor=BG_CARD,
        plot_bgcolor=BG_SUBTLE,
        margin=dict(l=35, r=20, t=25, b=25),
        xaxis=dict(
            title=dict(text="Muestra (#)", font=dict(color=TEXT_MUTED, size=9, family=FONT_FAMILY)),
            showgrid=True, gridcolor=BORDER_LIGHT,
            tickfont=dict(color=TEXT_MUTED, size=8, family=FONT_FAMILY)
        ),
        yaxis=dict(
            title=dict(text="PWM / Posicion", font=dict(color=TEXT_MUTED, size=9, family=FONT_FAMILY)),
            showgrid=True, gridcolor=BORDER_LIGHT,
            tickfont=dict(color=TEXT_MUTED, size=8, family=FONT_FAMILY)
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1, font=dict(size=9, color=TEXT_MUTED, family=FONT_FAMILY))
    )
    return fig_hist


def _build_reticle_style(pos_val: int) -> dict:
    reticle_pct = max(4.0, min(96.0, 50.0 + (pos_val / 1000.0) * 46.0))
    return {
        "position": "absolute", "left": f"{reticle_pct:.1f}%", "top": "50%",
        "width": "18px", "height": "18px", "borderRadius": "50%",
        "backgroundColor": BLUE_PRIMARY, "border": "2px solid #FFFFFF",
        "boxShadow": "0 1px 4px rgba(37, 99, 235, 0.45)",
        "transform": "translate(-50%, -50%)", "transition": "left 0.12s ease-out"
    }


# DASH CALLBACK 1: FAST LIVE TELEMETRY (300ms - badges, battery %, reticle, sensor bars)
@app.callback(
    Output("badge-status", "children"),
    Output("badge-status", "color"),
    Output("badge-vbat", "children"),
    Output("badge-vbat", "style"),
    Output("badge-modo", "children"),
    Output("badge-motores", "children"),
    Output("badge-track", "children"),
    Output("graph-sensors", "figure"),
    Output("reticle-pos-text", "children"),
    Output("reticle-pointer", "style"),
    Output("store-fast-state", "data"),
    Input("interval-fast", "n_intervals"),
    State("store-fast-state", "data"),
)
def update_fast_telemetry(n_intervals, prev_state):
    disp_id = "idline_esp32"
    active_track = (
        EstadoRobot.objects.filter(dispositivo_id=disp_id)
        .values_list('active_track_id', flat=True)
        .first()
    ) or 1

    latest = (
        LecturaSensor.objects.filter(dispositivo_id=disp_id)
        .only('id', 'modo', 'm1', 'm2', 'vbat_mv', 'posicion', 'sensores', 'timestamp')
        .order_by('-id')
        .first()
    )

    latest_id = latest.id if latest else None
    is_online = False
    if latest and latest.timestamp:
        diff = (datetime.now(timezone.utc) - latest.timestamp).total_seconds()
        is_online = diff <= 8.0

    status_badge_text = "ONLINE" if is_online else "OFFLINE"
    status_badge_color = "primary" if is_online else "secondary"
    new_state = {"id": latest_id, "online": is_online, "track": active_track}

    # Short-circuit if nothing changed since last tick
    if isinstance(prev_state, dict) and prev_state == new_state:
        return (no_update,) * 11

    # If only online/offline flipped without a new reading, update only status badge
    if (
        isinstance(prev_state, dict)
        and prev_state.get("id") == latest_id
        and prev_state.get("track") == active_track
    ):
        return (
            status_badge_text,
            status_badge_color,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            new_state,
        )

    vbat_text, vbat_style = format_vbat_badge(latest.vbat_mv if latest else None)
    modo_text = f"MODO: {latest.modo}" if latest else "MODO: IDLE"
    motores_text = f"M1: {latest.m1} | M2: {latest.m2}" if latest else "M1: 0 | M2: 0"
    track_badge_text = f"PISTA ACTIVA #{active_track}"

    sensor_vals = [0] * 8
    pos_val = 0
    if latest and latest.sensores and isinstance(latest.sensores, list):
        s_list = latest.sensores[:8]
        sensor_vals = s_list + [0] * (8 - len(s_list))
        pos_val = latest.posicion

    fig_sens = build_sensors_figure(sensor_vals)
    reticle_pos_text = f"{pos_val:+d}"
    reticle_pointer_style = _build_reticle_style(pos_val)

    return (
        status_badge_text,
        status_badge_color,
        vbat_text,
        vbat_style,
        modo_text,
        motores_text,
        track_badge_text,
        fig_sens,
        reticle_pos_text,
        reticle_pointer_style,
        new_state,
    )


# DASH CALLBACK 2: CHARTS & TRACK HISTORY (reactive on store-fast-state or track dropdown)
@app.callback(
    Output("dropdown-track-id", "options"),
    Output("dropdown-track-id", "value"),
    Output("graph-track-map", "figure"),
    Output("graph-telemetry-history", "figure"),
    Output("store-charts-state", "data"),
    Input("store-fast-state", "data"),
    Input("dropdown-track-id", "value"),
    State("store-charts-state", "data"),
)
def update_charts_telemetry(fast_state, selected_track_id, prev_state):
    disp_id = "idline_esp32"
    active_track = (
        EstadoRobot.objects.filter(dispositivo_id=disp_id)
        .values_list('active_track_id', flat=True)
        .first()
    ) or 1
    latest_id = (
        LecturaSensor.objects.filter(dispositivo_id=disp_id)
        .values_list('id', flat=True)
        .order_by('-id')
        .first()
    )

    try:
        triggered_id = ctx.triggered_id
    except Exception:
        triggered_id = None

    lookup_track = selected_track_id if selected_track_id is not None else active_track
    ref_info = _get_latest_reference_track(disp_id, track_id=lookup_track)
    ref_updated = ref_info.get("updated_at") if ref_info else None
    new_state = {
        "id": latest_id,
        "track": selected_track_id,
        "active": active_track,
        "ref": ref_updated,
    }
    if (
        triggered_id != "dropdown-track-id"
        and isinstance(prev_state, dict)
        and prev_state == new_state
    ):
        return (no_update,) * 5

    db_tracks = list(
        LecturaSensor.objects.filter(dispositivo_id=disp_id)
        .values_list('track_id', flat=True)
        .distinct()
    )
    if active_track not in db_tracks:
        db_tracks.append(active_track)
    db_tracks = sorted(list(set(db_tracks)))

    track_options = [
        {"label": f"Pista #{t}{' (En Curso)' if t == active_track else ''}", "value": t}
        for t in db_tracks
    ]
    current_view_track = selected_track_id if selected_track_id in db_tracks else active_track
    new_state["track"] = current_view_track

    track_readings = list(
        LecturaSensor.objects.filter(
            dispositivo_id=disp_id,
            track_id=current_view_track
        )
        .only('id', 'm1', 'm2', 'vbat_mv', 'posicion', 'timestamp', 'muestras')
        .order_by('id')
    )
    fig_map = build_track_map_figure(track_readings, current_view_track)

    recent_readings = list(
        LecturaSensor.objects.filter(dispositivo_id=disp_id)
        .only('id', 'm1', 'm2', 'posicion')
        .order_by('-id')[:50]
    )
    recent_readings.reverse()
    fig_hist = build_history_figure(recent_readings)

    return (
        track_options,
        current_view_track,
        fig_map,
        fig_hist,
        new_state,
    )


# DASH CALLBACK 3: UPLOAD TRACK REFERENCE PHOTOS (2-4) -> GEMINI VISION AI -> MAP OVERLAY
@app.callback(
    Output("upload-track-feedback", "children"),
    Output("graph-track-map", "figure", allow_duplicate=True),
    Input("upload-track-photo", "contents"),
    State("upload-track-photo", "filename"),
    State("dropdown-track-id", "value"),
    prevent_initial_call=True,
)
def handle_track_photo_upload(contents, filenames, selected_track_id):
    if not contents:
        return no_update, no_update

    disp_id = "idline_esp32"
    alert_style = {
        "borderRadius": "8px",
        "fontSize": "11px",
        "padding": "7px 10px",
        "marginBottom": "0",
    }

    content_list = [contents] if isinstance(contents, str) else list(contents)
    if len(content_list) < 2 or len(content_list) > 4:
        return dbc.Alert(
            f"Debes subir entre 2 y 4 fotos desde esquinas opuestas del tablero (seleccionadas: {len(content_list)}).",
            color="warning",
            style=alert_style,
        ), no_update

    try:
        images_payload = []
        for idx, item in enumerate(content_list):
            if not isinstance(item, str) or "," not in item:
                return dbc.Alert(
                    f"Formato de imagen inválido en la foto #{idx + 1}.",
                    color="warning",
                    style=alert_style,
                ), no_update

            header, b64_data = item.split(",", 1)
            if not b64_data:
                return dbc.Alert(
                    f"Contenido de imagen vacío en la foto #{idx + 1}.",
                    color="warning",
                    style=alert_style,
                ), no_update

            mime_type = "image/jpeg"
            if header.startswith("data:") and ";" in header:
                mime_type = header[5:].split(";", 1)[0] or "image/jpeg"

            images_payload.append({
                "image_base64": b64_data,
                "mime_type": mime_type,
            })

        active_track = (
            EstadoRobot.objects.filter(dispositivo_id=disp_id)
            .values_list('active_track_id', flat=True)
            .first()
        ) or 1
        target_track_id = int(selected_track_id) if selected_track_id is not None else active_track

        from django.test import Client as DjangoClient
        client = DjangoClient()
        response = client.post(
            "/api/pista/referencia/",
            data=json.dumps({
                "device_id": disp_id,
                "track_id": target_track_id,
                "images": images_payload,
            }),
            content_type="application/json",
        )

        try:
            res_data = response.json()
        except Exception:
            res_data = {}

        if response.status_code not in (200, 201) or not res_data.get("ok", True):
            err_msg = (
                res_data.get("error")
                or res_data.get("detail")
                or f"Error HTTP {response.status_code} al procesar las imágenes."
            )
            color = "warning" if "GEMINI_API_KEY" in str(err_msg) else "danger"
            return dbc.Alert(err_msg, color=color, style=alert_style), no_update

        points = res_data.get("points") or []
        res_track_id = res_data.get("track_id", target_track_id)
        photo_count = res_data.get("photo_count", len(images_payload))
        feedback = dbc.Alert(
            f"✓ Pista #{res_track_id}: {photo_count} fotos procesadas, {len(points)} puntos detectados y superpuestos.",
            color="success",
            style=alert_style,
        )

        track_readings = list(
            LecturaSensor.objects.filter(
                dispositivo_id=disp_id,
                track_id=res_track_id,
            )
            .only('id', 'm1', 'm2', 'vbat_mv', 'posicion', 'timestamp', 'muestras')
            .order_by('id')
        )
        fig_map = build_track_map_figure(track_readings, res_track_id)
        return feedback, fig_map

    except Exception as exc:
        return dbc.Alert(
            f"Error al procesar fotos de pista: {exc}",
            color="danger",
            style=alert_style,
        ), no_update


@app.callback(
    Output("upload-track-feedback", "children", allow_duplicate=True),
    Output("graph-track-map", "figure", allow_duplicate=True),
    Input("btn-clear-ref-track", "n_clicks"),
    State("dropdown-track-id", "value"),
    prevent_initial_call=True,
)
def handle_clear_track_reference(n_clicks, selected_track_id):
    if not n_clicks:
        return no_update, no_update

    disp_id = "idline_esp32"
    alert_style = {
        "borderRadius": "8px",
        "fontSize": "11px",
        "padding": "7px 10px",
        "marginBottom": "0",
    }
    target_track_id = int(selected_track_id) if selected_track_id is not None else 1
    try:
        from telemetria.models import PistaReferencia
        deleted, _ = PistaReferencia.objects.filter(
            device_id=disp_id, track_id=target_track_id
        ).delete()
    except Exception as exc:
        return dbc.Alert(
            f"Error al borrar referencia IA: {exc}",
            color="danger",
            style=alert_style,
        ), no_update

    track_readings = list(
        LecturaSensor.objects.filter(dispositivo_id=disp_id, track_id=target_track_id)
        .only('id', 'm1', 'm2', 'vbat_mv', 'posicion', 'timestamp', 'muestras')
        .order_by('id')
    )
    fig_map = build_track_map_figure(track_readings, target_track_id)
    msg = (
        f"Referencia IA de la Pista #{target_track_id} eliminada."
        if deleted
        else f"La Pista #{target_track_id} no tenía referencia IA guardada."
    )
    return dbc.Alert(msg, color="info" if deleted else "secondary", style=alert_style), fig_map


# Backward-compatible unified helper (used by unit tests & verify_end_to_end.py)
def update_telemetry(n_intervals, selected_track_id):
    disp_id = "idline_esp32"
    active_track = (
        EstadoRobot.objects.filter(dispositivo_id=disp_id)
        .values_list('active_track_id', flat=True)
        .first()
    ) or 1

    latest = (
        LecturaSensor.objects.filter(dispositivo_id=disp_id)
        .only('id', 'modo', 'm1', 'm2', 'vbat_mv', 'posicion', 'sensores', 'timestamp')
        .order_by('-id')
        .first()
    )

    is_online = False
    if latest and latest.timestamp:
        diff = (datetime.now(timezone.utc) - latest.timestamp).total_seconds()
        is_online = diff <= 8.0

    vbat_text, _ = format_vbat_badge(latest.vbat_mv if latest else None)
    modo_text = f"MODO: {latest.modo}" if latest else "MODO: IDLE"
    motores_text = f"M1: {latest.m1} | M2: {latest.m2}" if latest else "M1: 0 | M2: 0"
    status_badge_text = "ONLINE" if is_online else "OFFLINE"
    status_badge_color = "primary" if is_online else "secondary"
    track_badge_text = f"PISTA ACTIVA #{active_track}"

    db_tracks = list(
        LecturaSensor.objects.filter(dispositivo_id=disp_id)
        .values_list('track_id', flat=True)
        .distinct()
    )
    if active_track not in db_tracks:
        db_tracks.append(active_track)
    db_tracks = sorted(list(set(db_tracks)))

    track_options = [
        {"label": f"Pista #{t}{' (En Curso)' if t == active_track else ''}", "value": t}
        for t in db_tracks
    ]
    current_view_track = selected_track_id if selected_track_id in db_tracks else active_track

    track_readings = list(
        LecturaSensor.objects.filter(
            dispositivo_id=disp_id,
            track_id=current_view_track
        )
        .only('id', 'm1', 'm2', 'vbat_mv', 'posicion', 'timestamp', 'muestras')
        .order_by('id')
    )
    fig_map = build_track_map_figure(track_readings, current_view_track)

    sensor_vals = [0] * 8
    pos_val = 0
    if latest and latest.sensores and isinstance(latest.sensores, list):
        s_list = latest.sensores[:8]
        sensor_vals = s_list + [0] * (8 - len(s_list))
        pos_val = latest.posicion
    fig_sens = build_sensors_figure(sensor_vals)

    recent_readings = list(
        LecturaSensor.objects.filter(dispositivo_id=disp_id)
        .only('id', 'm1', 'm2', 'posicion')
        .order_by('-id')[:50]
    )
    recent_readings.reverse()
    fig_hist = build_history_figure(recent_readings)

    reticle_pos_text = f"{pos_val:+d}"
    reticle_pointer_style = _build_reticle_style(pos_val)

    return (
        status_badge_text,
        status_badge_color,
        vbat_text,
        modo_text,
        motores_text,
        track_badge_text,
        track_options,
        current_view_track,
        fig_map,
        fig_sens,
        fig_hist,
        reticle_pos_text,
        reticle_pointer_style
    )


if __name__ == '__main__':
    print("Iniciando Dashboard localmente en http://127.0.0.1:8050/dashboard/ ...")
    app.run(debug=True, port=8050)
