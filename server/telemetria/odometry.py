import math
from typing import List, Dict, Any, Optional

# Physical parameters of IDLine ESP32 robot
WHEELBASE_M = 0.128       # 85mm physical track width + ~1.5x differential tire scrub/slip factor
WHEEL_DIAMETER_M = 0.032  # Wheel diameter: 32 mm
V_NOMINAL_MV = 7400.0     # Nominal 2S Li-ion battery voltage in mV
V_MAX_SPEED_MPS = 0.85    # Realistic loaded top speed at 7.4V for 32mm wheels


def calculate_odometry_point(
    x: float,
    y: float,
    theta: float,
    m1: int,
    m2: int,
    vbat_mv: Optional[int],
    dt: float,
    pos: int = 0
) -> tuple[float, float, float, float]:
    """
    Computes next (x, y, theta, v) using differential drive kinematics
    with battery voltage compensation.
    
    m1: Left motor command (-1000..1000 or -255..255)
    m2: Right motor command (-1000..1000 or -255..255)
    vbat_mv: Battery voltage in millivolts
    dt: Time step in seconds
    pos: Line sensor position (-1000..1000, 0 is centered)
    """
    if dt <= 0:
        dt = 0.05
    elif dt > 0.5:
        dt = 0.5

    # Determine PWM scale (1000 for PID firmware or 255 for manual control)
    max_pwm = 1000.0 if max(abs(m1), abs(m2)) > 255 else 255.0
    u1 = max(-1.0, min(1.0, float(m1) / max_pwm))
    u2 = max(-1.0, min(1.0, float(m2) / max_pwm))

    # Motor deadband: below ~14% PWM N20 motors do not overcome static friction
    if 0 < abs(u1) < 0.14:
        u1 = 0.0
    if 0 < abs(u2) < 0.14:
        u2 = 0.0

    # Voltage compensation factor
    if vbat_mv and vbat_mv > 4000:
        v_clamped = max(5800.0, min(8600.0, float(vbat_mv)))
        voltage_factor = v_clamped / V_NOMINAL_MV
    else:
        voltage_factor = 1.0

    # Effective wheel velocities (m/s)
    v_left = u1 * V_MAX_SPEED_MPS * voltage_factor
    v_right = u2 * V_MAX_SPEED_MPS * voltage_factor

    # Linear and angular velocity (CCW-positive: m2 > m1 turns left/CCW)
    v = (v_left + v_right) / 2.0
    omega = (v_right - v_left) / WHEELBASE_M

    # 2nd Order Runge-Kutta / Midpoint integration
    delta_theta = omega * dt
    mid_theta = theta + (delta_theta / 2.0)

    next_x = x + v * math.cos(mid_theta) * dt
    next_y = y + v * math.sin(mid_theta) * dt
    next_theta = (theta + delta_theta) % (2.0 * math.pi)

    return next_x, next_y, next_theta, v


def _trim_leading_idle(items: List[Any], get_motors) -> List[Any]:
    """Skip leading idle points (|m1| < 35 and |m2| < 35), keeping at least 1."""
    if not items:
        return items
    for idx, item in enumerate(items):
        m1, m2 = get_motors(item)
        if not (abs(m1) < 35 and abs(m2) < 35):
            return items[idx:]
    return items[:1]


def reconstruct_trajectory(readings: List[Any]) -> Dict[str, Any]:
    """
    Reconstructs (x, y) track trajectory from a sequence of LecturaSensor records
    or burst 'muestras'.
    """
    trajectory: List[Dict[str, Any]] = []
    
    if not readings:
        return {
            "total_points": 0,
            "total_distance_m": 0.0,
            "duration_s": 0.0,
            "trajectory": [],
            "bounds": {"min_x": 0.0, "max_x": 0.0, "min_y": 0.0, "max_y": 0.0}
        }

    x, y, theta = 0.0, 0.0, 0.0
    total_dist = 0.0
    elapsed_t = 0.0

    # Check if any reading has embedded burst 'muestras'
    has_burst_muestras = any(getattr(r, 'muestras', None) for r in readings)

    if has_burst_muestras:
        parsed_samples = []
        for r in readings:
            muestras = getattr(r, 'muestras', None)
            vbat = getattr(r, 'vbat_mv', None) or 7400
            if isinstance(muestras, list):
                for sample in muestras:
                    if isinstance(sample, (list, tuple)) and len(sample) >= 4:
                        # Format: [t_ms, pos, m1, m2, (status/vbat)]
                        t_ms = int(sample[0])
                        pos = int(sample[1])
                        m1 = int(sample[2])
                        m2 = int(sample[3])
                        s_vbat = int(sample[4]) if len(sample) >= 5 and sample[4] > 2000 else vbat
                    elif isinstance(sample, dict):
                        t_ms = int(sample.get("t_ms", 0))
                        pos = int(sample.get("pos", 0))
                        m1 = int(sample.get("m1", 0))
                        m2 = int(sample.get("m2", 0))
                        s_vbat = int(sample.get("vbat_mv", vbat))
                    else:
                        continue
                    parsed_samples.append((t_ms, pos, m1, m2, s_vbat))

        active_samples = _trim_leading_idle(parsed_samples, lambda s: (s[2], s[3]))

        if active_samples:
            _, first_pos, first_m1, first_m2, first_vbat = active_samples[0]
        else:
            first_r = readings[0]
            first_pos = getattr(first_r, 'posicion', 0)
            first_m1 = getattr(first_r, 'm1', 0)
            first_m2 = getattr(first_r, 'm2', 0)
            first_vbat = getattr(first_r, 'vbat_mv', None) or 7400

        trajectory.append({
            "x": 0.0,
            "y": 0.0,
            "theta": 0.0,
            "t": 0.0,
            "m1": first_m1,
            "m2": first_m2,
            "vbat_mv": first_vbat,
            "pos": first_pos,
            "v_mps": 0.0
        })

        # Reconstruct from high-frequency memory samples
        prev_t_ms = None
        for t_ms, pos, m1, m2, s_vbat in active_samples:
            if prev_t_ms is None:
                dt = 0.02
            else:
                dt = max(0.005, min(0.2, (t_ms - prev_t_ms) / 1000.0))
            prev_t_ms = t_ms
            elapsed_t += dt

            x, y, theta, v = calculate_odometry_point(x, y, theta, m1, m2, s_vbat, dt, pos)
            step_dist = abs(v * dt)
            total_dist += step_dist

            trajectory.append({
                "x": round(x, 4),
                "y": round(y, 4),
                "theta": round(theta, 3),
                "t": round(elapsed_t, 3),
                "m1": m1,
                "m2": m2,
                "vbat_mv": s_vbat,
                "pos": pos,
                "v_mps": round(v, 3)
            })
    else:
        active_readings = _trim_leading_idle(
            readings,
            lambda r: (getattr(r, 'm1', 0), getattr(r, 'm2', 0))
        )

        # Origin point
        first_r = active_readings[0]
        initial_vbat = getattr(first_r, 'vbat_mv', None) or 7400
        trajectory.append({
            "x": 0.0,
            "y": 0.0,
            "theta": 0.0,
            "t": 0.0,
            "m1": getattr(first_r, 'm1', 0),
            "m2": getattr(first_r, 'm2', 0),
            "vbat_mv": initial_vbat,
            "pos": getattr(first_r, 'posicion', 0),
            "v_mps": 0.0
        })

        # Reconstruct sequentially from LecturaSensor records
        prev_time = None
        for r in active_readings:
            curr_time = getattr(r, 'timestamp', None)
            if prev_time and curr_time:
                dt = (curr_time - prev_time).total_seconds()
                dt = max(0.02, min(0.5, dt))
            else:
                dt = 0.05
            prev_time = curr_time
            elapsed_t += dt

            m1 = getattr(r, 'm1', 0)
            m2 = getattr(r, 'm2', 0)
            vbat = getattr(r, 'vbat_mv', None) or 7400
            pos = getattr(r, 'posicion', 0)

            x, y, theta, v = calculate_odometry_point(x, y, theta, m1, m2, vbat, dt, pos)
            step_dist = abs(v * dt)
            total_dist += step_dist

            trajectory.append({
                "x": round(x, 4),
                "y": round(y, 4),
                "theta": round(theta, 3),
                "t": round(elapsed_t, 3),
                "m1": m1,
                "m2": m2,
                "vbat_mv": vbat,
                "pos": pos,
                "v_mps": round(v, 3)
            })

    xs = [p["x"] for p in trajectory]
    ys = [p["y"] for p in trajectory]

    bounds = {
        "min_x": round(min(xs), 4) if xs else 0.0,
        "max_x": round(max(xs), 4) if xs else 0.0,
        "min_y": round(min(ys), 4) if xs else 0.0,
        "max_y": round(max(ys), 4) if xs else 0.0,
    }

    return {
        "total_points": len(trajectory),
        "total_distance_m": round(total_dist, 3),
        "duration_s": round(elapsed_t, 3),
        "trajectory": trajectory,
        "bounds": bounds
    }


def _extract_xy(point: Any) -> tuple[float, float]:
    """Extracts (x, y) floats from a dict, tuple, or list point."""
    if isinstance(point, dict):
        return float(point.get("x", 0.0)), float(point.get("y", 0.0))
    if isinstance(point, (tuple, list)) and len(point) >= 2:
        return float(point[0]), float(point[1])
    raise ValueError(f"Unsupported point format: {type(point).__name__}")


def _format_point_like(template: Any, x: float, y: float) -> Any:
    """Formats (x, y) matching the container type of `template` without mutating it."""
    rx = round(x, 6)
    ry = round(y, 6)
    if isinstance(template, dict):
        out = dict(template)
        out["x"] = rx
        out["y"] = ry
        return out
    if isinstance(template, tuple):
        return (rx, ry, *template[2:]) if len(template) > 2 else (rx, ry)
    if isinstance(template, list):
        return [rx, ry, *template[2:]] if len(template) > 2 else [rx, ry]
    return (rx, ry)


def _resample_by_arclength(
    points: List[tuple[float, float]],
    num_samples: int
) -> List[tuple[float, float]]:
    """Resamples a 2D polyline to `num_samples` evenly spaced points by arc length."""
    if len(points) <= 1 or num_samples <= 1:
        return list(points[:num_samples])

    cum = [0.0]
    for i in range(1, len(points)):
        d = math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
        cum.append(cum[-1] + d)

    total_len = cum[-1]
    if total_len <= 1e-12:
        return [points[0]] * num_samples

    resampled: List[tuple[float, float]] = []
    seg = 0
    last_seg = len(points) - 2
    for j in range(num_samples):
        target = (j / (num_samples - 1)) * total_len
        while seg < last_seg and cum[seg + 1] < target:
            seg += 1
        seg_len = cum[seg + 1] - cum[seg]
        if seg_len <= 1e-12:
            resampled.append(points[seg])
        else:
            alpha = max(0.0, min(1.0, (target - cum[seg]) / seg_len))
            x = points[seg][0] + alpha * (points[seg + 1][0] - points[seg][0])
            y = points[seg][1] + alpha * (points[seg + 1][1] - points[seg][1])
            resampled.append((x, y))
    return resampled


def _fit_similarity_2d(
    src: List[tuple[float, float]],
    dst: List[tuple[float, float]]
) -> tuple[float, float, float, tuple[float, float], tuple[float, float], float]:
    """
    Computes 2D similarity transform (scale, cos_t, sin_t, src_mean, dst_mean, rmsd)
    minimizing sum || s * R * (src_i - src_mean) + dst_mean - dst_i ||^2 with det(R)=+1.
    """
    n = len(src)
    sx_mean = sum(p[0] for p in src) / n
    sy_mean = sum(p[1] for p in src) / n
    dx_mean = sum(q[0] for q in dst) / n
    dy_mean = sum(q[1] for q in dst) / n

    s_pp = 0.0
    s_qq = 0.0
    a_sum = 0.0
    b_sum = 0.0
    for (px, py), (qx, qy) in zip(src, dst):
        cpx = px - sx_mean
        cpy = py - sy_mean
        cqx = qx - dx_mean
        cqy = qy - dy_mean
        s_pp += cpx * cpx + cpy * cpy
        s_qq += cqx * cqx + cqy * cqy
        a_sum += cpx * cqx + cpy * cqy
        b_sum += cpx * cqy - cpy * cqx

    if s_pp <= 1e-12 or s_qq <= 1e-12:
        return 1.0, 1.0, 0.0, (sx_mean, sy_mean), (dx_mean, dy_mean), float("inf")

    norm_ab = math.hypot(a_sum, b_sum)
    if norm_ab <= 1e-12:
        cos_t, sin_t = 1.0, 0.0
        scale = math.sqrt(s_qq / s_pp)
    else:
        cos_t = a_sum / norm_ab
        sin_t = b_sum / norm_ab
        scale = norm_ab / s_pp

    sq_err = 0.0
    for (px, py), (qx, qy) in zip(src, dst):
        cpx = px - sx_mean
        cpy = py - sy_mean
        tx = dx_mean + scale * (cpx * cos_t - cpy * sin_t)
        ty = dy_mean + scale * (cpx * sin_t + cpy * cos_t)
        sq_err += (tx - qx) ** 2 + (ty - qy) ** 2
    rmsd = math.sqrt(sq_err / n)

    return scale, cos_t, sin_t, (sx_mean, sy_mean), (dx_mean, dy_mean), rmsd


def align_trajectory_to_reference(
    trajectory: List[Any],
    reference_points: List[Any]
) -> List[Any]:
    """
    Aligns a reconstructed odometry trajectory onto normalized 0..1 `reference_points`
    using a 2D similarity fit (translation, rotation, uniform scale) via 2D Kabsch /
    Procrustes with arc-length resampling when point counts differ.

    Preserves the point format of `trajectory` (dicts with 'x'/'y' or (x, y) tuples/lists)
    and returns a shallow copy unchanged if either input has fewer than 2 points.
    """
    if not trajectory:
        return []

    traj_xy = [_extract_xy(p) for p in trajectory]
    if len(traj_xy) < 2 or not reference_points or len(reference_points) < 2:
        return [_format_point_like(p, x, y) for p, (x, y) in zip(trajectory, traj_xy)]

    ref_xy = [_extract_xy(p) for p in reference_points]

    if len(traj_xy) == len(ref_xy):
        src_corr = traj_xy
        dst_fwd = ref_xy
    else:
        num_samples = min(max(len(traj_xy), len(ref_xy), 64), 256)
        src_corr = _resample_by_arclength(traj_xy, num_samples)
        dst_fwd = _resample_by_arclength(ref_xy, num_samples)

    fit_fwd = _fit_similarity_2d(src_corr, dst_fwd)
    best_fit = fit_fwd

    if len(traj_xy) != len(ref_xy):
        fit_rev = _fit_similarity_2d(src_corr, list(reversed(dst_fwd)))
        if fit_rev[5] + 1e-9 < fit_fwd[5]:
            best_fit = fit_rev

    scale, cos_t, sin_t, (sx_mean, sy_mean), (dx_mean, dy_mean), _ = best_fit

    aligned: List[Any] = []
    for pt, (px, py) in zip(trajectory, traj_xy):
        cpx = px - sx_mean
        cpy = py - sy_mean
        ax = dx_mean + scale * (cpx * cos_t - cpy * sin_t)
        ay = dy_mean + scale * (cpx * sin_t + cpy * cos_t)
        aligned.append(_format_point_like(pt, ax, ay))

    return aligned
