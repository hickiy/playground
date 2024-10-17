import { Upload } from 'element-ui';
import FileViewer from './upload-list.vue';
import compressImage from '@/utils/compressImg.js';
import request from '@/utils/request.js';

let timer = null;
let beforeUploadMsg = [];

export default {
  name: Upload.name,
  extends: Upload,
  props: {
    // 扩展属性 提供默认的文件校验
    limitSize: {
      type: Number,
      default: 100
    },
    // 扩展属性 质量压缩比例 0.1-1之间的小数 仅上传图片时有效
    qualityScale: {
      type: Number,
      default: 0.8
    },
    // 扩展属性 最小质量 单位MB 小于minQuality不进行压缩（质量、尺寸） 仅上传图片时有效
    minQuality: {
      type: Number,
      default: 1
    },
    // 扩展属性 最小尺寸  小于minWitdh不进行尺寸压缩  仅上传图片时有效
    minWitdh: {
      type: Number,
      default: 800
    },
    multiple: {
      type: Boolean,
      default: true
    },
    beforeUpload: {
      default() {
        return (file) => {
          // 当多个文件同时上传时，设置一个宏任务，在本次微任务循环结束执行，避免当多个文件验证不通过时，弹出多次验证弹窗问题
          if (!timer) {
            timer = window.setTimeout(() => {
              if (beforeUploadMsg.length) {
                this.$message.warning(beforeUploadMsg[0]);
                beforeUploadMsg = [];
              }
              window.clearTimeout(timer);
              timer = null;
            }, 0);
          }
          let regStr = `.(${this.accept.replace(/(,\s+)/g, '|').replace(/\./g, '')})$`;
          // 文件校验逻辑
          if (this.accept && !new RegExp(regStr, 'i').test(file.name)) {
            // 文件校验逻辑, 如果有accept属性，校验文件类型
            beforeUploadMsg.push('文件类型不正确!');
          } else if (this.limitSize && file.size > this.limitSize * 1024 * 1024) {
            // 文件校验逻辑, 如果有limitSize属性，校验文件大小
            beforeUploadMsg.push(`文件超过${this.limitSize}M!`);
          }
          return !beforeUploadMsg.length;
        };
      }
    },
    onSuccess: {
      default() {
        return (res, file, fileList) => {
          let data = res.data;
          try {
            file.fileName = data.name;
            file.fileUrl = data.url;
            file.limitSize = data.size;
            file.fileSuffix = data.type;
            file.url = data.url;
            file.type = data.type;
            file.extraObj = data.extraObj ?? null;
            delete file.raw; // 删除原始文件对象
            delete file.response; // 删除原始响应对象
            if (this.fileList.length != fileList.length) {
              this.fileList.splice(0, this.fileList.length, ...fileList);
            }
            setTimeout(this.dispatch, 0, 'ElFormItem', 'el.form.change');
          } catch (err) {
            console.error(err);
          }
        };
      }
    },
    onRemove: {
      default() {
        return (file) => {
          let i = this.fileList.indexOf(file);
          if (i > -1) this.fileList.splice(i, 1);
          setTimeout(this.dispatch, 0, 'ElFormItem', 'el.form.change');
        };
      }
    },
    onExceed: {
      default() {
        return () => {
          this.$message.warning(`最多上传${this.limit}个文件`);
        };
      }
    },
    onError: {
      default() {
        return (err) => {
          // 上传失败时，删除上传的文件
          this.fileList.splice(0, this.fileList.length - 1);
          // 触发表单change事件，用于表单验证
          setTimeout(this.dispatch, 0, 'ElFormItem', 'el.form.change');
        };
      }
    },
    // 自定义上传行为
    httpRequest: {
      type: Function,
      default(option) {
        // 上传方法
        function upload() {
          // 生成formData
          const formData = new FormData();
          // 添加额外参数
          if (option.data) {
            Object.keys(option.data).forEach(key => {
              formData.append(key, option.data[key]);
            });
          }
          // 添加文件
          formData.append(option.filename, option.file, option.file.name);
          request({
            url: option.action,
            method: 'post',
            data: formData,
            headers: {
              'Content-Type': 'multipart/form-data',
              ...option.headers,
              repeatSubmit: false
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
        // 上传文件前，判断文件是否需要压缩
        if (/image\/.*/.test(option.file.type) && option.file.size > this.minQuality * 1024 * 1024) {
          compressImage(option.file, this.qualityScale, this.minWitdh)
            .then((blob) => {
              const file = new File([blob], option.file.name, { type: blob.type });
              option.file = file;
              upload();
            })
            .catch((err) => {
              err.msg = '图片压缩失败';
              option.onError(err);
            });
        } else {
          upload();
        }
      }
    }
  },
  render(h) {
    if (this.listType != 'text') {
      this.$scopedSlots.file = (props) => {
        return h(FileViewer, {
          props: { ...props, uploadFiles: this.uploadFiles, onPriview: this.OnPreview, fileUpload: this.reupload },
          on: {
            remove: (file) => {
              let i = this.uploadFiles.indexOf(file);
              if (i > -1) this.uploadFiles.splice(i, 1);
              this.onRemove(file, this.uploadFiles);
            }
          }
        });
      };
    }
    return Upload.render.call(this, h);
  },
  methods: {
    handleError(err, rawFile) {
      const file = this.getFile(rawFile);
      file.status = 'fail';
      this.onError(err, file, this.uploadFiles);
    },
    reupload(file) {
      file.status = 'ready';
      this.submit();
    },
    dispatch(componentName, eventName, params) {
      var parent = this.$parent || this.$root;
      var name = parent.$options.componentName;

      while (parent && (!name || name !== componentName)) {
        parent = parent.$parent;

        if (parent) {
          name = parent.$options.componentName;
        }
      }
      if (parent) {
        parent.$emit.apply(parent, [eventName].concat(params));
      }
    }
  }
};
