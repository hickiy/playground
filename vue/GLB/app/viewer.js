/**
 * ZYSBF 智能设备房 · GLB 三维查看器
 * -------------------------------------------------------------------------
 *  · 固定机位：眼高 1.6 m、俯角 45°，方位角与距离由求解器自动确定
 *  · 建筑半剖切：仅对建筑外壳（ZYSBF）施加裁剪面，设备（ZYSBF_SB_*）不被裁剪
 *  · 一键回归：复位机位、剖切、标注等全部状态
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

/* ============================ 配置 ============================ */
const qs = new URLSearchParams(location.search);
const num = (k, d) => (qs.has(k) ? parseFloat(qs.get(k)) : d);

const CFG = {
  eye: num('eye', 1.6),          // 眼高（相对室内地坪，m）
  pitch: num('pitch', 45),       // 俯角（度）
  fov: num('fov', 78),           // 垂直视场角
  cutOn: qs.get('cut') !== '0',
  cutRatio: num('cutpos', 0.5),  // 0 = 不切, 0.5 = 正中半切, 1 = 全开
  labels: qs.get('labels') !== '0',
  shadows: qs.get('shadows') !== '0',
  yaw: qs.has('yaw') ? num('yaw', 0) : null,     // 调试：强制方位角
  dist: qs.has('dist') ? num('dist', 8) : null,  // 调试：强制距离
  parts: qs.get('parts'),                         // 调试：指定被裁剪的外壳分件
  debug: qs.get('debug') === '1',
};

/* 缩放限制：镜头只能放大到 MIN_FOV，设备不会被缩得比默认更小；
   机位推进限制在 [MIN_DIST, MAX_DIST]，既能走到设备跟前，也不会飞得太远。 */
const MIN_FOV = 22;      // 最小画幅（≈5 倍放大）
const MAX_FOV = 140;     // 最大画幅（由取景上限进一步收紧）
const MIN_DIST = 1.0;    // 最近机位（m）
const MAX_DIST = 14.0;   // 最远机位（m）

/**
 * 机位数据模型（可直接编辑、可被鼠标实时回写）
 *   eye   眼高（相对室内地坪，m）
 *   az    方位角（°，0° = +Z 方向，顺时针为正）
 *   pitch 光轴俯角（°，正值 = 向下看）
 *   dist  相机到目标点的水平距离（m）
 *   tx/tz 目标点世界坐标 X / Z（m）；目标点高度由俯角推算
 *   fov   画幅垂直视场角（°）
 */
const VIEW = {
  eye: num('eye', 1.6), az: num('yaw', 250), pitch: num('pitch', 45),
  dist: num('dist', 6.5), tx: 0, tz: 0, fov: num('fov', 78),
};
let pinnedView = null;   // 用户「固定」的机位数据
try {
  const saved = localStorage.getItem('zysbf.pinnedView');
  if (saved) pinnedView = JSON.parse(saved);
} catch { pinnedView = null; }

const $ = (s) => document.querySelector(s);
const ui = {
  loader: $('#loader'), ldMsg: $('#ldMsg'), ldBar: $('#ldBar'), ldErr: $('#ldErr'),
  labels: $('#labels'),
  sEquip: $('#sEquip'), sTri: $('#sTri'), sSize: $('#sSize'), sVis: $('#sVis'), sVisChip: $('#sVisChip'),
  btnReset: $('#btnReset'), btnPin: $('#btnPin'), btnOverview: $('#btnOverview'),
  btnCut: $('#btnCut'), btnLabels: $('#btnLabels'), btnShadows: $('#btnShadows'),
  btnCopy: $('#btnCopy'), btnRefit: $('#btnRefit'),
  rCut: $('#rCut'), vCut: $('#vCut'), viewJson: $('#viewJson'),
  nEye: $('#nEye'), nAz: $('#nAz'), nPitch: $('#nPitch'), nDist: $('#nDist'),
  nTx: $('#nTx'), nTz: $('#nTz'), nFov: $('#nFov'),
  hEyePitch: $('#hEyePitch'), hAz: $('#hAz'), hDist: $('#hDist'),
  hCam: $('#hCam'), hTgt: $('#hTgt'), hPlane: $('#hPlane'), hShift: $('#hShift'),
  nEyeTxt: $('#nEyeTxt'), nPitchTxt: $('#nPitchTxt'),
};

/* ============================ 渲染器 / 场景 ============================ */
const canvas = $('#scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.localClippingEnabled = true;   // 局部裁剪：只裁建筑外壳

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xd9e2ef);
scene.fog = new THREE.Fog(0xd9e2ef, 45, 110);

const camera = new THREE.PerspectiveCamera(VIEW.fov, innerWidth / innerHeight, 0.05, 400);

const controls = new OrbitControls(camera, canvas);
controls.enablePan = false;      // 平移由自定义逻辑处理（沿地面平移模型，保持机位数据自洽）
controls.enableZoom = false;      // 缩放由自定义滚轮处理（镜头变焦 / 机位推进）
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.rotateSpeed = 0.55;
// 左键 = 平移模型（自定义），右键 = 旋转，中键禁用
controls.mouseButtons = { LEFT: -1, MIDDLE: -1, RIGHT: THREE.MOUSE.ROTATE };
// 方位角不设限（360° 自由旋转），垂直范围由「相机不穿地坪」动态约束

/**
 * 左键拖拽：默认平移模型（沿地面挪动画面，视角与放大倍数不变），
 * 切成「旋转视角」后左键直接旋转；右键 / Ctrl+左键 始终为旋转。
 */
let leftDragMode = 'pan';
let panState = null;
canvas.addEventListener('pointerdown', (e) => {
  if (e.button !== 0) return;
  const wantRotate = e.ctrlKey || e.metaKey || leftDragMode === 'rotate';
  controls.mouseButtons.LEFT = wantRotate ? THREE.MOUSE.ROTATE : -1;
  if (wantRotate) return;                       // 交给 OrbitControls 旋转
  panState = { x: e.clientX, y: e.clientY, id: e.pointerId };
  try { canvas.setPointerCapture(e.pointerId); } catch { /* 忽略 */ }
}, true);
canvas.addEventListener('pointermove', (e) => {
  if (!panState) return;
  const dx = e.clientX - panState.x, dy = e.clientY - panState.y;
  panState.x = e.clientX; panState.y = e.clientY;
  if (!dx && !dy) return;

  // 每像素对应的世界位移（按当前“画幅”换算，而非虚拟视锥）
  const dist = camera.position.distanceTo(controls.target);
  const tanRender = framing.tanRender || Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);
  const worldPerPixel = (2 * tanRender * dist) / innerHeight;

  const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
  right.y = 0; right.normalize();
  const fwd = new THREE.Vector3();
  camera.getWorldDirection(fwd); fwd.y = 0; fwd.normalize();

  const move = new THREE.Vector3()
    .addScaledVector(right, -dx * worldPerPixel)
    .addScaledVector(fwd, dy * worldPerPixel);

  // 目标点限制在建筑外扩 3 m 内，避免平移出去只剩空地
  if (shellBox) {
    const t = controls.target.clone().add(move);
    t.x = THREE.MathUtils.clamp(t.x, shellBox.min.x - 3, shellBox.max.x + 3);
    t.z = THREE.MathUtils.clamp(t.z, shellBox.min.z - 3, shellBox.max.z + 3);
    move.subVectors(t, controls.target);
  }

  camera.position.add(move);
  controls.target.add(move);
  controls.update();
});
const endPan = (e) => {
  if (!panState) return;
  panState = null;
  try { canvas.releasePointerCapture(e.pointerId); } catch { /* 忽略 */ }
};
canvas.addEventListener('pointerup', endPan);
canvas.addEventListener('pointercancel', endPan);
addEventListener('blur', () => { panState = null; });   // 防止丢失 pointerup 后一直处于平移状态
canvas.addEventListener('contextmenu', (e) => e.preventDefault());   // 右键旋转时屏蔽菜单

/**
 * 滚轮 = 镜头变焦（FOV）：
 *   · 画幅变窄 → 设备等比放大（针孔成像，比例恒定，不会变形）
 *   · 画幅变宽 → 受上限约束，设备不会缩得比默认机位更小
 * Ctrl + 滚轮 = 机位推进（水平距离）：真正走近设备细看。
 */
canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  const factor = e.deltaY > 0 ? 1.12 : 1 / 1.12;
  if (e.ctrlKey) {                       // 机位推进
    VIEW.dist = THREE.MathUtils.clamp(VIEW.dist * factor, MIN_DIST, MAX_DIST);
    applyView();
    readView();
  } else {                               // 镜头变焦
    setRenderedFov(THREE.MathUtils.clamp(VIEW.fov * factor, MIN_FOV, framing.maxFov || MIN_FOV));
  }
  syncViewInputs();
  syncViewHud();
  ui.viewJson.value = viewJson();
  updateVisibilityStat();
}, { passive: false });

/* 灯光：环境光 + 主光（带阴影）+ 补光 */
const pmrem = new THREE.PMREMGenerator(renderer);
const envRT = pmrem.fromScene(new RoomEnvironment(), 0.04);
scene.environment = envRT.texture;
scene.environmentIntensity = 0.75;

scene.add(new THREE.HemisphereLight(0xffffff, 0x9fb0c6, 0.75));

const key = new THREE.DirectionalLight(0xfff6ea, 2.3);
key.position.set(9, 14, 8);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.bias = -0.0012;
key.shadow.normalBias = 0.02;
const sc = key.shadow.camera;
sc.left = -12; sc.right = 12; sc.top = 12; sc.bottom = -12; sc.near = 1; sc.far = 45;
scene.add(key, key.target);

const fill = new THREE.DirectionalLight(0x9dc4ff, 0.5);
fill.position.set(-8, 7, -9);
scene.add(fill);

/* ============================ 模型加载与分类 ============================ */
const shellParts = [];   // 建筑外壳分件
const equipNodes = [];  // 设备节点
let shellBox = null;    // 建筑世界包围盒
let slabBox = new THREE.Box3();   // 室内地面板包围盒
let floorY = 0;         // 室内地坪高度（世界坐标）
let groundPlane = null;
let gridHelper = null;
let currentCenter = new THREE.Vector3();
let lastTanRender = 0;          // 当前画幅半高切线（离轴取景结果）
const cutPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
const CLIP_PLANES = [cutPlane];      // 所有被剖切材质共用同一个数组（避免每次比较引用导致着色器重编译）

const loader = new GLTFLoader();
loader.load('./zysbf.glb',
  (gltf) => { onLoaded(gltf); },
  (ev) => {
    if (ev.lengthComputable) {
      const p = ev.loaded / ev.total;
      ui.ldBar.style.width = (p * 100).toFixed(1) + '%';
      ui.ldMsg.textContent = `正在加载模型 zysbf.glb … ${(p * 100).toFixed(0)}%`;
    }
  },
  (err) => {
    ui.ldMsg.textContent = '模型加载失败';
    ui.ldErr.style.display = 'block';
    ui.ldErr.innerHTML = location.protocol === 'file:'
      ? '浏览器禁止在 <b>file://</b> 协议下读取本地模型。<br/>请在项目目录执行 <b>npm start</b>（或 <b>python -m http.server 8899</b>）后访问 <b>http://127.0.0.1:8899/</b>。'
      : ('<b>' + (err?.message || err) + '</b><br/>请确认 zysbf.glb 与 index.html 位于同一目录。');
  });

/* ============================ 加载完成 ============================ */
function onLoaded(gltf) {
  const modelRoot = gltf.scene;
  scene.add(modelRoot);

  let tris = 0;
  modelRoot.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
      const g = o.geometry;
      tris += (g.index ? g.index.count : g.attributes.position.count) / 3;
    }
  });
  modelRoot.updateMatrixWorld(true);

  /* --- 分组：外壳 vs 设备 --- */
  modelRoot.children.forEach((child) => {
    const name = child.name || '';
    const meshes = [];
    child.traverse((o) => { if (o.isMesh) meshes.push(o); });
    if (!meshes.length) return;

    if (/^ZYSBF_SB_/i.test(name)) {
      const box = new THREE.Box3();
      meshes.forEach((m) => box.union(new THREE.Box3().setFromObject(m)));
      equipNodes.push({
        name: name.toUpperCase(), meshes, box,
        center: box.getCenter(new THREE.Vector3()),
      });
    } else {
      meshes.forEach((m) => {
        shellParts.push({
          mesh: m, mat: m.material.clone(), index: shellParts.length,
          box: new THREE.Box3().setFromObject(m), ground: false,
        });
      });
    }
  });

  /* --- 材质独立化 --- */
  shellParts.forEach((p) => { p.mesh.material = p.mat; p.mesh.material.needsUpdate = true; });

  /* --- 判定地坪与地面件 --- */
  shellBox = new THREE.Box3();
  shellParts.forEach((p) => shellBox.union(p.box));
  const bs = shellBox.getSize(new THREE.Vector3());
  const footprint = Math.max(1e-6, bs.x * bs.z);

  const areaOf = (p) => { const s = p.box.getSize(new THREE.Vector3()); return (s.x * s.z) / footprint; };
  // 室内地坪 = 覆盖大部分建筑面积的“薄板”顶面
  const slabs = shellParts.filter((p) => {
    const s = p.box.getSize(new THREE.Vector3());
    return s.y < 0.6 && areaOf(p) > 0.12;
  });
  floorY = slabs.length ? Math.max(...slabs.map((p) => p.box.max.y)) : shellBox.min.y;

  shellParts.forEach((p) => {
    const s = p.box.getSize(new THREE.Vector3());
    p.ground = areaOf(p) > 0.12 && p.box.max.y <= floorY + 0.35 && s.y < 1.0;
  });

  // 地面板范围（用于约束机位必须站在室内地面上）
  slabBox.makeEmpty();
  shellParts.filter((p) => p.ground).forEach((p) => slabBox.union(p.box));
  if (slabBox.isEmpty()) slabBox.copy(shellBox);

  /* --- 场地地面 / 网格（略低于室内地坪，形成台基落差） --- */
  groundPlane = new THREE.Mesh(
    new THREE.PlaneGeometry(200, 200),
    new THREE.MeshStandardMaterial({ color: 0xc3cede, roughness: 0.95, metalness: 0 })
  );
  groundPlane.rotation.x = -Math.PI / 2;
  groundPlane.position.y = floorY - 0.38;
  groundPlane.receiveShadow = true;
  scene.add(groundPlane);

  gridHelper = new THREE.GridHelper(60, 120, 0x7f9ac4, 0xa7bad6);
  gridHelper.position.y = floorY - 0.372;
  gridHelper.material.transparent = true;
  gridHelper.material.opacity = 0.55;
  scene.add(gridHelper);

  key.target.position.copy(shellBox.getCenter(new THREE.Vector3()));
  key.position.copy(key.target.position).add(new THREE.Vector3(9, 14, 8));

  /* --- 统计 --- */
  ui.sEquip.textContent = equipNodes.length;
  ui.sTri.textContent = (tris / 1000).toFixed(1) + 'k';
  ui.sSize.textContent = `${bs.x.toFixed(1)}×${bs.y.toFixed(1)}×${bs.z.toFixed(1)} m`;

  if (CFG.debug) {
    const fmt = (b) => b.min.toArray().map((v) => +v.toFixed(2)).join(',') + ' | ' + b.max.toArray().map((v) => +v.toFixed(2)).join(',');
    console.log('[DBG] floorY=' + floorY.toFixed(3) +
      ' shell=[' + fmt(shellBox) + ']');
    console.log('[DBG] SHELL_PARTS ' + JSON.stringify(shellParts.map((p) => ({
      i: p.index, g: p.ground ? 1 : 0, min: p.box.min.toArray().map((v) => +v.toFixed(2)), max: p.box.max.toArray().map((v) => +v.toFixed(2)),
    }))));
    console.log('[DBG] EQUIP ' + JSON.stringify(equipNodes.map((e) => ({
      n: e.name, min: e.box.min.toArray().map((v) => +v.toFixed(2)), max: e.box.max.toArray().map((v) => +v.toFixed(2)),
    }))));
  }

  /* --- 固定机位 + 剖切 --- */
  buildLabels();
  reposition();
  if (CFG.debug) console.log('[DBG] VIEW0 ' + JSON.stringify(VIEW) + ' framing=' + JSON.stringify(framing));

  ui.loader.style.opacity = '0';
  setTimeout(() => { ui.loader.style.display = 'none'; }, 520);
  syncUI();
  animate();
}

/* ============================ 固定机位求解 ============================ */
/**
 * 机位约束：眼高固定、俯角固定（默认 45°）。在此前提下搜索方位角与距离，
 * 使尽可能多的设备完整落入取景画幅。
 * 取景使用「离轴投影」：画幅可在垂直方向整体平移，在不改变相机轴线角度
 * （仍是 45° 俯角）的前提下让设备群充满画面。
 */

/** 设备内容在相机切平面上的角度（切线）范围 */
function contentTangentRange(pos, fwd, up) {
  let tMin = Infinity, tMax = -Infinity;
  const v = new THREE.Vector3();
  equipNodes.forEach((e) => {
    const b = e.box;
    // 高于眼位的壁挂设备在 45° 俯角下本就无法完整呈现，只取其落地角点
    const ys = b.max.y > pos.y ? [b.min.y] : [b.min.y, b.max.y];
    for (const x of [b.min.x, b.max.x])
      for (const y of ys)
        for (const z of [b.min.z, b.max.z]) {
          v.set(x - pos.x, y - pos.y, z - pos.z);
          const zc = v.dot(fwd);
          if (zc <= 0.05) continue;
          const t = v.dot(up) / zc;
          if (t < tMin) tMin = t;
          if (t > tMax) tMax = t;
        }
  });
  return { tMin, tMax };
}

function solveFixedCamera() {
  const center = new THREE.Vector3();
  const all = new THREE.Box3();
  equipNodes.forEach((e) => all.union(e.box));
  if (all.isEmpty()) all.copy(shellBox);
  all.getCenter(center);

  const tanF = Math.tan(THREE.MathUtils.degToRad(VIEW.fov) / 2);  // 画幅半高切线
  const aspect = innerWidth / innerHeight;
  const pitch = THREE.MathUtils.degToRad(VIEW.pitch);
  const cp = Math.cos(pitch), sp = Math.sin(pitch);
  const eyeY = floorY + VIEW.eye;

  const evaluate = (yaw, dist) => {
    const dx = Math.sin(yaw), dz = Math.cos(yaw);
    const px = center.x + dx * dist, py = eyeY, pz = center.z + dz * dist;
    // 基向量：fwd / right / up
    const fx = -dx * cp, fy = -sp, fz = -dz * cp;
    const rx = dz, rz = -dx;                    // right = fwd × worldUp
    const ux = -dx * sp, uy = cp, uz = -dz * sp; // up = right × fwd
    const pos = new THREE.Vector3(px, py, pz);
    const fwdV = new THREE.Vector3(fx, fy, fz);
    const upV = new THREE.Vector3(ux, uy, uz);

    // 取景窗口：把设备内容包进画幅并居中
    const { tMin, tMax } = contentTangentRange(pos, fwdV, upV);
    if (!Number.isFinite(tMin)) return { full: 0, partial: 0, fill: 0, maxExt: 0, offY: 1, offX: 1, near: 0, outside: 0, score: -1e9 };
    const span = tMax - tMin;
    const tanRender = Math.max(tanF, span * 1.35);
    const B = (tMin + tMax) / 2 - tanRender / 2;      // 画幅下边界（切线）
    const tanH = aspect * tanRender;                   // 画幅水平半切线

    let full = 0, partial = 0, maxExt = 0;
    let gMinS = Infinity, gMaxS = -Infinity;
    equipNodes.forEach((e) => {
      const b = e.box;
      let vis = 0, tot = 0;
      let eMinS = Infinity, eMaxS = -Infinity, eMinT = Infinity, eMaxT = -Infinity;
      for (const x of [b.min.x, b.max.x])
        for (const y of [b.min.y, b.max.y])
          for (const z of [b.min.z, b.max.z]) {
            const vx = x - px, vy = y - py, vz = z - pz;
            const zc = vx * fx + vy * fy + vz * fz;
            tot++;
            if (zc <= 0.05) continue;
            const s = (vx * rx + vz * rz) / zc;
            const t = (vx * ux + vy * uy + vz * uz) / zc;
            if (t >= B && t <= B + tanRender && Math.abs(s) <= tanH) vis++;
            eMinS = Math.min(eMinS, s); eMaxS = Math.max(eMaxS, s);
            eMinT = Math.min(eMinT, t); eMaxT = Math.max(eMaxT, t);
            gMinS = Math.min(gMinS, s); gMaxS = Math.max(gMaxS, s);
          }
      const frac = tot ? vis / tot : 0;
      if (frac >= 0.999) full++;
      else if (frac > 0) partial++;
      if (vis) maxExt = Math.max(maxExt, (eMaxS - eMinS) / tanH, (eMaxT - eMinT) / tanRender);
    });

    // 画面占用率
    const fillY = Math.min(1, span / tanRender);
    const fillX = Number.isFinite(gMinS) ? Math.min(1, (gMaxS - gMinS) / (2 * tanH)) : 0;
    const fill = fillY * 0.6 + fillX * 0.4;
    const offX = Number.isFinite(gMinS) ? Math.abs((gMinS + gMaxS) / 2) / tanH : 1;
    // 设备占满画面（贴脸）时惩罚
    const loom = Math.max(0, maxExt - 0.9) * 260;
    // 机位尽量留在建筑平面内，避免画面被室外空地占据
    const outside = (shellBox && (px < shellBox.min.x + 0.2 || px > shellBox.max.x - 0.2 ||
      pz < shellBox.min.z + 0.2 || pz > shellBox.max.z - 0.2)) ? 800 : 0;
    // 关闭剖切时必须站到室内，否则会被外墙挡住
    const outsideRoom = (!CFG.cutOn && slabBox && !slabBox.isEmpty() &&
      (px < slabBox.min.x + 0.25 || px > slabBox.max.x - 0.25 ||
       pz < slabBox.min.z + 0.25 || pz > slabBox.max.z - 0.25)) ? 900 : 0;
    // 与设备保持安全距离，避免单个设备遮挡整个画面
    let near = 0;
    equipNodes.forEach((e) => {
      const b = e.box;
      const bdx = Math.max(0, Math.max(b.min.x - px, px - b.max.x));
      const bdy = Math.max(0, Math.max(b.min.y - py, py - b.max.y));
      const bdz = Math.max(0, Math.max(b.min.z - pz, pz - b.max.z));
      const d = Math.sqrt(bdx * bdx + bdy * bdy + bdz * bdz);
      if (d < 2.6) near += (2.6 - d) * 120;
    });
    const score = full * 1000 + partial * 150 + fill * 250
      - loom - near * 0.6 - outside - outsideRoom - offX * 60;
    return { full, partial, fill, maxExt, offX, near, outside, outsideRoom, score };
  };

  let best = null;
  const perYaw = [];
  // URL 调试参数中的方位角为角度制，内部统一使用弧度
  const yawOverride = CFG.yaw !== null ? CFG.yaw * Math.PI / 180 : null;
  if (yawOverride !== null && CFG.dist !== null) {
    best = { yaw: yawOverride, dist: CFG.dist, ...evaluate(yawOverride, CFG.dist) };
  } else {
    const yaws = yawOverride !== null ? [yawOverride]
      : Array.from({ length: 36 }, (_, i) => (i / 36) * Math.PI * 2);   // 10° 步进
    for (const yaw of yaws) {
      let by = null;
      for (let d = MIN_DIST; d <= MAX_DIST; d += 0.15) {
        const r = evaluate(yaw, d);
        if (!by || r.score > by.score) by = { yaw, dist: d, ...r };
      }
      perYaw.push({ deg: Math.round(THREE.MathUtils.radToDeg(yaw)), dist: +by.dist.toFixed(2), vis: by.full + by.partial, full: by.full, fill: +by.fill.toFixed(2), score: Math.round(by.score) });
      if (!best || by.score > best.score) best = by;
    }
    // 细化
    for (let d = Math.max(MIN_DIST, best.dist - 1.0); d <= Math.min(MAX_DIST, best.dist + 1.0); d += 0.05) {
      const r = evaluate(best.yaw, d);
      if (r.score > best.score) best = { yaw: best.yaw, dist: d, ...r };
    }
    if (CFG.debug) console.log('[DBG] perYaw ' + JSON.stringify(perYaw));
  }

  // 机位可位于建筑剖切开口一侧（室内或室外），只要不贴脸设备即可
  const yaw = best.yaw, dist = best.dist;
  currentCenter.copy(center);

  return { yaw, dist, score: best.score, center, eyeY, full: best.full };
}

/* ============================ 机位数据 ⇄ 相机 ============================ */
/** 目标点高度：由光轴俯角推算（俯角 45° 时目标点在地面以下） */
function targetY() {
  return (floorY + VIEW.eye) - VIEW.dist * Math.tan(THREE.MathUtils.degToRad(VIEW.pitch));
}

/** 由机位数据驱动相机 */
function applyView() {
  const az = THREE.MathUtils.degToRad(VIEW.az);
  const camY = floorY + VIEW.eye;
  camera.position.set(
    VIEW.tx + VIEW.dist * Math.sin(az),
    camY,
    VIEW.tz + VIEW.dist * Math.cos(az)
  );
  controls.target.set(VIEW.tx, targetY(), VIEW.tz);
  camera.lookAt(controls.target);
  camera.fov = VIEW.fov;
  camera.updateProjectionMatrix();
  controls.update();
  updatePolarLimit();
  applyFraming();
}

/** 由相机状态反算机位数据（鼠标旋转/缩放后实时回写） */
function readView() {
  const P = camera.position, Q = controls.target;
  const dx = P.x - Q.x, dz = P.z - Q.z;
  const R = Math.hypot(dx, dz);
  VIEW.dist = R;
  VIEW.az = (THREE.MathUtils.radToDeg(Math.atan2(dx, dz)) + 360) % 360;
  VIEW.pitch = THREE.MathUtils.clamp(
    THREE.MathUtils.radToDeg(Math.atan2(P.y - Q.y, Math.max(R, 1e-3))), -89, 89);
  VIEW.eye = P.y - floorY;
  VIEW.tx = Q.x; VIEW.tz = Q.z;
}

/** 垂直旋转范围：限制相机不穿到地面以下 */
function updatePolarLimit() {
  const Q = controls.target, P = camera.position;
  const r = P.distanceTo(Q) || 1;
  const c = THREE.MathUtils.clamp((floorY + 0.25 - Q.y) / r, -1, 1);
  controls.maxPolarAngle = Math.max(controls.minPolarAngle + 0.05, Math.acos(c));
}

/**
 * 离轴取景（移轴镜头）：
 *   ① computeFraming() —— 按当前机位下设备内容所占的角度范围，算出画幅的
 *      垂直位置与松紧，让设备群充满画面；结果被「冻结」在 framing 中。
 *   ② applyFraming()  —— 把冻结的取景参数套用到相机上。
 * 冻结很关键：若每次鼠标操作都重新取景，画幅会跟着内容不停重排，
 * 缩放时看起来就像物体被拉伸变形。冻结后缩放只改变机位，画面比例恒定。
 */
let framing = { tanRender: 0, B: 0, tanV: 1, maxFov: MAX_FOV };

function computeFraming() {
  camera.updateMatrixWorld();
  const m = camera.matrixWorld;
  const up = new THREE.Vector3(m.elements[4], m.elements[5], m.elements[6]).normalize();
  const fwd = new THREE.Vector3(m.elements[8], m.elements[9], m.elements[10]).normalize().negate();
  const { tMin, tMax } = contentTangentRange(camera.position, fwd, up);
  if (!Number.isFinite(tMin)) return;

  const tanF = Math.tan(THREE.MathUtils.degToRad(VIEW.fov) / 2);
  const span = tMax - tMin;
  const tanRender = Math.max(tanF, span * 1.35);          // 至少能装下全部内容
  const B = (tMin + tMax) / 2 - tanRender / 2;            // 画幅下边界（切线）
  const tanV = Math.max(Math.abs(B), Math.abs(B + tanRender)) * 1.02;  // 虚拟视锥半高

  framing = { tanRender, B, tanV, maxFov: Math.min(MAX_FOV, THREE.MathUtils.radToDeg(2 * Math.atan(tanRender))) };
  VIEW.fov = THREE.MathUtils.radToDeg(2 * Math.atan(tanRender));  // 面板显示实际画幅
  lastTanRender = tanRender;
}

/** 重新取景：按当前机位重新对焦内容（冻结值刷新） */
function refitFraming() {
  computeFraming();
  applyFraming();
  syncViewInputs();
  syncViewHud();
}

function applyFraming() {
  const { tanRender, B, tanV } = framing;
  if (!tanRender) { camera.clearViewOffset(); camera.updateProjectionMatrix(); return; }

  const w = innerWidth, h = innerHeight;
  const aspect = w / h;
  camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(tanV));
  camera.aspect = aspect * (tanRender / tanV);
  const fullHeight = (2 * tanV * h) / tanRender;
  const offsetY = (h * (tanV - B - tanRender)) / tanRender;
  camera.setViewOffset(w, fullHeight, 0, offsetY, w, h);
  camera.updateProjectionMatrix();
}

/** 画幅 FOV 调整 = 镜头变焦：围绕画幅中心缩放，比例恒定、无形变。
 *  上限为当前取景的自动适配值 → 设备不会被缩得比默认机位更小。 */
function setRenderedFov(deg) {
  const lo = MIN_FOV, hi = Math.max(MIN_FOV, framing.maxFov || MAX_FOV);
  const fov = THREE.MathUtils.clamp(deg, lo, hi);
  const tanNew = Math.tan(THREE.MathUtils.degToRad(fov) / 2);
  if (framing.tanRender) {
    const center = framing.B + framing.tanRender / 2;   // 保持画幅中心不动
    framing.tanRender = tanNew;
    framing.B = center - tanNew / 2;
    framing.tanV = Math.max(Math.abs(framing.B), Math.abs(framing.B + tanNew)) * 1.02;
    lastTanRender = tanNew;
  }
  VIEW.fov = fov;
  applyFraming();
}

function applyCut() {
  const dir = new THREE.Vector3(Math.sin(THREE.MathUtils.degToRad(VIEW.az)), 0, Math.cos(THREE.MathUtils.degToRad(VIEW.az)));
  // 剖切面以「建筑中心」为基准，垂直于视线方向 —— 50% 即正中切开
  const anchor = shellBox ? shellBox.getCenter(new THREE.Vector3()) : currentCenter.clone();
  const span = shellBox ? shellBox.getSize(new THREE.Vector3()).length() : 20;
  // 0% = 完整建筑；50% = 正中半切；100% = 外壳完全移除
  const offset = (0.5 - CFG.cutRatio) * span * 0.55;
  const point = anchor.clone().addScaledVector(dir, offset);

  // 法线背向相机 → 保留远侧一半，切掉近侧（相机侧）墙体
  cutPlane.normal.copy(dir).negate();
  cutPlane.constant = -cutPlane.normal.dot(point);

  const forceParts = CFG.parts ? CFG.parts.split(',').map((v) => parseInt(v, 10)) : null;
  shellParts.forEach((p) => {
    const shouldClip = CFG.cutOn && !p.ground && (forceParts ? forceParts.includes(p.index) : true);
    // 只在“是否剖切”状态变化时改材质，避免每帧重建数组触发着色器重编译
    if (p.clipped !== shouldClip) {
      p.clipped = shouldClip;
      p.mat.clippingPlanes = shouldClip ? CLIP_PLANES : null;
      p.mat.clipShadows = true;
      p.mat.side = shouldClip ? THREE.DoubleSide : THREE.FrontSide;
      p.mat.needsUpdate = true;
    }
  });

  ui.hPlane.textContent = CFG.cutOn
    ? (forceParts ? '指定分件' : `${CFG.cutRatio < 0.5 ? '半切' : CFG.cutRatio > 0.5 ? '深切' : '正中'} ${(CFG.cutRatio * 100).toFixed(0)}% · ⟂镜头`)
    : '关闭';
  ui.btnCut.classList.toggle('on', CFG.cutOn);
}

/* ============================ 设备标注 ============================ */
const labelEls = [];
function buildLabels() {
  ui.labels.innerHTML = '';
  labelEls.length = 0;
  equipNodes.forEach((e) => {
    const d = document.createElement('div');
    d.className = 'lbl';
    d.textContent = e.name.replace('ZYSBF_', '');
    ui.labels.appendChild(d);
    labelEls.push({ el: d, node: e });
  });
}

function updateLabels() {
  if (!CFG.labels) { labelEls.forEach((l) => (l.el.style.display = 'none')); return; }
  const v = new THREE.Vector3();
  const w = innerWidth, h = innerHeight;
  labelEls.forEach((l) => {
    v.copy(l.node.center).project(camera);
    if (v.z > 1) { l.el.style.display = 'none'; return; }
    const x = (v.x * 0.5 + 0.5) * w;
    const y = (-v.y * 0.5 + 0.5) * h;
    if (x < -60 || x > w + 60 || y < -30 || y > h + 30) { l.el.style.display = 'none'; return; }
    l.el.style.display = 'block';
    l.el.style.left = x.toFixed(1) + 'px';
    l.el.style.top = y.toFixed(1) + 'px';
  });
}

/* ============================ 可视设备统计 ============================ */
function updateVisibilityStat() {
  const v = new THREE.Vector3();
  let visible = 0;
  const hidden = [];
  equipNodes.forEach((e) => {
    const b = e.box;
    let any = false;
    for (const x of [b.min.x, b.max.x])
      for (const y of [b.min.y, b.max.y])
        for (const z of [b.min.z, b.max.z]) {
          v.set(x, y, z).project(camera);
          if (v.z <= 1 && Math.abs(v.x) <= 1 && Math.abs(v.y) <= 1) { any = true; break; }
        }
    if (any) visible++; else hidden.push(e.name);
  });
  ui.sVis.textContent = `${visible}/${equipNodes.length}`;
  ui.sVisChip.classList.toggle('ok', visible === equipNodes.length);
  if (CFG.debug) console.log('[DBG] invisible=' + JSON.stringify(hidden));
}

/* ============================ 背景 ============================ */
function makeBackdrop() {
  const c = document.createElement('canvas');
  c.width = 8; c.height = 256;
  const g = c.getContext('2d');
  const grad = g.createLinearGradient(0, 0, 0, 256);
  grad.addColorStop(0, '#101a33');
  grad.addColorStop(0.55, '#0b1020');
  grad.addColorStop(1, '#070a14');
  g.fillStyle = grad; g.fillRect(0, 0, 8, 256);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.mapping = THREE.EquirectangularReflectionMapping;
  return tex;
}

/* ============================ UI 绑定 ============================ */
function syncUI() {
  ui.vCut.textContent = (CFG.cutRatio * 100).toFixed(0) + '%';
  ui.nEyeTxt.textContent = VIEW.eye.toFixed(2) + ' m';
  ui.nPitchTxt.textContent = VIEW.pitch.toFixed(0) + '°';
  setRangeFill(ui.rCut);
  ui.btnLabels.classList.toggle('on', CFG.labels);
  ui.btnShadows.classList.toggle('on', CFG.shadows);
  ui.btnCut.classList.toggle('on', CFG.cutOn);
  ui.btnPin.classList.toggle('on', !!pinnedView);
  ui.btnPin.firstChild.textContent = pinnedView ? '取消固定机位' : '固定此机位';
}

function setRangeFill(el) {
  const p = ((el.value - el.min) / (el.max - el.min)) * 100;
  el.style.setProperty('--p', p + '%');
}

/** 机位数据 → 输入框（正在编辑的输入框不覆盖） */
function syncViewInputs() {
  const set = (el, v, dec) => { if (el && document.activeElement !== el) el.value = v.toFixed(dec); };
  set(ui.nEye, VIEW.eye, 2);
  set(ui.nAz, VIEW.az, 1);
  set(ui.nPitch, VIEW.pitch, 1);
  set(ui.nDist, VIEW.dist, 2);
  set(ui.nTx, VIEW.tx, 2);
  set(ui.nTz, VIEW.tz, 2);
  set(ui.nFov, VIEW.fov, 0);
}

/** 机位数据 → HUD 实时读数 */
function syncViewHud() {
  const P = camera.position, Q = controls.target;
  const slant = P.distanceTo(Q);
  ui.hEyePitch.textContent = `${VIEW.eye.toFixed(2)} m / ${VIEW.pitch.toFixed(1)}°`;
  ui.hAz.textContent = VIEW.az.toFixed(1) + '°';
  ui.hDist.textContent = `${VIEW.dist.toFixed(2)} m / ${slant.toFixed(2)} m`;
  ui.hCam.textContent = `${P.x.toFixed(2)}, ${P.y.toFixed(2)}, ${P.z.toFixed(2)}`;
  ui.hTgt.textContent = `${Q.x.toFixed(2)}, ${Q.y.toFixed(2)}, ${Q.z.toFixed(2)}`;
  const rendered = lastTanRender > 0 ? THREE.MathUtils.radToDeg(2 * Math.atan(lastTanRender)) : VIEW.fov;
  ui.hShift.textContent = `${rendered.toFixed(0)}° 画幅 / 轴 ${VIEW.pitch.toFixed(0)}°`;
}

/** 当前机位数据（可复制 / 可固定） */
function viewJson() {
  const P = camera.position, Q = controls.target;
  return JSON.stringify({
    eye: +VIEW.eye.toFixed(2),
    azimuth: +VIEW.az.toFixed(2),
    pitch: +VIEW.pitch.toFixed(2),
    distance: +VIEW.dist.toFixed(2),
    target: [+Q.x.toFixed(2), +Q.y.toFixed(2), +Q.z.toFixed(2)],
    camera: [+P.x.toFixed(2), +P.y.toFixed(2), +P.z.toFixed(2)],
    fov: +VIEW.fov.toFixed(1),
    cut: +(CFG.cutRatio * 100).toFixed(0),
  });
}

function resetView() {
  CFG.cutOn = true; CFG.cutRatio = 0.5; CFG.labels = true; CFG.shadows = true;
  ui.rCut.value = 50;
  renderer.shadowMap.enabled = CFG.shadows;
  key.castShadow = CFG.shadows;
  scene.traverse((o) => {
    if (o.isMesh) { o.castShadow = CFG.shadows && o !== groundPlane; o.receiveShadow = CFG.shadows; }
  });
  if (groundPlane) groundPlane.receiveShadow = CFG.shadows;

  if (pinnedView) {                 // 回到用户固定的机位
    Object.assign(VIEW, pinnedView);
    VIEW.dist = THREE.MathUtils.clamp(VIEW.dist, MIN_DIST, MAX_DIST);
    VIEW.fov = THREE.MathUtils.clamp(VIEW.fov, MIN_FOV, MAX_FOV);
    applyView();
  } else {                          // 回到求解出的标准机位
    VIEW.eye = 1.6; VIEW.pitch = 45; VIEW.fov = 78;
    reposition();
  }
  applyCut();
  syncUI();
  updateVisibilityStat();
}

/** 设备总览：抬高机位、放浅俯角，把高位壁挂设备也纳入画面 */
function overviewView() {
  VIEW.eye = 4.4; VIEW.pitch = 33; VIEW.fov = 38;
  reposition();
}

/** 依据当前眼高/俯角/视场角重新求解机位（方位角与距离），并应用 */
function reposition() {
  if (pinnedView) {                       // 已固定机位：直接恢复，不重新求解
    Object.assign(VIEW, pinnedView);
    VIEW.dist = THREE.MathUtils.clamp(VIEW.dist, MIN_DIST, MAX_DIST);
    VIEW.fov = THREE.MathUtils.clamp(VIEW.fov, MIN_FOV, MAX_FOV);
    applyView();
  } else {
    const best = solveFixedCamera();
    VIEW.az = THREE.MathUtils.radToDeg(best.yaw);
    VIEW.dist = THREE.MathUtils.clamp(best.dist, MIN_DIST, MAX_DIST);
    VIEW.tx = best.center.x;
    VIEW.tz = best.center.z;
    applyView();
  }
  computeFraming();     // 冻结本机位下的取景（缩放/旋转时画面不再重排）
  applyFraming();
  applyCut();
  syncUI();
  syncViewInputs();
  syncViewHud();
  updateVisibilityStat();
}

ui.btnReset.addEventListener('click', () => { resetView(); });
ui.btnOverview.addEventListener('click', () => { overviewView(); });
ui.btnCut.addEventListener('click', () => { CFG.cutOn = !CFG.cutOn; reposition(); });
ui.btnLabels.addEventListener('click', () => { CFG.labels = !CFG.labels; syncUI(); });
ui.btnShadows.addEventListener('click', () => {
  CFG.shadows = !CFG.shadows;
  renderer.shadowMap.enabled = CFG.shadows; key.castShadow = CFG.shadows;
  scene.traverse((o) => { if (o.isMesh) { o.castShadow = CFG.shadows && o !== groundPlane; o.receiveShadow = CFG.shadows; } });
  if (gridHelper) gridHelper.visible = CFG.shadows;
  syncUI();
});

/* 固定 / 取消固定当前机位 */
ui.btnPin.addEventListener('click', () => {
  if (pinnedView) {
    pinnedView = null;
    localStorage.removeItem('zysbf.pinnedView');
  } else {
    pinnedView = { eye: VIEW.eye, az: VIEW.az, pitch: VIEW.pitch, dist: VIEW.dist, tx: VIEW.tx, tz: VIEW.tz, fov: VIEW.fov };
    localStorage.setItem('zysbf.pinnedView', JSON.stringify(pinnedView));
  }
  syncUI();
});

/* 左键操作模式切换：平移模型 / 旋转视角 */
document.querySelectorAll('#segDrag button').forEach((btn) => {
  btn.addEventListener('click', () => {
    leftDragMode = btn.dataset.mode === 'rotate' ? 'rotate' : 'pan';
    document.querySelectorAll('#segDrag button').forEach((b) => b.classList.toggle('on', b === btn));
  });
});

/* 重新取景：按当前机位重新对焦设备内容（冻结值刷新） */
ui.btnRefit.addEventListener('click', () => { refitFraming(); syncUI(); });

/* 复制当前机位数据 */
ui.btnCopy.addEventListener('click', async () => {
  const txt = viewJson();
  ui.viewJson.value = txt;
  ui.viewJson.focus();
  ui.viewJson.select();
  let ok = false;
  try { await navigator.clipboard.writeText(txt); ok = true; } catch { /* 剪贴板不可用 */ }
  ui.btnCopy.textContent = ok ? '已复制' : '已选中';
  setTimeout(() => { ui.btnCopy.textContent = '复制'; }, 1600);
});

ui.rCut.addEventListener('input', (e) => { CFG.cutRatio = e.target.value / 100; applyCut(); syncUI(); });

/* 机位数据输入：眼高 / 方位角 / 俯角 / 水平距离 / 目标 X,Z / 画幅 FOV */
const bindNum = (el, key, transform = (v) => v, apply) => {
  const handler = () => {
    const v = parseFloat(el.value);
    if (!isFinite(v)) return;
    VIEW[key] = transform(v);
    if (apply) apply();
    else {
      applyView();
      applyCut();
    }
    syncUI();
    syncViewInputs();
    syncViewHud();
    ui.viewJson.value = viewJson();
    updateVisibilityStat();
  };
  el.addEventListener('input', handler);
  el.addEventListener('change', handler);
};
bindNum(ui.nEye, 'eye');
bindNum(ui.nAz, 'az', (v) => (v + 360) % 360);
bindNum(ui.nPitch, 'pitch');
bindNum(ui.nDist, 'dist', (v) => THREE.MathUtils.clamp(v, MIN_DIST, MAX_DIST));
bindNum(ui.nTx, 'tx');
bindNum(ui.nTz, 'tz');
// 画幅 FOV = 镜头变焦（画面比例恒定，不产生形变；只能放大，不能把设备缩得更小）
bindNum(ui.nFov, 'fov', (v) => THREE.MathUtils.clamp(v, MIN_FOV, MAX_FOV), () => setRenderedFov(VIEW.fov));

addEventListener('keyup', (e) => {
  if (e.key === 'Control' || e.key === 'Meta') controls.mouseButtons.LEFT = -1;
});

addEventListener('keydown', (e) => {
  if (e.target && /^(INPUT|TEXTAREA)$/.test(e.target.tagName)) return;
  if (e.key === 'r' || e.key === 'R') resetView();
  if (e.key === 'o' || e.key === 'O') overviewView();
  if (e.key === 'c' || e.key === 'C') { CFG.cutOn = !CFG.cutOn; reposition(); }
  if (e.key === 'l' || e.key === 'L') { CFG.labels = !CFG.labels; syncUI(); }
  if (e.key === 'f' || e.key === 'F') ui.btnPin.click();
});

addEventListener('resize', () => {
  renderer.setSize(innerWidth, innerHeight);
  applyFraming();
});

/* 鼠标旋转 / 缩放：实时回写机位数据（取景保持冻结，避免画面重排变形） */
let changeLog = 0;
controls.addEventListener('change', () => {
  if (CFG.debug && changeLog++ < 6) console.log('[DBG] change#' + changeLog + ' P=' + JSON.stringify(camera.position.toArray().map((v) => +v.toFixed(3))) + ' Q=' + JSON.stringify(controls.target.toArray().map((v) => +v.toFixed(3))));
  readView();
  applyCut();        // 剖切面跟随视角：始终朝向相机，旋转时建筑始终是剖开的
  syncViewInputs();
  syncViewHud();
  ui.viewJson.value = viewJson();
});
controls.addEventListener('end', () => { updateVisibilityStat(); });

/* ============================ 主循环 ============================ */
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
  updateLabels();
  syncViewHud();
}
