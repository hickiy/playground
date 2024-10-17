import { ElForm } from 'element-plus';
export default {
  name: 'ElForm',
  extends: ElForm,
  setup(props, ctx) {
    const render = ElForm.setup(props, ctx);
    const hasAppend = ctx.slots.append && props.inline;
    const isCollapse = ref(true);
    const wrapRef = ref(null);
    const showCollapse = ref(false);
    onMounted(() => {
      if (hasAppend) {
        // 当el-form的label-width设置为auto时，它会在布局过程中动态计算label的宽度
        // 此处等待el-form计算完label的宽度，在下一个事件循环中获取wrapRef的scrollHeight和clientHeight，
        setTimeout(() => {
          showCollapse.value = wrapRef.value?.scrollHeight > wrapRef.value?.clientHeight;
        }, 0);
      }
    });
    return (...arg) => {
      return hasAppend
        ? [
            <div
              class={['flex flex-row overflow-hidden justify-between', isCollapse.value ? 'h-62px' : '']}
              ref={wrapRef}
            >
              {render(...arg)}
              <div class="flex-shrink-0">
                {...ctx.slots.append()}
                {showCollapse.value && (
                  <el-button link type="primary" onClick={() => (isCollapse.value = !isCollapse.value)}>
                    {isCollapse.value ? '展开' : '收起'}
                    <el-icon>{isCollapse.value ? <ArrowDownBold /> : <ArrowUpBold />}</el-icon>
                  </el-button>
                )}
              </div>
            </div>
          ]
        : render(...arg);
    };
  }
};
