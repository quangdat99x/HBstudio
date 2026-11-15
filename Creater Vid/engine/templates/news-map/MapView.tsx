import React from 'react';
import {AbsoluteFill, staticFile, useCurrentFrame} from 'remotion';
import MAPS from './maps.json';
import {camP, COL, ein, INTER, mix, OSWALD} from './theme';
import {Panel, QuoteBox} from './Overlays';

const M = (MAPS as any).maps;
const DS_TIME: string = ((MAPS as any).deepstate_datetime || '').replace(' o ', ', ');

export type Pt = {x: number; y: number; kind: string; at: number; label: string; side: string};

export const STYLE: Record<string, {r: number; fill: string; label: string; size: number; weight: number; tag: boolean}> = {
  base: {r: 7, fill: COL.white, label: COL.white, size: 30, weight: 500, tag: false},
  dim: {r: 5, fill: '#aab4d0', label: '#b4bedb', size: 24, weight: 500, tag: false},
  claim: {r: 10, fill: COL.red, label: COL.white, size: 32, weight: 700, tag: true},
  dimclaim: {r: 7, fill: 'rgba(215,38,46,0.7)', label: '#e3b5b8', size: 24, weight: 500, tag: false},
  event: {r: 10, fill: COL.amber, label: COL.white, size: 32, weight: 700, tag: true},
  reply: {r: 8, fill: COL.cyan, label: COL.white, size: 28, weight: 600, tag: true},
};
export const HOT = new Set(['claim', 'event']);

// Bản đồ dựng bằng code (style v2): nền địa hình ASTER + đèn đêm VIIRS (NASA GIBS) cắt theo đất liền Natural Earth 1:10m,
// bờ biển phát sáng, biên giới rõ, vùng (oblast) của điểm nóng tô đỏ, máy quay phóng chậm + nghiêng nhẹ kiểu 3D.
// maps.json cũ (không có raster/coast/borders/regions) vẫn chạy: phần thiếu tự bỏ qua.
export const MapView: React.FC<{c: any; dur: number}> = ({c, dur}) => {
  const f = useCurrentFrame();
  const m = M[c.map];
  const p = camP(f, dur);
  const [a, b] = c.cam || [[1, 960, 540], [1.08, 960, 540]];
  const s = mix(a[0], b[0], p);
  const ox = mix(a[1], b[1], p);
  const oy = mix(a[2], b[2], p);
  // màn hình = tâm + (điểm − tâm)·s  (phóng quanh (ox, oy): không bao giờ lộ mép bản đồ khi s ≥ 1)
  const scr = (x: number, y: number) => [ox + (x - ox) * s, oy + (y - oy) * s];
  const geo = `translate(${ox} ${oy}) scale(${s}) translate(${-ox} ${-oy})`;
  const tilt = c.tilt === false ? 0 : mix(9, 4, p);
  const id = c.map;
  const hot = (c.points || []).filter((pt: Pt) => HOT.has(pt.kind));
  const regions = hot
    .map((pt: Pt) => ({pt, r: regionOf(m, pt)}))
    .filter((x: any) => x.r)
    .filter((x: any, i: number, all: any[]) => all.findIndex((y) => y.r.d === x.r.d) === i);
  return (
    <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 40%, #0b1c4a 0%, #050c24 60%, #02060f 100%)', overflow: 'hidden'}}>
      <AbsoluteFill style={{transform: `perspective(2200px) rotateX(${tilt}deg) scale(${1 + tilt * 0.012})`, transformOrigin: '50% 60%'}}>
        <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{position: 'absolute'}}>
          <defs>
            <clipPath id={`land-${id}`}>
              <path d={m.land} />
            </clipPath>
            <filter id="mglow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="5" />
            </filter>
            <filter id="mshadow" x="-10%" y="-10%" width="120%" height="130%">
              <feGaussianBlur stdDeviation="14" />
            </filter>
            <pattern id="hatch" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="14" height="14" fill="rgba(215,38,46,0.16)" />
              <line x1="0" y1="0" x2="0" y2="14" stroke="rgba(215,38,46,0.55)" strokeWidth="4" />
            </pattern>
          </defs>
          <Graticule m={m} scr={scr} />
          <g transform={geo}>
            {/* bóng đổ dưới đất liền: tấm bản đồ nổi lên khỏi mặt biển */}
            <path d={m.land} fill="#000" opacity={0.75} transform="translate(0 14)" filter="url(#mshadow)" />
            {m.raster ? (
              <image href={staticFile(m.raster)} x={0} y={0} width={1920} height={1080} preserveAspectRatio="none" clipPath={`url(#land-${id})`} />
            ) : (
              <path d={m.land} fill="#1d2d61" />
            )}
            {m.lakes ? <path d={m.lakes} fill="#06102c" stroke="rgba(120,170,255,0.45)" strokeWidth={1} vectorEffect="non-scaling-stroke" /> : null}
            <path d={m.adm1} fill="none" stroke="rgba(220,228,250,0.22)" strokeWidth={1.2} strokeDasharray="6 5" vectorEffect="non-scaling-stroke" />
            <path d={m.rivers} fill="none" stroke="#4f86dc" strokeOpacity={0.75} strokeWidth={1.8} vectorEffect="non-scaling-stroke" />
            {/* bờ biển phát sáng */}
            {m.coast ? (
              <>
                <path d={m.coast} fill="none" stroke="#5fa8ff" strokeOpacity={0.55} strokeWidth={7} vectorEffect="non-scaling-stroke" filter="url(#mglow)" />
                <path d={m.coast} fill="none" stroke="#b8dcff" strokeWidth={1.6} vectorEffect="non-scaling-stroke" />
              </>
            ) : (
              <path d={m.land} fill="none" stroke="rgba(235,240,255,0.7)" strokeWidth={2.2} vectorEffect="non-scaling-stroke" />
            )}
            {m.borders ? (
              <>
                <path d={m.borders} fill="none" stroke="#ffffff" strokeOpacity={0.35} strokeWidth={6} vectorEffect="non-scaling-stroke" filter="url(#mglow)" />
                <path d={m.borders} fill="none" stroke="#f2f5ff" strokeWidth={2.2} vectorEffect="non-scaling-stroke" />
              </>
            ) : null}
            {c.ds && m.ds_occ ? (
              <g opacity={ein(f, 6, 24)}>
                <path d={m.ds_grey} fill="rgba(200,190,175,0.26)" stroke="rgba(200,190,175,0.6)" strokeWidth={1.2} vectorEffect="non-scaling-stroke" />
                <path d={m.ds_occ} fill="rgba(215,38,46,0.30)" stroke="rgba(215,38,46,0.85)" strokeWidth={1.4} vectorEffect="non-scaling-stroke" />
              </g>
            ) : null}
            {regions.map(({pt, r}: any, i: number) => <Region key={i} d={r.d} at={pt.at} f={f} color={STYLE[pt.kind].fill} />)}
            {(c.rings || []).map((r: any, i: number) => {
              const q = ein(f, r.at, r.at + 24);
              if (q <= 0) return null;
              const per = Math.PI * (3 * (r.rx + r.ry) - Math.sqrt((3 * r.rx + r.ry) * (r.rx + 3 * r.ry)));
              return (
                <g key={i}>
                  <ellipse cx={r.cx} cy={r.cy} rx={r.rx} ry={r.ry} fill="rgba(215,38,46,0.12)" stroke={COL.red} strokeWidth={8} strokeOpacity={0.4}
                    vectorEffect="non-scaling-stroke" filter="url(#mglow)" opacity={q} />
                  <ellipse cx={r.cx} cy={r.cy} rx={r.rx} ry={r.ry} fill="none" stroke={COL.red} strokeWidth={3.5}
                    strokeDasharray={`16 10`} strokeDashoffset={(1 - q) * per - f * 0.6} vectorEffect="non-scaling-stroke" opacity={q} />
                </g>
              );
            })}
            {(c.zones || []).map((z: any, i: number) => {
              const q = ein(f, z.at, z.at + 18);
              if (q <= 0) return null;
              return <circle key={i} cx={z.cx} cy={z.cy} r={z.r * q} fill="url(#hatch)" stroke={COL.red} strokeWidth={3} strokeDasharray="12 8" vectorEffect="non-scaling-stroke" />;
            })}
          </g>
          {c.route ? <Route c={c} m={m} scr={scr} f={f} /> : null}
          {(c.points || []).map((pt: Pt, i: number) => <Marker key={i} pt={pt} scr={scr} f={f} />)}
          {(c.rings || []).map((r: any, i: number) => {
            const q = ein(f, r.at + 10, r.at + 26);
            if (q <= 0 || !r.label) return null;
            const [x, y] = scr(r.cx, r.cy - r.ry);
            return (
              <text key={i} x={x} y={y - 18} textAnchor="middle" fontFamily={OSWALD} fontWeight={700} fontSize={30} fill={COL.red} opacity={q}
                stroke="rgba(6,12,32,0.95)" strokeWidth={6} paintOrder="stroke">{r.label}</text>
            );
          })}
          {(c.zones || []).map((z: any, i: number) => {
            const q = ein(f, z.at + 8, z.at + 22);
            if (q <= 0) return null;
            const [x, y] = scr(z.cx, z.cy - z.r);
            return (
              <text key={i} x={x} y={y - 16} textAnchor="middle" fontFamily={OSWALD} fontWeight={700} fontSize={32} fill={COL.white} opacity={q}
                stroke="rgba(6,12,32,0.95)" strokeWidth={6} paintOrder="stroke">{z.label}</text>
            );
          })}
          {c.border ? (
            <text x={c.border.x} y={c.border.y} textAnchor="middle" fontFamily={OSWALD} fontWeight={500} fontSize={26} letterSpacing="0.08em" fill="rgba(255,255,255,0.55)"
              stroke="rgba(6,12,32,0.8)" strokeWidth={5} paintOrder="stroke">
              {c.border.text}
            </text>
          ) : null}
          {(c.glabels || []).map((l: any, i: number) => (
            <text key={'lb' + i} x={scr(l.x, l.y)[0]} y={scr(l.x, l.y)[1]} textAnchor="middle" fontFamily={OSWALD} fontWeight={l.weight || 500} fontSize={l.size || 30}
              letterSpacing="0.14em" fill={l.color || 'rgba(255,255,255,0.6)'} opacity={ein(f, l.at || 0, (l.at || 0) + 14)}
              stroke="rgba(6,12,32,0.8)" strokeWidth={l.stroke ?? 5} paintOrder="stroke">{l.text}</text>
          ))}
          {c.sea ? (
            <text x={c.sea.x} y={c.sea.y} textAnchor="middle" fontFamily={OSWALD} fontWeight={500} fontSize={30} letterSpacing="0.3em"
              fill="#8fb4ee" opacity={ein(f, c.sea.at, c.sea.at + 14) * 0.85}>{c.sea.text}</text>
          ) : null}
        </svg>
        <Tags points={c.points || []} scr={scr} f={f} />
      </AbsoluteFill>
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
        Карта: Natural Earth{m.raster ? ' · NASA (ASTER, VIIRS)' : ''}{c.ds ? ` · DeepState, ${DS_TIME}` : ''}
      </div>
    </AbsoluteFill>
  );
};

// vùng hành chính chứa điểm: địa danh trong maps.json trùng toạ độ (±3 px) hoặc trùng đầu nhãn
export const regionOf = (m: any, pt: Pt) => {
  if (!m.regions || m.k > 600) return null; // bản đồ cấp thành phố: vùng hành chính to hơn khung
  for (const [name, xy] of Object.entries(m.places || {}) as [string, number[]][]) {
    if (!m.regions[name] || (m.regions[name].frac ?? 0) > 0.4) continue;
    if (Math.hypot(xy[0] - pt.x, xy[1] - pt.y) < 3 || pt.label.toLowerCase().startsWith(name.toLowerCase())) return m.regions[name];
  }
  return null;
};

const Region: React.FC<{d: string; at: number; f: number; color: string}> = ({d, at, f, color}) => {
  const q = ein(f, at + 4, at + 30);
  if (q <= 0) return null;
  const breathe = 0.75 + 0.25 * Math.sin((f - at) / 14);
  return (
    <g opacity={q}>
      <path d={d} fill={color} fillOpacity={0.16 * breathe} />
      <path d={d} fill="none" stroke={color} strokeOpacity={0.55} strokeWidth={9} vectorEffect="non-scaling-stroke" filter="url(#mglow)" />
      <path d={d} fill="none" stroke={color} strokeWidth={2.4} vectorEffect="non-scaling-stroke" />
    </g>
  );
};

// lưới kinh vĩ mờ trên biển và đất: cho cảm giác "bản đồ tác chiến", dịch theo máy quay
const Graticule: React.FC<{m: any; scr: (x: number, y: number) => number[]}> = ({m, scr}) => {
  if (!m.center || !m.k) return null;
  const [lon0, lat0] = m.center;
  const kx = m.k * Math.cos((lat0 * Math.PI) / 180);
  const span = 540 / m.k;
  const step = span > 4 ? 5 : span > 1.5 ? 1 : span > 0.7 ? 0.5 : 0.25;
  const lines: string[] = [];
  for (let lon = Math.ceil((lon0 - 1100 / kx) / step) * step; lon <= lon0 + 1100 / kx; lon += step) {
    const x = 960 + (lon - lon0) * kx;
    const [x1, y1] = scr(x, -200);
    const [x2, y2] = scr(x, 1280);
    lines.push(`M${x1.toFixed(1)},${y1.toFixed(1)}L${x2.toFixed(1)},${y2.toFixed(1)}`);
  }
  for (let lat = Math.ceil((lat0 - 700 / m.k) / step) * step; lat <= lat0 + 700 / m.k; lat += step) {
    const y = 540 - (lat - lat0) * m.k;
    const [x1, y1] = scr(-200, y);
    const [x2, y2] = scr(2120, y);
    lines.push(`M${x1.toFixed(1)},${y1.toFixed(1)}L${x2.toFixed(1)},${y2.toFixed(1)}`);
  }
  return <path d={lines.join('')} fill="none" stroke="rgba(140,175,240,0.10)" strokeWidth={1} />;
};

// chấm đánh dấu: hào quang + lõi; điểm nóng có vòng sóng lan liên tục và ống ngắm xoay
export const Marker: React.FC<{pt: Pt; scr: (x: number, y: number) => number[]; f: number}> = ({pt, scr, f}) => {
  const st = STYLE[pt.kind] || STYLE.base;
  const q = ein(f, pt.at, pt.at + 12);
  if (q <= 0) return null;
  const [x, y] = scr(pt.x, pt.y);
  const isHot = HOT.has(pt.kind);
  const t = f - pt.at;
  const waves = isHot ? [0, 1, 2].map((k) => ((t + k * 20) % 60) / 60) : [];
  const pop = 1 + 0.6 * Math.max(0, 1 - Math.abs(t - 8) / 8);
  return (
    <g opacity={Math.min(1, q * 1.4)}>
      {waves.map((w, i) => (
        <circle key={i} cx={x} cy={y} r={st.r + w * 70} fill="none" stroke={st.fill} strokeWidth={3 * (1 - w) + 0.5} opacity={(1 - w) * 0.8} />
      ))}
      <circle cx={x} cy={y} r={st.r * (isHot ? 3.2 : 2)} fill={st.fill} opacity={isHot ? 0.35 : 0.18} filter="url(#mglow)" />
      {isHot ? (
        <g transform={`translate(${x} ${y}) rotate(${t * 1.5})`} opacity={0.9}>
          <circle r={st.r * 2.6} fill="none" stroke={st.fill} strokeWidth={2} strokeDasharray="10 8" />
          {[0, 90, 180, 270].map((r) => (
            <line key={r} x1={st.r * 3.1} y1={0} x2={st.r * 4.1} y2={0} stroke={st.fill} strokeWidth={3} transform={`rotate(${r})`} />
          ))}
        </g>
      ) : null}
      <circle cx={x} cy={y} r={st.r * (0.6 + 0.4 * q) * (isHot ? pop : 1)} fill={st.fill} stroke="#ffffff" strokeWidth={isHot ? 2.5 : 1.5} />
    </g>
  );
};

// nhãn địa danh: điểm nóng = thẻ chữ có vạch màu; điểm phụ = chữ có bóng
export const Tags: React.FC<{points: Pt[]; scr: (x: number, y: number) => number[]; f: number}> = ({points, scr, f}) => (
  <>
    {points.map((pt, i) => {
      const st = STYLE[pt.kind] || STYLE.base;
      const q = ein(f, pt.at + 2, pt.at + 14);
      if (q <= 0) return null;
      const [x, y] = scr(pt.x, pt.y);
      const left = pt.side === 'l';
      const gap = st.tag ? st.r * 4.4 : st.r + 12;
      const slide = (1 - q) * 24 * (left ? 1 : -1);
      return (
        <div key={i} style={{position: 'absolute', top: y, left: left ? undefined : x + gap + slide, right: left ? 1920 - x + gap - slide : undefined,
          transform: 'translateY(-50%)', opacity: q, whiteSpace: 'nowrap', display: 'flex', flexDirection: left ? 'row-reverse' : 'row'}}>
          {st.tag ? (
            <>
              <div style={{width: 6, background: st.fill}} />
              <div style={{background: 'rgba(6,12,32,0.86)', padding: '4px 14px 6px', fontFamily: OSWALD, fontWeight: st.weight, fontSize: st.size, color: st.label,
                letterSpacing: '0.02em', boxShadow: '0 6px 24px rgba(0,0,0,0.5)'}}>{pt.label}</div>
            </>
          ) : (
            <div style={{fontFamily: OSWALD, fontWeight: st.weight, fontSize: st.size, color: st.label,
              textShadow: '0 0 6px rgba(4,8,24,1), 0 0 14px rgba(4,8,24,0.9), 0 2px 3px rgba(0,0,0,0.9)'}}>{pt.label}</div>
          )}
        </div>
      );
    })}
  </>
);

// vệt sáng quét chéo rất nhẹ qua khung
export const Sweep: React.FC<{f: number}> = ({f}) => {
  const x = ((f * 6) % 3600) - 900;
  return (
    <AbsoluteFill style={{pointerEvents: 'none', mixBlendMode: 'screen',
      background: `linear-gradient(105deg, rgba(0,0,0,0) ${x - 260}px, rgba(120,170,255,0.07) ${x}px, rgba(0,0,0,0) ${x + 260}px)`}} />
  );
};

export const Route: React.FC<{c: any; m: any; scr: (x: number, y: number) => number[]; f: number}> = ({c, m, scr, f}) => {
  const r = c.route;
  const pts = r.names.map((n: string) => scr(m.places[n][0], m.places[n][1]));
  let len = 0;
  const segs: number[] = [];
  for (let i = 1; i < pts.length; i++) {
    const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    segs.push(d);
    len += d;
  }
  const q = ein(f, r.at, r.at + r.dur);
  if (q <= 0) return null;
  const d = 'M' + pts.map((p: number[]) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('L');
  // đầu mũi tên tại vị trí đang vẽ
  let rest = q * len;
  let hx = pts[0][0];
  let hy = pts[0][1];
  let ang = 0;
  for (let i = 1; i < pts.length; i++) {
    const s = segs[i - 1];
    ang = Math.atan2(pts[i][1] - pts[i - 1][1], pts[i][0] - pts[i - 1][0]);
    if (rest <= s) {
      hx = pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * (rest / s);
      hy = pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * (rest / s);
      break;
    }
    rest -= s;
    hx = pts[i][0];
    hy = pts[i][1];
  }
  const ah = 22;
  const arrow = `M${hx},${hy} L${hx - ah * Math.cos(ang - 0.45)},${hy - ah * Math.sin(ang - 0.45)} L${hx - ah * Math.cos(ang + 0.45)},${hy - ah * Math.sin(ang + 0.45)}Z`;
  let acc = 0;
  return (
    <g>
      <path d={d} fill="none" stroke={COL.amber} strokeOpacity={0.5} strokeWidth={14} strokeDasharray={`${q * len} ${len}`} strokeLinecap="round" filter="url(#mglow)" />
      <path d={d} fill="none" stroke={COL.amber} strokeWidth={5} strokeDasharray={`${q * len} ${len}`} strokeLinecap="round" />
      <path d={d} fill="none" stroke="rgba(6,12,32,0.6)" strokeWidth={2} strokeDasharray="2 14" />
      {q < 1 ? <circle cx={hx} cy={hy} r={16} fill={COL.amber} opacity={0.6} filter="url(#mglow)" /> : null}
      <path d={arrow} fill={COL.amber} />
      {(r.stamps || []).map((st: any, i: number) => {
        if (i > 0) acc += segs[i - 1];
        const show = q * len >= acc - 1;
        if (!show) return null;
        const [x, y] = pts[i];
        const o = typeof st === 'string' ? {text: st, dx: 0, dy: -26} : st;
        return (
          <text key={i} x={x + o.dx} y={y + o.dy} textAnchor="middle" fontFamily={INTER} fontWeight={600} fontSize={26} fill={COL.amber}
            stroke="rgba(6,12,32,0.95)" strokeWidth={6} paintOrder="stroke">{o.text}</text>
        );
      })}
    </g>
  );
};

export const Legend: React.FC<{f: number}> = ({f}) => (
  <div style={{position: 'absolute', left: 44, top: 142, opacity: ein(f, 8, 24), background: 'rgba(6,12,32,0.82)', padding: '12px 18px', fontFamily: INTER, fontSize: 23, color: COL.white}}>
    <div style={{fontFamily: OSWALD, fontWeight: 500, fontSize: 22, letterSpacing: '0.06em', color: '#c8d0e4', marginBottom: 8}}>ПО ДАННЫМ DEEPSTATE · {DS_TIME}</div>
    <div style={{display: 'flex', alignItems: 'center', gap: 10}}>
      <span style={{width: 26, height: 16, background: 'rgba(215,38,46,0.45)', border: '2px solid rgba(215,38,46,0.9)', display: 'inline-block'}} /> под контролем ВС РФ
    </div>
    <div style={{display: 'flex', alignItems: 'center', gap: 10, marginTop: 6}}>
      <span style={{width: 26, height: 16, background: 'rgba(200,190,175,0.4)', border: '2px solid rgba(200,190,175,0.8)', display: 'inline-block'}} /> серая зона / статус неизвестен
    </div>
  </div>
);

export const BigNumber: React.FC<{b: any; f: number}> = ({b, f}) => {
  const q = ein(f, b.at, b.at + 16);
  if (q <= 0) return null;
  return (
    <div style={{position: 'absolute', left: 60, top: 300, opacity: q, transform: `scale(${0.9 + 0.1 * q})`, transformOrigin: 'left center'}}>
      <div style={{fontFamily: OSWALD, fontWeight: 700, fontSize: 230, lineHeight: 0.95, color: COL.white, textShadow: '0 8px 40px rgba(0,0,0,0.6)'}}>{b.value}</div>
      <div style={{fontFamily: INTER, fontWeight: 600, fontSize: 34, color: COL.white, background: 'rgba(215,38,46,0.9)', padding: '6px 16px', display: 'inline-block'}}>{b.sub}</div>
    </div>
  );
};
