<template>
  <div class="hello">
    <el-input v-model="form.value" type="number" :decimal="2"></el-input>
    <el-table :data="[]" height="100%" border>
      <el-table-column label="序号" type="index" width="60"></el-table-column>
      <el-table-column label="" prop="" min-width="120"></el-table-column>
      <el-table-column label="" prop="" min-width="120"></el-table-column>
      <el-table-column label="" prop="" min-width="120"></el-table-column>
      <el-table-column label="" prop="" min-width="120"></el-table-column>
      <el-table-column label="" prop="" min-width="120"></el-table-column>
    </el-table>
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
