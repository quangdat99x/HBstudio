# Bộ bản đồ bản tin (RULEBOOK.news mục 4.4)

Mẫu dùng chung cho mọi dự án Tin tức (Điểm tin 24h, tin nóng). Không nằm trong `src/`, nên app không tự chép vào `film/`;
Claude của dự án chép khi dựng bước hình:

| Tệp mẫu | Chép tới | Ghi chú |
|---|---|---|
| `Map3D.tsx` | `film/src/digest/Map3D.tsx` | mặc định cho mọi cảnh `"type": "map"` |
| `MapView.tsx` | `film/src/digest/MapView.tsx` | bản phẳng, dự phòng `"flat": true`; Map3D dùng lại Marker, Tags, Route… của nó |
| `build_maps.py` | `notes/tools/build_maps.py` | chỉ sửa `MAPS`, `PLACES` (và docstring nguồn toạ độ) |

`ne/` là Natural Earth 1:10m dùng chung (phạm vi công cộng, không đưa vào git); `build_maps.py` tự tìm nó qua
liên kết `film/node_modules` → engine, thiếu tệp thì tự tải.

## Hai component cần gì từ dự án

- `./theme`: `camP, COL, ein, INTER, mix, OSWALD` · `./Overlays`: `Panel, QuoteBox` · `./maps.json` (do `build_maps.py` sinh).
- `Scene.tsx`: `case 'map': return c.flat ? <MapView c={c} dur={dur} /> : <Map3D c={c} dur={dur} />;`
- `maplibre-gl` đã có trong engine (node_modules dùng chung): **không** `npm install` trong `film/`.

## Chạy

```
E:\Tool\bgremove\.venv\Scripts\python.exe notes\tools\build_maps.py
```
(cần numpy + PIL; tải nền NASA GIBS → `film/public/img/maps/<bản đồ>.jpg`, ghi `film/src/digest/maps.json`).

## Cấu hình cảnh (toạ độ px của `maps.json`, Map3D tự đổi ra kinh vĩ)

`map, cam [[s,x,y],[s,x,y]], points [{x,y,kind: base|dim|claim|dimclaim|event|reply, at, label, side}], rings, zones, route,
glabels, sea, border, panel, quote, big, scheme, ds` và các khoá riêng của Map3D:

- `flat: true` → bản phẳng (mất mạng, tile lỗi).
- `fly: true|false` → bay vào từ trên cao (mặc định khi cảnh ≥ 150 khung).
- `dive: true|false` → lao xuống ảnh vệ tinh + nhà 3D ở điểm nóng (mặc định khi cảnh ≥ 180 khung, đúng một điểm `claim`/`event`, không có `quote`).

## Nguồn (tự ghi góc dưới trái)

OpenStreetMap qua OpenFreeMap (đường, nước, biên giới quốc tế, nhà) · NASA GIBS VIIRS Black Marble (đèn đêm) ·
Sentinel-2 cloudless 2016 by EOX, CC BY 4.0 (ảnh vệ tinh) · AWS Terrain Tiles (địa hình). Render cần mạng để tải tile.

## Bộ đệm tile

`engine/scripts/tilecache.mjs` (cổng 5098) tự chạy kèm `npx remotion render` (`remotion.config.ts`) và `scripts/stills.mjs`,
lưu tile ở `<Creater Vid>/work/tilecache` cho mọi dự án; Map3D hỏi `/ping` trước, không có thì tải thẳng. Đo cảnh 445 khung:
không đệm 116 s, đệm rỗng 159 s, đệm ấm 47 s; không đệm còn hay thiếu khối nhà. Soát ảnh tĩnh bản đồ trước khi render để làm ấm đệm.
