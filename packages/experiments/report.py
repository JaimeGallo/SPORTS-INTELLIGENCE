"""Markdown report for EXP-001a (Spanish, probabilistic language only)."""

from __future__ import annotations

from typing import Any

ECE_TARGET = 0.03


def _f(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/d"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _pct(value: Any) -> str:
    return "n/d" if value is None else f"{100 * value:.1f}%"


def render_markdown(d: dict[str, Any]) -> str:
    out: list[str] = []
    w = out.append
    w(f"# {d['experiment'].upper()}: informe de resultados\n")
    if d["provider"] == "synthetic":
        w(
            "> **DATOS SINTÉTICOS.** Este informe valida el pipeline con un proceso generador conocido. "
            "Sus cifras no dicen nada sobre el fútbol real.\n"
        )
    w("> Probabilidad no es certeza. Edge no es garantía de resultado. Simulación sin dinero real.\n")
    w("| Campo | Valor |\n| --- | --- |")
    for key in (
        "backtest_run_id",
        "dataset_version",
        "config_hash",
        "code_version",
        "provider",
        "n_predictions",
        "n_snapshots",
        "coherence_violations",
    ):
        w(f"| {key} | `{d[key]}` |")
    ing = d["ingestion"]
    w(
        f"| ingesta | {ing['payloads']} ficheros, {ing['matches']} partidos, {ing['odds']} cuotas, "
        f"{ing['issues']} incidencias de calidad |\n"
    )

    w("## 1. Integridad (leakage)\n")
    ok = d["max_history_available_vs_as_of_ok"]
    w(f"- Todas las predicciones usan solo datos con `available_at <= as_of`: **{'sí' if ok else 'NO'}**.")
    w(
        f"- Coherencia entre líneas (P(Over) no crece con la línea): **{d['coherence_violations']} violaciones**."
    )
    if d["skipped_for_insufficient_history"]:
        skipped = sum(d["skipped_for_insufficient_history"].values())
        w(
            f"- Predicciones omitidas por historial insuficiente (inicio de serie): {skipped} (partido x modelo)."
        )
    w("")

    w("## 2. Selección en validación\n")
    w("Elegido por log loss medio en las temporadas de validación; el test no interviene en la elección.\n")
    w(
        "| Objetivo | Familia | Modelo | Calibrador | Log loss | Brier | ECE |\n| --- | --- | --- | --- | ---: | ---: | ---: |"
    )
    for r in d["selected"]:
        w(
            f"| {r['target']} | {r['family']} | `{r['model_version']}` | {r['calibrator']} | {_f(r['log_loss'])} | "
            f"{_f(r['brier'])} | {_f(r['ece'])} |"
        )
    w("")

    w("## 3. Test fuera de muestra\n")
    w(
        "| Mercado | Línea | Familia | Calibrador | N | Tasa real | P media | Brier | Log loss | ECE |\n"
        "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    for r in sorted(d["test_scores"], key=lambda r: (r["market_key"], r["line"], r["family"])):
        flag = "" if r["ece"] is None or r["ece"] < ECE_TARGET else " ⚠"
        w(
            f"| {r['market_key']} | {r['line']} | {r['family']} | {r['calibrator']} | {r['n']} | {_pct(r['base_rate'])} | "
            f"{_pct(r['mean_p'])} | {_f(r['brier'])} | {_f(r['log_loss'])} | {_f(r['ece'])}{flag} |"
        )
    w(f"\n⚠ = ECE por encima del objetivo de {ECE_TARGET}.\n")

    w("## 4. Modelos frente al baseline ingenuo (test)\n")
    w(
        "Diferencia de log loss por observación (modelo menos baseline; negativo = mejor), intervalo bootstrap 95% "
        "remuestreando partidos.\n"
    )
    w(
        "| Mercado | Línea | Familia | N | Δ log loss | IC 95% | Lectura |\n| --- | ---: | --- | ---: | ---: | --- | --- |"
    )
    for c in sorted(d["comparisons_vs_baseline"], key=lambda c: (c["market_key"], c["line"], c["family"])):
        ll = c["log_loss_diff"]
        if ll["high"] < 0:
            verdict = "mejor que el baseline"
        elif ll["low"] > 0:
            verdict = "peor que el baseline"
        else:
            verdict = "sin diferencia concluyente"
        w(
            f"| {c['market_key']} | {c['line']} | {c['family']} | {c['n']} | {_f(ll['estimate'], 5)} | "
            f"[{_f(ll['low'], 5)}, {_f(ll['high'], 5)}] | {verdict} |"
        )
    w("")

    m = d["market"]
    w("## 5. Comparación con el mercado\n")
    if not m.get("available"):
        w(f"No disponible: {m.get('reason')}.\n")
    else:
        w(
            f"Mercado `{m['market_key']}` línea {m['line']}. Cuotas pre-partido usables en `as_of`: {m['prematch_quotes']} "
            f"(casas: {m['prematch_bookmakers']}); margen medio {_f(m['mean_prematch_overround'])}. "
            f"Cuotas de cierre (solo evaluación): {m['closing_quotes']}.\n"
        )
        w(
            "| Modelo | Calibrador | Frente a | N | LL modelo | LL mercado | Δ LL (IC 95%) | |edge| medio |\n"
            "| --- | --- | --- | ---: | ---: | ---: | --- | ---: |"
        )
        for e in m["models"].values():
            for name in ("prematch", "closing"):
                v = e.get(f"vs_{name}")
                if not v:
                    continue
                diff = v["log_loss_diff_model_minus_market"]
                w(
                    f"| {e['family']} | {e['calibrator']} | {name} | {v['n']} | {_f(v['model_log_loss'])} | "
                    f"{_f(v['market_log_loss'])} | {_f(diff['estimate'], 5)} [{_f(diff['low'], 5)}, {_f(diff['high'], 5)}] | "
                    f"{_pct(v['mean_abs_edge'])} |"
                )
        w("\n### Simulación paper (stake plano, sin dinero real)\n")
        w(
            "| Modelo | Apuestas | ROI | IC 95% ROI | Acierto | Edge medio | CLV medio | Drawdown máx. |\n"
            "| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |"
        )
        for _version, e in m["models"].items():
            p = e["paper"]
            roi = p["roi"]
            roi_est = _pct(roi["estimate"]) if roi else "n/d"
            roi_ci = f"[{_pct(roi['low'])}, {_pct(roi['high'])}]" if roi else "n/d"
            w(
                f"| {e['family']} | {p['n_bets']} | {roi_est} | {roi_ci} | {_pct(p['hit_rate'])} | "
                f"{_pct(p['mean_edge'])} | {_pct(p['mean_clv'])} | {_f(p['max_drawdown'], 1)} |"
            )
        w(
            "\nUn ROI positivo con un intervalo que incluye el cero no es evidencia de edge. El CLV positivo frente al "
            "cierre es una señal más estable que el ROI en muestras pequeñas.\n"
        )

    w("## 6. Criterios de éxito\n")
    eces = [r["ece"] for r in d["test_scores"] if r["ece"] is not None]
    worst = max(eces) if eces else None
    better = [c for c in d["comparisons_vs_baseline"] if c["log_loss_diff"]["high"] < 0]
    worse = [c for c in d["comparisons_vs_baseline"] if c["log_loss_diff"]["low"] > 0]
    w(
        f"1. Reproducibilidad: dataset `{d['dataset_version']}`, configuración `{d['config_hash']}`, código "
        f"`{d['code_version']}`. Verificar re-ejecutando: el `summary.json` debe ser idéntico."
    )
    w(f"2. Sin leakage: **{'cumple' if ok else 'NO cumple'}**.")
    w(
        f"3. Calibración (ECE < {ECE_TARGET} en test): peor ECE {_f(worst)}: "
        f"**{'cumple' if worst is not None and worst < ECE_TARGET else 'no cumple en todos los mercados'}**."
    )
    w(
        f"4. Frente al baseline: {len(better)} combinaciones mejores, {len(worse)} peores, "
        f"{len(d['comparisons_vs_baseline']) - len(better) - len(worse)} sin diferencia concluyente."
    )
    w(
        "5. Reconstrucción: cada predicción está en `predictions` con su `feature_snapshot_id` y su liquidación."
    )
    w("")
    return "\n".join(out)
