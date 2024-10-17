<script lang="jsx">
import { Form, Button } from 'element-ui';
export default {
  name: Form.name,
  extends: Form,
  data() {
    return {
      showCollapse: false,
      isCollapse: true
    };
  },
  computed: {
    hasAppend() {
      return this.$slots.expand && this.inline;
    }
  },
  mounted() {
    this.showCollapse = this.$refs.formWrap?.scrollHeight > this.$refs.formWrap?.clientHeight;
  },
  render(h) {
    const vnode = Form.render.call(this, h);
    if (this.hasAppend) {
      return (
        <div
          class={[
            'flex flex-row overflow-hidden justify-between',
            this.isCollapse ? `${this.size ?? 'default'}-height` : ''
          ]}
          ref="formWrap"
        >
          <div>{vnode}</div>
          <div class="flex-shrink-0">
            {this.$slots.expand}
            {this.showCollapse && (
              <el-link type="primary" class="ml-1" underline={false} onClick={() => (this.isCollapse = !this.isCollapse)}>
                {this.isCollapse ? '展开' : '收起'}
                <i class={['mr-1 text-base', this.isCollapse ? 'el-icon-arrow-down' : 'el-icon-arrow-up']} />
              </el-link>
            )}
          </div>
        </div>
      );
    } else {
      return vnode;
    }
  }
};
</script>

<style lang="scss" , scoped>
.mini-height {
  height: 47px;
}
.small-height {
  height: 51px;
}
.medium-height {
  height: 58px;
}
.default-height {
  height: 62px;
}
</style>
