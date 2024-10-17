import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue2';
import vueJsx from '@vitejs/plugin-vue2-jsx';
import UnoCSS from 'unocss/vite';
export default defineConfig({
  plugins: [
    vue(),
    vueJsx(),
    UnoCSS(),
  ],
  transpileDependencies: true
})
