"""spec → 차트 PNG 생성 (matplotlib). 루브릭 막대·갭 막대·포지셔닝 산점도."""
from __future__ import annotations
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 한글 폰트 자동 선택(설치된 것 중)
def _korean_font():
    for cand in ["AppleGothic", "Apple SD Gothic Neo", "Noto Sans CJK KR",
                 "Noto Sans KR", "Malgun Gothic", "NanumGothic"]:
        try:
            font_manager.findfont(cand, fallback_to_default=False)
            return cand
        except Exception:
            continue
    return None

_KF = _korean_font()
if _KF:
    plt.rcParams["font.family"] = _KF
plt.rcParams["axes.unicode_minus"] = False

INK = "#2B1B4D"
PINK = "#E0457B"
PURPLE = "#5B3FA0"
PURPLE_DK = "#3D2A6B"
GREEN = "#3FA864"
ORANGE = "#E08E0B"
RED = "#C0392B"
SHOP_COLORS = [PINK, "#7B5FC0", PURPLE_DK, "#9C8AC8", "#C9BFE6", "#6A5AA0", "#B9A9DC"]


def rubric_bar(spec, out_path):
    """슬라이드 9: 항목별 루브릭 점수(자사 강조 + 경쟁사)."""
    items = ["Thumbnail", "Shop main", "Localization", "Promo design", "Consistency"]
    keys = ["thumbnail", "shop_main", "localization", "promo_design", "consistency"]
    shops = spec["shops"]
    ds = spec["design_scores"]
    n = len(shops)
    fig, ax = plt.subplots(figsize=(7.4, 4.3), dpi=150)
    width = 0.8 / n
    import numpy as np
    x = np.arange(len(items))
    for i, sh in enumerate(shops):
        sid = sh["id"]
        vals = [ds[sid][k] for k in keys]
        own = sh["role"] == "own"
        ax.bar(x + i * width, vals, width,
               label=("★ " if own else "") + sh["name"],
               color=SHOP_COLORS[i % len(SHOP_COLORS)],
               edgecolor="white", linewidth=0.4, zorder=3)
    ax.set_xticks(x + width * (n - 1) / 2)
    ax.set_xticklabels(items, fontsize=10)
    ax.set_ylim(0, 5.4)
    ax.set_ylabel("Rubric score (1-5)", fontsize=10, color=INK)
    ax.set_title("Design Rubric by Item  (own shops lead)", fontsize=13, color=INK, weight="bold", pad=12)
    ax.legend(ncol=min(n, 4), fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.10), frameon=False)
    ax.grid(axis="y", color="#E3DFF0", zorder=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def gap_bar(spec, out_path):
    """슬라이드 12: 자사 vs 그룹 1위 달성률(%) 가로 막대."""
    rows = sorted(spec["gap"], key=lambda g: g["achievement_pct"], reverse=True)
    labels = [g["label"] for g in rows]
    vals = [g["achievement_pct"] for g in rows]

    def color_for(v):
        return GREEN if v >= 90 else (PINK if v >= 80 else (ORANGE if v >= 60 else RED))

    fig, ax = plt.subplots(figsize=(7.0, 4.3), dpi=150)
    y = range(len(labels))
    ax.barh(list(y), vals, color=[color_for(v) for v in vals], zorder=3, height=0.62)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(0, 112)
    ax.axvline(100, color="#B9B0D0", linestyle="--", linewidth=1, zorder=2)
    for i, v in enumerate(vals):
        ax.text(v + 2, i, f"{v:.0f}%", va="center", fontsize=10, weight="bold", color=INK)
    own_name = next((g["leader_shop"] for g in rows), "")
    ax.set_title("Gap Analysis · BOH vs Group Leader (100% = leader)", fontsize=12.5,
                 color=INK, weight="bold", pad=12)
    ax.set_xlabel("Achievement vs group leader (%)", fontsize=10, color=INK)
    ax.grid(axis="x", color="#E3DFF0", zorder=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def positioning_price_review(spec, out_path):
    """슬라이드 6: 가격 중앙값 × 리뷰볼륨 산점도(없으면 생성)."""
    fig, ax = plt.subplots(figsize=(6.6, 4.6), dpi=150)
    for i, sh in enumerate(spec["shops"]):
        m = spec["metrics"][sh["id"]]
        own = sh["role"] == "own"
        ax.scatter(m["price_median"], m["review_volume"], s=320 if own else 240,
                   marker="*" if own else "o",
                   color=PINK if own else "#9C8AC8", edgecolor=INK if own else "white",
                   linewidth=1.4 if own else 0.6, zorder=3)
        ax.annotate(("★ " if own else "") + sh["name"],
                    (m["price_median"], m["review_volume"]),
                    textcoords="offset points", xytext=(8, 6),
                    fontsize=9, weight="bold" if own else "normal", color=INK)
    ax.set_xlabel("Price median (JPY)", fontsize=10, weight="bold", color=INK)
    ax.set_ylabel("Review volume (Σ)", fontsize=10, weight="bold", color=INK)
    ax.set_title("Positioning · Price x Review Volume", fontsize=13, color=INK, weight="bold", pad=10)
    ax.grid(color="#E3DFF0", zorder=0)
    for s in ax.spines.values():
        s.set_color("#D8D2EA")
    fig.tight_layout(); fig.savefig(out_path, bbox_inches="tight", facecolor="white"); plt.close(fig)
    return out_path


def positioning_follower_sat(spec, out_path):
    """슬라이드 7: 팔로워 × 만족도 산점도(없으면 생성)."""
    fig, ax = plt.subplots(figsize=(6.6, 4.6), dpi=150)
    for sh in spec["shops"]:
        m = spec["metrics"][sh["id"]]
        own = sh["role"] == "own"
        ax.scatter(m["followers"] / 1e6, m["satisfaction"], s=320 if own else 240,
                   marker="*" if own else "o",
                   color=PINK if own else "#9C8AC8", edgecolor=INK if own else "white",
                   linewidth=1.4 if own else 0.6, zorder=3)
        ax.annotate(("★ " if own else "") + sh["name"],
                    (m["followers"] / 1e6, m["satisfaction"]),
                    textcoords="offset points", xytext=(8, 6),
                    fontsize=9, weight="bold" if own else "normal", color=INK)
    ax.set_xlabel("Followers (millions)", fontsize=10, weight="bold", color=INK)
    ax.set_ylabel("Satisfaction (%)", fontsize=10, weight="bold", color=INK)
    ax.set_title("Positioning · Followers x Satisfaction", fontsize=13, color=INK, weight="bold", pad=10)
    ax.grid(color="#E3DFF0", zorder=0)
    for s in ax.spines.values():
        s.set_color("#D8D2EA")
    fig.tight_layout(); fig.savefig(out_path, bbox_inches="tight", facecolor="white"); plt.close(fig)
    return out_path
