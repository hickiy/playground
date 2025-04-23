import { ElInput } from 'element-plus';

export default {
  extends: ElInput,
  props: {
    decimal: {
      type: Number, // 保留小数位数
    }
  },
  setup(props, ctx) {
    if (props.type === 'number' && props.decimal != null) {
      let originEmit = ctx.emit;
      return ElInput.setup(props, {
        ...ctx,
        emit: (event, ...args) => {
          if (event === 'update:modelValue') {
            let value = args[0];
            const [integer, decimal] = value.split('.');
            if (decimal?.length > props.decimal) {
              value = `${integer}.${decimal.slice(0, props.decimal)}`;
            }
            originEmit(event, value);
          } else {
            originEmit(event, ...args);
          }
        }
      });
    } else {
      return ElInput.setup(props, ctx);
    }
  }
}