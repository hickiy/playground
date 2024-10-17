<template>
  <div class="el-table-setting flex items-center">
    <div v-if="title" class="title font-bold">{{ title }}</div>
    <div class="grow">
      <slot></slot>
    </div>
    <el-popover width="240" trigger="click">
      <template #reference>
        <div class="ml-3 setting cursor-pointer self-center flex flex-row justify-center items-center">
          <el-icon size="1.5em">
            <Setting />
          </el-icon>
        </div>
      </template>
      <template #default>
        <div class="popover-title">列表展示信息</div>
        <el-checkbox :indeterminate="true">全部（{{ ids.length + '/' + columns.length }}项）</el-checkbox>
        <el-checkbox-group v-model="ids" class="flex flex-col">
          <el-checkbox
            v-for="(c, i) in columns"
            :label="c.label"
            :value="c.id"
            :key="c.id"
            :disabled="!!c.fixed || c.type != 'default'"
            :checked="true"
            @change="columnChange($event, c)"
          ></el-checkbox>
        </el-checkbox-group>
      </template>
    </el-popover>
  </div>
</template>

<script>
export default {
  name: 'table-setting',
  props: ['title', 'setTable'],
  data() {
    return {
      columns: [],
      ids: []
    };
  },
  mounted() {
    this.$nextTick(() => {
      this.columns = [...this.$parent.store?.states?._columns.value];
    });
  },
  methods: {
    columnChange(val, col) {
      const store = this.$parent.store;
      if (val) {
        store.commit('insertColumn', col, null);
      } else {
        store.commit('removeColumn', col, null);
      }
    }
  }
};
</script>

<style lang="scss" scoped>
.el-table-setting {
  width: 100%;
  padding: 12px 8px;
}
.title {
  color: #1e2e4e;
  height: 16px;
  line-height: 16px;
  border-left: 2px solid #0e36ac;
  text-indent: 8px;
}
.setting {
  width: 30px;
  height: 30px;
  border: 1px solid #e5e6eb;
  border-radius: 4px;
}
.popover-title {
  font-size: 16px;
  font-weight: 400;
  color: #86909c;
}
</style>

