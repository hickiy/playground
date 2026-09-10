"""集中管理项目常量、URL、选择器与关键词。"""

# ---- 页面 URL ----
ACTIVITY_URL = (
    "https://pro.m.jd.com/mall/active/3Rcw1NV6pjiUBpznNHooXjPNAicD/"
    "index.html?babelChannel=ttt1&categoryId=331801&serviceType=jdxc&skuId=100240903791"
)

# ---- 抢购页关键词 ----
# 兑换按钮候选文本（实测为「立即免费兑换」；售罄时显示「已抢完」）
GRAB_BUTTON_TEXTS = ["立即免费兑换", "立即兑换", "马上抢", "去抢购", "去兑换",
                     "立即领取", "立即抢购"]
# 点击兑换后弹出的「确认」按钮文案（实测弹窗为「您将使用N积分兑换」，
# 确认按钮为「确认兑换」）
CONFIRM_KEYWORDS = ["确认兑换", "确认领取", "确定兑换", "我知道了", "去使用"]
