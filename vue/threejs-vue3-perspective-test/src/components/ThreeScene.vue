<template>
  <div ref="sceneContainer" class="scene-container"></div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import TWEEN from '@tweenjs/tween.js'

const EYE_HEIGHT = 1.65 // 人眼高度（米）
const DEFAULT_AZIMUTH = 45 // 默认机位：东南 45°
const DEFAULT_FOV = 45
const MIN_DISTANCE = 10
const MAX_DISTANCE = 80
const MIN_HEIGHT = 0.5
const MAX_HEIGHT = 40
const MIN_FOV = 20
const MAX_FOV = 80
const MAX_PAN = 30 // 水平平移范围（米）

const emit = defineEmits(['camera-change'])
const sceneContainer = ref(null)
// 半剖裁切面：法线指向楼体内部，切掉朝向相机的一半
const sectionPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0)
const sectionPlanes = [sectionPlane]
const cameraTarget = new THREE.Vector3()
const cameraParams = {
  height: EYE_HEIGHT,
  azimuth: DEFAULT_AZIMUTH,
  distance: 30,
  fov: DEFAULT_FOV,
  section: 50, // 剖开比例（%）：50 穿过楼体中心
  panX: 0, // 水平平移：相对楼体中心的 X 偏移
  panZ: 0 // 水平平移：相对楼体中心的 Z 偏移
}
const site = {
  center: new THREE.Vector3(),
  size: new THREE.Vector3(),
  floorY: 0,
  ready: false
}

let scene, camera, renderer, controls, gridHelper, animationFrameId
let lastEmitTime = 0
let lastEmitted = ''

onMounted(() => {
  initThree()
  loadModel()
  window.addEventListener('resize', onWindowResize)
  animate()
})

onUnmounted(() => {
  cancelAnimationFrame(animationFrameId)
  window.removeEventListener('resize', onWindowResize)
  if (renderer) {
    renderer.domElement.removeEventListener('wheel', onWheel)
    renderer.dispose()
  }
  TWEEN.removeAll()
})

const initThree = () => {
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x14161a)

  camera = new THREE.PerspectiveCamera(DEFAULT_FOV, window.innerWidth / window.innerHeight, 0.1, 500)
  camera.position.set(30, 20, 30)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.setSize(window.innerWidth, window.innerHeight)
  renderer.localClippingEnabled = true
  renderer.domElement.addEventListener('wheel', onWheel, { passive: false })
  sceneContainer.value.appendChild(renderer.domElement)

  // 左键环视（可上下俯仰），右键水平平移，滚轮缩放
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.06
  controls.enableRotate = true
  controls.enableZoom = false
  controls.enablePan = true
  controls.screenSpacePanning = false // 平移只在水平面内移动，机位高度不受影响
  controls.panSpeed = 0.6
  controls.mouseButtons = {
    LEFT: THREE.MOUSE.ROTATE,
    MIDDLE: THREE.MOUSE.DOLLY,
    RIGHT: THREE.MOUSE.PAN
  }

  scene.add(new THREE.AmbientLight(0xffffff, 0.6))
  scene.add(new THREE.HemisphereLight(0xffffff, 0x2a2f36, 1.2))

  const sun = new THREE.DirectionalLight(0xffffff, 1.5)
  sun.position.set(18, 30, 14)
  scene.add(sun)

  const fill = new THREE.DirectionalLight(0xffffff, 0.5)
  fill.position.set(-16, 12, -18)
  scene.add(fill)
}

const loadModel = () => {
  const loader = new GLTFLoader()
  loader.load(
    '/model.glb',
    (gltf) => {
      const model = gltf.scene
      scene.add(model)
      fitScene(model)
      enableSection(model)
      resetView(false)
    },
    undefined,
    () => {
      console.warn('未检测到 /public/model.glb，使用 Mock 演示模型。')
      const mock = createMockScene()
      scene.add(mock)
      fitScene(mock)
      enableSection(mock)
      resetView(false)
    }
  )
}

// 楼体外壳：JYJLJ_* 为建筑构件，JYJLJ_SB_* 为室内设备
const isShellMesh = (mesh) =>
  mesh.name.startsWith('JYJLJ') && !mesh.name.startsWith('JYJLJ_SB')

// 给朝相机一侧的墙体 / 屋顶挂上裁切面；只保留地面薄层，避免设备悬空
const enableSection = (model) => {
  model.traverse((child) => {
    if (!child.isMesh || !isShellMesh(child)) return

    const height = new THREE.Box3().setFromObject(child).getSize(new THREE.Vector3()).y
    if (height < 0.3) return

    const materials = Array.isArray(child.material) ? child.material : [child.material]
    materials.forEach((mat) => {
      mat.clippingPlanes = sectionPlanes
      mat.clipShadows = true
      mat.side = THREE.DoubleSide // 剖开后仍能看到远侧墙体内表面
      mat.needsUpdate = true
    })
  })
}

const createMockScene = () => {
  const group = new THREE.Group()

  const shell = new THREE.Mesh(
    new THREE.BoxGeometry(30, 7.3, 20),
    new THREE.MeshStandardMaterial({ color: 0x9aa4b2, roughness: 0.8, metalness: 0.05 })
  )
  shell.name = 'JYJLJ_1'
  group.add(shell)

  const colors = [0xff5722, 0x2196f3, 0xffeb3b, 0x9c27b0, 0x009688]
  for (let i = 0; i < 12; i++) {
    const device = new THREE.Mesh(
      new THREE.CylinderGeometry(0.5, 0.5, 1.6, 16),
      new THREE.MeshStandardMaterial({ color: colors[i % colors.length], roughness: 0.4, metalness: 0.6 })
    )
    device.name = `JYJLJ_SB_${String(i + 1).padStart(2, '0')}`
    device.position.set((Math.random() - 0.5) * 22, -1.6, (Math.random() - 0.5) * 14)
    group.add(device)
  }

  return group
}

const fitScene = (object) => {
  const box = new THREE.Box3().setFromObject(object)
  box.getSize(site.size)
  box.getCenter(site.center)
  site.floorY = box.min.y
  site.ready = true

  cameraTarget.set(site.center.x, site.floorY, site.center.z)
  controls.target.copy(cameraTarget)

  if (gridHelper) {
    scene.remove(gridHelper)
    gridHelper.geometry.dispose()
  }
  gridHelper = new THREE.GridHelper(Math.max(site.size.x, site.size.z) * 1.5, 24, 0x3a424d, 0x262b33)
  gridHelper.position.set(site.center.x, site.floorY, site.center.z)
  scene.add(gridHelper)
}

// 距离由建筑对角线决定，保证整个平面刚好收进画面
const fitDistance = (fov = DEFAULT_FOV) => {
  const halfDiagonal = Math.hypot(site.size.x, site.size.z) / 2
  const vFov = THREE.MathUtils.degToRad(fov)
  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * camera.aspect)
  return THREE.MathUtils.clamp((halfDiagonal / Math.tan(hFov / 2)) * 1.08, MIN_DISTANCE, MAX_DISTANCE)
}

// 由参数驱动相机：目标点可在水平面内平移，高度 / 方位 / 距离 / 视场角独立可调
const applyCamera = () => {
  if (!site.ready) return
  const azimuth = THREE.MathUtils.degToRad(cameraParams.azimuth)

  cameraTarget.set(site.center.x + cameraParams.panX, site.floorY, site.center.z + cameraParams.panZ)
  camera.position.set(
    cameraTarget.x + Math.sin(azimuth) * cameraParams.distance,
    cameraTarget.y + cameraParams.height,
    cameraTarget.z + Math.cos(azimuth) * cameraParams.distance
  )
  camera.fov = cameraParams.fov
  camera.updateProjectionMatrix()

  controls.target.copy(cameraTarget)
  // 俯仰范围由「机位高度」上下限换算，上下旋转时高度仍落在有效区间内
  controls.minPolarAngle = Math.atan2(cameraParams.distance, MAX_HEIGHT)
  controls.maxPolarAngle = Math.atan2(cameraParams.distance, MIN_HEIGHT)
  controls.update()
}

const resetView = (animated = true) => {
  if (!site.ready) return
  const target = {
    height: EYE_HEIGHT,
    azimuth: DEFAULT_AZIMUTH,
    distance: fitDistance(),
    fov: DEFAULT_FOV,
    section: 50,
    panX: 0,
    panZ: 0
  }
  if (animated) {
    tweenCameraParams(target, 700)
  } else {
    Object.assign(cameraParams, target)
    applyCamera()
    emitCameraParams()
  }
}

// 参数级补间：高度、方位、距离、视场角同时平滑过渡
const tweenCameraParams = (target, duration = 600) => {
  TWEEN.removeAll()
  const from = { ...cameraParams }
  const deltaAzimuth = ((target.azimuth - from.azimuth + 540) % 360) - 180
  const state = { t: 0 }

  new TWEEN.Tween(state, TWEEN)
    .to({ t: 1 }, duration)
    .easing(TWEEN.Easing.Cubic.InOut)
    .onUpdate(() => {
      const t = state.t
      cameraParams.height = THREE.MathUtils.lerp(from.height, target.height, t)
      cameraParams.distance = THREE.MathUtils.lerp(from.distance, target.distance, t)
      cameraParams.fov = THREE.MathUtils.lerp(from.fov, target.fov, t)
      cameraParams.azimuth = (from.azimuth + deltaAzimuth * t + 360) % 360
      cameraParams.section = THREE.MathUtils.lerp(from.section, target.section, t)
      cameraParams.panX = THREE.MathUtils.lerp(from.panX, target.panX, t)
      cameraParams.panZ = THREE.MathUtils.lerp(from.panZ, target.panZ, t)
      applyCamera()
    })
    .start()
}

// 上一视角 / 下一视角：方位角按 90° 步进
const stepView = (direction) => {
  if (!site.ready) return
  tweenCameraParams(
    { ...cameraParams, azimuth: (cameraParams.azimuth + direction * 90 + 360) % 360 },
    600
  )
}

// 面板修改参数：立即生效
const setCameraParams = (partial) => {
  TWEEN.removeAll()
  if (partial.height !== undefined) {
    cameraParams.height = THREE.MathUtils.clamp(partial.height, MIN_HEIGHT, MAX_HEIGHT)
  }
  if (partial.distance !== undefined) {
    cameraParams.distance = THREE.MathUtils.clamp(partial.distance, MIN_DISTANCE, MAX_DISTANCE)
  }
  if (partial.azimuth !== undefined) {
    cameraParams.azimuth = ((partial.azimuth % 360) + 360) % 360
  }
  if (partial.fov !== undefined) {
    cameraParams.fov = THREE.MathUtils.clamp(partial.fov, MIN_FOV, MAX_FOV)
  }
  if (partial.section !== undefined) {
    cameraParams.section = THREE.MathUtils.clamp(partial.section, 0, 100)
  }
  if (partial.panX !== undefined) {
    cameraParams.panX = THREE.MathUtils.clamp(partial.panX, -MAX_PAN, MAX_PAN)
  }
  if (partial.panZ !== undefined) {
    cameraParams.panZ = THREE.MathUtils.clamp(partial.panZ, -MAX_PAN, MAX_PAN)
  }
  applyCamera()
  emitCameraParams()
}

// 滚轮缩放只改水平距离，保持机位高度不变
const onWheel = (event) => {
  event.preventDefault()
  TWEEN.removeAll()
  const factor = Math.exp(event.deltaY * 0.0012)
  cameraParams.distance = THREE.MathUtils.clamp(
    cameraParams.distance * factor,
    MIN_DISTANCE,
    MAX_DISTANCE
  )
  applyCamera()
  emitCameraParams()
}

// 平移范围限制在楼体附近，避免把机位拖飞
const clampPan = () => {
  if (!site.ready) return
  const x = THREE.MathUtils.clamp(controls.target.x, site.center.x - MAX_PAN, site.center.x + MAX_PAN)
  const z = THREE.MathUtils.clamp(controls.target.z, site.center.z - MAX_PAN, site.center.z + MAX_PAN)
  const dx = x - controls.target.x
  const dz = z - controls.target.z
  if (dx === 0 && dz === 0) return

  controls.target.x = x
  controls.target.z = z
  camera.position.x += dx
  camera.position.z += dz
}

// 把相机实际状态同步回参数面板（拖动环视 / 平移时实时显示）
const syncCameraParams = () => {
  if (!site.ready) return
  cameraParams.panX = controls.target.x - site.center.x
  cameraParams.panZ = controls.target.z - site.center.z
  cameraTarget.set(controls.target.x, site.floorY, controls.target.z)

  const offsetX = camera.position.x - controls.target.x
  const offsetY = camera.position.y - controls.target.y
  const offsetZ = camera.position.z - controls.target.z
  const horizontal = Math.hypot(offsetX, offsetZ)
  if (horizontal < 0.01) return

  cameraParams.height = offsetY
  cameraParams.distance = horizontal
  cameraParams.azimuth = (THREE.MathUtils.radToDeg(Math.atan2(offsetX, offsetZ)) + 360) % 360
}

const emitCameraParams = () => {
  const pitch = THREE.MathUtils.radToDeg(Math.atan2(cameraParams.height, cameraParams.distance))
  const payload = {
    height: +cameraParams.height.toFixed(2),
    azimuth: +cameraParams.azimuth.toFixed(1),
    distance: +cameraParams.distance.toFixed(1),
    fov: +cameraParams.fov.toFixed(1),
    section: cameraParams.section,
    panX: +cameraParams.panX.toFixed(2),
    panZ: +cameraParams.panZ.toFixed(2),
    pitch: +pitch.toFixed(1),
    // 相机实时世界坐标
    pos: {
      x: +camera.position.x.toFixed(2),
      y: +camera.position.y.toFixed(2),
      z: +camera.position.z.toFixed(2)
    },
    // 观察目标点实时坐标
    target: {
      x: +cameraTarget.x.toFixed(2),
      y: +cameraTarget.y.toFixed(2),
      z: +cameraTarget.z.toFixed(2)
    }
  }
  const key = JSON.stringify(payload)
  if (key === lastEmitted) return
  lastEmitted = key
  emit('camera-change', payload)
}

// 剖切面随相机方位实时更新：法线指向楼体内部，
// 按剖开比例沿法线偏移（50% 穿过中心，0% 贴近相机，100% 切到远侧边缘）
const updateSectionPlane = () => {
  if (!site.ready) return
  const dx = site.center.x - camera.position.x
  const dz = site.center.z - camera.position.z
  const length = Math.hypot(dx, dz)
  if (length < 0.5) return

  const nx = dx / length
  const nz = dz / length
  sectionPlane.normal.set(nx, 0, nz)

  // 楼体沿法线方向的投影深度（AABB 近似）
  const depth = Math.abs(site.size.x * nx) + Math.abs(site.size.z * nz)
  // 相机一侧边缘到中心为 depth/2，比例越大切得越深
  const offset = (cameraParams.section / 100 - 0.5) * depth
  sectionPlane.constant = -(nx * site.center.x + nz * site.center.z) - offset
}

const onWindowResize = () => {
  camera.aspect = window.innerWidth / window.innerHeight
  camera.updateProjectionMatrix()
  renderer.setSize(window.innerWidth, window.innerHeight)
}

const animate = (time = 0) => {
  animationFrameId = requestAnimationFrame(animate)
  TWEEN.update()
  controls.update()
  clampPan()
  syncCameraParams()
  updateSectionPlane()
  if (time - lastEmitTime > 100) {
    lastEmitTime = time
    emitCameraParams()
  }
  renderer.render(scene, camera)
}

defineExpose({ resetView, stepView, setCameraParams })
</script>

<style scoped>
.scene-container {
  width: 100%;
  height: 100%;
}
</style>
