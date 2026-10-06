"""Compare EXP-001a runs straight from PostgreSQL: the football-data.co.uk reference run, the control run with
the FootyStats window, and the FootyStats Premier League run.

    python experiments/exp001a/compare_runs.py \\
        --five jevs:bt_dmxbm5nnf921xyn4 --control jevs:bt_y9fb6smbnpxfts6t \\
        --footystats jevs_fs:bt_1rh8493mbesqmkth

Each run is `database:backtest_run_id`. Every metric comes from `packages.calibration.metrics`, the same
functions the experiment report uses. Prints four blocks:

1. data agreement between the control database (football-data.co.uk) and the FootyStats database;
2. the three runs on the same Premier League 2024/25 matches;
3. paired bootstrap of the log loss difference between runs (resampling whole matches);
4. calibration of the five-league run broken down by league.
"""

from __future__ import annotations

import argparse
import re

import pandas as pd
from sqlalchemy import create_engine, text

from packages.calibration import metrics as mt

FAMILY = re.compile(r"-(league_freq|poisson|dixon_coles|negbin)-")
TEAM_MAP = {  # FootyStats name -> football-data.co.uk name
    "AFC Bournemouth": "Bournemouth",
    "Brighton & Hove Albion": "Brighton",
    "Cardiff City": "Cardiff",
    "Huddersfield Town": "Huddersfield",
    "Ipswich Town": "Ipswich",
    "Leeds United": "Leeds",
    "Leicester City": "Leicester",
    "Luton Town": "Luton",
    "Manchester City": "Man City",
    "Manchester United": "Man United",
    "Newcastle United": "Newcastle",
    "Norwich City": "Norwich",
    "Nottingham Forest": "Nott'm Forest",
    "Tottenham Hotspur": "Tottenham",
    "West Bromwich Albion": "West Brom",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
}
PREDICTIONS = text(
    """
    select p.match_id, p.market_key, p.line::float as line, p.model_version, p.probability as p,
           (s.outcome = 'hit')::int as y, se.label as season, c.competition_key,
           (m.kickoff_at at time zone 'Europe/London')::date::text || '|' || th.name || '|' || ta.name as mkey
    from predictions p
    join settlements s using (prediction_id)
    join matches m using (match_id)
    join teams th on th.team_id = m.home_team_id
    join teams ta on ta.team_id = m.away_team_id
    join seasons se on se.season_id = m.season_id
    join competitions c on c.competition_id = se.competition_id
    where p.backtest_run_id = :run
    """
)


def _stat(side: str, period: str, stat: str, alias: str) -> str:
    team = "m.home_team_id" if side == "home" else "m.away_team_id"
    return (
        f"max(case when ms.team_id = {team} and ms.period = '{period}' and ms.stat_key = '{stat}' "
        f"then ms.value end) as {alias}"
    )


STATS = text(
    f"""
    select (m.kickoff_at at time zone 'Europe/London')::date::text as d, th.name as home, ta.name as away,
           {_stat("home", "FT", "goals", "hg")}, {_stat("away", "FT", "goals", "ag")},
           {_stat("home", "1H", "goals", "hg1")}, {_stat("away", "1H", "goals", "ag1")},
           {_stat("home", "FT", "corners", "hc")}, {_stat("away", "FT", "corners", "ac")},
           se.label as season
    from matches m
    join seasons se on se.season_id = m.season_id
    join competitions c on c.competition_id = se.competition_id
    join teams th on th.team_id = m.home_team_id
    join teams ta on ta.team_id = m.away_team_id
    left join match_statistics ms on ms.match_id = m.match_id
    where c.competition_key = 'ENG-PL' and se.label between '2018-2019' and '2024-2025'
    group by 1, 2, 3, se.label
    """
)


def _engine(base: str, database: str):  # type: ignore[no-untyped-def]
    return create_engine(f"{base}/{database}")


def load_run(base: str, spec: str, *, footystats: bool = False) -> pd.DataFrame:
    database, run_id = spec.split(":")
    with _engine(base, database).connect() as conn:
        df = pd.read_sql(PREDICTIONS, conn, params={"run": run_id})
    df["family"] = df["model_version"].map(lambda v: FAMILY.search(v).group(1))  # type: ignore[union-attr]
    # the ECE noise reference simulates outcomes row by row: a fixed row order keeps it reproducible
    df = df.sort_values(["mkey", "market_key", "line", "model_version"]).reset_index(drop=True)
    if footystats:  # align team names so matches can be paired across sources
        df["mkey"] = df["mkey"].map(
            lambda k: "|".join([k.split("|")[0], *(TEAM_MAP.get(t, t) for t in k.split("|")[1:])])
        )
    return df


def score(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    rows = []
    for key, g in df.groupby(by, sort=True):
        p, y = g["p"].to_numpy(), g["y"].to_numpy()
        rows.append(
            {
                **dict(zip(by, key if isinstance(key, tuple) else (key,), strict=True)),
                "n": len(g),
                "base_rate": y.mean(),
                "mean_p": p.mean(),
                "brier": mt.brier(p, y),
                "log_loss": mt.log_loss(p, y),
                "ece": mt.expected_calibration_error(p, y),
                "ece_noise": mt.ece_noise_reference(p),
            }
        )
    return pd.DataFrame(rows)


def data_agreement(base: str, control_db: str, footystats_db: str) -> None:
    frames = []
    for database, footystats in ((control_db, False), (footystats_db, True)):
        with _engine(base, database).connect() as conn:
            df = pd.read_sql(STATS, conn)
        if footystats:
            df["home"], df["away"] = df["home"].replace(TEAM_MAP), df["away"].replace(TEAM_MAP)
        frames.append(df)
    j = frames[0].merge(
        frames[1], on=["season", "d", "home", "away"], suffixes=("_fd", "_fs"), how="outer", indicator=True
    )
    print("## 1. Acuerdo de datos (Premier League 2018/19 a 2024/25)\n")
    print("Partidos:", j["_merge"].value_counts().to_dict())
    both = j[j["_merge"] == "both"].copy()
    rows = {}
    for name, col in [
        ("goles FT local", "hg"),
        ("goles FT visitante", "ag"),
        ("goles 1T local", "hg1"),
        ("goles 1T visitante", "ag1"),
        ("córners local", "hc"),
        ("córners visitante", "ac"),
    ]:
        diff = both[f"{col}_fs"] - both[f"{col}_fd"]
        rows[name] = {
            "comparables": int(diff.notna().sum()),
            "distintos": int((diff != 0).sum()),
            "FootyStats menos": int((diff < 0).sum()),
            "FootyStats más": int((diff > 0).sum()),
        }
    print(pd.DataFrame(rows).T.to_string())
    both["dif"] = (both.hc_fs + both.ac_fs) - (both.hc_fd + both.ac_fd)
    print(
        "\nDiferencia en córners totales (FootyStats menos football-data):",
        both["dif"].value_counts().sort_index().to_dict(),
    )
    per_season = both.groupby("season")["dif"].apply(lambda s: round(100 * float((s != 0).mean()), 1))
    print("Partidos con córners distintos por temporada (%):", per_season.to_dict())
    totals = pd.DataFrame({"fd": both.hc_fd + both.ac_fd, "fs": both.hc_fs + both.ac_fs})
    for line in (7.5, 8.5, 9.5, 10.5, 11.5):
        flips = int(((totals.fd > line) != (totals.fs > line)).sum())
        print(f"  línea {line}: cambia el resultado Over/Under en {flips} de {len(totals)} partidos")
    print("\nDiferencias de 2 o más córners:")
    outliers = both[both["dif"].abs() >= 2][["d", "home", "away", "hc_fd", "ac_fd", "hc_fs", "ac_fs", "dif"]]
    print(outliers.sort_values("d").to_string(index=False))


def per_match_log_loss(df: pd.DataFrame) -> pd.DataFrame:
    df = df.assign(ll=mt.per_obs_log_loss(df["p"].to_numpy(), df["y"].to_numpy()))
    return df.groupby(["mkey", "market_key", "family"], as_index=False)["ll"].mean()  # mean over lines


def paired(x: pd.DataFrame, y: pd.DataFrame, label: str) -> pd.DataFrame:
    j = x.merge(y, on=["mkey", "market_key", "family"], suffixes=("_x", "_y"))
    rows = []
    for (market, family), g in j.groupby(["market_key", "family"]):
        iv = mt.bootstrap_mean(
            (g["ll_x"] - g["ll_y"]).to_numpy(), groups=g["mkey"].to_numpy(), n_boot=1000, seed=7
        )
        rows.append(
            {
                "comparación": label,
                "mercado": market,
                "familia": family,
                "n": len(g),
                "dLL": iv.estimate,
                "IC95_bajo": iv.low,
                "IC95_alto": iv.high,
                "lectura": "diferencia" if iv.excludes_zero() else "ruido",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--five", required=True, help="database:run of the five-league football-data run")
    parser.add_argument(
        "--control", required=True, help="database:run of the football-data control (EPL, FootyStats window)"
    )
    parser.add_argument("--footystats", required=True, help="database:run of the FootyStats EPL run")
    parser.add_argument("--base-url", default="postgresql+psycopg://postgres@127.0.0.1:5432")
    args = parser.parse_args()
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)

    data_agreement(args.base_url, args.control.split(":")[0], args.footystats.split(":")[0])

    runs = {
        "A (5 ligas, football-data)": load_run(args.base_url, args.five),
        "B (control football-data)": load_run(args.base_url, args.control),
        "C (FootyStats)": load_run(args.base_url, args.footystats, footystats=True),
    }
    epl = {k: v[(v["competition_key"] == "ENG-PL") & (v["season"] == "2024-2025")] for k, v in runs.items()}

    print("\n## 2. Mismos 380 partidos: Premier League 2024/25, goles FT Over/Under 2.5\n")
    rows = []
    for name, df in epl.items():
        t = score(df[(df["market_key"] == "goals_ft_total") & (df["line"] == 2.5)], ["family"])
        rows.append(t.assign(run=name))
    print(
        pd.concat(rows)[
            ["run", "family", "n", "base_rate", "mean_p", "brier", "log_loss", "ece", "ece_noise"]
        ]
        .round(4)
        .to_string(index=False)
    )

    print("\n## 3. Diferencia de log loss pareada por partido (media sobre las líneas)")
    print("Negativo = el primero es mejor.\n")
    a, b, c = (per_match_log_loss(epl[k]) for k in epl)
    both_seasons = {
        k: v[(v["competition_key"] == "ENG-PL") & v["season"].isin(["2023-2024", "2024-2025"])]
        for k, v in runs.items()
        if not k.startswith("A")
    }
    b2, c2 = (per_match_log_loss(v) for v in both_seasons.values())
    print(
        pd.concat(
            [
                paired(a, b, "A - B, EPL 2024/25"),
                paired(b, c, "B - C, EPL 2024/25"),
                paired(b2, c2, "B - C, EPL 2023/24 + 2024/25"),
            ]
        )
        .round(5)
        .to_string(index=False)
    )

    print("\n## 4. Run de 5 ligas por liga (test 2024/25 + 2025/26), modelos de equipo\n")
    test = runs["A (5 ligas, football-data)"]
    test = test[test["season"].isin(["2024-2025", "2025-2026"]) & (test["family"] != "league_freq")]
    t = score(test, ["competition_key", "market_key", "line", "family"])
    t["fuera_del_ruido"] = (t["ece"] > 0.03) & (t["ece"] > t["ece_noise"])
    print(
        t.groupby("competition_key")
        .agg(
            celdas=("ece", "size"),
            ece_medio=("ece", "mean"),
            ece_max=("ece", "max"),
            ece_sobre_0_03=("ece", lambda s: int((s > 0.03).sum())),
            fuera_del_ruido=("fuera_del_ruido", "sum"),
        )
        .round(4)
        .to_string()
    )
    over_target, outside_noise = int((t["ece"] > 0.03).sum()), int(t["fuera_del_ruido"].sum())
    print(f"\nTotal: {len(t)} celdas, {over_target} con ECE > 0.03, {outside_noise} fuera del ruido")
    for market, line in (("corners_ft_total", 9.5), ("goals_ft_total", 2.5)):
        sel = test[(test["market_key"] == market) & (test["line"] == line) & (test["family"] == "poisson")]
        print(f"\n{market} {line} (poisson):")
        print(
            score(sel, ["competition_key"])[
                ["competition_key", "n", "base_rate", "mean_p", "log_loss", "ece", "ece_noise"]
            ]
            .round(4)
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()
