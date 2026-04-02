"""升级版因子评分测试."""

from __future__ import annotations

import pandas as pd

from stock_master.analysis.reporter import format_score_summary
from stock_master.analysis.quantitative import compute_score


def _build_kline(rows: int = 80) -> pd.DataFrame:
    closes = [10 + i * 0.2 for i in range(rows)]
    frame = pd.DataFrame(
        {
            "收盘": closes,
            "最高": [c + 0.3 for c in closes],
            "最低": [c - 0.3 for c in closes],
            "成交量": [1000 + i * 10 for i in range(rows)],
        }
    )
    frame["MA20"] = frame["收盘"].rolling(20).mean().bfill()
    frame["RSI14"] = 58.0
    return frame


def test_compute_score_returns_factor_breakdown_and_confidence():
    kline = _build_kline()
    valuation = {"pe_ttm": 14.0, "pb": 1.8}
    valuation_history = pd.DataFrame({"pe_ttm": [10.0, 12.0, 13.0, 14.0, 18.0, 20.0]})
    financial = pd.DataFrame(
        [
            {
                "报告期": "2025-12-31",
                "ROE(%)": 18.0,
                "毛利率(%)": 35.0,
                "净利率(%)": 18.0,
                "营收同比(%)": 22.0,
                "净利同比(%)": 25.0,
                "资产负债率(%)": 32.0,
                "流动比率": 1.9,
            }
        ]
    )
    news = [
        {"title": "公司回购股份并上调回购额度", "content": "董事会通过新的回购方案"},
        {"title": "机构维持买入评级", "content": "目标价上调"},
    ]

    result = compute_score(
        kline,
        valuation,
        financial=financial,
        valuation_history=valuation_history,
        news=news,
    )

    assert set(result.factors) == {"质量", "估值", "趋势", "风险", "催化剂"}
    assert result.factors["质量"].score > 70
    assert result.factors["质量"].coverage == 1.0
    assert result.factors["估值"].coverage == 1.0
    assert result.confidence > 75
    assert result.to_dict()["综合"] > 0


def test_compute_score_marks_missing_data_instead_of_defaulting_to_neutral():
    result = compute_score(
        pd.DataFrame(),
        {},
        financial=pd.DataFrame(),
        valuation_history=pd.DataFrame(),
        news=[],
    )

    assert result.factors["质量"].status == "missing"
    assert result.factors["估值"].status == "missing"
    assert result.factors["趋势"].status == "missing"
    assert result.factors["风险"].status == "missing"
    assert result.factors["催化剂"].status == "missing"
    assert result.confidence == 0.0
    assert result.to_dict()["综合"] == 0.0


def test_score_summary_marks_missing_factors_as_na():
    result = compute_score(
        pd.DataFrame(),
        {},
        financial=pd.DataFrame(),
        valuation_history=pd.DataFrame(),
        news=[],
    )

    markdown = format_score_summary(result)

    assert "N/A" in markdown
