import { ElForm } from 'element-plus';
import { ref } from 'vue';
export default {
  name: ElForm.name,
  extends: ElForm,
  setup(props, ctx) {
    const defaultSlot = ctx.slots.default;
    const isCollapse = ref(true);
    ctx.slots.default = () => [
      <div
        style={{
          display: "flex",
          flexFlow: "row nowrap",
          justifyContent: "space-between",
          border: isCollapse.value ? "1px solid red" : "",
        }}
      >
        <div>{...defaultSlot()}</div>
        <div>
          <el-button
            link
            type="primary"
            onClick={() => (isCollapse.value = !isCollapse.value)}
          >
            {isCollapse.value ? "展开" : "收起"}
            <el-icon>
              {isCollapse.value ? <ArrowDownBold /> : <ArrowUpBold />}
            </el-icon>
          </el-button>
        </div>
      </div>,
    ];
    return ElForm.setup(props, ctx);
  },
};
