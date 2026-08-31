from pathlib import Path

from handlers.analysis import normalize_analysis
from utils.formatters import format_commercial_report


def _raw_analysis():
    item = {"name": "Порог", "reason": "Коррозия", "status": "confirmed",
            "parts_cost": 10_000, "labor_cost": 20_000, "total_cost": 999_999,
            "priority": "critical"}
    return {
        "market": {"region": {"low": 200_000, "mid": 250_000, "high": 300_000},
                   "rf": {"low": 190_000, "mid": 240_000, "high": 310_000},
                   "realistic_sale_price": 250_000, "quick_sale_price": 230_000,
                   "market_comment": "Экспертная оценка"},
        "repairs": {"critical_repairs": [item], "sale_preparation": [], "maintenance": [],
                    "potential_repairs": [], "risk_reserve": 15_000},
        "economics": {"target_purchase_price": 190_000, "excellent_purchase_price": 170_000},
        "risk": {"risk_score": 45, "risk_level": "medium", "main_risks": ["Коррозия"],
                 "worst_case_expense": 50_000, "comment": "Нужен подъемник"},
        "liquidity": {"liquidity_score": 80, "liquidity_level": "high", "comment": "Ликвидна"},
        "inspection_checklist": ["Проверить пороги на подъемнике"],
        "negotiation": {"start_offer": 150_000, "negotiation_arguments": ["Коррозия"]},
        "verdict": {"code": "only_after_discount", "score": 60, "should_inspect": True,
                    "summary": "Только после торга", "main_profit_factor": "Ликвидность",
                    "main_loss_risk": "Скрытая коррозия"},
    }


def test_normalizer_recalculates_all_math_in_python():
    car = {"car_model": "Лада", "year": 2011, "mileage": 250_000,
           "region": "Новосибирск", "purchase_price": 240_000}
    result = normalize_analysis(_raw_analysis(), car)
    assert result["repairs"]["critical_repairs"][0]["total_cost"] == 30_000
    assert result["repairs"]["recommended_preparation_cost"] == 30_000
    assert result["economics"]["total_investment"] == 270_000
    assert result["economics"]["expected_profit"] == -20_000
    assert result["economics"]["roi_percent"] == -7.4
    assert result["economics"]["required_discount"] == 50_000


def test_commercial_report_contains_decision_sections():
    car = {"car_model": "Лада", "year": 2011, "mileage": 250_000,
           "region": "Новосибирск", "purchase_price": 240_000}
    report = format_commercial_report(normalize_analysis(_raw_analysis(), car))
    assert "КОММЕРЧЕСКИЙ АНАЛИЗ" in report
    assert "ROI: <b>-7.4%</b>" in report
    assert "ПОТЕНЦИАЛЬНЫЕ РЕМОНТЫ" in report
    assert "Стоит ехать смотреть: <b>Да</b>" in report


def test_full_prompt_accepts_all_questionnaire_fields():
    template = (Path(__file__).parents[1] / "prompts" / "full_analysis.txt").read_text(encoding="utf-8")
    prompt = template.format_map({"car_model": "Лада", "year": 2011, "mileage": 250_000,
                                  "engine": "1.6 МКПП", "region": "Новосибирск",
                                  "purchase_price": 200_000, "listing_description": "Текст",
                                  "photo_damage": "Царапина", "additional_info": "Нет"})
    assert "Лада" in prompt and '"potential_repairs"' in prompt
