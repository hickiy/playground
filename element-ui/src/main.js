import Vue from 'vue'
import App from './App.vue'
import ElementUI from './components/index.js'
import 'uno.css'; // uno.css
import 'element-ui/lib/theme-chalk/index.css';
import './assets/index.css';

Vue.use(ElementUI)

Vue.config.productionTip = false

new Vue({
  render: h => h(App),
}).$mount('#app')
