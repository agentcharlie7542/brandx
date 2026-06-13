"""스냅샷 차분 기반 판매량·매출 추정.

추정식:
  일간 판매량 ≈ 일간 신규 리뷰 수 ÷ REVIEW_RATE
  일간 매출   ≈ 일간 판매량 × 당일 가격

REVIEW_RATE(리뷰 작성률)는 업계 통용치 0.30을 기본값으로 하되,
'販売 배지(sold_count)'가 있는 상품으로 캘리브레이션 권장:
  실측 작성률 = 리뷰 증가량 ÷ sold_count 증가량
"""
import pandas as pd

from db import connect

REVIEW_RATE = 0.30   # 큐텐 리뷰 작성률 가정 (포인트 지급으로 높음, 20~40%)
REVIEW_RATE_BY_PLATFORM = {
    "qoo10": 0.30,
    "rakuten": 0.04,  # 라쿠텐은 리뷰 인센티브가 약해 작성률 낮음 (통상 2~6%, 보정 필수)
}
SMOOTH_DAYS = 7      # 리뷰 작성 지연 평활용 이동평균 일수


def estimate() -> pd.DataFrame:
    conn = connect()
    df = pd.read_sql(
        """SELECT s.goods_code, p.name, p.platform, p.shop_id,
                  s.snap_date, s.price, s.review_count, s.sold_count
           FROM snapshots s JOIN products p USING(goods_code)
           ORDER BY s.goods_code, s.snap_date""",
        conn,
    )
    if df.empty:
        return df

    g = df.groupby("goods_code")
    df["new_reviews"] = g["review_count"].diff().clip(lower=0)
    df["new_sold_badge"] = g["sold_count"].diff().clip(lower=0)  # 있으면 실측

    # 추정 판매량: 배지 실측이 있으면 우선, 없으면 플랫폼별 리뷰 작성률로 역산
    rate = df["platform"].map(REVIEW_RATE_BY_PLATFORM).fillna(REVIEW_RATE)
    df["est_units"] = df["new_sold_badge"].fillna(df["new_reviews"] / rate)
    df["est_revenue_jpy"] = df["est_units"] * df["price"]

    # 이동평균 평활
    df["est_units_ma"] = g["est_units"].transform(lambda s: s.rolling(SMOOTH_DAYS, min_periods=1).mean())
    df["est_revenue_ma"] = g["est_revenue_jpy"].transform(lambda s: s.rolling(SMOOTH_DAYS, min_periods=1).mean())
    return df


def calibrate_review_rate() -> float | None:
    """판매 배지가 있는 상품으로 실제 리뷰 작성률 역산."""
    conn = connect()
    df = pd.read_sql(
        "SELECT goods_code, snap_date, review_count, sold_count FROM snapshots "
        "WHERE sold_count IS NOT NULL ORDER BY goods_code, snap_date",
        conn,
    )
    if df.empty:
        return None
    g = df.groupby("goods_code")
    dr = g["review_count"].diff().clip(lower=0).sum()
    ds = g["sold_count"].diff().clip(lower=0).sum()
    return round(dr / ds, 3) if ds and ds > 0 else None


def summary(df: pd.DataFrame, days: int = 30) -> pd.DataFrame:
    """최근 N일 상품별 추정 매출 요약."""
    cutoff = (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    recent = df[df["snap_date"] >= cutoff]
    out = (recent.groupby(["platform", "shop_id", "goods_code", "name"], dropna=False)
           .agg(est_units=("est_units", "sum"),
                est_revenue_jpy=("est_revenue_jpy", "sum"),
                avg_price=("price", "mean"),
                latest_reviews=("review_count", "max"))
           .sort_values("est_revenue_jpy", ascending=False)
           .reset_index())
    return out


if __name__ == "__main__":
    df = estimate()
    if df.empty:
        print("스냅샷 데이터 없음 — run.py를 며칠간 먼저 실행하세요.")
    else:
        rate = calibrate_review_rate()
        if rate:
            print(f"실측 리뷰 작성률(배지 기반): {rate}")
        print(summary(df).to_string(index=False))
