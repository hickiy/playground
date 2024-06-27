<!-- hickey 2024/06/25 -->
<script lang="jsx">
import { ref } from "vue";
import ElFormWrap from "./wrapForm.jsx";
export default {
  setup() {
    const form = ref({
      name: "",
    });
    return () => (
      <ElFormWrap model={form} labelWidth="80px" inline={true}>
        <el-form-item label="名字" prop="name">
          <el-input placeholder="请输入名字"></el-input>
        </el-form-item>
      </ElFormWrap>
    );
  },
};
</script>

<style scoped lang="scss"></style>
