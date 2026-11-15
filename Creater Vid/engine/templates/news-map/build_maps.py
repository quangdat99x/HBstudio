# -*- coding: utf-8 -*-
"""Bước 3 · bản đồ cho «Сводка за сутки · 16.10.2026»: chiếu Natural Earth 1:10m (phạm vi công cộng) thành đường SVG 1920×1080
→ film/src/digest/maps.json (bộ MapView của bản tin). Chạy bằng "$BGREMOVE_PY" (có numpy).
Phép chiếu: x = 960 + (lon − lon0)·k·cos(lat0), y = 540 − (lat − lat0)·k.
Toạ độ (WGS84, theo Wikipedia/OSM, kiểm 16.10.2026): Рязань 54.6292 N 39.7365 E; Борисоглебск 51.3655 N 42.0826 E (sân bay ở rìa bắc thành phố —
vẽ điểm thành phố); Маяки (Одесский р-н) 46.4128 N 30.2689 E; Измаил 45.3517 N 28.8364 E; Южный 46.6226 N 31.1028 E; Жешув 50.0412 N 22.0047 E;
Брюссель 50.8503 N 4.3517 E; Луцк 50.7472 N 25.3254 E; Шереметьево 55.9726 N 37.4146 E; Внуково 55.5915 N 37.2615 E; Домодедово 55.4088 N 37.9063 E;
Жуковский 55.5533 N 38.1517 E; аэропорт Сочи (Адлер) 43.4499 N 39.9566 E; Донецк 48.0159 N 37.8028 E; Симферополь 44.9521 N 34.1024 E.
Không tô vùng kiểm soát (không có dữ liệu mở đã kiểm) — chỉ địa danh."""
import json, math
from pathlib import Path
import numpy as np

PROJ = Path(__file__).resolve().parents[2]
# Natural Earth 1:10m dùng chung, nằm trong engine (film/node_modules là liên kết tới engine/node_modules);
# thiếu tệp nào thì tải về một lần từ kho natural-earth-vector (phạm vi công cộng)
ENGINE = (PROJ / "film/node_modules").resolve().parent
NE = ENGINE / "templates/news-map/ne"
NE_FILES = ("ne_10m_admin_0_countries", "ne_10m_admin_0_boundary_lines_land", "ne_10m_coastline", "ne_10m_admin_1_states_provinces",
            "ne_10m_admin_1_states_provinces_lines", "ne_10m_rivers_lake_centerlines", "ne_10m_lakes")


def ensure_ne():
    import urllib.request
    NE.mkdir(parents=True, exist_ok=True)
    for n in NE_FILES:
        dst = NE / f"{n}.geojson"
        if not dst.exists():
            print("tải", n)
            tmp = dst.with_suffix(".part")
            urllib.request.urlretrieve(f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{n}.geojson", tmp)
            tmp.replace(dst)
W, H = 1920, 1080

MAPS = {
    "ru_npz":   (42.40, 53.30, 3.00, False),
    "voronezh": (40.80, 51.60, 1.60, False),
    "odesa":    (29.90, 46.00, 0.85, False),
    "poland":   (24.50, 51.00, 3.20, False),
    "europe":   (14.00, 50.20, 7.00, False),
    "ukraine":  (31.40, 48.60, 4.00, False),
    "kyiv2022": (30.60, 50.90, 1.10, False),
    "crimea":   (34.40, 45.20, 1.30, False),
    "moscow":   (37.65, 55.68, 0.45, False),
    "sochi":    (39.60, 44.00, 1.50, False),
    "donetsk":  (37.80, 48.10, 1.30, False),
}

PLACES = {
    "Москва": (37.6173, 55.7558), "Рязань": (39.7365, 54.6292), "Саратов": (46.0342, 51.5331), "Тамбов": (41.4529, 52.7213),
    "Тула": (37.6173, 54.1931), "Пенза": (45.0, 53.2007), "Воронеж": (39.2003, 51.6720), "Липецк": (39.5999, 52.6031),
    "Борисоглебск": (42.0826, 51.3655), "Белгород": (36.5870, 50.5997), "Харьков": (36.2304, 49.9935),
    "Одесса": (30.7233, 46.4825), "Маяки": (30.2689, 46.4128), "Измаил": (28.8364, 45.3517), "Южный": (31.1028, 46.6226),
    "Белгород-Днестровский": (30.3486, 46.1871),
    "Варшава": (21.0122, 52.2297), "Жешув": (22.0047, 50.0412), "Киев": (30.5234, 50.4501), "Львов": (24.0297, 49.8397),
    "Брюссель": (4.3517, 50.8503), "Париж": (2.3522, 48.8566), "Лондон": (-0.1276, 51.5072), "Берлин": (13.4050, 52.5200),
    "Луцк": (25.3254, 50.7472), "Днепр": (35.0462, 48.4647),
    "Чернигов": (31.2893, 51.4982), "Бровары": (30.7909, 50.5110), "Ирпень": (30.2506, 50.5218), "Гостомель": (30.2056, 50.5694),
    "Симферополь": (34.1024, 44.9521), "Севастополь": (33.5224, 44.6167), "Керчь": (36.4733, 45.3562), "Ялта": (34.1663, 44.4952), "Херсон": (32.6169, 46.6354),
    "Шереметьево": (37.4146, 55.9726), "Внуково": (37.2615, 55.5915), "Домодедово": (37.9063, 55.4088), "Жуковский": (38.1517, 55.5533),
    "Сочи": (39.7303, 43.5855), "Сочи · аэропорт": (39.9566, 43.4499), "Краснодар": (38.9769, 45.0355), "Туапсе": (39.0753, 44.0987),
    "Донецк": (37.8028, 48.0159), "Краматорск": (37.5844, 48.7389), "Мариуполь": (37.5413, 47.0971), "Покровск": (37.1787, 48.2828), "Луганск": (39.3078, 48.5740),
}

def proj(m, lon, lat):
    lon0, lat0, hh, _ = MAPS[m]
    k = (H / 2) / hh
    return 960 + (lon - lon0) * k * math.cos(math.radians(lat0)), 540 - (lat - lat0) * k


def bbox_ll(m, margin=0.35):
    lon0, lat0, hh, _ = MAPS[m]
    hw = hh * (W / H) / math.cos(math.radians(lat0))
    return lon0 - hw * (1 + margin), lon0 + hw * (1 + margin), lat0 - hh * (1 + margin), lat0 + hh * (1 + margin)


# ---- clipping (khung chữ nhật mở rộng 160 px) và rút gọn ----
X0, Y0, X1, Y1 = -160, -160, W + 160, H + 160


def clip_poly(pts):
    def clip(points, inside, inter):
        out = []
        for i in range(len(points)):
            a, b = points[i - 1], points[i]
            ia, ib = inside(a), inside(b)
            if ib:
                if not ia:
                    out.append(inter(a, b))
                out.append(b)
            elif ia:
                out.append(inter(a, b))
        return out
    def ix(a, b, x):
        t = (x - a[0]) / (b[0] - a[0]); return (x, a[1] + t * (b[1] - a[1]))
    def iy(a, b, y):
        t = (y - a[1]) / (b[1] - a[1]); return (a[0] + t * (b[0] - a[0]), y)
    p = pts
    for inside, inter in ((lambda q: q[0] >= X0, lambda a, b: ix(a, b, X0)), (lambda q: q[0] <= X1, lambda a, b: ix(a, b, X1)),
                          (lambda q: q[1] >= Y0, lambda a, b: iy(a, b, Y0)), (lambda q: q[1] <= Y1, lambda a, b: iy(a, b, Y1))):
        if not p:
            return []
        p = clip(p, inside, inter)
    return p


def clip_line(pts):
    """cắt đường gấp khúc theo khung (Liang–Barsky từng đoạn), trả về các đoạn liền"""
    out, cur = [], []
    for a, b in zip(pts[:-1], pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t0, t1, ok = 0.0, 1.0, True
        for p, q in ((-dx, a[0] - X0), (dx, X1 - a[0]), (-dy, a[1] - Y0), (dy, Y1 - a[1])):
            if p == 0:
                if q < 0: ok = False; break
            else:
                r = q / p
                if p < 0: t0 = max(t0, r)
                else: t1 = min(t1, r)
        if not ok or t0 > t1:
            if len(cur) > 1: out.append(cur)
            cur = []; continue
        A = (a[0] + t0 * dx, a[1] + t0 * dy); B = (a[0] + t1 * dx, a[1] + t1 * dy)
        if not cur: cur = [A]
        elif t0 > 0:
            if len(cur) > 1: out.append(cur)
            cur = [A]
        cur.append(B)
        if t1 < 1:
            if len(cur) > 1: out.append(cur)
            cur = []
    if len(cur) > 1: out.append(cur)
    return out


def simplify(pts, tol=0.7):
    if len(pts) < 3:
        return pts
    P = np.asarray(pts, dtype=float)
    keep = np.zeros(len(P), bool); keep[0] = keep[-1] = True
    stack = [(0, len(P) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1: continue
        A, B = P[a], P[b]; seg = B - A; L = np.hypot(*seg)
        Q = P[a + 1:b]
        d = (np.abs(seg[0] * (Q[:, 1] - A[1]) - seg[1] * (Q[:, 0] - A[0])) / L) if L > 1e-9 else np.hypot(*(Q - A).T)
        i = int(np.argmax(d))
        if d[i] > tol:
            m = a + 1 + i; keep[m] = True; stack += [(a, m), (m, b)]
    return [tuple(p) for p in P[keep]]


def path(rings, close):
    s = []
    for r in rings:
        if len(r) < 2: continue
        s.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in r) + ("Z" if close else ""))
    return "".join(s)


def rings_of(geom):
    t, c = geom["type"], geom["coordinates"]
    if t == "Polygon": return [c]
    if t == "MultiPolygon": return c
    return []


def lines_of(geom):
    t, c = geom["type"], geom["coordinates"]
    if t == "LineString": return [c]
    if t == "MultiLineString": return c
    return []


def bb_hit(coords, bb):
    a = np.asarray(coords)[:, :2]
    return not (a[:, 0].max() < bb[0] or a[:, 0].min() > bb[1] or a[:, 1].max() < bb[2] or a[:, 1].min() > bb[3])


def poly_layer(m, polys, tol=0.7):
    bb = bbox_ll(m); out = []
    for poly in polys:
        for ri, ring in enumerate(poly):
            if not bb_hit(ring, bb): continue
            p = clip_poly([proj(m, x[0], x[1]) for x in ring])
            p = simplify(p, tol) if len(p) > 3 else p
            if len(p) >= 3: out.append(p)
    return path(out, True)


def line_layer(m, lines, tol=0.7, min_len=0):
    bb = bbox_ll(m); out = []
    for ln in lines:
        if not bb_hit(ln, bb): continue
        for part in clip_line([proj(m, x[0], x[1]) for x in ln]):
            part = simplify(part, tol)
            if len(part) >= 2: out.append(part)
    return path(out, False)


def inside(ring, x, y):
    """ray casting: điểm (lon, lat) nằm trong vòng ngoài của đa giác"""
    a = np.asarray(ring)[:, :2]
    xi, yi = a[:, 0], a[:, 1]
    xj, yj = np.roll(xi, 1), np.roll(yi, 1)
    hit = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / np.where(yj == yi, 1e-12, yj - yi) + xi)
    return bool(np.count_nonzero(hit) % 2)


# ---- nền raster (bản style v2): địa hình + đèn đêm từ NASA GIBS (phạm vi công cộng), khớp đúng phép chiếu ----
# Phép chiếu ở trên tuyến tính theo lon và lat → một ảnh WMS EPSG:4326 cùng khung là trùng từng điểm ảnh.
GIBS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
SC = 1.5  # độ phân giải gấp 1.5 khung để máy quay phóng tới ~1.3 vẫn nét
RASTER = PROJ / "film/public/img/maps"


def frame_bbox(m):
    lon0, lat0, hh, _ = MAPS[m]
    k = (H / 2) / hh
    kx = k * math.cos(math.radians(lat0))
    return lon0 - 960 / kx, lat0 - 540 / k, lon0 + 960 / kx, lat0 + 540 / k


def gibs(layer, bb, w, h):
    import io, urllib.request
    from PIL import Image
    url = (f"{GIBS}?SERVICE=WMS&REQUEST=GetMap&VERSION=1.1.1&LAYERS={layer}&STYLES=&SRS=EPSG:4326"
           f"&BBOX={bb[0]:.5f},{bb[1]:.5f},{bb[2]:.5f},{bb[3]:.5f}&WIDTH={w}&HEIGHT={h}&FORMAT=image/jpeg")
    for _ in range(3):
        try:
            return Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=90).read())).convert("RGB")
        except Exception as e:  # GIBS đôi khi trả lỗi tạm
            err = e
    raise err


def bake_raster(m):
    """địa hình nổi khối (tương phản cục bộ) tô navy + đèn thành phố ban đêm phát sáng → img/maps/<m>.jpg"""
    from PIL import Image, ImageFilter
    w, h = int(W * SC), int(H * SC)
    bb = frame_bbox(m)
    rel = gibs("ASTER_GDEM_Greyscale_Shaded_Relief", bb, w, h).convert("L")
    nite = gibs("VIIRS_Black_Marble", bb, w, h)
    g = np.asarray(rel, np.float32)
    hp = g - np.asarray(rel.filter(ImageFilter.GaussianBlur(18 * SC)), np.float32)
    t = np.clip(hp / (3 * max(hp.std(), 1.0)), -1, 1)
    lf = np.asarray(rel.filter(ImageFilter.GaussianBlur(70 * SC)), np.float32)
    lf = np.clip((lf - lf.mean()) / (3 * max(lf.std(), 1.0)), -1, 1)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    base = np.array([29, 46, 98], np.float32) * (1.08 - 0.18 * yy)[..., None]  # sáng nhẹ phía trên
    col = base * (1 + 0.55 * t + 0.18 * lf)[..., None]
    n = np.asarray(nite, np.float32)
    # Black Marble ~500 m/điểm: bản đồ cận cảnh (k lớn) thì làm mềm khối điểm ảnh và hạ độ sáng để không cháy trắng
    k = (H / 2) / MAPS[m][2]
    gain = min(1.0, (350 / k) ** (1.2 if k < 600 else 2.0))
    soft = max(0.0, k / 350 - 1) * 1.2 * SC
    if soft > 0:
        nite = nite.filter(ImageFilter.GaussianBlur(soft))
        n = np.asarray(nite, np.float32)
    lum = np.clip((n.max(-1) - 40) / 190, 0, 1) ** 1.35 * gain
    L = Image.fromarray((lum * 255).astype(np.uint8))
    g1 = np.asarray(L.filter(ImageFilter.GaussianBlur(5 * SC)), np.float32) / 255
    g2 = np.asarray(L.filter(ImageFilter.GaussianBlur(22 * SC)), np.float32) / 255
    light = (lum[..., None] * np.array([255, 214, 150]) * 0.9 + g1[..., None] * np.array([255, 170, 80]) * 0.9
             + g2[..., None] * np.array([255, 120, 50]) * 0.9)
    out = 255 - (255 - np.clip(col, 0, 255)) * (1 - np.clip(light, 0, 255) / 255)  # screen
    RASTER.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(RASTER / f"{m}.jpg", quality=86)
    return f"img/maps/{m}.jpg"


ensure_ne()
print("đọc Natural Earth…")
countries = json.load(open(NE / "ne_10m_admin_0_countries.geojson", encoding="utf-8"))["features"]
# chỉ biên giới quốc tế; bỏ các đường «Disputed / Indefinite / Line of control» (trung lập, không vẽ ranh giới tranh chấp)
borders = [l for f in json.load(open(NE / "ne_10m_admin_0_boundary_lines_land.geojson", encoding="utf-8"))["features"]
           if f["properties"].get("FEATURECLA", "").startswith("International") for l in lines_of(f["geometry"])]
coast = [l for f in json.load(open(NE / "ne_10m_coastline.geojson", encoding="utf-8"))["features"] for l in lines_of(f["geometry"])]
adm1_polys = [(f["properties"].get("name_ru") or f["properties"].get("name"), rings_of(f["geometry"]))
              for f in json.load(open(NE / "ne_10m_admin_1_states_provinces.geojson", encoding="utf-8"))["features"]
              if f["properties"].get("adm0_a3") in ("UKR", "RUS", "BLR", "POL", "MDA", "ROU", "LTU", "LVA", "EST", "FIN", "GEO")]
adm1 = json.load(open(NE / "ne_10m_admin_1_states_provinces_lines.geojson", encoding="utf-8"))["features"]
rivers = json.load(open(NE / "ne_10m_rivers_lake_centerlines.geojson", encoding="utf-8"))["features"]
lakes = json.load(open(NE / "ne_10m_lakes.geojson", encoding="utf-8"))["features"]

land_polys = [r for f in countries for r in rings_of(f["geometry"])]
adm1_lines = [l for f in adm1 if f["properties"].get("ADM0_A3") in ("UKR", "RUS", "BLR", "POL")
              for l in lines_of(f["geometry"])]
river_lines = [(l, f["properties"].get("scalerank", 9)) for f in rivers for l in lines_of(f["geometry"])]
lake_polys = [r for f in lakes for r in rings_of(f["geometry"])]
out = {"_note": "Natural Earth 1:10m (public domain)", "deepstate_datetime": "", "maps": {}}
for m, (lon0, lat0, hh, use_ds) in MAPS.items():
    k = (H / 2) / hh
    tol = 0.6
    big = [(l, r) for l, r in river_lines if r <= (7 if hh > 3 else 9)]
    rec = {
        "center": [lon0, lat0], "k": k,
        "land": poly_layer(m, land_polys, tol),
        "adm1": line_layer(m, adm1_lines, tol),
        "rivers": line_layer(m, [l for l, _ in big], tol),
        "lakes": poly_layer(m, [[r] for poly in lake_polys for r in poly[:1]], tol),
        "places": {n: [round(v, 1) for v in proj(m, lo, la)] for n, (lo, la) in PLACES.items()
                   if -100 < proj(m, lo, la)[0] < W + 100 and -100 < proj(m, lo, la)[1] < H + 100},
        "borders": line_layer(m, borders, tol),
        "coast": line_layer(m, coast, tol),
        "raster": bake_raster(m),
        "regions": {},
    }
    # vùng hành chính (oblast) chứa từng địa danh trong khung: MapView tô sáng vùng của điểm «claim»/«event»
    for n in rec["places"]:
        lo, la = PLACES[n]
        for rname, polys in adm1_polys:
            if any(inside(p[0], lo, la) for p in polys):
                # frac = phần khung mà vùng phủ (hộp bao): vùng gần kín khung thì tô cũng chẳng chỉ ra gì → MapView bỏ qua
                pts = [proj(m, x[0], x[1]) for p in polys for x in p[0]]
                xs = np.clip([q[0] for q in pts], 0, W); ys = np.clip([q[1] for q in pts], 0, H)
                frac = round(float((xs.max() - xs.min()) * (ys.max() - ys.min()) / (W * H)), 2)
                rec["regions"][n] = {"name": rname, "frac": frac, "d": poly_layer(m, [[p[0]] for p in polys], tol)}
                break
    out["maps"][m] = rec
    print(f"{m:14s} k={k:7.1f} land {len(rec['land'])//1000}k adm1 {len(rec['adm1'])//1000}k rivers {len(rec['rivers'])//1000}k "
          f"places {len(rec['places'])}" )
dst = PROJ / "film/src/digest/maps.json"
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(dst, round(dst.stat().st_size / 1e6, 2), "MB")
