import Element from 'element-ui';
// import Table from './el-table/el-table.js';
// import TableColumn from './el-table/el-table-column.js';
// import Upload from './el-upload/el-upload.js';
// import Form from './el-form/el-form.vue';
import Input from './el-input/el-input.js';
// import Image from './el-image/index.vue';

export default function (Vue) {
  Vue.use(Element);
  // Vue.component(Form.name, Form);
  // Vue.component(Table.name, Table);
  // Vue.component(TableColumn.name, TableColumn);
  // Vue.component(Upload.name, Upload);
  Vue.component(Input.name, Input);
  // Vue.component(Image.name, Image);
}
