import { ElTableColumn } from 'element-plus';
import { numSection } from '@/utils/formatNum';
import { strMask } from '@/utils/formatStr';
import { getCurrentInstance } from 'vue';

// 字符串截断配置
const truncationConf = {
  brCode: { // 电池编码
    startNum: 5, // 开始显示的字符数
    separator: '***', // 分隔符
    endNum: 5, // 结尾显示的字符数
    hoverToShowWhole: true // 鼠标悬浮是否显示全部内容
  },
  idCard: { // 身份证号
    startNum: 2,
    separator: '***',
    endNum: 4,
    hoverToShowWhole: false
  },
  phoneNumber: { // 手机号
    startNum: 3,
    separator: '***',
    endNum: 4,
    hoverToShowWhole: false
  },
  vin: { // 车架号
    startNum: 3,
    separator: '***',
    endNum: 4,
    hoverToShowWhole: true
  },
  default: { // 默认配置
    startNum: 3,
    separator: '***',
    endNum: 4,
    hoverToShowWhole: true
  }
};

export default {
  extends: ElTableColumn,
  props: {
    /**
     * 此处重写align属性, 为了保证用户传递的align具有最高优先级
     * 因此再值为null时, 表示用户没有传递align属性
     * 再用户未传递align属性时, 可以根据一些格式化属性来设置align属性
     * 具体逻辑在setup中实现，因为在props初始化阶段无法获取父组件传递的props
     */
    align: {
      type: String,
      default: null
    },
    /**
     * 设置字符串截断方式，用于敏感信息的展示
     * 默认为null，不进行截断
     * 如果为true，则使用默认的截断配置
     * 如果为字符串，则使用指定的截断配置
     */
    strTruncate: {
      type: [Boolean, String],
      default: null
    },
    /**
     * 设置数字格式化，用于金额等数字的展示
     * 默认为null，不进行格式化
     * 如果为true，则默认保留两位小数
     * 如果为数字，则保留指定位数的小数
     */
    numFormat: {
      type: [Boolean, Number],
      default: null
    },
    formatter: {
      default() {
        const instance = getCurrentInstance();
        return (row, col, val) => {
          const { numFormat, strTruncate } = instance.props;
          if (val === '' || val == null) {
            return '-';
          } else if (numFormat !== null) {
            return numSection(val, typeof numFormat == 'number' ? numFormat : 2);
          } else if (strTruncate !== null) {
            const conf = truncationConf[strTruncate] ?? truncationConf.default;
            return strMask(val, conf);
          } else {
            return val;
          }
        }
      }
    }
  },
  setup(props, ctx) {
    /**
     * 这里用于实现按照字段类型进行自定义的对齐设置
     * 由于vue3中的props是只读的，无法修改，因此创建影子props, 用于拦截align的读取
     * 当align为真，意味着用户传递了align属性，优先使用用户传递的align
     * 当align为假，表示用户未传递align属性，此时根据字段类型定义对齐方式
     * 如果以上规则都不符合，则默认为左对齐（left）与element-plus默认一致
     */
    const shadowProps = new Proxy(props, {
      get(target, key, receiver) {
        if (key == 'align') {
          const align = Reflect.get(target, key, receiver);
          const numFormat = Reflect.get(target, 'numFormat', receiver);
          if (align) {
            return align;
          } else if (numFormat !== null) {
            return 'right';
          } else {
            return 'left';
          }
        } else {
          return Reflect.get(target, key, receiver);
        }
      }
    });
    return ElTableColumn.setup(shadowProps, ctx);
  }
}
