import { TableColumn } from 'element-ui';
import { strTruncate, numFormat } from '@/utils/reg';
import { debounce } from 'throttle-debounce';

// 字符串截断配置
const truncationConf = {
  brCode: { // 车架号
    startNum: 5, // 开始显示的字符数
    separator: '***', // 分隔符
    endNum: 5, // 结尾显示的字符数
    hoverToShowWhole: true // 鼠标悬浮是否显示全部内容
  },
  idCard: {
    startNum: 2,
    separator: '***',
    endNum: 4,
    hoverToShowWhole: false
  },

  phoneNumber: {
    startNum: 3,
    separator: '***',
    endNum: 4,
    hoverToShowWhole: false
  },
  vin: {
    startNum: 3,
    separator: '***',
    endNum: 4,
    hoverToShowWhole: true
  },
  default: {
    startNum: 3,
    separator: '***',
    endNum: 4,
    hoverToShowWhole: true
  }
};

export default {
  name: TableColumn.name,
  extends: TableColumn,
  props: {
    // 列的对齐方式, 默认左对齐，如果有numFormat则默认右对齐，其他情况请手动设置
    align: {
      type: String,
      default() {
        return this.$options.propsData.numFormat != null ? 'right' : 'left';
      }
    },
    // 默认溢出隐藏，不希望隐藏的时候设置为false，或者设置min-width避免溢出
    showOverflowTooltip: {
      type: Boolean,
      default: true
    },
    // 此列是否可过滤
    canFilter: {
      type: Boolean,
      default: true
    },
    // 字符串截断
    strTruncate: {
      type: [Boolean, String],
      default: false
    },
    // 数字格式化
    numFormat: {
      type: Boolean,
      default: false
    },
    // 里程格式化
    mileFormat: {
      type: Boolean,
      default: false
    },
    formatter: {
      type: Function,
      default(row, col, val) {
        if (val == null || val === '') {
          return '-';
        } else if (col.numFormat) {
          return numFormat(val, 2);
        } else if (col.strTruncate) {
          const conf = truncationConf[col.strTruncate] || truncationConf.default;
          return strTruncate(val, conf);
        } else if (col.mileFormat) {
          return numFormat(val);
        } else {
          return val;
        }
      }
    }
  },
  created() {
    // 用于处理tooltip的显示
    this.activateTooltip = debounce(50, (tooltip) => tooltip.handleShowPopper());
    // 用于注入自定义的props
    this.columnConfig.canFilter = this.canFilter;
    this.columnConfig.strTruncate = this.strTruncate;
    this.columnConfig.numFormat = this.numFormat;
    this.columnConfig.mileFormat = this.mileFormat;
    /* 此处通过column组件的renderCell函数对单元格实际渲染内容进行加工
     */
    const originRenderCell = this.columnConfig.renderCell;
    this.columnConfig.renderCell = (h, data) => {
      let vnode = originRenderCell.call(this, h, data);
      // 实现复制弹出层，需要在外层包裹一层div，用于处理tooltip的显示
      const conf = truncationConf[this.strTruncate] || truncationConf.default;
      if (!this.strTruncate || conf.hoverToShowWhole) {
        vnode = h(
          'div',
          {
            on: {
              contextmenu: (event) => {
                event.preventDefault(); // 阻止浏览器默认菜单的显示
                let cell = event.target;
                const table = this.owner;
                while (cell && cell.tagName.toUpperCase() !== 'HTML') {
                  if (cell.tagName.toUpperCase() === 'TD') {
                    break;
                  } else {
                    cell = cell.parentNode;
                  }
                }
                const tooltip = table.$parent.$refs.copyBtn;
                let content = cell.innerText || cell.textContent;
                if (content && content == '-') return;
                if (content && content.indexOf('*') > 1) {
                  content = data.row[data.column.property];
                }
                tooltip.$emit('setContent', content);
                tooltip.referenceElm = cell;
                tooltip.$refs.popper && (tooltip.$refs.popper.style.display = 'none');
                tooltip.doDestroy();
                tooltip.setExpectedState(true);
                this.activateTooltip(tooltip);
              }
            }
          },
          [vnode]
        );
      }
      // 如果是字符串截断，需要在外层包裹一层div，用于处理tooltip的显示
      if (this.strTruncate && conf.hoverToShowWhole) {
        return h(
          'div',
          {
            on: {
              mouseenter: (event) => {
                let cell = event.target;
                const table = this.owner;
                while (cell && cell.tagName.toUpperCase() !== 'HTML') {
                  if (cell.tagName.toUpperCase() === 'TD') {
                    break;
                  } else {
                    cell = cell.parentNode;
                  }
                }
                const tooltip = table.$parent.$refs.tooltip;
                const content = data.row[data.column.property];
                if (content || content?.length > 1) {
                  tooltip.$emit('setContent', content);
                  tooltip.referenceElm = cell;
                  tooltip.$refs.popper && (tooltip.$refs.popper.style.display = 'none');
                  tooltip.doDestroy();
                  tooltip.setExpectedState(true);
                  this.activateTooltip(tooltip);
                }
              },
              mouseleave: () => {
                const tooltip = this.owner.$parent.$refs.tooltip;
                tooltip.setExpectedState(false);
                tooltip.handleClosePopper();
              }
            }
          },
          [vnode]
        );
      } else {
        return vnode;
      }
    };
  }
};
