// pages/pdfview/index.js
Page({

  /**
   * 页面的初始数据
   */
  data: {
  },

  onMessage(e) {
    console.log('Received message from web-view:', e.detail.data);
  },
})