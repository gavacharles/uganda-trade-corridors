"""Build presentation/highways_high_streets.pptx from the figures and outputs of the study.

    python presentation/build_deck.py

Needs python-pptx and Pillow. Numbers on the slides are read from outputs/ and scripts/config.py,
so the deck follows the corridors in config.CORRIDORS; the few fixed figures are noted in place.
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
import os, sys, tempfile
import pandas as pd
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import config as C  # noqa: E402

FIG = os.path.join(ROOT, "figures")
OUTP = os.path.join(ROOT, "outputs")
OUT = os.path.join(ROOT, "presentation", "highways_high_streets.pptx")
S = tempfile.mkdtemp()   # cropped images for the slides


def crop(src, box, name):
    Image.open(os.path.join(FIG, src)).crop(box).save(os.path.join(S, name))


crop("m01_study_area.png", (160, 150, 1375, 1530), "m01.png")
crop("m01_study_area.png", (160, 370, 1375, 1530), "m01_title.png")
crop("m02_bottlenecks.png", (140, 140, 1590, 1545), "m02.png")
crop("g04_time_map.png", (0, 120, 1713, 999), "g04.png")
crop("f12_rail_map.png", (0, 60, 1193, 1318), "f12.png")
_m4 = Image.open(os.path.join(FIG, "m04_growth.png"))
crop("m04_growth.png", (0, 180, _m4.width, _m4.height - 80), "m04.png")

R = lambda f: pd.read_csv(os.path.join(OUTP, f))  # noqa: E731
SC, SB, REL, COST = R("scenarios.csv"), R("safety_by_type.csv"), R("reliability.csv"), R("costs.csv")
RE, RP, TYP, VAL = R("rail_economics.csv"), R("rail_proximity.csv"), R("typology_summary.csv"), R("validation.csv")
CAUSE, TOT, HOT, GROW = R("travel_time_causes.csv"), R("travel_time_totals.csv"), R("hotspots_mapped.csv"), R("growth_summary.csv")
STAB, GAP, MIX, FUEL = R("rank_stability.csv"), R("transit_gap.csv"), R("transit_stop_mix.csv"), R("fuel_co2.csv")
BS, BSM, FLD = R("black_spots_test.csv"), R("black_spots_matched.csv"), R("flood_events_check.csv")
CORR = list(C.CORRIDORS)
CLAB = [f"{C.CORRIDORS[c]['short']} ({C.CORRIDORS[c]['ref']})" for c in CORR]
N = len(CORR)
NW = ["no", "one", "two", "three", "four", "five", "six", "seven"][N]
KM = TYP.groupby("corridor").km.sum()
BUILDINGS_M = 1.54   # data/buildings.parquet: 1,542,424 footprints within 1 km (03_download_buildings.py)

DARK = RGBColor(0x17, 0x25, 0x2A)
LAT = RGBColor(0xC4, 0x53, 0x2D)      # laterite red: delay / growth
GRN = RGBColor(0x3A, 0x7D, 0x5C)      # savanna green: open road
SAND = RGBColor(0xD9, 0xA4, 0x41)     # settlement
INK = RGBColor(0x1E, 0x25, 0x28)
MUTED = RGBColor(0x5B, 0x67, 0x70)
TINT = RGBColor(0xEE, 0xF2, 0xF0)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
PALE = RGBColor(0xB8, 0xC7, 0xC4)
CCOL = {"kampala_malaba": RGBColor(0x2A, 0x78, 0xD6), "kampala_elegu": RGBColor(0xE8, 0x64, 0x3A),
        "kampala_katuna": RGBColor(0x1A, 0xA8, 0x78), "kampala_hoima": RGBColor(0xE8, 0x9C, 0x10),
        "kampala_bwera": RGBColor(0x8A, 0x5C, 0xC7)}
HEAD, BODY = "Cambria", "Calibri"


def rng(vals, fmt="{:.0f}", suffix=""):
    lo, hi = min(vals), max(vals)
    return f"{fmt.format(lo)}{suffix}" if round(lo) == round(hi) else f"{fmt.format(lo)}–{fmt.format(hi)}{suffix}"


prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def bg(slide, color):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = color


def text(slide, x, y, w, h, runs, size=16, color=INK, font=BODY, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False, space_after=0):
    """runs: str or list of paragraphs; a paragraph is str or list of (text, overrides)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        segs = para if isinstance(para, list) else [(para, {})]
        for seg, ov in segs:
            r = p.add_run()
            r.text = seg
            f = r.font
            f.name = ov.get("font", font)
            f.size = Pt(ov.get("size", size))
            f.bold = ov.get("bold", bold)
            f.italic = ov.get("italic", italic)
            f.color.rgb = ov.get("color", color)
    return tb


def title(slide, t, sub=None, dark=False):
    text(slide, 0.6, 0.45, 12.1, 0.8, t, size=34, font=HEAD, bold=True,
         color=WHITE if dark else INK)
    if sub:
        text(slide, 0.6, 1.22, 12.1, 0.5, sub, size=16, color=PALE if dark else MUTED)


def box(slide, x, y, w, h, fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    return s


def circle_num(slide, x, y, d, label, fill=LAT, size=16):
    c = box(slide, x, y, d, d, fill, shape=MSO_SHAPE.OVAL)
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size = Pt(size); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = BODY


def picture(slide, path, x, y, w=None, h=None):
    return slide.shapes.add_picture(path, Inches(x), Inches(y),
                                    Inches(w) if w else None, Inches(h) if h else None)


def source(slide, t, dark=False):
    text(slide, 0.6, 7.0, 12.1, 0.3, t, size=10, color=PALE if dark else MUTED)


def style_chart(chart, colors, legend=True, size=12):
    chart.font.size = Pt(size)
    chart.font.name = BODY
    chart.font.color.rgb = MUTED
    for s, c in zip(chart.plots[0].series, colors):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = c
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.TOP
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(size)
    va = chart.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = RGBColor(0xE3, 0xE7, 0xE6)
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(size - 1)
    ca = chart.category_axis
    ca.format.line.color.rgb = PALE
    ca.tick_labels.font.size = Pt(size)


share = TYP.pivot(index="corridor", columns="road_type", values="share").reindex(CORR)
gall = GROW[GROW.road_type == "all"].set_index("corridor").reindex(CORR)

# ---------------------------------------------------------------- 1 title
s = prs.slides.add_slide(BLANK); bg(s, DARK)
picture(s, f"{S}/m01_title.png", 6.35, 0.5, h=6.5)
text(s, 0.7, 1.7, 5.4, 0.4, "UGANDA TRADE CORRIDORS · OPEN-DATA STUDY", size=13, color=SAND, bold=True)
text(s, 0.7, 2.2, 5.4, 2.4, "Highways that became high streets", size=48, font=HEAD, bold=True, color=WHITE)
text(s, 0.7, 4.7, 5.4, 1.2,
     "What slows Uganda's main trade corridors, what each cause costs in time, fuel and safety, "
     "and how fast the roadside is filling in", size=18, color=PALE)
text(s, 0.7, 6.3, 7.4, 0.4, "Charles Gava", size=16, color=WHITE, bold=True)
s.notes_slide.notes_text_frame.text = (
    f"This study looks at the {NW} main roads out of Kampala. They were built to carry freight to the borders, "
    "but along much of their length they now also serve as the main street of villages and towns.")

# ---------------------------------------------------------------- 2 background: corridors
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, f"{NW.capitalize()} roads carry Uganda's trade",
      "A landlocked economy depends on a few paved routes to the sea and to its neighbours")
LEADS = {"kampala_malaba": "Kenya border; Northern Corridor to Mombasa",
         "kampala_elegu": "South Sudan border; Juba and the Gulu logistics hub",
         "kampala_katuna": "Rwanda border; Kigali and the Central Corridor",
         "kampala_hoima": "Albertine oil region",
         "kampala_bwera": "DR Congo border at Mpondwe; Kasese and North Kivu"}
rh = 5.0 / N
y = 1.95
for c in CORR:
    cfg = C.CORRIDORS[c]
    route = cfg["label"].split(",")[0].split(" (")[0]
    box(s, 0.6, y, 7.2, rh - 0.12, TINT)
    circle_num(s, 0.8, y + (rh - 0.12 - 0.6) / 2, 0.6, cfg["ref"], fill=CCOL[c], size=14)
    text(s, 1.65, y + 0.1, 4.9, 0.4, route, size=15, bold=True)
    text(s, 1.65, y + 0.45, 5.9, 0.4, LEADS.get(c, ""), size=12.5, color=MUTED)
    text(s, 6.3, y + 0.1, 1.3, 0.4, f"{KM[c]:.0f} km", size=15, bold=True, align=PP_ALIGN.RIGHT)
    y += rh
picture(s, f"{S}/m01.png", 8.3, 1.8, h=5.1)
source(s, "Map: corridor centrelines built from OpenStreetMap routes; squares are weighbridges, bars are border crossings.")
s.notes_slide.notes_text_frame.text = (
    f"Together the {NW} corridors cover about {KM.sum():,.0f} km. Four reach a border; the Hoima road serves the oil region. "
    "The Bwera road (A5) was added after the regional search found it as Kampala's fifth national route out of the city.")

# ---------------------------------------------------------------- 3 background: high streets
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "The same roads are now village high streets",
      "Markets, shops, schools, taxi stops and junctions have gathered along the tarmac")
stats = [(rng(share["roadside settlement"] * 100, suffix="%"), "of each corridor's length is\nroadside settlement", SAND),
         (rng(share["open road"] * 100, suffix="%"), "is still open road", GRN),
         (f"{BUILDINGS_M:.2f} M", f"building footprints within\n1 km of the {NW} roads", LAT)]
x = 0.6
for big, lab, col in stats:
    box(s, x, 2.1, 3.85, 2.3, TINT)
    text(s, x + 0.35, 2.35, 3.2, 1.0, big, size=54, bold=True, color=col, font=HEAD)
    text(s, x + 0.35, 3.45, 3.3, 0.8, lab, size=16, color=INK)
    x += 4.12
text(s, 0.6, 4.85, 12.1, 1.8, [
    [("Every village trading centre on a trunk road does two jobs. ", {"bold": True}),
     ("Long-distance trucks need speed and reliability; residents need to cross, stop, trade and turn. "
      "Where the two meet, traffic slows, crashes rise and freight costs grow.", {})],
    [("Nobody has measured, corridor-wide, how much time this costs, or how quickly it is spreading.",
      {"color": LAT, "bold": True})],
], size=18, space_after=10)
s.notes_slide.notes_text_frame.text = (
    "Shares come from clustering 500 m pieces of road into three types. Towns are "
    f"{rng(share['town'] * 100, suffix='%')} of length. Building counts are Google Open Buildings v3.")

# ---------------------------------------------------------------- 4 research problem
s = prs.slides.add_slide(BLANK); bg(s, DARK)
title(s, "Research problem", dark=True)
text(s, 0.6, 1.45, 6.0, 3.6, [
    [("Delay on Uganda's corridors is widely felt but poorly measured.", {"bold": True, "color": WHITE, "size": 22})],
    "Commercial traffic feeds need permissions and carry caveats. Public GPS traces on these roads are few and "
    "mostly from 2007–2013. There are no corridor-wide surveys of what slows traffic.",
    "So planners cannot say which causes cost the most time, where they concentrate, or whether they are getting worse.",
], size=17, color=PALE, space_after=14)
qs = [("1", "Where on each road is travel slowed, and by which causes?"),
      ("2", "How much has the roadside been built up since 2000?"),
      ("3", "Which stretches, and which fixes, would save the most time, fuel and risk?")]
y = 1.6
for n, q in qs:
    box(s, 7.1, y, 5.6, 1.35, RGBColor(0x22, 0x36, 0x3C))
    circle_num(s, 7.4, y + 0.35, 0.65, n, fill=LAT, size=20)
    text(s, 8.35, y + 0.2, 4.1, 0.95, q, size=18, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
    y += 1.6
text(s, 0.6, 5.6, 6.0, 1.0,
     [[("Approach: ", {"bold": True, "color": SAND}),
       ("measure the causes of delay from open data, cost them in minutes, fuel and exposure, "
        "and check the result against published trip, transit and crash records.", {})]],
     size=16, color=PALE)

# ---------------------------------------------------------------- 5 data
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Data: open sources only", "Every cause is measured from public data; published records are used only to check the model")
cards = [
    ("Roads & controls", "OpenStreetMap", "Routes, joining roads, signals, crossings, humps, police posts, weighbridges, water"),
    ("Buildings & growth", "Open Buildings v3 · GHSL", f"{BUILDINGS_M:.2f} M footprints within 1 km; built-up surface 2000–2020"),
    ("Terrain & rain", "Copernicus GLO-30 · CHIRPS", "Climb and grade per 500 m; daily rain 2006–2025"),
    ("Trip times", "Rome2rio, bus timetables", "Independent car trip times to check the model"),
    ("Trucks", "NCTTCA Observatory 2025–26", "GPS and RECTS transit times, stop reasons, border times, station truck counts"),
    ("Crashes", "Uganda Police traffic officers", "About 60 named crash black spots on the corridors (2018)"),
]
for i, (h, src, d) in enumerate(cards):
    cx = 0.6 + (i % 3) * 4.1
    cy = 2.0 + (i // 3) * 2.45
    box(s, cx, cy, 3.85, 2.2, TINT)
    text(s, cx + 0.3, cy + 0.25, 3.3, 0.4, h, size=20, bold=True, font=HEAD)
    text(s, cx + 0.3, cy + 0.72, 3.3, 0.35, src, size=14, bold=True, color=LAT)
    text(s, cx + 0.3, cy + 1.1, 3.3, 1.0, d, size=14, color=MUTED)
source(s, "Also: Sentinel-2 imagery for an experimental moving-truck index (not used in the model); NCTTCA GHG Emissions Baseline 2025 for truck counts.")

# ---------------------------------------------------------------- 6 method flow
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Methodology", "From road geometry to minutes, litres and exposure, with uncertainty carried through every step")
steps = [
    ("Cut", "Each corridor into 500 m pieces, every measurable cause attached"),
    ("Classify", "K-means on roadside measures: open road, roadside settlement, town"),
    ("Model", "Car and loaded-truck speed per piece, reduced by each cause; fixed stops added"),
    ("Attribute", "Switch one cause off at a time to get the minutes and litres it adds"),
    ("Simulate", "1,000 Monte Carlo draws over every assumption for 5–95% ranges"),
    ("Check", "Trip times, truck transit records, weighbridge stops, crash black spots, floods"),
]
w, gap = 1.9, 0.14
for i, (h, d) in enumerate(steps):
    x = 0.6 + i * (w + gap)
    box(s, x, 2.15, w, 3.2, TINT)
    circle_num(s, x + 0.25, 2.4, 0.6, str(i + 1), fill=LAT if i in (2, 3) else DARK, size=18)
    text(s, x + 0.25, 3.2, w - 0.45, 0.45, h, size=18, bold=True, font=HEAD)
    text(s, x + 0.25, 3.7, w - 0.45, 1.6, d, size=14, color=MUTED)
box(s, 0.6, 5.7, 12.1, 1.05, DARK)
text(s, 0.95, 5.85, 11.4, 0.8, [
    [("Causes in the model: ", {"bold": True, "color": SAND}),
     ("roadside activity · joining roads · town speed limits · curves · hills (trucks) · signals and crossings · "
      "speed humps · police posts · weighbridges · rain (wet-day scenario)", {})]],
    size=15, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
s.notes_slide.notes_text_frame.text = (
    "All assumptions and their ranges are at the top of scripts/travel_model.py. Congestion is not modelled: results "
    "describe light traffic. Fuel uses a physical model on the same speed profile (scripts/26_fuel_co2.py).")

# ---------------------------------------------------------------- 7 validation
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "The model reproduces independent trip times", "Car travel time in light traffic, minutes: model vs Rome2rio routing estimate")
est = VAL[VAL.kind == "estimate"].copy()
est["o"] = est.corridor.map(CORR.index)
est = est.sort_values("o")
est["route"] = [src.split("estimate, ")[1] if "estimate, " in src else f"Kampala–{C.CORRIDORS[c]['short']}"
                for src, c in zip(est.source, est.corridor)]
est["diff"] = (est.model_min - est.reported_min) / est.reported_min
cd = CategoryChartData()
cd.categories = list(est.route)
cd.add_series("Model", [float(v) for v in est.model_min])
cd.add_series("Routing estimate", [float(v) for v in est.reported_min])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.9), Inches(7.6), Inches(5.0), cd)
ch = gf.chart
style_chart(ch, [LAT, PALE], size=11)
pl = ch.plots[0]; pl.gap_width = 60; pl.overlap = -5
pl.has_data_labels = True
pl.data_labels.font.size = Pt(12); pl.data_labels.font.color.rgb = INK
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
ch.value_axis.maximum_scale = 400
good = est[est.corridor.isin(["kampala_elegu", "kampala_katuna", "kampala_hoima"])]
bw = est[est.corridor == "kampala_bwera"]
box(s, 8.6, 2.0, 4.1, 2.3, TINT)
text(s, 8.9, 2.2, 3.6, 2.0, [
    [(f"Within {rng(abs(good['diff']) * 100, suffix='%')}", {"bold": True, "size": 26, "color": GRN, "font": HEAD})],
    "on the Gulu, Kabale and Hoima roads." + (f" To Fort Portal the model runs {abs(bw['diff'].iloc[0]):.0%} fast."
                                              if len(bw) else ""),
], size=14, color=INK, space_after=6)
box(s, 8.6, 4.5, 4.1, 2.3, TINT)
text(s, 8.9, 4.7, 3.6, 2.0, [
    [("2–3 h vs ~1.5 h", {"bold": True, "size": 26, "color": LAT, "font": HEAD})],
    "Observed Kampala–Jinja trips far exceed the model. That gap is congestion at the Kampala end.",
], size=14, color=INK, space_after=6)
source(s, "Source: outputs/validation.csv. The Njeru estimate covers a shorter segment than the model's, so it is the least like-for-like.")

# ---------------------------------------------------------------- 8 road types
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Result 1 · Most of each corridor is settlement", "Share of corridor length by road type (500 m pieces, k-means)")
cd = CategoryChartData()
cd.categories = CLAB
for t in ("open road", "roadside settlement", "town"):
    cd.add_series(t.capitalize(), [round(float(v), 3) for v in share[t]])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED_100, Inches(0.5), Inches(1.9), Inches(8.2), Inches(5.0), cd)
ch = gf.chart
style_chart(ch, [GRN, SAND, LAT], size=13)
pl = ch.plots[0]; pl.gap_width = 45; pl.overlap = 100
pl.has_data_labels = True
pl.data_labels.number_format = '0%'; pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.CENTER
pl.data_labels.font.size = Pt(12); pl.data_labels.font.bold = True; pl.data_labels.font.color.rgb = WHITE
ch.category_axis.reverse_order = True
ch.value_axis.tick_labels.number_format = '0%'; ch.value_axis.tick_labels.number_format_is_linked = False
tb = lambda t, col: TYP[TYP.road_type == t][col]  # noqa: E731
text(s, 9.1, 2.1, 3.6, 4.6, [
    [("What the types look like", {"bold": True, "font": HEAD, "size": 19})],
    [("Open road: ", {"bold": True, "color": GRN}), (f"~{rng(tb('open road', 'buildings_100m'))} buildings within 100 m per piece", {})],
    [("Settlement: ", {"bold": True, "color": RGBColor(0xA8, 0x74, 0x10)}),
     (f"~{rng(tb('roadside settlement', 'buildings_100m'))} buildings, ~{rng(tb('roadside settlement', 'joining_roads'), '{:.1f}')} joining roads", {})],
    [("Town: ", {"bold": True, "color": LAT}),
     (f"~{rng(tb('town', 'buildings_100m'))} buildings, {rng(tb('town', 'joining_roads'))} joining roads", {})],
    [(f"The A9 to Hoima has only {TYP[(TYP.corridor == 'kampala_hoima') & (TYP.road_type == 'open road')].km.iloc[0]:.0f} km "
      "of truly open road.", {"italic": True, "color": MUTED})],
], size=15, space_after=12)
source(s, "Source: outputs/typology_summary.csv. Three types chosen by silhouette score, clustered jointly across the corridors.")

# ---------------------------------------------------------------- 9 causes
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Result 2 · Roadside activity is the biggest steady drag",
      "Minutes a loaded truck loses leaving Kampala, by cause (central estimate, dry day, light traffic)")
tc = CAUSE[(CAUSE.vehicle == "truck") & (CAUSE.direction == "outbound")].pivot(index="corridor", columns="cause",
                                                                                values="minutes").reindex(CORR)
causes = [("roadside activity", "Roadside activity", LAT), ("hills (trucks)", "Hills", RGBColor(0x8A, 0x6B, 0x4E)),
          ("weighbridge", "Weighbridges", DARK), ("speed humps (assumed)", "Speed humps (assumed)", SAND),
          ("police posts", "Police posts", RGBColor(0x4E, 0x7C, 0x8A)), ("joining roads", "Joining roads", GRN),
          ("signals and crossings", "Signals & crossings", PALE)]
cd = CategoryChartData()
cd.categories = CLAB
for key, lab, _ in causes:
    cd.add_series(lab, [round(float(v), 1) for v in tc[key]])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED, Inches(0.5), Inches(1.9), Inches(8.4), Inches(5.0), cd)
ch = gf.chart
style_chart(ch, [c for _, _, c in causes], size=12)
ch.plots[0].gap_width = 45; ch.plots[0].overlap = 100
ch.category_axis.reverse_order = True
ch.value_axis.has_title = True
ch.value_axis.axis_title.text_frame.text = "minutes added"
ch.value_axis.axis_title.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
car_first = STAB[(STAB.vehicle == "car") & (STAB.cause == "roadside activity")].share_first
wet = CAUSE[(CAUSE.vehicle == "truck") & (CAUSE.direction == "outbound") & (CAUSE.cause == "rain (wet day)")].minutes
text(s, 9.3, 2.0, 3.4, 4.8, [
    [("Cars: ", {"bold": True, "color": LAT}),
     (f"roadside activity is the largest cause in {rng(car_first * 100, suffix='%')} of draws on every road.", {})],
    [("Trucks: ", {"bold": True, "color": LAT}),
     ("weighbridges lead on the Malaba road, police posts on the Elegu road, hills on the Bwera and Katuna roads; "
      "rankings shift across draws.", {})],
    [(f"A wet day adds a further {rng(wet)} truck minutes.", {"italic": True, "color": MUTED})],
], size=15, space_after=12)
source(s, "Source: outputs/travel_time_causes.csv, outputs/rank_stability.csv. Town speed limits and curves (< 3 min) omitted.")
tt = TOT[(TOT.vehicle == "truck") & (TOT.direction == "outbound")].set_index("corridor").reindex(CORR)
s.notes_slide.notes_text_frame.text = (
    "Totals for a truck (model vs open-road-only): " +
    "; ".join(f"{C.CORRIDORS[c]['short']} {r.minutes:.0f} vs {r.open_road_minutes:.0f} min" for c, r in tt.iterrows()) +
    ". Report rankings with their Monte Carlo shares, not as single numbers.")

# ---------------------------------------------------------------- 9b race animation
s = prs.slides.add_slide(BLANK); bg(s, DARK)
text(s, 0.6, 0.5, 5.2, 1.4, "The same truck, every road", size=32, font=HEAD, bold=True, color=WHITE)
text(s, 0.6, 2.0, 5.0, 3.2, [
    "A loaded truck leaves Kampala on each corridor at the same moment, next to a truck on open road.",
    "Each road colours in with the delay it causes: towns, weighbridges, humps and hills.",
    [("The animation plays in slide-show mode.", {"italic": True, "color": SAND})],
], size=16, color=PALE, space_after=12)
picture(s, os.path.join(FIG, "a2_corridor_race.gif"), 6.3, 0.35, h=6.8)
s.notes_slide.notes_text_frame.text = "figures/a2_corridor_race.gif, from scripts/13_animations.py."

# ---------------------------------------------------------------- 10 hotspots
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
picture(s, f"{S}/m02.png", 0.4, 0.35, h=6.8)
x0 = 7.75
text(s, x0, 0.45, 5.1, 1.4, "Result 3 · Delay concentrates at a few points", size=28, font=HEAD, bold=True)
text(s, x0, 1.95, 5.1, 0.6, "Truck minutes lost per km vs open road; numbered: the worst 2 km stretches", size=14, color=MUTED)
top = HOT.sort_values("truck_excess_min", ascending=False).head(4)
y = 2.75
for r in top.itertuples():
    circle_num(s, x0, y + 0.05, 0.5, str(r.n), fill=DARK, size=15)
    text(s, x0 + 0.7, y, 4.4, 0.35, f"{r.place}, {C.CORRIDORS[r.corridor]['short']} road km {r.km_from:.0f}", size=16, bold=True)
    text(s, x0 + 0.7, y + 0.36, 4.4, 0.4, f"+{r.truck_excess_min:.1f} truck min · {r.main_causes.split(' ')[0]} "
         f"{' '.join(r.main_causes.split(';')[0].split(' ')[1:-1])}".strip(), size=13, color=MUTED)
    y += 0.9
led = HOT.main_causes.str.split(";").str[0].str.contains("weighbridge|police|signals").sum()
text(s, x0, 6.4, 5.1, 0.7, f"{led} of the {len(HOT)} worst stretches are led by weighbridges, police posts or signals.",
     size=14, italic=True, color=LAT)
s.notes_slide.notes_text_frame.text = (
    "Numbers come from outputs/hotspots_mapped.csv. Close-ups of each hotspot are in figures/m03_hotspots.png and figures/hotspots/, "
    "and one atlas sheet per corridor in figures/m05_atlas_*.png.")

# ---------------------------------------------------------------- 11 growth
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Result 4 · The roadside filled in fast, between towns", "Built-up land within 300 m of the road, 2000–2020 (GHSL)")
gw = gall.sort_values("growth_2000_2020_pct", ascending=False)
bw_ = 12.1 / N
for i, (c, r) in enumerate(gw.iterrows()):
    x = 0.6 + i * bw_
    box(s, x, 1.85, bw_ - 0.12, 0.75, TINT)
    text(s, x + 0.15, 1.9, bw_ - 0.3, 0.4, f"+{r.growth_2000_2020_pct:.0f}%", size=22, bold=True, color=LAT, font=HEAD)
    text(s, x + 1.3, 2.0, bw_ - 1.45, 0.5, f"{C.CORRIDORS[c]['short']} ({C.CORRIDORS[c]['ref']})", size=13, color=INK)
picture(s, f"{S}/m04.png", 0.6, 2.75, w=12.1)
gset = GROW[GROW.road_type == "roadside settlement"].growth_pct
gtown = GROW[GROW.road_type == "town"].growth_pct
source(s, f"Roadside settlements grew {rng(gset, suffix='%')}, towns {rng(gtown, suffix='%')}. Maps: each corridor's "
       "fastest-growing 5 km; grey built by 2000, orange 2000–2020.")
s.notes_slide.notes_text_frame.text = (
    "Hectares within 300 m, 2000 to 2020: " +
    "; ".join(f"{C.CORRIDORS[c]['short']} {r.built_ha_2000:,.0f} to {r.built_ha_2020:,.0f}" for c, r in gall.iterrows()) +
    ". GHSL's projection gives only +5–10% for 2020–2026, far slower than the observed trend.")

# ---------------------------------------------------------------- 11b growth animation
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Twenty years of roadside building", "Each corridor's fastest-growing stretch, 2000–2020 (GHSL, observed)")
picture(s, os.path.join(FIG, "a1_roadside_growth.gif"), 0.6, 1.95, w=12.1)
source(s, "figures/a1_roadside_growth.gif. Plays in slide-show mode. A version continued to 2026 on GHSL's projection is in figures/.")

# ---------------------------------------------------------------- 11c time map
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "When distance becomes time", "The corridors redrawn so that length is loaded-truck travel time; dots mark each hour")
picture(s, os.path.join(S, "g04.png"), 0.9, 1.85, h=5.0)
source(s, "figures/g04_time_map.png. Grey: the roads as mapped. Towns, controls and hills stretch the lines.")

# ---------------------------------------------------------------- NEW transit gap
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Result 5 · Trucks spend most of the trip standing still",
      "Observed truck transit, Kampala ↔ border (NCTTCA Observatory 2025–26), against the model's driving time")
picture(s, os.path.join(FIG, "f14_transit_gap.png"), 0.4, 1.85, w=8.4)
wb = MIX[MIX.item == "Weighbridge"].median_hours.iloc[0] * 60
rest = MIX[MIX.item == "Rest/meals"].stopped_time_share_pct.iloc[0]
bord = MIX[MIX.item == "Border post procedures"].stopped_time_share_pct.iloc[0]
items = [(f"{rng(GAP.observed_h)} h", f"observed between Kampala and the borders; the model drives it in {rng(GAP.model_driving_h)} h."),
         (f"{rng(GAP.friction_share_pct)}%", "of the real truck trip is roadside and control friction; the rest is stopped time."),
         (f"{rest + bord:.0f}%", "of stopped time is rest, meals and border procedures (approx.)."),
         (f"{wb:.0f} min", "median weighbridge stop: the model's 10 min (5–30) assumption holds.")]
y = 1.95
for big, t in items:
    text(s, 9.1, y, 3.6, 0.5, big, size=24, bold=True, color=LAT, font=HEAD)
    text(s, 9.1, y + 0.5, 3.6, 0.8, t, size=12.5, color=INK)
    y += 1.25
source(s, "outputs/transit_gap.csv, transit_stop_mix.csv (scripts/24_transit_gap.py). GPS: fleet sample; RECTS: bonded transit cargo. Kampala–Hoima not reported.")
s.notes_slide.notes_text_frame.text = (
    "The Malaba border crossing averaged 48 min in 2025 (Busia 2.55 h), against about 2 h lost to friction on the "
    "Kampala–Malaba road. Fixing roadside friction matters for reliability and safety, but truck transit time is "
    "dominated by stops: rest, border procedures, insecurity and administrative checks.")

# ---------------------------------------------------------------- 12a fixes
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Result 6 · Controls are the quickest wins", "Truck minutes saved per trip leaving Kampala, by fix (central estimate)")
cd = CategoryChartData()
cd.categories = CLAB
fixes = [("wim", "Weigh-in-motion", GRN), ("no_police", "No police stops", RGBColor(0x4E, 0x7C, 0x8A)),
         ("bypass_2", "Bypass 2 worst towns", SAND), ("service_all", "Service roads, all settlements", LAT)]
for key, lab, _ in fixes:
    d = SC[(SC.vehicle == "truck") & (SC.scenario == key)].set_index("corridor").reindex(CORR)
    cd.add_series(lab, [round(float(v), 1) for v in d.minutes_saved])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.9), Inches(8.2), Inches(5.0), cd)
ch = gf.chart
style_chart(ch, [c for _, _, c in fixes], size=11)
pl = ch.plots[0]; pl.gap_width = 60; pl.overlap = -5
pl.has_data_labels = True
pl.data_labels.number_format = '0'; pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.data_labels.font.size = Pt(10); pl.data_labels.font.color.rgb = INK
tcost = COST[COST.vehicle == "truck"].cost_per_year_usd_m.sum()
fy = FUEL.groupby("corridor").friction_fuel_usd_year_m.first().sum()
text(s, 9.1, 2.05, 3.6, 4.8, [
    [(f"US${tcost:.0f} M a year", {"bold": True, "size": 28, "color": LAT, "font": HEAD})],
    "in truck time lost to delay on the five roads at central values, plus about "
    f"US${fy:.0f} M in extra diesel burnt slowing and re-accelerating.",
    [("Weigh-in-motion and ending police stops save more per trip than bypasses in light traffic. "
      "Truck counts are surveyed on the Malaba, Katuna and Bwera roads, assumed on the others.", {"color": MUTED})],
], size=14, space_after=10)
source(s, "outputs/scenarios.csv, costs.csv, fuel_co2.csv (scripts 16, 17, 26). Congestion relief from bypasses is not captured by the light-traffic model.")

# ---------------------------------------------------------------- NEW fuel and CO2
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Result 7 · Stop-go costs fuel and carbon", "Extra diesel per loaded truck trip from friction, and CO₂ a year (physical fuel model, 1,000 draws)")
picture(s, os.path.join(FIG, "f16_fuel_co2.png"), 0.6, 1.8, w=12.1)
fo = FUEL[FUEL.direction == "outbound"]
co2 = FUEL.groupby("corridor").friction_co2_kt_year.first().sum()
source(s, f"{rng(fo.friction_litres_trip)} L extra per trip ({rng(fo.friction_pct_of_trip_fuel)}% of trip fuel); about {co2:.0f} kt CO₂ "
       "a year. Humps are assumed (one per town piece), so the Malaba figure has a wide range. outputs/fuel_co2.csv.")

# ---------------------------------------------------------------- 12b safety and reliability
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Result 8 · Settlements carry most of the risk", "Roadside settlements: share of people within 300 m vs share of exposure (people × trucks × speed⁴)")
cd = CategoryChartData()
cd.categories = CLAB
st = SB[SB.road_type == "roadside settlement"].set_index("corridor").reindex(CORR)
cd.add_series("Share of people", [round(float(v), 2) for v in st.people_share])
cd.add_series("Share of exposure", [round(float(v), 2) for v in st.exposure_share])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.5), Inches(1.9), Inches(7.6), Inches(5.0), cd)
ch = gf.chart
style_chart(ch, [SAND, LAT], size=12)
pl = ch.plots[0]; pl.gap_width = 55; pl.overlap = -5
pl.has_data_labels = True
pl.data_labels.number_format = '0%'; pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.data_labels.font.size = Pt(12); pl.data_labels.font.color.rgb = INK
ch.category_axis.reverse_order = True
ch.value_axis.maximum_scale = 1.0
ch.value_axis.tick_labels.number_format = '0%'; ch.value_axis.tick_labels.number_format_is_linked = False
tr = REL[REL.vehicle == "truck"]
box(s, 8.5, 2.0, 4.2, 2.3, TINT)
text(s, 8.8, 2.2, 3.7, 2.0, [
    [("Trucks run at 55–60 km/h", {"bold": True, "size": 22, "color": LAT, "font": HEAD})],
    "through settlements that are not classed as towns, so risk concentrates where people live between towns.",
], size=13, space_after=6)
box(s, 8.5, 4.5, 4.2, 2.3, TINT)
fl = FLD.iloc[0] if len(FLD) else None
text(s, 8.8, 4.7, 3.7, 2.0, [
    [(f"{tr.buffer_index.min():.0%}–{tr.buffer_index.max():.0%} slower", {"bold": True, "size": 22, "color": DARK, "font": HEAD})],
    "on a bad-rain day (95th percentile, 2006–2025) than on a typical day." +
    (f" The May 2020 Mpondwe flood stretch ranks at the {fl.percentile:.0f}th percentile of flood exposure." if fl is not None else ""),
], size=13, space_after=6)
source(s, "outputs/safety_by_type.csv, reliability.csv, flood_events_check.csv (scripts 18, 19). Exposure is not a crash rate.")

# ---------------------------------------------------------------- NEW black spots
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Result 9 · Police crash black spots sit in busy settlements",
      "Stretches holding a named black spot, against random stretches near a named place (5,000 permutations)")
picture(s, os.path.join(FIG, "f15_black_spots.png"), 0.4, 1.85, w=8.3)
bn = BS[BS.null == "stretches near a named place"].set_index("measure")
g_ = lambda m, k: bn.loc[m, k]  # noqa: E731
pfmt = lambda p: "p < 0.001" if p < 0.001 else f"p = {p:.3f}"  # noqa: E731
items = [(f"{int(BSM.matched.sum())} / {len(BSM)}", "police-named black spots located by name in OSM."),
         (f"{g_('buildings within 300 m', 'black_spot_mean_pct'):.0f}th pct", f"on roadside buildings "
          f"({pfmt(g_('buildings within 300 m', 'p_value'))}); joining roads {g_('joining roads', 'black_spot_mean_pct'):.0f}th."),
         (f"{g_('truck speed', 'black_spot_mean_pct'):.0f}th pct", f"on truck speed ({pfmt(g_('truck speed', 'p_value'))}): "
          "black spots are slower, busier places, not fast bends."),
         (f"{g_('safety exposure index', 'black_spot_mean_pct'):.0f}th pct", "on the exposure index "
          f"({pfmt(g_('safety exposure index', 'p_value'))}): its speed⁴ term under-weights busy, slower places.")]
y = 1.95
for big, t in items:
    text(s, 9.0, y, 3.7, 0.5, big, size=22, bold=True, color=LAT, font=HEAD)
    text(s, 9.0, y + 0.48, 3.7, 0.8, t, size=12.5, color=INK)
    y += 1.22
source(s, "Daily Monitor (23 Dec 2018), black spots named by Uganda Police traffic officers; outputs/black_spots_*.csv (script 25). "
       "Name matching misses forest and swamp spots.")

# ---------------------------------------------------------------- 12c rail
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
picture(s, os.path.join(S, "f12.png"), 0.4, 0.35, h=6.8)
x0 = 7.0
text(s, x0, 0.45, 5.8, 1.3, "Rail along the bottlenecks", size=30, font=HEAD, bold=True)
text(s, x0, 1.35, 5.8, 0.6, "Least-cost screening alignments and the existing metre-gauge railway", size=14, color=MUTED)
near = RP[(RP.corridor == "kampala_malaba") & (RP.railway == "in use")].share_of_truck_delay.iloc[0]
others = RP[(RP.corridor != "kampala_malaba") & (RP.railway == "in use")].share_of_truck_delay.max()
g = lambda line, var, m: RE[(RE.line == line) & (RE.variant == var) & (RE.measure == m)].iloc[0]  # noqa: E731
be = g("Eastern", "through from Mombasa", "freight needed to break even")
bc = g("Eastern", "through from Mombasa", "benefit / cost")
rt = g("Eastern", "domestic", "door-to-door time by rail")
dom = RE[(RE.variant == "domestic") & (RE.measure == "benefit / cost")]
items = [(f"{near:.0%}", f"of the Malaba road's truck delay lies within 10 km of the railway the SGR follows; "
                         f"on the other roads, {others:.0%} or less."),
         (f"{rt.central:.0f} h", "door to door by rail for domestic freight on the eastern line, against about 5 h by truck: "
                                 "terminals, not line-haul, set the time."),
         (f"≤ {dom.p95.max():.2f}", f"benefit/cost for any of the {len(dom)} lines on Ugandan freight alone; through traffic from "
                                    f"Mombasa needs about {be.central:.0f} Mt a year to break even."),
         ]
y = 2.2
for big, t in items:
    text(s, x0, y, 1.6, 0.7, big, size=26, bold=True, color=LAT, font=HEAD)
    text(s, x0 + 1.75, y + 0.05, 4.05, 1.3, t, size=13, color=INK)
    y += 1.45
text(s, x0, 6.45, 5.8, 0.6, "Counting only freight costs and CO2 from today's Ugandan traffic: transit growth, passengers and "
     "congestion relief carry the case.", size=12, italic=True, color=MUTED)
s.notes_slide.notes_text_frame.text = (
    "scripts/23_rail.py. Alignments minimise length x grade above 1.5% x built-up share inside 25 km of each road; screening only. "
    "Capital cost from the eastern SGR contract (EUR 2.7 bn for 273 km). 30% of each road's truck freight moved (15-50%). "
    f"Eastern line with through traffic: benefit/cost {bc.central:.2f} (up to {bc.p95:.2f}).")

# ---------------------------------------------------------------- discussion
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Discussion", "What the results suggest for corridor policy")
pts = [
    ("Settlement is the chronic problem", LAT,
     "Roadside activity costs the most time for cars on every road, is growing fastest where it is newest, and is where "
     "police place their crash black spots. Access management and service roads address the cause."),
    ("Controls are the cheap wins", DARK,
     "Weighbridges and police posts produce the worst single stretches. Weigh-in-motion and ending police stops save "
     "more per trip than bypasses in light traffic, and cut stop-go fuel."),
    ("Stopped time dwarfs driving time", GRN,
     "Trucks take 17–93 h between Kampala and the borders, of which friction is a small share. Rest, border and "
     "administrative stops need their own reforms alongside the road."),
    ("Growth outpaces the road", SAND,
     f"At {rng(gall.growth_2000_2020_pct, suffix='%')} in 20 years, today's open road is tomorrow's settlement. "
     "Land-use control along the corridors is time-critical."),
]
for i, (h, col, d) in enumerate(pts):
    cx = 0.6 + (i % 2) * 6.15
    cy = 1.95 + (i // 2) * 2.5
    box(s, cx, cy, 5.95, 2.3, TINT)
    circle_num(s, cx + 0.3, cy + 0.3, 0.5, str(i + 1), fill=col, size=15)
    text(s, cx + 1.0, cy + 0.33, 4.7, 0.45, h, size=19, bold=True, font=HEAD)
    text(s, cx + 1.0, cy + 0.85, 4.7, 1.4, d, size=14, color=MUTED)
s.notes_slide.notes_text_frame.text = (
    "These are implications from a light-traffic model, not project appraisals. The weighbridge stop assumption is now "
    "supported by the Observatory's measured median of 12 minutes.")

# ---------------------------------------------------------------- limits
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Limitations and next steps")
lims = [
    ("Congestion is not modelled", "Results describe light traffic; peak-hour delay near Kampala is larger."),
    ("Speed humps are under-mapped", "One per town piece is assumed (range 0–2); they drive the Malaba fuel figure."),
    ("Truck counts are partly assumed", "Surveyed on the Malaba, Katuna and Bwera roads; assumed on the Elegu and Hoima roads."),
    ("Growth data end in 2020", "GHSL's projection to 2026 is slower than the observed trend."),
]
y = 1.55
for h, d in lims:
    box(s, 0.6, y, 7.3, 1.15, TINT)
    text(s, 0.9, y + 0.15, 6.8, 0.4, h, size=17, bold=True)
    text(s, 0.9, y + 0.55, 6.8, 0.55, d, size=14, color=MUTED)
    y += 1.3
box(s, 8.3, 1.55, 4.4, 5.05, DARK)
text(s, 8.65, 1.85, 3.8, 4.6, [
    [("Next steps", {"bold": True, "size": 22, "color": WHITE, "font": HEAD})],
    "Count speed humps from Mapillary street-level detections",
    "Observe 2016–2023 growth with Open Buildings 2.5D Temporal",
    "Swap GLO-30 for FABDEM terrain",
    "Apply the method to eleven capitals (regional paper)",
    "Write up the paper",
], size=15, color=PALE, space_after=12)

# ---------------------------------------------------------------- close
s = prs.slides.add_slide(BLANK); bg(s, DARK)
text(s, 0.7, 1.2, 11.9, 0.5, "CONCLUSION", size=13, bold=True, color=SAND)
text(s, 0.7, 1.75, 11.9, 1.5, "Uganda's corridors are becoming high streets faster than they are being managed as highways.",
     size=34, font=HEAD, bold=True, color=WHITE)
cl = [("1", "Open data alone reproduce trip times within a few percent, outside Kampala."),
      ("2", "Roadside activity is the largest steady delay; weighbridges are the worst single points."),
      ("3", f"Roadside building grew {rng(gall.growth_2000_2020_pct, suffix='%')} in 2000–2020, mostly between towns."),
      ("4", "Friction is a small part of truck transit, but it costs fuel and sits where crashes happen.")]
y = 3.55
for n, t in cl:
    circle_num(s, 0.7, y, 0.55, n, fill=LAT, size=16)
    text(s, 1.55, y + 0.02, 11.0, 0.55, t, size=19, color=PALE, anchor=MSO_ANCHOR.MIDDLE)
    y += 0.72
text(s, 0.7, 6.55, 11.9, 0.4, "Code, outputs, maps and animations: github.com/gavacharles/uganda-trade-corridors", size=13, color=PALE)

prs.save(OUT)
print("saved", OUT, f"({len(prs.slides)} slides)")
