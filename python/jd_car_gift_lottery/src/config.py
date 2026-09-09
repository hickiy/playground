"""集中管理项目常量、URL、选择器与关键词。"""

# ---- 页面 URL ----
ACTIVITY_URL = (
    "https://pro.m.jd.com/mall/active/3Rcw1NV6pjiUBpznNHooXjPNAicD/"
    "index.html?babelChannel=ttt1&categoryId=331801&serviceType=jdxc&skuId=100240903791"
)

# ---- 抢购页选择器 / 关键词 ----
# 目标商品卡片：免费小保养（页面稳定命名，非 `__` 哈希类名）
GRAB_CARD_SELECTOR = (
    ".product-info-section:has(.product-title:has-text('免费小保养'))"
)
# 进入后需切换到的分类 Tab
GRAB_TAB_TEXT = "免费保养"
# 兑换按钮候选文本（实测为「立即免费兑换」；售罄时显示「已抢完」）
GRAB_BUTTON_TEXTS = ["立即免费兑换", "立即兑换", "马上抢", "去抢购", "去兑换",
                     "立即领取", "立即抢购"]
SOLD_OUT_TEXT = "已抢完"
# 成功弹窗中常出现的文本（避开页面常驻的“兑换成功用户公示”，避免误判）
SUCCESS_KEYWORDS = ["恭喜您", "领取成功", "恭喜", "已领取", "兑换成功"]
# 常见弹窗/遮罩类名线索，用于定位“成功”弹窗
MODAL_CLASS_HINTS = ["modal", "dialog", "popup", "mask", "toast", "overlay"]
# 点击兑换后弹出的「确认」按钮文案（实测弹窗为「您将使用N积分兑换」，确认按钮为「确认兑换」）
# 仅保留明确的确认/推进文案，避免与主兑换按钮（GRAB_BUTTON_TEXTS 含「立即领取」）混淆
CONFIRM_KEYWORDS = ["确认兑换", "确认领取", "确定兑换", "我知道了", "去使用"]
