"""Lightweight Gemini Vision REST client using only Python stdlib."""

import base64
import json
import math
import os
import re
import urllib.error
import urllib.request


DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

TRACK_EXTRACTION_PROMPT = (
    "Analyze this overhead photo of a line-follower robot track (black tape/line on a "
    "light/white background). Trace the ordered centerline polyline of the black track "
    "contour.\n"
    "Return ONLY valid JSON with this exact structure and no extra text:\n"
    '{"points": [[x, y], ...], "closed": true}\n'
    "Rules:\n"
    "- Every coordinate x and y must be normalized floats in [0.0, 1.0], where (0.0, 0.0) "
    "is the top-left corner and (1.0, 1.0) is the bottom-right corner of the image.\n"
    "- Order points sequentially along the track contour (typically 20 to 80 points to "
    "accurately capture straights, curves, and hairpins).\n"
    "- Set \"closed\" to true if the track forms a continuous closed loop, or false if open.\n"
    "- Do not include markdown fences or commentary."
)

MULTI_VIEW_TRACK_EXTRACTION_PROMPT = (
    "You are given 2 to 4 photos of the SAME line-follower robot track (black tape/line on a "
    "light/white mat, board, or tiled floor) taken from different or opposite corners.\n"
    "Use the rectangular borders, tile grid lines, or mat corners visible across all views "
    "to triangulate geometry, cross-reference near/far sections, and compensate perspective "
    "distortion into a single consolidated top-down orthographic view.\n"
    "Trace the ordered centerline polyline of the black track contour in that rectified "
    "top-down coordinate frame.\n"
    "Return ONLY valid JSON with this exact structure and no extra text:\n"
    '{"points": [[x, y], ...], "closed": true}\n'
    "Rules:\n"
    "- Every coordinate x and y must be normalized floats in [0.0, 1.0], where (0.0, 0.0) "
    "is the top-left corner and (1.0, 1.0) is the bottom-right corner of the rectified "
    "top-down track area.\n"
    "- Order points sequentially along the consolidated black track contour (typically 25 to "
    "90 points to accurately capture straights, curves, and hairpins).\n"
    "- Set \"closed\" to true if the track forms a continuous closed loop, or false if open.\n"
    "- Do not include markdown fences or commentary."
)

_DATA_URL_RE = re.compile(r"^data:([^;]+);base64,(.+)$", re.DOTALL | re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


class VisionAIConfigError(RuntimeError):
    """Raised when required Gemini Vision configuration (e.g. API key) is missing."""


class VisionAIError(RuntimeError):
    """Raised when Gemini Vision API call or response validation fails."""


def _strip_data_url(image_base64: str, mime_type: str | None) -> tuple[str, str]:
    """Normalize base64 payload by stripping an optional data-URL header."""
    if not isinstance(image_base64, str) or not image_base64.strip():
        raise ValueError("image_base64 debe ser una cadena no vacia.")

    raw = image_base64.strip()
    resolved_mime = (mime_type or "").strip() or "image/jpeg"

    match = _DATA_URL_RE.match(raw)
    if match:
        header_mime, raw = match.group(1).strip(), match.group(2).strip()
        if not mime_type and header_mime:
            resolved_mime = header_mime

    compact_b64 = re.sub(r"\s+", "", raw)
    try:
        decoded = base64.b64decode(compact_b64, validate=True)
    except Exception as exc:
        raise ValueError(f"image_base64 invalido: {exc}") from exc

    if not decoded:
        raise ValueError("La imagen decodificada esta vacia.")

    return compact_b64, resolved_mime


def parse_and_validate_track_json(raw_text: str) -> dict:
    """Parse Gemini output as strict JSON and validate/clamp normalized track points."""
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise VisionAIError("La respuesta de Gemini Vision esta vacia.")

    cleaned = raw_text.strip()
    fence_match = _CODE_FENCE_RE.match(cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise VisionAIError(f"Respuesta JSON invalida de Gemini Vision: {exc}") from exc

    if not isinstance(parsed, dict):
        raise VisionAIError("El JSON de respuesta debe ser un objeto.")

    raw_points = parsed.get("points")
    if not isinstance(raw_points, list) or len(raw_points) < 2:
        raise VisionAIError("El campo 'points' debe contener al menos 2 coordenadas [x, y].")

    validated_points = []
    for idx, pt in enumerate(raw_points):
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            raise VisionAIError(f"Punto #{idx} invalido: se esperaba [x, y].")
        x_raw, y_raw = pt[0], pt[1]
        if isinstance(x_raw, bool) or isinstance(y_raw, bool):
            raise VisionAIError(f"Punto #{idx} contiene booleanos en lugar de numeros.")
        try:
            x_val = float(x_raw)
            y_val = float(y_raw)
        except (TypeError, ValueError) as exc:
            raise VisionAIError(f"Punto #{idx} no es numerico.") from exc

        if not (math.isfinite(x_val) and math.isfinite(y_val)):
            raise VisionAIError(f"Punto #{idx} contiene valores no finitos.")

        x_clamped = round(max(0.0, min(1.0, x_val)), 5)
        y_clamped = round(max(0.0, min(1.0, y_val)), 5)
        validated_points.append([x_clamped, y_clamped])

    closed = parsed.get("closed", True)
    if not isinstance(closed, bool):
        raise VisionAIError("El campo 'closed' debe ser booleano.")

    return {
        "points": validated_points,
        "closed": closed,
    }


def _normalize_image_item(item) -> tuple[str, str]:
    """Normalize an image input (dict, tuple, or base64 string) into (clean_b64, mime_type)."""
    if isinstance(item, dict):
        b64 = item.get("image_base64") or item.get("data") or ""
        mime = item.get("mime_type")
        return _strip_data_url(b64, mime)
    if isinstance(item, (tuple, list)) and len(item) == 2:
        return _strip_data_url(item[0], item[1])
    if isinstance(item, str):
        return _strip_data_url(item, None)
    raise ValueError("Cada imagen debe ser un dict {'image_base64', 'mime_type'} o cadena base64.")


def extract_track_polyline(
    images,
    timeout: float | None = None,
) -> dict:
    """Call Gemini Vision API with 1..4 images to extract a consolidated 0..1 track polyline."""
    if timeout is None:
        try:
            timeout = float(os.environ.get("GEMINI_VISION_TIMEOUT", "120.0"))
        except ValueError:
            timeout = 120.0
    if not isinstance(images, (list, tuple)):
        raise ValueError("images debe ser una lista de 1 a 4 imagenes.")
    if len(images) < 1 or len(images) > 4:
        raise ValueError("Se requieren entre 1 y 4 imagenes (2 a 4 para vista multi-angulo).")

    normalized_images = [_normalize_image_item(item) for item in images]

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise VisionAIConfigError(
            "GEMINI_API_KEY no esta configurada en las variables de entorno."
        )

    model = os.environ.get("GEMINI_VISION_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
    url = f"{GEMINI_ENDPOINT_TEMPLATE.format(model=model)}?key={api_key}"

    prompt = (
        MULTI_VIEW_TRACK_EXTRACTION_PROMPT
        if len(normalized_images) >= 2
        else TRACK_EXTRACTION_PROMPT
    )
    parts = [{"text": prompt}]
    for clean_b64, resolved_mime in normalized_images:
        parts.append(
            {
                "inline_data": {
                    "mime_type": resolved_mime,
                    "data": clean_b64,
                }
            }
        )

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        err_detail = ""
        try:
            err_detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise VisionAIError(
            f"Error HTTP {exc.code} desde Gemini Vision: {err_detail or exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise VisionAIError(f"Error de red al conectar con Gemini Vision: {exc.reason}") from exc
    except TimeoutError as exc:
        raise VisionAIError("Tiempo de espera agotado al consultar Gemini Vision.") from exc

    try:
        response_json = json.loads(resp_body)
        candidates = response_json.get("candidates") or []
        resp_parts = candidates[0]["content"]["parts"]
        text_output = "".join(
            part.get("text", "") for part in resp_parts if isinstance(part, dict)
        )
    except (json.JSONDecodeError, IndexError, KeyError, TypeError) as exc:
        raise VisionAIError(
            f"Estructura inesperada en la respuesta de Gemini Vision: {exc}"
        ) from exc

    return parse_and_validate_track_json(text_output)


def extract_track_from_image(
    image_base64: str,
    mime_type: str | None = None,
    timeout: float | None = None,
) -> dict:
    """Backward-compatible single-image wrapper around extract_track_polyline()."""
    return extract_track_polyline(
        [{"image_base64": image_base64, "mime_type": mime_type}],
        timeout=timeout,
    )


extract_track_polyline_from_base64 = extract_track_from_image
