import { createApp } from 'vue'
import App from './App.vue'
import ElementPlus from './components/index'
import 'element-plus/dist/index.css'
import './assets/index.css'

const app = createApp(App)

app.use(ElementPlus)
app.mount('#app')

