<template>
  <div class="hello">
    <el-form :model="form">
      <el-form-item label="test input" prop="value" :rules="{
        required: true,
        message: '请输入数字',
        trigger: 'change',
      }">
        <el-input v-model="form.value" type="number" :decimal="6"></el-input>
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
        value: '',
      },
    };
  }
};
</script>

<style scoped>
.hello {
  width: 80%;
  margin: 0 auto;
}
</style>
