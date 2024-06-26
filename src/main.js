import { createApp } from 'vue';
import './style.css';
import App from './App.vue';
import ElementPlus from 'element-plus'; // element-plus
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'; // element-plus 中文
import 'element-plus/dist/index.css';
import * as ElementPlusIconsVue from '@element-plus/icons-vue';

const app = createApp(App);
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component);
}
// element-plus 全量引入
app.use(ElementPlus, {
  size: 'small', // 支持 large、default、small
  locale: zhCn, // element-plus 中文
});
app.mount('#vue-app');
