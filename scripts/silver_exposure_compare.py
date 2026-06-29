"""白银 exposure 对比 + 601212 PB 安全边际图

对比三只「带银」A股，判定谁是干净的白银敞口；并给 601212 出 PB 分位/安全边际图。
- 盛达资源 000603：国内最大原生银生产商（银主业纯正）
- 兴业银锡 000426：银 + 锡 + 铅锌（银/锡双主线）
- 白银有色 601212：主业铜冶炼，银仅副产品（名字「白银」=甘肃白银市，非金属）

输出 4 张图到 research/assets/，并把统计写到 stdout + scratchpad/silver_stats.json 供 md 引用。
用法：python scripts/silver_exposure_compare.py
"""
import json
import time
import warnings
from pathlib import Path

import akshare as ak
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")
plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path("/Users/arthur.lee/codes/quantlab")
ASSETS = ROOT / "research" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)
SCRATCH = Path("/private/tmp/claude-501/-Users-arthur-lee-codes-quantlab-research/"
               "b563e99d-1dc1-4dbc-ae33-ab87bf580ae4/scratchpad")

RED, GREEN, BLUE, GOLD = "#c0392b", "#1e8449", "#2471a3", "#b8860b"
GREY = "#7f8c8d"


def retry(fn, *a, **k):
    for i in range(5):
        try:
            return fn(*a, **k)
        except Exception as e:  # noqa
            if i == 4:
                print("FAIL", getattr(fn, "__name__", fn), str(e)[:90])
                return None
            time.sleep(1.5)


STOCKS = {  # 显示名 -> (sina代码, em代码, 一句话主业)
    "盛达资源": ("sz000603", "000603", "原生银龙头·银主业纯正"),
    "兴业银锡": ("sz000426", "000426", "银+锡+铅锌·双主线"),
    "白银有色": ("sh601212", "601212", "铜冶炼为主·银仅副产品"),
}
COLORS = {"盛达资源": GREEN, "兴业银锡": GOLD, "白银有色": RED}


def fut(sym):
    h = retry(ak.futures_main_sina, symbol=sym)
    c = [x for x in h.columns if "日期" in x][0]
    v = [x for x in h.columns if "收盘" in x][0]
    h[c] = pd.to_datetime(h[c])
    return h.set_index(c).sort_index()[v].astype(float)


print("拉商品主连 …")
ag, cu, au = fut("AG0"), fut("CU0"), fut("AU0")

print("拉个股价格(前复权) …")
px, pb = {}, {}
for name, (scode, ecode, _) in STOCKS.items():
    d = retry(ak.stock_zh_a_daily, symbol=scode, adjust="qfq")
    d["date"] = pd.to_datetime(d["date"])
    px[name] = d.set_index("date")["close"].astype(float)
    v = retry(ak.stock_value_em, symbol=ecode)
    if v is not None and len(v):
        dcol = [c for c in v.columns if "日期" in str(c)][0]
        v[dcol] = pd.to_datetime(v[dcol])
        v = v.set_index(dcol).sort_index()
        pb[name] = pd.to_numeric(v["市净率"], errors="coerce").dropna()
    time.sleep(0.5)

now = min(s.index[-1] for s in px.values())
stats = {"as_of": str(now.date()), "stocks": {}}


# ---------- 相关性 / β / 本轮回撤 ----------
def beta(stock_ret, factor_ret):
    df = pd.concat([stock_ret, factor_ret], axis=1).dropna()
    if len(df) < 30:
        return np.nan, np.nan
    s, f = df.iloc[:, 0], df.iloc[:, 1]
    b = np.cov(s, f)[0, 1] / np.var(f)
    r = np.corrcoef(s, f)[0, 1]
    return b, r


win_start = now - pd.Timedelta(days=365)
for name in STOCKS:
    p = px[name]
    sr = p.pct_change()[lambda x: x.index >= win_start]
    row = {}
    for fac_name, fac in [("银", ag), ("铜", cu), ("金", au)]:
        b, r = beta(sr, fac.pct_change())
        row[f"beta_{fac_name}"] = round(float(b), 2)
        row[f"corr_{fac_name}"] = round(float(r), 2)
    # 本轮：2026-01 见顶
    y = p[p.index >= now - pd.Timedelta(days=420)]
    peak = float(y.max())
    peak_d = y.idxmax()
    trough_since = p[p.index >= peak_d]
    row["cycle_peak"] = round(peak, 2)
    row["cycle_peak_date"] = str(peak_d.date())
    row["last"] = round(float(p.iloc[-1]), 2)
    row["dd_from_peak"] = round((p.iloc[-1] / peak - 1) * 100, 1)
    row["max_dd"] = round((trough_since.min() / peak - 1) * 100, 1)
    # 本轮自低点涨幅（炒作幅度）：取 2024 低点
    base = p[(p.index >= "2024-06-01") & (p.index <= "2025-03-01")]
    if len(base):
        lo = float(base.min())
        row["run_up_pct"] = round((peak / lo - 1) * 100, 0)
        row["base_low"] = round(lo, 2)
    stats["stocks"][name] = row

# PB 分位
for name in STOCKS:
    if name not in pb:
        continue
    s = pb[name]
    cur = float(s.iloc[-1])
    pct = float((s < cur).mean() * 100)
    med = float(s.median())
    lo = float(s.min())
    stats["stocks"][name].update({
        "pb": round(cur, 2), "pb_pct": round(pct, 1),
        "pb_min": round(lo, 2), "pb_med": round(med, 2), "pb_max": round(float(s.max()), 2),
        "pb_hist_from": str(s.index[0].date()),
        # 安全边际：现价跌到 PB 中位 / PB 底 对应的价位
        "price_at_pb_med": round(stats["stocks"][name]["last"] * med / cur, 2),
        "price_at_pb_min": round(stats["stocks"][name]["last"] * lo / cur, 2),
    })

# ---------- 主营构成：银占毛利比例（谁是干净的银敞口的硬证据） ----------
SILVER_LINES = ("电银", "银精粉", "矿产银", "银锭")  # 显性以银为主的产品行
comp = {}
for name, (scode, ecode, _) in STOCKS.items():
    sym = ("SH" if scode.startswith("sh") else "SZ") + ecode
    df = retry(ak.stock_zygc_em, symbol=sym)
    if df is None or not len(df):
        continue
    df = df[df["分类类型"] == "按产品分类"].copy()
    dcol = [c for c in df.columns if "报告" in c or "日期" in c or "截止" in c]
    if dcol:
        df = df[df[dcol[0]] == df[dcol[0]].max()]
    df["利润比例"] = pd.to_numeric(df["利润比例"], errors="coerce")
    comp[name] = df[["主营构成", "利润比例"]].reset_index(drop=True)
    ag_share = df[df["主营构成"].str.contains("|".join(SILVER_LINES))]["利润比例"].sum()
    stats["stocks"][name]["silver_profit_share"] = round(float(ag_share) * 100, 1)

SCRATCH.mkdir(parents=True, exist_ok=True)
(SCRATCH / "silver_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2))
print(json.dumps(stats, ensure_ascii=False, indent=2))


# ================= 图 1：归一化走势（本轮泡沫+崩盘） =================
def normalize(s, base_date="2024-06-03"):
    s = s[s.index >= base_date]
    return s / s.iloc[0] * 100


fig, ax = plt.subplots(figsize=(13, 6.5))
ax.plot(normalize(ag).index, normalize(ag).values, color="#34495e", lw=2.6,
        label="沪银 AG0(银价基准)", zorder=5)
for name in STOCKS:
    n = normalize(px[name])
    ax.plot(n.index, n.values, color=COLORS[name], lw=1.7, alpha=0.9,
            label=f"{name} {STOCKS[name][2]}")
ax.axhline(100, color=GREY, lw=0.8, ls="--")
ax.axvline(pd.Timestamp("2026-01-29"), color=GREY, lw=1.0, ls=":")
ax.text(pd.Timestamp("2026-01-29"), ax.get_ylim()[1] * 0.96, " 银价见顶 2026-01-29",
        color=GREY, fontsize=9, va="top")
ax.set_ylabel("归一化(2024-06=100)", fontsize=11)
ax.set_title("图1｜本轮白银泡沫与崩盘中，三只「带银」A股谁在跟银价走\n"
             "（同涨同跌≈银敞口；涨跌幅度差≈杠杆/题材溢价）", fontsize=12.5)
ax.legend(loc="upper left", fontsize=10)
ax.grid(alpha=0.25)
fig.savefig(ASSETS / "白银敞口_归一化走势.png", dpi=130, bbox_inches="tight")
plt.close(fig)


# ================= 图 2：对 银/铜/金 的 β 与相关性 =================
fig, (axL, axR) = plt.subplots(1, 2, figsize=(14, 5.5), gridspec_kw={"wspace": 0.22})
names = list(STOCKS)
facs = ["银", "铜", "金"]
fcolors = {"银": "#34495e", "铜": "#cd7f32", "金": GOLD}
x = np.arange(len(names))
w = 0.25
for j, f in enumerate(facs):
    vals = [stats["stocks"][n][f"beta_{f}"] for n in names]
    bars = axL.bar(x + (j - 1) * w, vals, w, label=f"对{f}", color=fcolors[f])
    for xi, v in zip(x + (j - 1) * w, vals):
        axL.text(xi, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=8.5)
axL.set_xticks(x)
axL.set_xticklabels(names, fontsize=10)
axL.set_ylabel("β（个股收益对商品收益的弹性）", fontsize=10)
axL.set_title("近1年 β：谁对银价弹性最大", fontsize=11)
axL.legend(fontsize=9)
axL.grid(alpha=0.25, axis="y")
for j, f in enumerate(facs):
    vals = [stats["stocks"][n][f"corr_{f}"] for n in names]
    axR.bar(x + (j - 1) * w, vals, w, label=f"对{f}", color=fcolors[f])
    for xi, v in zip(x + (j - 1) * w, vals):
        axR.text(xi, v + 0.01, f"{v:.2f}", ha="center", va="bottom", fontsize=8.5)
axR.set_xticks(x)
axR.set_xticklabels(names, fontsize=10)
axR.set_ylabel("相关系数", fontsize=10)
axR.set_title("近1年 相关性：跟谁走得最近", fontsize=11)
axR.legend(fontsize=9)
axR.grid(alpha=0.25, axis="y")
fig.suptitle("图2｜谁是「干净的白银敞口」——对银的 β/相关性越高、对铜越低，越纯", fontsize=13)
fig.savefig(ASSETS / "白银敞口_beta相关性.png", dpi=130, bbox_inches="tight")
plt.close(fig)


# ================= 图 3：601212 PB 温度计 / 安全边际 =================
name = "白银有色"
s = pb[name]
cur = float(s.iloc[-1])
med, lo, hi = s.median(), s.min(), s.max()
p20, p80 = s.quantile(0.20), s.quantile(0.80)
fig, ax = plt.subplots(figsize=(13, 6.5))
ax.axhspan(lo, p20, color=GREEN, alpha=0.10)
ax.axhspan(p80, hi, color=RED, alpha=0.10)
ax.plot(s.index, s.values, color="#2c3e50", lw=1.3)
for yv, txt, col in [(lo, f"历史底 {lo:.2f}", GREEN),
                     (med, f"中位 {med:.2f}", BLUE),
                     (p80, f"80分位 {p80:.2f}", RED)]:
    ax.axhline(yv, color=col, lw=1.1, ls="--")
    ax.text(s.index[0], yv, f" {txt}", color=col, fontsize=9.5, va="bottom")
ax.scatter([s.index[-1]], [cur], color=RED, zorder=6, s=70)
ax.annotate(f"当前 PB {cur:.2f}（{stats['stocks'][name]['pb_pct']:.0f}分位）",
            (s.index[-1], cur), textcoords="offset points", xytext=(-160, 10),
            color=RED, fontsize=11, fontweight="bold")
ax.text(0.015, 0.06,
        f"现价 {stats['stocks'][name]['last']}元；按 PB 回到中位→约 "
        f"{stats['stocks'][name]['price_at_pb_med']}元(再{(stats['stocks'][name]['price_at_pb_med']/stats['stocks'][name]['last']-1)*100:+.0f}%)，"
        f"回到历史底→约 {stats['stocks'][name]['price_at_pb_min']}元"
        f"(再{(stats['stocks'][name]['price_at_pb_min']/stats['stocks'][name]['last']-1)*100:+.0f}%)",
        transform=ax.transAxes, fontsize=10.5, color="#34495e",
        bbox=dict(boxstyle="round", fc="#fdf6e3", ec=GREY))
ax.set_ylabel("市净率 PB", fontsize=11)
ax.set_title(f"图3｜601212 白银有色 PB 安全边际图（自 {stats['stocks'][name]['pb_hist_from']}）\n"
             "跌了66%，PB 仍在历史中上区——估值无安全边际，绿区才是「机会区」", fontsize=12.5)
ax.grid(alpha=0.25)
fig.savefig(ASSETS / "601212_PB安全边际.png", dpi=130, bbox_inches="tight")
plt.close(fig)


# ================= 图 4：三股 PB 分位横向对比 =================
fig, ax = plt.subplots(figsize=(12, 6))
ys = np.arange(len(names))[::-1]
for yi, name in zip(ys, names):
    if name not in pb:
        continue
    s = pb[name]
    lo, med, hi, cur = s.min(), s.median(), s.max(), float(s.iloc[-1])
    pct = stats["stocks"][name]["pb_pct"]
    ax.hlines(yi, lo, hi, color=GREY, lw=3, alpha=0.5)
    ax.plot(med, yi, "|", color=BLUE, ms=18, mew=2.5)
    ax.scatter(cur, yi, color=COLORS[name], s=130, zorder=6)
    ax.text(cur, yi + 0.20, f"当前PB {cur:.2f}（{pct:.0f}分位）",
            ha="center", fontsize=10, color=COLORS[name], fontweight="bold")
    # 底/中位标签上下错位，避免数值接近时重叠
    ax.text(lo, yi - 0.22, f"底{lo:.2f}", fontsize=8.5, color=GREEN, ha="center")
    ax.text(med, yi - 0.40, f"中位{med:.2f}", fontsize=8.5, color=BLUE, ha="center")
ax.set_yticks(ys)
ax.set_yticklabels([f"{n}\n{STOCKS[n][2]}" for n in names], fontsize=10)
ax.set_ylim(-0.95, len(names) - 1 + 0.95)
ax.set_xlim(0, max(pb[n].max() for n in names if n in pb) * 1.03)
ax.set_xlabel("市净率 PB（灰线=历史区间，蓝| =中位，圆点=当前）", fontsize=10.5)
ax.set_title("图4｜三股 PB 历史分位对比：当前估值离各自「历史底」还有多远",
             fontsize=12.5, pad=14)
ax.grid(alpha=0.2, axis="x")
fig.savefig(ASSETS / "白银敞口_PB分位对比.png", dpi=130, bbox_inches="tight")
plt.close(fig)

# ================= 图 5：主营毛利构成（银占多少） =================
# 100% 堆叠：把亏损行(利润比例<0)裁为0后归一，银行高亮
fig, ax = plt.subplots(figsize=(12, 5.5))
ys = np.arange(len(names))[::-1]
for yi, name in zip(ys, names):
    if name not in comp:
        continue
    df = comp[name].copy()
    df["w"] = df["利润比例"].clip(lower=0)
    tot = df["w"].sum()
    if tot <= 0:
        continue
    df["w"] = df["w"] / tot
    df = df.sort_values("w", ascending=False)
    left = 0.0
    for _, r in df.iterrows():
        is_ag = any(k in r["主营构成"] for k in SILVER_LINES)
        col = "#34495e" if is_ag else "#d5dbdb"
        ax.barh(yi, r["w"], left=left, color=col, edgecolor="white", height=0.55)
        if r["w"] > 0.07:
            ax.text(left + r["w"] / 2, yi, r["主营构成"].replace("(含银)", "").replace("(含金)", ""),
                    ha="center", va="center", fontsize=8.5,
                    color="white" if is_ag else "#34495e")
        left += r["w"]
    ax.text(1.012, yi, f"银占毛利 {stats['stocks'][name]['silver_profit_share']:.0f}%",
            va="center", fontsize=10.5, color="#34495e", fontweight="bold")
ax.set_yticks(ys)
ax.set_yticklabels([f"{n}\n{STOCKS[n][2]}" for n in names], fontsize=10)
ax.set_xlim(0, 1.0)
ax.set_xlabel("毛利构成(FY2025，亏损产品已剔除并归一；深色=以银为主的产品)", fontsize=10)
ax.set_title("图5｜「银占毛利」才是硬证据：兴业银锡 40% > 盛达资源 ~29%（另铅锌精粉含银）> 白银有色 12%\n"
             "601212 主业阴极铜毛利率≈0，银只是零头——名字带「白银」≠ 白银股", fontsize=12)
fig.savefig(ASSETS / "白银敞口_毛利构成.png", dpi=130, bbox_inches="tight")
plt.close(fig)

print("\n图表已输出 research/assets/：")
for f in ["白银敞口_归一化走势.png", "白银敞口_beta相关性.png",
          "601212_PB安全边际.png", "白银敞口_PB分位对比.png", "白银敞口_毛利构成.png"]:
    print("  -", f)
