import { Input } from 'element-ui';
export default {
  name: Input.name,
  extends: Input,
  props: {
    /**
     * @description 小数位数
     * @type {Number}
     * @default null
     * @example
     * <el-input v-model="value" type="number" :decimal="2"></el-input> // 最多输入2位小数
     * <el-input v-model="value" type="number" :decimal="0"></el-input> // 只能输入整数
     */
    decimal: Number
  },
  render(h) {
    const vnode = Input.render.call(this, h);
    if (this.type == 'number' && this.decimal != null) {
      vnode.data.on.mousewheel = (e) => e.preventDefault();
      const inputHandlers = this._events.input ?? [];
      this._events.input = [(value) => {
        const [integer, decimal] = value.split('.');
        if (decimal?.length > this.decimal) {
          if (this.decimal === 0) {
            inputHandlers.forEach((handler) => handler(integer));
          } else {
            inputHandlers.forEach((handler) => handler(`${integer}.${decimal.slice(0, this.decimal)}`));
          }
        } else {
          inputHandlers.forEach((handler) => handler(value));
        }
      }]
    }
    return vnode;
  }
};
