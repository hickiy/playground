/*  hickey 2023/11/7 */
import { ElUpload, ElMessage, useFormItem } from 'element-plus';
import request from '@/utils/request';
import { getCurrentInstance, h } from 'vue';
import FileSlot from './file-slot.vue';

export default {
  extends: ElUpload,
  props: {
    action: {
      type: String,
      default: '/ems/upload'
    },
    listType: {
      type: String,
      default: 'picture-card'
    },
    limitSize: {
      type: Number,
      default: 10
    },
    beforeUpload: {
      default(props) {
        const instance = getCurrentInstance();
        return function (file) {
          // 当多个文件同时上传时，设置一个宏任务，在本次微任务循环结束执行，避免当多个文件验证不通过时，弹出多次验证弹窗问题
          instance.beforeUploadMsg = [];
          if (!instance.timer) {
            instance.timer = window.setTimeout(() => {
              if (instance.beforeUploadMsg?.length) {
                ElMessage.warning(instance.beforeUploadMsg[0]);
                instance.beforeUploadMsg = [];
              }
              window.clearTimeout(instance.timer);
              instance.timer = null;
            }, 0);
          }
          let regStr = `.(${props.accept.replace(/(,\s+)/g, '|').replace(/\./g, '')})$`;
          if (props.accept && !new RegExp(regStr, 'i').test(file.name)) {
            // 校验文件类型，不符合则提示，如果不存在accept属性，则不校验
            instance.beforeUploadMsg.push('文件类型不正确!');
          } else if (instance.limitSize && file.size > instance.limitSize * 1024 * 1024) {
            // 校验文件大小，不符合则提示，如果不存在limitSize属性，则不校验
            instance.beforeUploadMsg.push(`文件超过${instance.limitSize}M!`);
          }
          return !instance.beforeUploadMsg.length;
        };
      }
    },
    onSuccess: {
      default() {
        const instance = getCurrentInstance();
        return (res, file, fileList) => {
          const data = res.data;
          file.fileName = data.name;
          file.fileUrl = data.url;
          file.limitSize = data.size;
          file.fileSuffix = data.type;
          file.url = data.url;
          file.type = data.type;
          file.extraObj = data.extraObj ?? null;
          delete file.raw; // 删除原始文件对象
          delete file.response; // 删除原始响应对象
          instance.formItem?.validate?.('change');
        };
      }
    },
    onExceed: {
      type: Function,
      default(file, fileList) {
        ElMessage.warning(`最多上传${fileList?.length}个文件`);
      }
    },
    onRemove: {
      default() {
        const instance = getCurrentInstance();
        return () => {
          instance.formItem?.validate?.('change');
        };
      }
    },
    onChange: {
      default() {
        const instance = getCurrentInstance();
        return () => {
          setTimeout(() => {
            instance.formItem?.validate?.('change');
          }, 0);
        };
      }
    },
    httpRequest: {
      type: Function,
      default(option) {
        const formData = new FormData();
        if (option.data) {
          for (const [key, value] of Object.entries(option.data)) {
            if (Array.isArray(value) && value.length) formData.append(key, ...value);
            else formData.append(key, value);
          }
        }
        formData.append(option.filename, option.file, option.file.name);

        request({
          url: option.action,
          method: 'post',
          data: formData,
          headers: {
            'Content-Type': 'multipart/form-data',
            ...option.headers
          },
          withCredentials: option.withCredentials,
          onUploadProgress(evt) {
            evt.percent = evt.total > 0 ? (evt.loaded / evt.total) * 100 : 0;
            option.onProgress(evt);
          }
        })
          .then((res) => {
            option.onSuccess(res);
          })
          .catch((err) => {
            option.onError(err);
          });
      }
    }
  },
  setup(props, ctx) {
    const { form, formItem } = useFormItem();
    const render = ElUpload.setup(props, ctx);
    // 处理表单校验
    var instance = getCurrentInstance();
    instance.formItem = formItem;
    instance.form = form;
    const fileSlot = (scopes) => [h(FileSlot, {
      ...scopes,
      disabled: props.disabled,
      remove: (file) => {
        let i = props.fileList.indexOf(file);
        if (i > -1) props.fileList.splice(i, 1);
        props.onRemove(file, props.fileList);
      },
      // TODO: 在自动上传禁用时，点击上传按钮上传文件
      upload(file) { }
    })];
    return (...args) => {
      // fileSlot插槽
      if (props.listType == 'picture-card') {
        ctx.slots.file = fileSlot;
      };
      return render(...args);
    }
  },
};
