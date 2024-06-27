import { ref, onUpdated } from "vue";
import ChildComponent from "./childComponent.vue";
export default {
  name: "WrapComponent",
  extends: ChildComponent,
  setup(props, ctx) {
    const defaultSlot = ctx.slots.default;
    const hasBorder = ref(true);
    ctx.slots.default = () => [
      <div
        style={{
          display: "flex",
          flexFlow: "row nowrap",
          justifyContent: "space-between",
          border: hasBorder.value ? "1px solid red" : "",
        }}
      >
        <div>{...defaultSlot()}</div>
        <button onClick={() => (hasBorder.value = !hasBorder.value)}>
          Toggle Border
        </button>
      </div>,
    ];
    onUpdated(() => {
      console.log("WrapComponent updated");
    });
    return (...args) => ChildComponent.render(...args);
  },
};
