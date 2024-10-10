Page({
  data: {},
  onShow() {
    wx.getUserInfo({
      success(res) {
        console.log(res);
      }
    })
  },
  bindtap() {
    wx.chooseMessageFile({
      count: 100,
      success: (res) => {
        console.log(res);
        this.uploadFile(res.tempFiles[0]);
      }
    })
  },
  uploadFile(file) {
    wx.uploadFile({
      filePath: file.path,
      name: file.name,
      url: 'http://localhost:49000/file/upload',
      success(res) {
        console.log(res);
      }
    })
  },
  getGeo() {
    wx.getLocation({
      type: 'wgs84',
      success: function (res) {
        var latitude = res.latitude; // 纬度
        var longitude = res.longitude; // 经度
        var speed = res.speed; // 速度
        var accuracy = res.accuracy; // 精度
        console.log(res);
      }
    })
  }
})