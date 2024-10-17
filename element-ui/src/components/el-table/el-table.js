import { Table, Tooltip, Button } from 'element-ui';
import TableSetting from './el-table-setting.vue';
import { copy } from '@/utils/clipboard';
export default {
  name: Table.name,
  inheritAttrs: false,
  props: {
    // 是否显示设置面板
    setTable: {
      type: [Boolean, Array], // TODO 使用传入的参数进行初始的列过滤
      default: undefined
    },
    // 设置面板的标题
    title: {
      type: [String],
      default: ''
    }
  },
  data() {
    return {
      tooltipContent: ''
    };
  },
  activated() {
    this.originTable.doLayout();
  },
  deactivated() {
    this.cleaning();
  },
  destroyed() {
    this.cleaning();
  },
  computed: {
    originTable() {
      return this.$refs['origin-table'];
    }
  },
  methods: {
    // 清除tooltip,防止在页面切换时，tooltip未关闭
    cleaning() {
      setTimeout(() => {
        let tooltip = this.$refs['tooltip'];
        tooltip?.setExpectedState?.(false);
        tooltip?.handleClosePopper?.();
        this.originTable?.$children?.forEach((element) => {
          if (element.$options?.name == 'ElTableBody') {
            element.$refs?.tooltip?.setExpectedState?.(false);
            element.$refs?.tooltip?.handleClosePopper?.();
          }
        });
      }, 500);
    },
    clearSelection(...arg) {
      this.originTable.clearSelection(...arg);
    },
    toggleRowSelection(...arg) {
      this.originTable.toggleRowSelection(...arg);
    },
    toggleAllSelection(...arg) {
      this.originTable.toggleAllSelection(...arg);
    },
    toggleRowExpansion(...arg) {
      this.originTable.toggleRowExpansion(...arg);
    },
    setCurrentRow(...arg) {
      this.originTable.setCurrentRow(...arg);
    },
    clearSort(...arg) {
      this.originTable.clearSort(...arg);
    },
    clearFilter(...arg) {
      this.originTable.clearFilter(...arg);
    },
    doLayout() {
      this.originTable.doLayout();
    },
    sort(...arg) {
      this.originTable.sort(...arg);
    }
  },
  render(h) {
    // table设置面板
    const setting = h(
      TableSetting,
      {
        props: {
          title: this.title,
          setTable: this.setTable
        },
        ref: 'table-setting'
      },
      [this.$slots.prepend]
    );

    // el-table组件
    const table = h(Table,
      {
        props: this.$attrs,
        on: this.$listeners,
        ref: 'origin-table'
      },
      [this.$slots.default]
    );

    // tooltip组件，用于显示列过滤的内容
    const tooltip = h(Tooltip, {
      props: {
        placement: 'top',
        effect: 'dark',
        content: this.tooltipContent
      },
      on: {
        setContent: (content) => {
          this.tooltipContent = content;
        }
      },
      ref: 'tooltip'
    });

    // tooltip组件，用于显示复制弹出按钮
    const copyBtn = h(
      Tooltip,
      {
        props: {
          placement: 'bottom',
          effect: 'light',
          'visible-arrow': false,
          'popper-class': 'copy-btn-tooltip',
          'hide-after': 1500
        },
        ref: 'copyBtn',
        on: {
          setContent: (content) => {
            this.copyBtnContent = content;
          }
        }
      },
      [
        h(
          Button,
          {
            props: {
              type: 'text',
              size: 'mini'
            },
            on: {
              click: () => {
                if (this.copyBtnContent && copy(this.copyBtnContent)) {
                  this.$message({
                    message: '复制成功',
                    type: 'success'
                  });
                }
              }
            },
            slot: 'content'
          },
          '复制'
        )
      ]
    );

    const children = [table, tooltip, copyBtn];
    if (this.setTable) {
      children.unshift(setting);
    }
    const style = {
      width: '100%',
      position: 'relative',
      overflow: 'hidden',
      flex: 1
    };
    if (this.$attrs.height) {
      typeof this.$attrs.height == 'number' && (style.height = this.$attrs.height + 'px');
      typeof this.$attrs.height == 'string' && (style.height = this.$attrs.height);
    }
    if (this.setTable) {
      style.display = 'flex';
      style.flexFlow = 'column ';
    }
    return h('div', { style }, children);
  }
};
