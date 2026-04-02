"""结构化 dossier 输出测试."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import yaml

from stock_master.analysis.quantitative import compute_score
from stock_master.data.cache import DataCache
from stock_master.pipeline.context_builder import build_context
from stock_master.pipeline.dossier import build_stock_dossier


def _sample_kline(rows: int = 80) -> pd.DataFrame:
    closes = [20 + i * 0.15 for i in range(rows)]
    frame = pd.DataFrame(
        {
            "收盘": closes,
            "最高": [c + 0.25 for c in closes],
            "最低": [c - 0.25 for c in closes],
            "成交量": [3000 + i * 20 for i in range(rows)],
        }
    )
    frame["MA20"] = frame["收盘"].rolling(20).mean().bfill()
    frame["RSI14"] = 55.0
    return frame


def test_build_context_writes_context_and_dossier(tmp_path: Path):
    info = {"股票简称": "测试股份", "行业": "软件服务", "上市日期": "2020-01-01"}
    valuation = {"pe_ttm": 16.0, "pb": 2.4, "ps_ttm": 3.2}
    valuation_history = pd.DataFrame({"pe_ttm": [10.0, 12.0, 14.0, 16.0, 18.0, 20.0]})
    financial = pd.DataFrame(
        [
            {
                "报告期": "2025-12-31",
                "ROE(%)": 16.0,
                "毛利率(%)": 40.0,
                "净利率(%)": 18.0,
                "营收同比(%)": 20.0,
                "净利同比(%)": 25.0,
                "资产负债率(%)": 30.0,
                "流动比率": 1.8,
            }
        ]
    )
    news = [{"title": "公司获批新产品", "content": "预计贡献新增收入", "time": "2026-04-02", "source": "测试社"}]
    macro = {
        "market_regime": "稳增长",
        "policy_bias": "中性偏积极",
        "liquidity": "宽松",
        "headline": "政策环境对成长股中性偏利好",
    }
    peers = [
        {"code": "300001", "name": "同业A", "pe_ttm": 20.0, "pb": 3.0},
        {"code": "300002", "name": "同业B", "pe_ttm": 18.0, "pb": 2.8},
    ]

    with (
        patch("stock_master.pipeline.context_builder.fetch_stock_info", return_value=info),
        patch("stock_master.pipeline.context_builder.fetch_daily_kline", return_value=_sample_kline()),
        patch("stock_master.pipeline.context_builder.fetch_valuation", return_value=valuation),
        patch("stock_master.pipeline.context_builder.fetch_valuation_history", return_value=valuation_history),
        patch("stock_master.pipeline.context_builder.fetch_financial_summary", return_value=financial),
        patch("stock_master.pipeline.context_builder.fetch_news", return_value=news),
        patch("stock_master.pipeline.context_builder.fetch_macro_snapshot", return_value=macro),
        patch("stock_master.pipeline.context_builder.fetch_peer_benchmark", return_value=peers),
    ):
        context_path = build_context(
            "300999",
            output_dir=tmp_path,
            cache=DataCache(tmp_path / "cache.db"),
        )

    dossier_path = tmp_path / "dossier.yaml"

    assert context_path.exists()
    assert dossier_path.exists()
    assert (tmp_path / "agents").exists()

    text = context_path.read_text(encoding="utf-8")
    assert "证据覆盖度" in text
    assert "因子评分" in text
    assert "估值历史分位" in text
    assert "新手行动建议" in text

    dossier = yaml.safe_load(dossier_path.read_text(encoding="utf-8"))
    assert dossier["code"] == "300999"
    assert dossier["stock_name"] == "测试股份"
    assert "coverage" in dossier
    assert "factors" in dossier
    assert dossier["coverage"]["coverage_ratio"] > 0


def test_dossier_requires_more_evidence_when_risk_factor_missing():
    financial = pd.DataFrame(
        [
            {
                "报告期": "2025-12-31",
                "ROE(%)": 22.0,
                "毛利率(%)": 45.0,
                "净利率(%)": 20.0,
                "营收同比(%)": 30.0,
                "净利同比(%)": 32.0,
            }
        ]
    )
    valuation = {"pe_ttm": 10.0, "pb": 1.5}
    valuation_history = pd.DataFrame({"pe_ttm": [12.0, 14.0, 16.0, 18.0]})

    score = compute_score(
        pd.DataFrame(),
        valuation,
        financial=financial,
        valuation_history=valuation_history,
        news=[],
    )
    dossier = build_stock_dossier(
        code="002273",
        stock_name="测试股份",
        score=score,
        info={"股票简称": "测试股份"},
        kline=pd.DataFrame(),
        valuation=valuation,
        financial=financial,
        news=[],
        macro={},
        peers=[],
    )

    assert dossier.rookie_action.verdict == "先补证据"
