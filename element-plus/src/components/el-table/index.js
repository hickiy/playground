import { ElTable } from 'element-plus';
import Prepend from './prepend.vue';
import { h } from 'vue';
export default {
  extends: ElTable,
  props: {
    setTable: {
      type: [Boolean, Array],
      default: null
    },
    title: {
      type: [String],
      default: null
    },
    showOverflowTooltip: {
      type: Boolean,
      default: true
    },
  },
  setup(props, ctx) {
    return ElTable.setup(props, ctx);
  },
  render(...args) {
    const children = [ElTable.render.apply(this, args)];
    // return children[0]
    if (this.height) {
      typeof this.height == 'number' && (children[0].props.style.height = this.height + 'px');
      typeof this.height == 'string' && (children[0].props.style.height = this.height);
    }
    // table设置面板
    const setting = h(
      Prepend,
      {
        title: this.title,
        setTable: this.setTable,
        ref: 'table-setting'
      },
      {
        default: this.$slots.prepend
      }
    );
    if (this.setTable) {
      children.unshift(setting);
    }
    const style = {
      width: '100%',
      position: 'relative',
      overflow: 'hidden',
      flex: 1
    };
    if (this.setTable) {
      style.display = 'flex';
      style.flexFlow = 'column';
    }
    return h('div', { style, 'data-prefix': 'el' }, children);
  },
};
