<template>
  <div class="hello">
    <el-form :model="form" ref="form" label-width="120px">
      <el-form-item label="测试" prop="value">
        <el-input v-model="form.value" type="number" :decimal="2"></el-input>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
export default {
  name: "Play",
  data() {
    return {
      form: {
        value: 0,
      },
    };
  },
};
</script>

<style scoped>
.hello {
  width: 80%;
  margin: 0 auto;
}
</style>
