// 生成 src-tauri/icons/icon.ico（内含 32x32 与 16x16 两个 32 位 BGRA 图层）。
//
// 不依赖任何图像库，也不需要对外部图片做转换：直接在内存里画像素并拼装 ICO 容器。
//
// 用法：node scripts/make-icon.js

const fs = require('node:fs');
const path = require('node:path');

const OUT_FILE = path.resolve(__dirname, '..', 'src-tauri', 'icons', 'icon.ico');

/** 圆角方块内部判定：把点归一化到 [0,1] 后用圆角矩形的距离场判断。 */
function insideRoundRect(u, v, radius) {
  const dx = Math.max(radius - u, 0) + Math.max(u - (1 - radius), 0);
  const dy = Math.max(radius - v, 0) + Math.max(v - (1 - radius), 0);
  return dx * dx + dy * dy <= radius * radius;
}

/** 点到线段的距离，用于绘制带粗细的折线（人字形）。 */
function distanceToSegment(px, py, ax, ay, bx, by) {
  const vx = bx - ax;
  const vy = by - ay;
  const wx = px - ax;
  const wy = py - ay;
  const len2 = vx * vx + vy * vy;
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, (wx * vx + wy * vy) / len2));
  const cx = ax + t * vx;
  const cy = ay + t * vy;
  return Math.hypot(px - cx, py - cy);
}

/** 计算某个归一化坐标点的颜色（返回 [r,g,b,a]）。 */
function shade(u, v) {
  if (!insideRoundRect(u, v, 0.22)) return [0, 0, 0, 0];

  // 人字形（"下一站" 的视觉隐喻），用两条线段拼出来。
  const thickness = 0.085;
  const d1 = distanceToSegment(u, v, 0.36, 0.29, 0.63, 0.5);
  const d2 = distanceToSegment(u, v, 0.63, 0.5, 0.36, 0.71);
  if (Math.min(d1, d2) <= thickness) return [0x4c, 0xc2, 0xff, 0xff];

  return [0x0f, 0x11, 0x15, 0xff];
}

/** 渲染一张 size x size 的 RGBA 位图，4x4 超采样做抗锯齿。 */
function render(size) {
  const pixels = Buffer.alloc(size * size * 4);
  const sub = 4;
  const step = 1 / (size * sub);

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let r = 0;
      let g = 0;
      let b = 0;
      let a = 0;

      // 对每个像素做 4x4 子采样并按 alpha 加权平均，边缘因此不会有锯齿。
      for (let sy = 0; sy < sub; sy++) {
        for (let sx = 0; sx < sub; sx++) {
          const u = (x * sub + sx + 0.5) * step;
          const v = (y * sub + sy + 0.5) * step;
          const [pr, pg, pb, pa] = shade(u, v);
          const w = pa / 255;
          r += pr * w;
          g += pg * w;
          b += pb * w;
          a += pa;
        }
      }

      const samples = sub * sub;
      const alpha = a / samples;
      const weight = alpha / 255 || 1;
      const i = (y * size + x) * 4;
      pixels[i + 0] = Math.round(r / samples / weight);
      pixels[i + 1] = Math.round(g / samples / weight);
      pixels[i + 2] = Math.round(b / samples / weight);
      pixels[i + 3] = Math.round(alpha);
    }
  }
  return pixels;
}

/** 把 RGBA 位图封装成 ICO 内部的 DIB（BITMAPINFOHEADER + BGRA 自下而上 + AND 掩码）。 */
function buildDib(size) {
  const rgba = render(size);

  const header = Buffer.alloc(40);
  header.writeUInt32LE(40, 0); // biSize
  header.writeInt32LE(size, 4); // biWidth
  header.writeInt32LE(size * 2, 8); // biHeight，含 XOR 与 AND 两部分
  header.writeUInt16LE(1, 12); // biPlanes
  header.writeUInt16LE(32, 14); // biBitCount
  header.writeUInt32LE(0, 16); // biCompression = BI_RGB
  header.writeUInt32LE(size * size * 4, 20); // biSizeImage

  const xor = Buffer.alloc(size * size * 4);
  for (let y = 0; y < size; y++) {
    const srcRow = size - 1 - y; // DIB 行序自下而上
    for (let x = 0; x < size; x++) {
      const s = (srcRow * size + x) * 4;
      const d = (y * size + x) * 4;
      xor[d + 0] = rgba[s + 2]; // B
      xor[d + 1] = rgba[s + 1]; // G
      xor[d + 2] = rgba[s + 0]; // R
      xor[d + 3] = rgba[s + 3]; // A
    }
  }

  // AND 掩码按 1bpp、每行补齐到 4 字节；透明度已由 A 通道表达，这里全 0。
  const maskRowBytes = Math.ceil(size / 32) * 4;
  const mask = Buffer.alloc(maskRowBytes * size);

  return Buffer.concat([header, xor, mask]);
}

/** 拼装完整的 .ico 文件。 */
function buildIco(sizes) {
  const images = sizes.map((size) => ({ size, data: buildDib(size) }));

  const dir = Buffer.alloc(6);
  dir.writeUInt16LE(0, 0); // reserved
  dir.writeUInt16LE(1, 2); // type = 1 (icon)
  dir.writeUInt16LE(images.length, 4);

  const entries = Buffer.alloc(16 * images.length);
  let offset = dir.length + entries.length;

  images.forEach((image, index) => {
    const base = index * 16;
    entries.writeUInt8(image.size >= 256 ? 0 : image.size, base + 0); // width
    entries.writeUInt8(image.size >= 256 ? 0 : image.size, base + 1); // height
    entries.writeUInt8(0, base + 2); // 调色板数量
    entries.writeUInt8(0, base + 3); // reserved
    entries.writeUInt16LE(1, base + 4); // planes
    entries.writeUInt16LE(32, base + 6); // 位深
    entries.writeUInt32LE(image.data.length, base + 8);
    entries.writeUInt32LE(offset, base + 12);
    offset += image.data.length;
  });

  return Buffer.concat([dir, entries, ...images.map((image) => image.data)]);
}

const ico = buildIco([32, 16]);
fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });
fs.writeFileSync(OUT_FILE, ico);

console.log(`已生成 ${path.relative(process.cwd(), OUT_FILE)}（${ico.length} 字节，含 32x32 与 16x16）`);
