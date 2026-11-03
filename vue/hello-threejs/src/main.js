import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import './style.css'

const container = document.querySelector('#scene-container')
const toast = document.querySelector('#selection-toast')
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
renderer.shadowMap.enabled = true
renderer.shadowMap.type = THREE.PCFShadowMap
renderer.outputColorSpace = THREE.SRGBColorSpace
renderer.toneMapping = THREE.ACESFilmicToneMapping
renderer.toneMappingExposure = 1.15
container.append(renderer.domElement)

const scene = new THREE.Scene()
scene.background = new THREE.Color('#f3f6fb')
scene.fog = new THREE.Fog('#f3f6fb', 16, 34)

const perspectiveCamera = new THREE.PerspectiveCamera(42, 1, 0.1, 100)
perspectiveCamera.position.set(7.5, 6.5, 10)
perspectiveCamera.lookAt(0, 0.8, 0)
const orthographicCamera = new THREE.OrthographicCamera(-6, 6, 6, -6, 0.1, 100)
orthographicCamera.position.copy(perspectiveCamera.position)
orthographicCamera.lookAt(0, 0.8, 0)
let camera = perspectiveCamera

function createControls(activeCamera, target) {
  const instance = new OrbitControls(activeCamera, renderer.domElement)
  instance.target.copy(target)
  instance.enableDamping = true
  instance.dampingFactor = 0.06
  instance.minDistance = 5
  instance.maxDistance = 22
  return instance
}

let controls = createControls(camera, new THREE.Vector3(0, 0.8, 0))

scene.add(new THREE.HemisphereLight('#eaf3ff', '#8e9bac', 2.1))
const keyLight = new THREE.DirectionalLight('#fff4df', 3.2)
keyLight.position.set(-4, 9, 6)
keyLight.castShadow = true
keyLight.shadow.mapSize.set(1024, 1024)
keyLight.shadow.camera.left = -8
keyLight.shadow.camera.right = 8
keyLight.shadow.camera.top = 8
keyLight.shadow.camera.bottom = -8
scene.add(keyLight)

const floor = new THREE.Mesh(
  new THREE.PlaneGeometry(200, 200),
  new THREE.MeshStandardMaterial({ color: '#edf1f7', roughness: 0.92 }),
)
floor.rotation.x = -Math.PI / 2
floor.position.y = -0.035
floor.receiveShadow = true
scene.add(floor)

const grid = new THREE.GridHelper(16, 32, '#9aabc0', '#d5deea')
grid.position.y = 0.005
scene.add(grid)
const axes = new THREE.AxesHelper(3)
axes.position.set(0, 0.02, 0)
scene.add(axes)

const objects = [
  createObject(
    '立方体',
    'BoxGeometry',
    new THREE.BoxGeometry(1.35, 1.35, 1.35),
    '#5278f6',
    new THREE.Vector3(-2.2, 0.68, 0),
    '由长、宽、高组成的基础网格。',
  ),
  createObject(
    '球体',
    'SphereGeometry',
    new THREE.SphereGeometry(0.82, 40, 28),
    '#35b89a',
    new THREE.Vector3(0, 0.82, 0),
    '经纬度细分的曲面；细分越多，表面越平滑。',
  ),
  createObject(
    '圆环',
    'TorusKnotGeometry',
    new THREE.TorusKnotGeometry(0.58, 0.22, 120, 16),
    '#f0a54b',
    new THREE.Vector3(2.2, 0.95, 0),
    '由一条空间曲线扫掠截面得到的参数曲面。',
  ),
]

function createObject(name, geometryName, geometry, color, position, description) {
  const material = new THREE.MeshStandardMaterial({
    color,
    roughness: 0.32,
    metalness: 0.08,
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.name = name
  mesh.position.copy(position)
  mesh.castShadow = true
  mesh.receiveShadow = true
  mesh.userData = {
    geometryName,
    description,
    initialPosition: position.clone(),
    baseEmissive: material.emissive.clone(),
  }
  scene.add(mesh)
  return mesh
}

let selectedObject = null
let autoRotate = false
let wireframe = false

const objectList = document.querySelector('#object-list')
for (const object of objects) {
  const item = document.createElement('button')
  item.className = 'object-item'
  item.type = 'button'
  item.dataset.object = object.name
  item.innerHTML = `
    <span class="object-swatch" style="--swatch: #${object.material.color.getHexString()}"></span>
    <span class="object-copy"><strong>${object.name}</strong><small>${object.userData.geometryName}</small></span>
    <span class="object-arrow">↗</span>
  `
  item.addEventListener('click', () => selectObject(object))
  objectList.append(item)
}

const sliders = {
  x: document.querySelector('#position-x'),
  y: document.querySelector('#position-y'),
  z: document.querySelector('#position-z'),
}
const outputs = {
  x: document.querySelector('#value-x'),
  y: document.querySelector('#value-y'),
  z: document.querySelector('#value-z'),
}

for (const axis of ['x', 'y', 'z']) {
  sliders[axis].addEventListener('input', () => {
    if (!selectedObject) return
    selectedObject.position[axis] = Number(sliders[axis].value)
    updatePositionPanel()
  })
}

function selectObject(object) {
  if (selectedObject) {
    selectedObject.material.emissive.copy(selectedObject.userData.baseEmissive)
    selectedObject.material.emissiveIntensity = 0
  }

  selectedObject = object
  selectedObject.material.emissive.set('#ffffff')
  selectedObject.material.emissiveIntensity = 0.18
  toast.textContent = `${object.name} · ${object.userData.geometryName}`
  toast.classList.add('is-visible')
  document.querySelectorAll('.object-item').forEach((item) => {
    item.classList.toggle('is-selected', item.dataset.object === object.name)
  })
  Object.values(sliders).forEach((slider) => {
    slider.disabled = false
  })
  document.querySelector('#transform-hint').textContent = object.userData.description
  updatePositionPanel()
}

function updatePositionPanel() {
  if (!selectedObject) return
  for (const axis of ['x', 'y', 'z']) {
    const value = selectedObject.position[axis]
    sliders[axis].value = String(value)
    outputs[axis].value = value.toFixed(1)
  }
}

const raycaster = new THREE.Raycaster()
const pointer = new THREE.Vector2()
renderer.domElement.addEventListener('pointerdown', (event) => {
  if (event.button !== 0) return
  const bounds = renderer.domElement.getBoundingClientRect()
  pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1
  pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  const [hit] = raycaster.intersectObjects(objects)
  if (hit) selectObject(hit.object)
})

document.querySelector('#camera-toggle').addEventListener('click', () => {
  const position = camera.position.clone()
  const target = controls.target.clone()
  controls.dispose()
  camera = camera === perspectiveCamera ? orthographicCamera : perspectiveCamera
  camera.position.copy(position)
  camera.lookAt(target)
  controls = createControls(camera, target)
  controls.update()
  document.querySelector('#camera-value').textContent =
    camera === perspectiveCamera ? '透视' : '正交'
  resizeRenderer()
})

bindToggle('#axes-toggle', () => {
  axes.visible = !axes.visible
  return axes.visible
})
bindToggle('#grid-toggle', () => {
  grid.visible = !grid.visible
  return grid.visible
})
bindToggle('#wireframe-toggle', () => {
  wireframe = !wireframe
  objects.forEach((object) => {
    object.material.wireframe = wireframe
  })
  return wireframe
})
bindToggle('#rotate-toggle', () => {
  autoRotate = !autoRotate
  controls.autoRotate = autoRotate
  return autoRotate
})

function bindToggle(selector, toggle) {
  const button = document.querySelector(selector)
  button.addEventListener('click', () => {
    const isOn = toggle()
    button.setAttribute('aria-pressed', String(isOn))
    button.querySelector('.switch').classList.toggle('is-on', isOn)
  })
}

document.querySelector('#reset-button').addEventListener('click', () => {
  for (const object of objects) {
    object.position.copy(object.userData.initialPosition)
    object.rotation.set(0, 0, 0)
    object.material.wireframe = false
  }
  wireframe = false
  setToggleState('#wireframe-toggle', false)
  axes.visible = true
  grid.visible = true
  setToggleState('#axes-toggle', true)
  setToggleState('#grid-toggle', true)
  autoRotate = false
  controls.autoRotate = false
  setToggleState('#rotate-toggle', false)
  if (camera !== perspectiveCamera) {
    document.querySelector('#camera-toggle').click()
  }
  controls.target.set(0, 0.8, 0)
  camera.position.set(7.5, 6.5, 10)
  controls.update()
  if (selectedObject) updatePositionPanel()
  toast.classList.remove('is-visible')
})

function setToggleState(selector, isOn) {
  const button = document.querySelector(selector)
  button.setAttribute('aria-pressed', String(isOn))
  button.querySelector('.switch').classList.toggle('is-on', isOn)
}

function resizeRenderer() {
  const { width, height } = container.getBoundingClientRect()
  if (!width || !height) return
  renderer.setSize(width, height, false)
  if (camera === perspectiveCamera) {
    camera.aspect = width / height
  } else {
    const viewHeight = 12
    const viewWidth = viewHeight * (width / height)
    camera.left = -viewWidth / 2
    camera.right = viewWidth / 2
    camera.top = viewHeight / 2
    camera.bottom = -viewHeight / 2
  }
  camera.updateProjectionMatrix()
}

const resizeObserver = new ResizeObserver(resizeRenderer)
resizeObserver.observe(container)
resizeRenderer()

const timer = new THREE.Timer()
renderer.setAnimationLoop(() => {
  timer.update()
  const delta = timer.getDelta()
  controls.update(delta)
  renderer.render(scene, camera)
})
