<template>
  <div class="el-table-setting fl-r ai-c">
    <div v-if="title" class="title fs16 fw-b">{{ title }}</div>
    <div class="fl-r f1 jc-fe ai-c">
      <slot></slot>
      <div class="setting fl-r jc-c ai-c cs-po">
        <el-popover placement="bottom-start" width="240" trigger="click">
          <i slot="reference" class="el-icon-s-tools fs20 pointer" style="margin-top: 4px"></i>
          <div class="popover-title">列表展示信息</div>
          <el-checkbox class="mb15" :indeterminate="true"
            >全部（{{ ids.length + '/' + columns.length }}项）</el-checkbox
          >
          <el-checkbox-group v-model="ids" class="fl-c">
            <el-checkbox
              class="mb10"
              v-for="(c, i) in columns"
              :label="c.id"
              :key="c.id"
              :disabled="checkin(c)"
              :checked="true"
              @change="columnChange($event, c, i)"
              >{{ c.label }}</el-checkbox
            >
          </el-checkbox-group>
        </el-popover>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'el-table-setting',
  props: ['title', 'setTable'],
  data() {
    return {
      columns: [],
      ids: []
    };
  },
  mounted() {
    this.$nextTick(() => {
      this.columns = [...this.$parent.$refs['origin-table'].store.states._columns];
    });
  },
  methods: {
    checkin(col) {
      return !!col.fixed || !col.property || col.type != 'default' || !col.canFilter;
    },
    // TODO 将过滤后的列配置通过事件抛出
    columnChange(val, col, index) {
      const store = this.$parent.$refs['origin-table'].store;
      if (val) {
        store.commit('insertColumn', col, index, null);
      } else {
        store.commit('removeColumn', col, null);
      }
      this.$parent.$refs['origin-table'].doLayout();
    }
  }
};
</script>

<style lang="scss" scoped>
.el-table-setting {
  width: 100%;
  padding: 12px 8px;
  min-height: 30px;
}
.title {
  color: #1e2e4e;
  height: 16px;
  line-height: 16px;
  border-left: 2px solid #0e36ac;
  text-indent: 8px;
}
.setting {
  width: 36px;
  border-radius: 2px 2px 2px 2px;
  border: 1px solid #e5e6eb;
  margin-left: 8px;
}
.popover-title {
  font-size: 16px;
  font-weight: 400;
  color: #86909c;
  margin-bottom: 25px;
}
</style>
