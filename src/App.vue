<!-- hickey 2024/06/25 -->
<template>
  <ElFormWrap :model="form" ref="form" label-width="80px" inline>
    <el-form-item label="名字" prop="name">
      <el-input placeholder="请输入名字"></el-input>
    </el-form-item>
  </ElFormWrap>
</template>
<script>
import { ref } from "vue";
import ElFormWrap from "./wrapForm.jsx";
export default {
  components: {
    ElFormWrap,
  },
  setup() {
    const form = ref({
      name: "",
    });
    return {
      form,
    };
  },
};
</script>

<style scoped lang="scss"></style>
