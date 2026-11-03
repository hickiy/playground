<template>
  <div class="app-container">
    <div class="tips-panel">
      <h3>建筑半剖 · 人眼机位</h3>
      <p>相机默认在人眼高度 <b>1.65m</b>、<b>45°</b> 方位环视楼体，靠近相机的一半自动剖开。</p>
      <p>左键拖拽环视、上下拖动调整俯仰，右键拖拽水平移动，滚轮缩放；右侧面板参数实时联动。</p>
    </div>

    <aside class="param-panel">
      <h3>机位参数</h3>
      <div class="live-info">
        <div class="live-title">实时机位</div>
        <div class="live-row"><span>相机 X</span><b>{{ camera.pos.x.toFixed(2) }}</b></div>
        <div class="live-row"><span>相机 Y</span><b>{{ camera.pos.y.toFixed(2) }}</b></div>
        <div class="live-row"><span>相机 Z</span><b>{{ camera.pos.z.toFixed(2) }}</b></div>
        <div class="live-row"><span>目标 X</span><b>{{ camera.target.x.toFixed(2) }}</b></div>
        <div class="live-row"><span>目标 Y</span><b>{{ camera.target.y.toFixed(2) }}</b></div>
        <div class="live-row"><span>目标 Z</span><b>{{ camera.target.z.toFixed(2) }}</b></div>
        <div class="live-row"><span>俯仰角</span><b>{{ camera.pitch.toFixed(1) }}°</b></div>
      </div>

      <div v-for="item in sliders" :key="item.key" class="param">
        <div class="param-head">
          <span>{{ item.label }}</span>
          <b>{{ formatValue(item) }}</b>
        </div>
        <input
          type="range"
          :min="item.min"
          :max="item.max"
          :step="item.step"
          :value="camera[item.key]"
          @input="onSliderInput(item.key, $event)"
        />
      </div>

      <div class="step-buttons">
        <button @click="stepView(1)">▲ 上一视角</button>
        <button @click="stepView(-1)">▼ 下一视角</button>
      </div>
      <button class="reset" @click="resetView">一键回归</button>
      <button class="copy" @click="copyCameraParams">{{ copyLabel }}</button>
    </aside>

    <ThreeScene ref="sceneRef" @camera-change="onCameraChange" />
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import ThreeScene from './components/ThreeScene.vue'

const sliders = [
  { key: 'height', label: '机位高度', unit: 'm', min: 0.5, max: 40, step: 0.05, decimals: 2 },
  { key: 'azimuth', label: '方位角', unit: '°', min: 0, max: 359, step: 1, decimals: 0 },
  { key: 'distance', label: '观察距离', unit: 'm', min: 10, max: 80, step: 0.5, decimals: 1 },
  { key: 'panX', label: '水平平移 X', unit: 'm', min: -30, max: 30, step: 0.1, decimals: 1 },
  { key: 'panZ', label: '水平平移 Z', unit: 'm', min: -30, max: 30, step: 0.1, decimals: 1 },
  { key: 'fov', label: '视场角', unit: '°', min: 20, max: 80, step: 1, decimals: 0 },
  { key: 'section', label: '剖开比例', unit: '%', min: 0, max: 100, step: 1, decimals: 0 }
]

const sceneRef = ref(null)
const camera = reactive({
  height: 1.65,
  azimuth: 45,
  distance: 30,
  fov: 45,
  section: 50,
  panX: 0,
  panZ: 0,
  pitch: 0,
  pos: { x: 0, y: 0, z: 0 },
  target: { x: 0, y: 0, z: 0 }
})
const copied = ref('idle') // idle | ok | fail
const copyLabel = computed(() => {
  if (copied.value === 'ok') return '✓ 已复制机位参数'
  if (copied.value === 'fail') return '复制失败，请检查剪贴板权限'
  return '复制机位参数'
})

const formatValue = (item) => `${camera[item.key].toFixed(item.decimals)}${item.unit}`

const onCameraChange = (params) => Object.assign(camera, params)

const onSliderInput = (key, event) => {
  const value = Number(event.target.value)
  camera[key] = value
  sceneRef.value?.setCameraParams({ [key]: value })
}

const stepView = (direction) => sceneRef.value?.stepView(direction)
const resetView = () => sceneRef.value?.resetView()

// 复制完整机位参数，便于调整好后固化到代码里
const copyCameraParams = async () => {
  const params = {
    position: [camera.pos.x, camera.pos.y, camera.pos.z],
    target: [camera.target.x, camera.target.y, camera.target.z],
    fov: camera.fov,
    section: camera.section,
    height: camera.height,
    azimuth: camera.azimuth,
    distance: camera.distance,
    panX: camera.panX,
    panZ: camera.panZ
  }
  try {
    await navigator.clipboard.writeText(JSON.stringify(params, null, 2))
    copied.value = 'ok'
  } catch (error) {
    console.warn('复制机位参数失败', error)
    copied.value = 'fail'
  }
  setTimeout(() => (copied.value = 'idle'), 1600)
}
</script>

<style scoped>
.app-container {
  position: relative;
  width: 100vw;
  height: 100vh;
}
.tips-panel {
  position: absolute;
  top: 20px;
  left: 20px;
  z-index: 10;
  background: rgba(0, 0, 0, 0.78);
  color: #fff;
  padding: 15px 22px;
  border-radius: 8px;
  font-family: sans-serif;
  max-width: 320px;
  border: 1px solid #3a3f46;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  pointer-events: none;
}
h3 {
  margin: 0 0 6px;
  color: #42b883;
  font-size: 17px;
}
p {
  font-size: 13px;
  line-height: 1.6;
  margin: 6px 0;
  color: #c3c8cf;
}
p b {
  color: #fff;
}
.param-panel {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 10;
  width: 264px;
  max-height: calc(100vh - 40px);
  overflow-y: auto;
  padding: 16px 18px 18px;
  border-radius: 10px;
  background: rgba(18, 20, 24, 0.9);
  border: 1px solid #3a3f46;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
  font-family: sans-serif;
  color: #c3c8cf;
}
.param-panel h3 {
  margin: 0 0 12px;
  font-size: 15px;
  color: #42b883;
}
.live-info {
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 6px;
  background: rgba(66, 184, 131, 0.08);
  border: 1px solid rgba(66, 184, 131, 0.25);
}
.live-title {
  font-size: 12px;
  color: #42b883;
  margin-bottom: 6px;
}
.live-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  line-height: 1.7;
  color: #8a929c;
}
.live-row b {
  color: #fff;
  font-variant-numeric: tabular-nums;
}
.param {
  margin-bottom: 12px;
}
.param-head {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  margin-bottom: 6px;
}
.param-head b {
  color: #fff;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.param input[type='range'] {
  width: 100%;
  accent-color: #42b883;
  cursor: pointer;
}
.step-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
}
.step-buttons button,
.reset,
.copy {
  width: 100%;
  padding: 9px 0;
  font-size: 13px;
  border-radius: 6px;
  cursor: pointer;
  background: #232830;
  color: #c3c8cf;
  border: 1px solid #3a3f46;
  transition: all 0.2s;
}
.step-buttons button:hover {
  color: #fff;
  border-color: #42b883;
}
.reset {
  margin-top: 10px;
  padding: 10px 0;
  color: #ffd166;
  border-color: #5d5230;
}
.reset:hover {
  color: #14161a;
  background: #ffd166;
  border-color: #ffd166;
}
.copy {
  margin-top: 8px;
  color: #42b883;
  border-color: #2f5c46;
}
.copy:hover {
  color: #14161a;
  background: #42b883;
  border-color: #42b883;
}
</style>
