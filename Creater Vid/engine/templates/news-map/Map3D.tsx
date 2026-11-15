import React, {useEffect, useMemo, useRef, useState} from 'react';
import {AbsoluteFill, continueRender, delayRender, Easing, useCurrentFrame} from 'remotion';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import MAPS from './maps.json';
import {camP, COL, ein, INTER, mix, OSWALD} from './theme';
import {Panel, QuoteBox} from './Overlays';
import {BigNumber, HOT, Legend, Marker, Pt, regionOf, Route, STYLE, Sweep, Tags} from './MapView';

const M = (MAPS as any).maps;

// Bản đồ 3D (mặc định cho mọi cảnh 'map' từ 17.10.2026, RULEBOOK.news 4.4): MapLibre GL + địa hình nổi (AWS Terrarium) + đèn đêm VIIRS + đường, biên giới OSM (OpenFreeMap).
// Đọc đúng cấu hình của cảnh 'map' (toạ độ px của maps.json) → tự đổi ra kinh vĩ, nên mọi cảnh bản đồ cũ đều chạy được.
// Máy quay: bay vào từ trên cao (nhìn thẳng) rồi nghiêng 3D quanh điểm nóng.
const STYLE_3D: any = {
  version: 8,
  transition: {duration: 0, delay: 0}, // đổi paint theo khung hình phải có hiệu lực ngay
  sources: {
    omt: {type: 'vector', url: 'https://tiles.openfreemap.org/planet'},
    shade: {type: 'raster-dem', tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'], tileSize: 256, maxzoom: 13, encoding: 'terrarium'},
    dem: {type: 'raster-dem', tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'], tileSize: 256, maxzoom: 13, encoding: 'terrarium'},
    nite: {type: 'raster', tiles: ['https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_Black_Marble/default/2016-01-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.png'],
      tileSize: 256, maxzoom: 8},
    // ảnh vệ tinh Sentinel-2 cloudless 2016 (EOX, CC BY 4.0, ~10 m/điểm): chỉ hiện khi máy quay xuống cấp thành phố
    sat: {type: 'raster', tiles: ['https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg'], tileSize: 256, maxzoom: 14},
  },
  sky: {'sky-color': '#0b1c4a', 'horizon-color': '#1b3170', 'fog-color': '#050c24', 'sky-horizon-blend': 0.6, 'horizon-fog-blend': 0.6, 'fog-ground-blend': 0.4},
  terrain: {source: 'dem', exaggeration: 2.2},
  layers: [
    {id: 'bg', type: 'background', paint: {'background-color': '#0c1a44'}},
    // đèn đêm VIIRS chỉ có tới zoom 8: cận cảnh thành phố thì mờ dần để không thành mảng trắng, đường phố OSM thay vào
    {id: 'nite', type: 'raster', source: 'nite', paint: {'raster-opacity': ['interpolate', ['linear'], ['zoom'], 7, 1, 9.5, 0.3], 'raster-saturation': -0.1, 'raster-brightness-min': 0.24, 'raster-contrast': 0.3, 'raster-hue-rotate': 8, 'raster-fade-duration': 0}},
    {id: 'sat', type: 'raster', source: 'sat', paint: {'raster-opacity': ['interpolate', ['linear'], ['zoom'], 9, 0, 10.8, 0.95],
      'raster-saturation': -0.2, 'raster-brightness-max': 0.82, 'raster-contrast': 0.12, 'raster-fade-duration': 0}},
    {id: 'shade', type: 'hillshade', source: 'shade', paint: {'hillshade-exaggeration': 0.9, 'hillshade-shadow-color': '#02050f', 'hillshade-highlight-color': '#5f84d8', 'hillshade-accent-color': '#0a1638'}},
    {id: 'water', type: 'fill', source: 'omt', 'source-layer': 'water', paint: {'fill-color': '#040a1f', 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 10, 0.92, 12, 0.55]}},
    {id: 'river', type: 'line', source: 'omt', 'source-layer': 'waterway', filter: ['==', ['get', 'class'], 'river'], paint: {'line-color': '#4f86dc', 'line-width': 1.4, 'line-opacity': 0.8}},
    {id: 'roads-glow', type: 'line', source: 'omt', 'source-layer': 'transportation', filter: ['match', ['get', 'class'], ['motorway', 'trunk', 'primary', 'secondary'], true, false],
      paint: {'line-color': '#f0a93a', 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.4, 10, 2.2], 'line-opacity': ['interpolate', ['linear'], ['zoom'], 8, 0.28, 11, 0.6], 'line-blur': 1}},
    {id: 'adm4', type: 'line', source: 'omt', 'source-layer': 'boundary', filter: ['all', ['==', ['get', 'admin_level'], 4], ['!=', ['get', 'maritime'], 1]],
      paint: {'line-color': 'rgba(220,228,250,0.35)', 'line-width': 1.1, 'line-dasharray': [3, 2]}},
    {id: 'adm2-glow', type: 'line', source: 'omt', 'source-layer': 'boundary',
      filter: ['all', ['==', ['get', 'admin_level'], 2], ['!=', ['get', 'maritime'], 1], ['!=', ['get', 'disputed'], 1]],
      paint: {'line-color': '#ffffff', 'line-width': 7, 'line-opacity': 0.25, 'line-blur': 4}},
    {id: 'adm2', type: 'line', source: 'omt', 'source-layer': 'boundary',
      filter: ['all', ['==', ['get', 'admin_level'], 2], ['!=', ['get', 'maritime'], 1], ['!=', ['get', 'disputed'], 1]],
      paint: {'line-color': '#f2f5ff', 'line-width': 2}},
    // nhà 3D dựng khối (OSM render_height) khi lao xuống mục tiêu
    {id: 'buildings', type: 'fill-extrusion', source: 'omt', 'source-layer': 'building', minzoom: 12.5, filter: ['!=', ['get', 'hide_3d'], true],
      paint: {'fill-extrusion-color': '#c3cde6', 'fill-extrusion-height': ['coalesce', ['get', 'render_height'], 8],
        'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0], 'fill-extrusion-opacity': 0.85, 'fill-extrusion-vertical-gradient': true}},
  ],
};

// bộ đệm tile trên đĩa (engine/scripts/tilecache.mjs, chạy kèm lượt render): có thì mọi tile đi qua nó, không thì tải thẳng
const TILE_CACHE = 'http://127.0.0.1:5098';
let cacheOk: Promise<boolean> | null = null;
const tileCache = () =>
  (cacheOk ??= fetch(`${TILE_CACHE}/ping`, {signal: AbortSignal.timeout(1500)})
    .then((r) => r.ok)
    .catch(() => false));

// px của maps.json → kinh vĩ (nghịch đảo phép chiếu trong notes/tools/build_maps.py)
const unproj = (m: any, x: number, y: number): [number, number] => {
  const [lon0, lat0] = m.center;
  return [lon0 + (x - 960) / (m.k * Math.cos((lat0 * Math.PI) / 180)), lat0 - (y - 540) / m.k];
};
const zoomOf = (m: any, s: number) => Math.log2((m.k * Math.cos((m.center[1] * Math.PI) / 180) * s * 360) / 512);

// đường SVG "M x,y L … Z" của vùng → đa giác GeoJSON
const pathToGeo = (m: any, d: string) => ({
  type: 'Feature',
  properties: {},
  geometry: {
    type: 'MultiPolygon',
    coordinates: d.split('M').filter(Boolean).map((r) => {
      const ring = r.replace(/Z/g, '').split('L').map((p) => {
        const [x, y] = p.split(',').map(Number);
        return unproj(m, x, y);
      });
      return [[...ring, ring[0]]];
    }),
  },
});

export const Map3D: React.FC<{c: any; dur: number}> = ({c, dur}) => {
  const f = useCurrentFrame();
  const m = M[c.map];
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [, setTick] = useState(0);
  const [boot] = useState(() => delayRender('map3d load', {timeoutInMilliseconds: 110000}));

  const hot: Pt[] = (c.points || []).filter((pt: Pt) => HOT.has(pt.kind));
  const region = useMemo(() => {
    const h = hot.map((pt) => ({pt, r: regionOf(m, pt)})).find((x) => x.r);
    return h ? {at: h.pt.at, color: STYLE[h.pt.kind].fill, geo: pathToGeo(m, h.r.d)} : null;
  }, [c.map]);

  // máy quay: điểm đích = tâm cam cuối của cảnh phẳng, phóng thêm tới mức các điểm chính (trừ dim) vẫn nằm gọn trong khung.
  // Cảnh dài (≥ 150 khung) bay vào từ trên cao (zoom −1.3, nhìn thẳng) rồi nghiêng 55°; cảnh ngắn (và nền menu) đã nghiêng sẵn, chỉ trôi nhẹ.
  // Chiều xoay đổi theo cảnh (băm tên bản đồ + nhãn) để nhiều cảnh liền không lặp một kiểu. c.fly = true/false ép kiểu.
  const [a, b] = c.cam || [[1, 960, 540], [1.08, 960, 540]];
  const p = camP(f, dur);
  const key = (c.points || []).map((pt: Pt) => pt.label).join('') + c.map;
  const dir = [...key].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) | 0, 7) & 1 ? 1 : -1;
  const main = (c.points || []).filter((pt: Pt) => pt.kind !== 'dim' && pt.kind !== 'dimclaim');
  const spread = Math.max(0.35, ...main.map((pt: Pt) => Math.max(Math.abs(pt.x - b[1]) / 780, Math.abs(pt.y - b[2]) / 400)));
  // cảnh có hộp trích dẫn giữa khung: giữ đúng cỡ khung của bản phẳng để điểm không lọt dưới hộp
  const zEnd = zoomOf(m, b[0]) + (c.quote ? 0 : Math.max(0, Math.min(0.8, -Math.log2(spread))));
  const target = unproj(m, b[1], b[2]);
  const flyIn = c.fly ?? dur >= 150;
  let cam: {center: [number, number]; zoom: number; pitch: number; bearing: number};
  if (flyIn) {
    const fly = ein(f, 0, Math.min(dur * 0.55, 110));
    const start = unproj(m, mix(a[1], 960, 0.5), mix(a[2], 540, 0.5));
    cam = {
      center: [mix(start[0], target[0], fly), mix(start[1], target[1], fly)],
      zoom: mix(zoomOf(m, a[0]) - 1.3, zEnd, fly) + 0.12 * p,
      pitch: mix(0, 55, fly),
      bearing: dir * (mix(0, 20, fly) + 6 * p),
    };
  } else {
    cam = {center: target, zoom: zEnd - 0.25 + 0.3 * p, pitch: mix(42, 54, p), bearing: dir * mix(8, 18, p)};
  }
  // lao xuống mục tiêu (kiểu Google Maps 3D): cảnh dài có đúng một điểm nóng, không có hộp trích dẫn → sau khi điểm hiện,
  // máy quay hạ xuống zoom ~13.6, nghiêng 62°: ảnh vệ tinh + nhà 3D thay nền đêm. c.dive = true/false ép kiểu.
  const diveOn = c.dive ?? (flyIn && hot.length === 1 && !c.quote && dur >= 180);
  let diveQ = 0;
  if (diveOn && hot.length) {
    const t0 = Math.max(hot[0].at + 20, dur * 0.45);
    const q = ein(f, t0, Math.max(t0 + 30, dur * 0.92), Easing.inOut(Easing.cubic));
    diveQ = q;
    const tgt = unproj(m, hot[0].x, hot[0].y);
    cam = {
      center: [mix(cam.center[0], tgt[0], Math.min(1, q * 1.6)), mix(cam.center[1], tgt[1], Math.min(1, q * 1.6))],
      zoom: mix(cam.zoom, 13.6, q),
      pitch: mix(cam.pitch, 62, q),
      bearing: cam.bearing + dir * 35 * q,
    };
  }
  // hộp trích dẫn chiếm giữa khung: dời tâm nhìn xuống dưới hộp, nghiêng ít hơn để điểm phía bắc không trôi lên dưới hộp
  const pad = c.quote ? {top: 420, bottom: 0, left: 0, right: 0} : {top: 0, bottom: 0, left: 0, right: 0};
  const view = {...cam, pitch: c.quote ? Math.min(cam.pitch, 38) : cam.pitch, padding: pad};

  useEffect(() => {
    let mp: maplibregl.Map | null = null;
    let gone = false;
    tileCache().then((cached) => {
      if (gone) return;
      const viaCache = (url: string) => ({url: cached && /^https?:\/\//.test(url) ? `${TILE_CACHE}/fetch?u=${encodeURIComponent(url)}` : url});
      const created = new maplibregl.Map({
        container: box.current!, style: STYLE_3D, interactive: false, attributionControl: false, fadeDuration: 0, transformRequest: viaCache,
        canvasContextAttributes: {preserveDrawingBuffer: true, antialias: true}, pixelRatio: 1, maxPitch: 75, ...view,
      });
      mp = created;
      setup(created);
    });
    const setup = (mp: maplibregl.Map) => mp.on('load', () => {
      if (c.ds && m.ds_occ) {
        mp.addSource('ds-grey', {type: 'geojson', data: pathToGeo(m, m.ds_grey) as any});
        mp.addSource('ds-occ', {type: 'geojson', data: pathToGeo(m, m.ds_occ) as any});
        mp.addLayer({id: 'ds-grey', type: 'fill', source: 'ds-grey', paint: {'fill-color': 'rgba(200,190,175,0.3)', 'fill-outline-color': 'rgba(200,190,175,0.7)'}});
        mp.addLayer({id: 'ds-occ', type: 'fill', source: 'ds-occ', paint: {'fill-color': 'rgba(215,38,46,0.32)', 'fill-outline-color': 'rgba(215,38,46,0.9)'}});
      }
      if (region) {
        mp.addSource('region', {type: 'geojson', data: region.geo as any});
        mp.addLayer({id: 'region-fill', type: 'fill', source: 'region', paint: {'fill-color': region.color, 'fill-opacity': 0}});
        mp.addLayer({id: 'region-glow', type: 'line', source: 'region', paint: {'line-color': region.color, 'line-width': 9, 'line-blur': 6, 'line-opacity': 0}});
        mp.addLayer({id: 'region-line', type: 'line', source: 'region', paint: {'line-color': region.color, 'line-width': 2.5, 'line-opacity': 0}});
      }
      map.current = mp;
      setReady(true);
      continueRender(boot);
    });
    return () => {
      gone = true;
      mp?.remove();
    };
  }, []);

  useEffect(() => {
    const mp = map.current;
    if (!ready || !mp) return;
    const h = delayRender(`map3d frame ${f}`, {timeoutInMilliseconds: 110000});
    mp.jumpTo(view);
    if (region) {
      const q = ein(f, region.at + 4, region.at + 30) * (1 - 0.85 * diveQ); // xuống ảnh vệ tinh thì vùng tô nhạt dần
      const breathe = 0.75 + 0.25 * Math.sin((f - region.at) / 14);
      mp.setPaintProperty('region-fill', 'fill-opacity', 0.18 * q * breathe);
      mp.setPaintProperty('region-glow', 'line-opacity', 0.6 * q);
      mp.setPaintProperty('region-line', 'line-opacity', q);
    }
    setTick((t) => t + 1); // vẽ lại lớp chấm, nhãn theo máy quay mới
    let done = false;
    const finish = () => {
      if (!done) {
        done = true;
        continueRender(h);
      }
    };
    mp.once('idle', finish);
    mp.triggerRepaint();
    const t = setTimeout(finish, 60000);
    return () => clearTimeout(t);
  }, [f, ready]);

  // px phẳng → màn hình (có tính nghiêng, độ cao địa hình)
  const scr = (x: number, y: number) => {
    const mp = map.current;
    if (!mp) return [-999, -999];
    const pt = mp.project(unproj(m, x, y));
    return [pt.x, pt.y];
  };

  // vòng, vùng tròn vẽ trên mặt đất (px phẳng) → đa giác trên màn hình, có phối cảnh
  const ellipse = (cx: number, cy: number, rx: number, ry: number, q = 1) =>
    'M' + Array.from({length: 49}, (_, i) => {
      const t = (i / 48) * Math.PI * 2;
      const [x, y] = scr(cx + Math.cos(t) * rx * q, cy + Math.sin(t) * ry * q);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join('L') + 'Z';
  const texts = [
    ...(c.rings || []).filter((r: any) => r.label).map((r: any) => ({x: r.cx, y: r.cy - r.ry, at: r.at + 10, text: r.label, color: COL.red, size: 30, weight: 700})),
    ...(c.zones || []).map((z: any) => ({x: z.cx, y: z.cy - z.r, at: z.at + 8, text: z.label, color: COL.white, size: 32, weight: 700})),
    ...(c.glabels || []).map((l: any) => ({...l, at: l.at || 0, color: l.color || 'rgba(255,255,255,0.7)', size: l.size || 30, weight: l.weight || 500, spacing: '0.14em'})),
    ...(c.sea ? [{...c.sea, color: '#8fb4ee', size: 30, weight: 500, spacing: '0.3em'}] : []),
    ...(c.border ? [{...c.border, at: 0, color: 'rgba(255,255,255,0.6)', size: 26, weight: 500, spacing: '0.08em'}] : []),
  ];

  return (
    <AbsoluteFill style={{background: '#050c24'}}>
      <div ref={box} style={{position: 'absolute', width: 1920, height: 1080}} />
      {ready ? (
        <AbsoluteFill>
          <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{position: 'absolute'}}>
            <defs>
              <filter id="mglow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="5" />
              </filter>
            </defs>
            {(c.rings || []).map((r: any, i: number) => {
              const q = ein(f, r.at, r.at + 24);
              if (q <= 0) return null;
              const d = ellipse(r.cx, r.cy, r.rx, r.ry);
              return (
                <g key={'r' + i} opacity={q}>
                  <path d={d} fill="rgba(215,38,46,0.12)" stroke={COL.red} strokeWidth={8} strokeOpacity={0.4} filter="url(#mglow)" />
                  <path d={d} fill="none" stroke={COL.red} strokeWidth={3.5} strokeDasharray="16 10" strokeDashoffset={-f * 0.6} />
                </g>
              );
            })}
            {(c.zones || []).map((z: any, i: number) => {
              const q = ein(f, z.at, z.at + 18);
              if (q <= 0) return null;
              return <path key={'z' + i} d={ellipse(z.cx, z.cy, z.r, z.r, q)} fill="rgba(215,38,46,0.22)" stroke={COL.red} strokeWidth={3} strokeDasharray="12 8" />;
            })}
            {c.route ? <Route c={c} m={m} scr={scr} f={f} /> : null}
            {(c.points || []).map((pt: Pt, i: number) => <Marker key={i} pt={pt} scr={scr} f={f} />)}
            {texts.map((l: any, i: number) => {
              const q = ein(f, l.at, l.at + 14);
              if (q <= 0 || !l.text) return null;
              const [x, y] = scr(l.x, l.y);
              return (
                <text key={'t' + i} x={x} y={y - 14} textAnchor="middle" fontFamily={OSWALD} fontWeight={l.weight} fontSize={l.size} letterSpacing={l.spacing || '0.04em'}
                  fill={l.color} opacity={q} stroke="rgba(6,12,32,0.9)" strokeWidth={6} paintOrder="stroke">{l.text}</text>
              );
            })}
          </svg>
          <Tags points={c.points || []} scr={scr} f={f} />
        </AbsoluteFill>
      ) : null}
      <Sweep f={f} />
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 46%, rgba(0,0,0,0) 52%, rgba(0,0,0,0.5) 100%)', pointerEvents: 'none'}} />
      {c.ds ? <Legend f={f} /> : null}
      {c.scheme ? (
        <div style={{position: 'absolute', left: 44, top: 142, fontFamily: OSWALD, fontWeight: 500, fontSize: 24, letterSpacing: '0.1em', color: '#c8d0e4',
          background: 'rgba(6,12,32,0.7)', padding: '4px 12px'}}>СХЕМА · НЕ КАРТА ЛИНИИ ФРОНТА</div>
      ) : null}
      {c.big ? <BigNumber b={c.big} f={f} /> : null}
      <Panel p={c.panel} />
      <QuoteBox q={c.quote} />
      <div style={{position: 'absolute', left: 44, bottom: 14, fontFamily: INTER, fontSize: 16, color: 'rgba(200,210,235,0.55)'}}>
        Карта: © OpenStreetMap · OpenFreeMap · NASA (VIIRS) · Sentinel-2 cloudless 2016 by EOX (Copernicus) · рельеф: AWS Terrain Tiles
      </div>
    </AbsoluteFill>
  );
};

