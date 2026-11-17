"""Plotly-Figuren: Umlauf als Gantt-Diagramm (Ladestand, Laden, Leerfahrten), Rampe als Heatmap, Regeln gegen das Optimum. Alle Achsen fest (`fixedrange`)."""

import plotly.graph_objects as go

import ebu_constants as C
import ebu_energy as E
from ebu_scenario import fmt_time
from ebu_texte import f1

COLOR_CHARGE = "#2ca02c"
COLOR_DEADHEAD = "rgba(120,120,120,0.55)"


def _hour_ticks(t0: int, t1: int):
    first = (t0 // 60) * 60
    vals = list(range(first, t1 + 60, 60))
    return vals, [fmt_time(v) for v in vals]


def build_umlauf(inst, prm: E.Params, plan: E.Plan, title: str = "") -> go.Figure:
    """Gantt: eine Zeile je Bus. Elektro-Fahrten nach Ladestand bei Ankunft gefärbt (rot = nahe der Reserve), grün = Ladeplatz belegt, grau = Leerfahrt."""
    fig = go.Figure()
    rows = len(plan.chains)
    labels = [f"Bus {k + 1}" + (" (Diesel)" if k in plan.diesel else "") for k in range(rows)]
    tx, ty, tb, tc, thov = [], [], [], [], []
    dx, dy, db, dhov = [], [], [], []
    for k, ch in enumerate(plan.chains):
        prof = None if k in plan.diesel else E.soc_profile(inst, prm, ch, plan.charged)
        for idx, t in enumerate(ch):
            dur = inst.end[t] - inst.start[t]
            route = "A → B" if inst.orig[t] == 0 else "B → A"
            if prof is None:
                dx.append(dur); dy.append(labels[k]); db.append(inst.start[t])
                dhov.append(f"Fahrt {t + 1} {route}<br>{fmt_time(inst.start[t])}–{fmt_time(inst.end[t])}<br>Diesel: keine Batteriegrenze")
            else:
                s0, s1 = prof[idx]
                tx.append(dur); ty.append(labels[k]); tb.append(inst.start[t]); tc.append(100.0 * s1 / prm.c)
                thov.append(f"Fahrt {t + 1} {route}<br>{fmt_time(inst.start[t])}–{fmt_time(inst.end[t])}<br>Ladestand bei Abfahrt {f1(s0)} kWh, bei Ankunft {f1(s1)} kWh")
    if tx:
        fig.add_trace(go.Bar(
            orientation="h", x=tx, y=ty, base=tb, width=0.8, name="Elektro-Fahrt", showlegend=False, hovertext=thov, hoverinfo="text",
            marker=dict(color=tc, colorscale="RdYlGn", cmin=0, cmax=100, line=dict(color="rgba(0,0,0,0.5)", width=0.6),
                        colorbar=dict(title=dict(text="Ladestand bei<br>Ankunft (% von C)", side="top"), tickvals=[0, 25, 50, 75, 100], len=0.8)),
        ))
    if dx:
        fig.add_trace(go.Bar(orientation="h", x=dx, y=dy, base=db, width=0.8, name="Diesel-Fahrt", hovertext=dhov, hoverinfo="text",
                             marker=dict(color=C.COLOR_DIESEL, line=dict(color="rgba(0,0,0,0.5)", width=0.6))))
    cx, cy, cb, chov, ex, ey, eb, ehov = [], [], [], [], [], [], [], []
    for k, ch in enumerate(plan.chains):
        for a, b in zip(ch, ch[1:]):
            dh = 0 if inst.dest[a] == inst.orig[b] else inst.dh_min
            if dh:
                ex.append(dh); ey.append(labels[k]); eb.append(inst.end[a])
                ehov.append(f"Leerfahrt zwischen den Endhaltepunkten, {dh} min")
            if (a, b) in plan.charged:
                site = E.charge_site(inst, prm, a, b)
                bg, en = E.charge_interval(inst, a, b, site)
                cx.append(max(1, en - bg)); cy.append(labels[k]); cb.append(bg)
                chov.append(f"Laden am Endhaltepunkt {'AB'[site]}: Platz belegt {fmt_time(bg)}–{fmt_time(en)}")
    if ex:
        fig.add_trace(go.Bar(orientation="h", x=ex, y=ey, base=eb, width=0.25, name="Leerfahrt", hovertext=ehov, hoverinfo="text", marker=dict(color=COLOR_DEADHEAD)))
    if cx:
        fig.add_trace(go.Bar(orientation="h", x=cx, y=cy, base=cb, width=0.25, name="Laden (Platz belegt)", hovertext=chov, hoverinfo="text", marker=dict(color=COLOR_CHARGE)))
    vals, texts = _hour_ticks(min(inst.start), max(inst.end))
    fig.update_layout(
        barmode="overlay", title=dict(text=title, font=dict(size=14)), height=130 + 26 * rows, margin=dict(l=10, r=10, t=40 if title else 10, b=40),
        legend=dict(orientation="h", y=-0.12), xaxis=dict(tickvals=vals, ticktext=texts, range=[min(inst.start) - 5, max(inst.end) + 5], fixedrange=True,
                                                         title="Uhrzeit", gridcolor=C.COLOR_GRID),
        yaxis=dict(autorange="reversed", fixedrange=True, type="category", categoryorder="array", categoryarray=labels),
    )
    return fig


def build_heatmap(z, xs, ys, texts, xtitle: str, ytitle: str, title: str = "") -> go.Figure:
    """Heatmap (Zeilen: Batterie, Spalten: Ladeleistung o. ä.) mit festem Farbbereich ab 0 und Text je Zelle."""
    zmax = max([v for row in z for v in row if v is not None] + [1])
    fig = go.Figure(go.Heatmap(z=z, x=[str(x) for x in xs], y=[str(y) for y in ys], text=texts, texttemplate="%{text}", colorscale="YlOrRd",
                               zmin=0, zmax=zmax, showscale=False, hoverinfo="text"))
    fig.update_layout(title=dict(text=title, font=dict(size=14)), height=110 + 52 * len(ys), margin=dict(l=10, r=10, t=40 if title else 10, b=40),
                      xaxis=dict(title=xtitle, fixedrange=True, type="category"), yaxis=dict(title=ytitle, fixedrange=True, type="category", autorange="reversed"))
    return fig


def build_rules(labels, buses, optimum: int | None, proven: bool, diesel: int) -> go.Figure:
    """Busse je Regel (waagerechte Balken) mit Dieselumlauf und Optimum als senkrechte Linien."""
    fig = go.Figure(go.Bar(orientation="h", y=labels, x=[0 if b is None else b for b in buses], marker=dict(color=C.COLOR_RULE),
                           text=["keine Lösung" if b is None else str(b) for b in buses], textposition="outside", hoverinfo="skip", cliponaxis=False))
    fig.add_vline(x=diesel, line=dict(color=C.COLOR_DIESEL, dash="dash"), annotation_text="Dieselumlauf", annotation_position="top")
    if optimum is not None:
        fig.add_vline(x=optimum, line=dict(color=C.COLOR_ELECTRIC, width=2),
                      annotation_text="Optimum" if proven else "beste bekannte Zahl (nicht bewiesen)", annotation_position="bottom")
    top = max([diesel] + [b for b in buses if b is not None] + ([optimum] if optimum is not None else [])) + 2
    fig.update_layout(height=120 + 38 * len(labels), margin=dict(l=10, r=30, t=30, b=30), xaxis=dict(range=[0, top], fixedrange=True, title="Busse"),
                      yaxis=dict(autorange="reversed", fixedrange=True))
    return fig
