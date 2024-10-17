<script>
import { Image } from 'element-ui';
import ImageViewer from './image-viewer.vue';
export default {
  name: Image.name,
  extends: Image,
  components: {
    ImageViewer: {
      ...Image.components.ImageViewer,
      render: ImageViewer.render,
      methods: ImageViewer.methods
    }
  }
};
</script>

<style></style>
