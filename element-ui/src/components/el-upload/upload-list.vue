<template>
  <div class="h100 w100" v-loading="file.status === 'uploading'">
    <el-preview-file v-if="file.status == 'success'" ref="file-previer" :file="file" :preview-src-list="fileList"></el-preview-file>
    <span :class="['el-upload-list__item-actions', file.status == 'fail' ? 'fail' : '']">
      <span v-if="!/.zip$/i.test(file.name || file.url)" class="el-upload-list__item-preview">
        <i v-if="file.status == 'ready' || file.status == 'fail'" class="el-icon-upload2" @click="fileUpload(file)"></i>
        <i v-else class="el-icon-zoom-in" @click="preview(file, $event)"></i>
      </span>
      <span class="el-upload-list__item-delete">
        <i v-if="!uploader.disabled" class="el-icon-delete" @click="$emit('remove', file)"></i>
      </span>
    </span>
  </div>
</template>

<script>
export default {
  name: 'FilePrevier',
  props: ['file', 'uploadFiles', 'onPriview', 'fileUpload'],
  inject: ['uploader'],
  computed: {
    fileList() {
      return this.uploadFiles.map((i) => i.url || i.fileUrl);
    }
  },
  methods: {
    preview(file, ev) {
      if (typeof this.onPriview == 'function') {
        this.onPreview(file);
      } else {
        this.$refs['file-previer'].clickHandler(ev);
      }
    }
  }
};
</script>

<style lang="scss" scoped>
.fail {
  opacity: 1 !important;
  span {
    color: #F56C6C !important;
    display: inline-block !important;
  }
}
</style>
