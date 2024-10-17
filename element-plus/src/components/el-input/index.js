/*  hickey 2023/11/7 */
import { ElInput } from 'element-plus';
export default {
  extends: ElInput,
  props: {
    decimal: Number
  },
  setup(props, ctx) {
    const render = ElInput.setup(props, ctx);
    const instance = getCurrentInstance();
    const updateModelValue = instance.vnode?.props?.['onUpdate:modelValue'];
    const wrapFn = (value) => {
      if (updateModelValue) {
        const [integer, decimal] = value.split('.');
        if (props.type == 'number' && props.decimal != null && decimal?.length > props.decimal) {
          updateModelValue(`${integer}.${decimal.slice(0, props.decimal)}`);
        } else {
          updateModelValue(value)
        }
      }
    };
    return (...args) => {
      const vnode = render(...args)
      instance.vnode.props['onUpdate:modelValue'] = wrapFn;
      return vnode;
    };
  }
};
