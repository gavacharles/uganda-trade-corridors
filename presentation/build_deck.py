"""Build presentation/highways_high_streets.pptx from the figures and outputs of the study.

    python presentation/build_deck.py

Needs python-pptx and Pillow. Numbers on the new-results slides are read from outputs/.
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
import os, tempfile
import pandas as pd
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIG = os.path.join(ROOT, "figures")
OUTP = os.path.join(ROOT, "outputs")
OUT = os.path.join(ROOT, "presentation", "highways_high_streets.pptx")
S = tempfile.mkdtemp()   # cropped images for the slides


def crop(src, box, name):
    Image.open(os.path.join(FIG, src)).crop(box).save(os.path.join(S, name))


crop("m01_study_area.png", (160, 150, 1375, 1530), "m01.png")
crop("m01_study_area.png", (160, 340, 1375, 1530), "m01_title.png")
crop("m02_bottlenecks.png", (140, 140, 1590, 1545), "m02.png")
crop("g04_time_map.png", (0, 120, 1713, 1005), "g04.png")
crop("f12_rail_map.png", (0, 60, 1193, 1318), "f12.png")
_im = Image.open(os.path.join(FIG, "m04_growth.png"))
_f = 1.0575
_panels = [_im.crop((int(x0 * _f), int(180 * _f), int((x0 + 472) * _f), int(705 * _f))) for x0 in (14, 514, 1014, 1514)]
_w, _h = _panels[0].size
_g = Image.new("RGB", (2 * _w + 20, 2 * _h + 20), (255, 255, 255))
for _i, _p in enumerate(_panels):
    _g.paste(_p, ((_i % 2) * (_w + 20), (_i // 2) * (_h + 20)))
_g.save(os.path.join(S, "m04_grid.png"))
SC = pd.read_csv(os.path.join(OUTP, "scenarios.csv"))
SB = pd.read_csv(os.path.join(OUTP, "safety_by_type.csv"))
REL = pd.read_csv(os.path.join(OUTP, "reliability.csv"))
COST = pd.read_csv(os.path.join(OUTP, "costs.csv"))
RE = pd.read_csv(os.path.join(OUTP, "rail_economics.csv"))
RP = pd.read_csv(os.path.join(OUTP, "rail_proximity.csv"))
CORR = ["kampala_malaba", "kampala_elegu", "kampala_katuna", "kampala_hoima"]
CLAB = ["Malaba (A1)", "Elegu (A6)", "Katuna (A2)", "Hoima (A9)"]

DARK = RGBColor(0x17, 0x25, 0x2A)
LAT = RGBColor(0xC4, 0x53, 0x2D)      # laterite red: delay / growth
GRN = RGBColor(0x3A, 0x7D, 0x5C)      # savanna green: open road
SAND = RGBColor(0xD9, 0xA4, 0x41)     # settlement
INK = RGBColor(0x1E, 0x25, 0x28)
MUTED = RGBColor(0x5B, 0x67, 0x70)
TINT = RGBColor(0xEE, 0xF2, 0xF0)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
PALE = RGBColor(0xB8, 0xC7, 0xC4)
HEAD, BODY = "Cambria", "Calibri"

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


# ---------------------------------------------------------------- 1 title
s = prs.slides.add_slide(BLANK); bg(s, DARK)
picture(s, f"{S}/m01_title.png", 6.45, 0.45, h=6.6)
text(s, 0.7, 1.7, 5.4, 0.4, "UGANDA TRADE CORRIDORS · OPEN-DATA STUDY", size=13, color=SAND, bold=True)
text(s, 0.7, 2.2, 5.4, 2.4, "Highways that became high streets", size=48, font=HEAD, bold=True, color=WHITE)
text(s, 0.7, 4.7, 5.4, 1.2,
     "What slows Uganda's main trade corridors, what each cause costs in travel time, "
     "and how fast the roadside is filling in", size=18, color=PALE)
text(s, 0.7, 6.3, 7.4, 0.4, "Charles Gava", size=16, color=WHITE, bold=True)
s.notes_slide.notes_text_frame.text = (
    "This study looks at the four main roads out of Kampala. They were built to carry freight to the borders, "
    "but along much of their length they now also serve as the main street of villages and towns.")

# ---------------------------------------------------------------- 2 background: corridors
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Four roads carry Uganda's trade", "A landlocked economy depends on a few paved routes to the sea and to its neighbours")
rows = [
    ("A1", "Kampala → Jinja → Malaba", "216 km", "Kenya border; Northern Corridor to Mombasa", RGBColor(0x2A, 0x78, 0xD6)),
    ("A6", "Kampala → Gulu → Elegu", "431 km", "South Sudan border; Juba and the Gulu logistics hub", RGBColor(0xE8, 0x64, 0x3A)),
    ("A2", "Kampala → Masaka → Mbarara → Katuna", "426 km", "Rwanda border; Kigali and the Central Corridor", RGBColor(0x1A, 0xA8, 0x78)),
    ("A9", "Kampala → Hoima", "194 km", "Albertine oil region", RGBColor(0xE8, 0x9C, 0x10)),
]
y = 2.0
for code, route, km, to, col in rows:
    box(s, 0.6, y, 7.2, 1.05, TINT)
    circle_num(s, 0.85, y + 0.2, 0.65, code, fill=col, size=15)
    text(s, 1.75, y + 0.16, 4.6, 0.4, route, size=17, bold=True)
    text(s, 1.75, y + 0.55, 5.9, 0.4, to, size=14, color=MUTED)
    text(s, 6.3, y + 0.16, 1.3, 0.4, km, size=17, bold=True, color=INK, align=PP_ALIGN.RIGHT)
    y += 1.2
picture(s, f"{S}/m01.png", 8.3, 1.8, h=5.1)
source(s, "Map: corridor centrelines built from OpenStreetMap routes; squares are weighbridges, bars are border crossings.")
s.notes_slide.notes_text_frame.text = (
    "Together the four corridors cover about 1,270 km. Three reach a border; the Hoima road serves the oil region. "
    "Almost all of Uganda's imports and exports, and transit freight to South Sudan, Rwanda and DR Congo, use them.")

# ---------------------------------------------------------------- 3 background: high streets
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "The same roads are now village high streets",
      "Markets, shops, schools, taxi stops and junctions have gathered along the tarmac")
stats = [("58–76%", "of each corridor's length is\nroadside settlement", SAND),
         ("17–34%", "is still open road", GRN),
         ("1.25 M", "building footprints within\n1 km of the four roads", LAT)]
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
    "Shares come from clustering 500 m pieces of road into three types. Most of each corridor is now roadside settlement; "
    "towns are 8–22% of length. Building counts are Google Open Buildings v3.")

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
      ("3", "Which stretches, and which fixes, would save the most time?")]
y = 1.6
for n, q in qs:
    box(s, 7.1, y, 5.6, 1.35, RGBColor(0x22, 0x36, 0x3C))
    circle_num(s, 7.4, y + 0.35, 0.65, n, fill=LAT, size=20)
    text(s, 8.35, y + 0.2, 4.1, 0.95, q, size=18, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
    y += 1.6
text(s, 0.6, 5.6, 6.0, 1.0,
     [[("Approach: ", {"bold": True, "color": SAND}),
       ("don't watch the traffic; measure the causes of delay from open data, cost them in minutes, "
        "and check the result against published trip times.", {})]],
     size=16, color=PALE)
s.notes_slide.notes_text_frame.text = (
    "The framing is deliberate: without usable traffic data, the study measures causes rather than observing speeds. "
    "This matches the approach of the companion accessibility study.")

# ---------------------------------------------------------------- 5 data
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Data: open sources only", "Every cause is measured from public data; nothing comes from traffic feeds, project records or surveys")
cards = [
    ("Roads & controls", "OpenStreetMap", "Routes, joining roads, signals, crossings, humps, police posts, weighbridges, water"),
    ("Buildings", "Google Open Buildings v3", "1.25 M footprints within 1 km; roadside activity within 100 m and 300 m"),
    ("Growth", "GHSL built-up surface", "2000–2020 observed, 2025–2030 projected, within 300 m of the road"),
    ("Terrain", "Copernicus GLO-30 DEM", "Climb in each direction and average grade, per 500 m"),
    ("Rain", "CHIRPS 2006–2025", "Days a year with ≥ 10 mm of rain"),
    ("Validation", "Routing estimates, bus timetables", "Independent trip times to check the model against"),
]
for i, (h, src, d) in enumerate(cards):
    cx = 0.6 + (i % 3) * 4.1
    cy = 2.0 + (i // 3) * 2.45
    box(s, cx, cy, 3.85, 2.2, TINT)
    text(s, cx + 0.3, cy + 0.25, 3.3, 0.4, h, size=20, bold=True, font=HEAD)
    text(s, cx + 0.3, cy + 0.72, 3.3, 0.35, src, size=14, bold=True, color=LAT)
    text(s, cx + 0.3, cy + 1.1, 3.3, 1.0, d, size=14, color=MUTED)
source(s, "Also: Sentinel-2 imagery for an experimental moving-truck index (not used in the model); NCTTCA Transport Observatory 2022 roughness data as context.")

# ---------------------------------------------------------------- 6 method flow
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Methodology", "From road geometry to minutes lost, with uncertainty carried through every step")
steps = [
    ("Cut", "Each corridor into 500 m pieces, every measurable cause attached"),
    ("Classify", "K-means on roadside measures: open road, roadside settlement, town"),
    ("Model", "Car and loaded-truck speed per piece, reduced by each cause; fixed stops added"),
    ("Attribute", "Switch one cause off at a time to get the minutes it adds"),
    ("Simulate", "1,000 Monte Carlo draws over every assumption for 5–95% ranges"),
    ("Validate", "Check against trip times; map the 10 worst 2 km on each road"),
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
    "Each piece starts at an open-road speed, reduced by roadside activity, joining roads, a town limit, curves, and for "
    "trucks, hills. Fixed delays are added for signals, crossings, assumed humps in towns, police posts and weighbridges. "
    "All assumptions and their ranges are at the top of 10_travel_time.py. Congestion is not modelled: results describe light traffic.")

# ---------------------------------------------------------------- 7 validation
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "The model reproduces independent trip times", "Car travel time in light traffic, minutes: model vs Rome2rio routing estimate")
cd = CategoryChartData()
cd.categories = ["Kampala–Gulu", "Kampala–Kabale", "Kampala–Hoima", "Kampala–Njeru"]
cd.add_series("Model", (266, 344, 164, 87))
cd.add_series("Routing estimate", (286, 345, 172, 66))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.9), Inches(7.6), Inches(5.0), cd)
ch = gf.chart
style_chart(ch, [LAT, PALE])
pl = ch.plots[0]; pl.gap_width = 60; pl.overlap = -5
pl.has_data_labels = True
pl.data_labels.font.size = Pt(13); pl.data_labels.font.color.rgb = INK
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
ch.value_axis.maximum_scale = 400
box(s, 8.6, 2.0, 4.1, 2.3, TINT)
text(s, 8.9, 2.2, 3.6, 2.0, [
    [("Within 1–7%", {"bold": True, "size": 26, "color": GRN, "font": HEAD})],
    "on the Gulu, Kabale and Hoima roads. The model runs below scheduled buses, as expected without stops.",
], size=14, color=INK, space_after=6)
box(s, 8.6, 4.5, 4.1, 2.3, TINT)
text(s, 8.9, 4.7, 3.6, 2.0, [
    [("2–3 h vs ~1.5 h", {"bold": True, "size": 26, "color": LAT, "font": HEAD})],
    "Observed Kampala–Jinja trips far exceed the model. That gap is congestion at the Kampala end.",
], size=14, color=INK, space_after=6)
source(s, "Source: outputs/validation.csv. The Njeru estimate covers a shorter segment than the model's 73.5 km, so it is the least like-for-like.")

# ---------------------------------------------------------------- 8 road types
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Result 1 · Most of each corridor is settlement", "Share of corridor length by road type (500 m pieces, k-means)")
cd = CategoryChartData()
cd.categories = ["Malaba (A1)", "Elegu (A6)", "Katuna (A2)", "Hoima (A9)"]
cd.add_series("Open road", (0.199, 0.342, 0.250, 0.165))
cd.add_series("Roadside settlement", (0.581, 0.582, 0.637, 0.756))
cd.add_series("Town", (0.220, 0.075, 0.113, 0.080))
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED_100, Inches(0.5), Inches(1.9), Inches(8.2), Inches(5.0), cd)
ch = gf.chart
style_chart(ch, [GRN, SAND, LAT], size=13)
pl = ch.plots[0]; pl.gap_width = 45; pl.overlap = 100
pl.has_data_labels = True
pl.data_labels.number_format = '0%'; pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.CENTER
pl.data_labels.font.size = Pt(13); pl.data_labels.font.bold = True; pl.data_labels.font.color.rgb = WHITE
ch.category_axis.reverse_order = True
ch.value_axis.tick_labels.number_format = '0%'; ch.value_axis.tick_labels.number_format_is_linked = False
text(s, 9.1, 2.1, 3.6, 4.6, [
    [("What the types look like", {"bold": True, "font": HEAD, "size": 19})],
    [("Open road: ", {"bold": True, "color": GRN}), ("~4–9 buildings within 100 m per piece", {})],
    [("Settlement: ", {"bold": True, "color": RGBColor(0xA8, 0x74, 0x10)}), ("~87–154 buildings, ~1.8 joining roads", {})],
    [("Town: ", {"bold": True, "color": LAT}), ("~340–416 buildings, 6–7 joining roads", {})],
    [("Even the \"open\" A9 to Hoima has only 32 km of truly open road.", {"italic": True, "color": MUTED})],
], size=15, space_after=12)
source(s, "Source: outputs/typology_summary.csv. Three types chosen by silhouette score.")

# ---------------------------------------------------------------- 9 causes
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Result 2 · Roadside activity is the biggest steady drag", "Minutes a loaded truck loses leaving Kampala, by cause (central estimate, dry day, light traffic)")
cd = CategoryChartData()
cd.categories = ["Malaba (A1)", "Elegu (A6)", "Katuna (A2)", "Hoima (A9)"]
causes = [
    ("Roadside activity", (25.1, 29.2, 34.6, 18.5), LAT),
    ("Hills", (8.6, 13.0, 38.1, 13.7), RGBColor(0x8A, 0x6B, 0x4E)),
    ("Weighbridges", (20.0, 10.0, 20.0, 0.0), DARK),
    ("Speed humps (assumed)", (19.0, 13.0, 19.2, 6.2), SAND),
    ("Police posts", (10.0, 15.0, 9.0, 4.0), RGBColor(0x4E, 0x7C, 0x8A)),
    ("Joining roads", (7.1, 10.2, 11.2, 4.9), GRN),
    ("Signals & crossings", (10.5, 3.6, 2.9, 0.5), PALE),
]
for n, v, _ in causes:
    cd.add_series(n, v)
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED, Inches(0.5), Inches(1.9), Inches(8.4), Inches(5.0), cd)
ch = gf.chart
style_chart(ch, [c for _, _, c in causes], size=12)
ch.plots[0].gap_width = 45; ch.plots[0].overlap = 100
ch.category_axis.reverse_order = True
ch.value_axis.has_title = True
ch.value_axis.axis_title.text_frame.text = "minutes added"
ch.value_axis.axis_title.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
text(s, 9.3, 2.0, 3.4, 4.8, [
    [("Cars: ", {"bold": True, "color": LAT}),
     ("roadside activity is the largest cause on the Gulu, Katuna and Hoima roads (17–28 min).", {})],
    [("Trucks: ", {"bold": True, "color": LAT}),
     ("the five weighbridges are the largest single delays, ~10 min each if every truck stops.", {})],
    [("Jinja road: ", {"bold": True, "color": LAT}),
     ("signals, crossings and humps compete with roadside activity; the ranking depends on assumptions.", {})],
    [("A wet day adds a further 24–53 truck minutes.", {"italic": True, "color": MUTED})],
], size=15, space_after=12)
source(s, "Source: outputs/travel_time_causes.csv. Town speed limits and curves (< 3 min) omitted. 5–95% ranges are wide: see speaker notes.")
s.notes_slide.notes_text_frame.text = (
    "Totals for a truck (model vs open-road-only): Malaba 304 vs 185 min, Elegu 476 vs 369, Katuna 527 vs 365, Hoima 226 vs 167. "
    "Monte Carlo ranges: roadside activity for trucks spans roughly 10–74 min; police posts 1–71 min; humps 1–45 min. "
    "Report rankings with their Monte Carlo shares, not as single numbers.")

# ---------------------------------------------------------------- 9b race animation
s = prs.slides.add_slide(BLANK); bg(s, DARK)
text(s, 0.6, 0.5, 5.2, 1.4, "The same truck, five roads", size=32, font=HEAD, bold=True, color=WHITE)
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
hs = [("1", "Nakawa, Kampala end of A1", "+8.5 truck / +7.6 car min · signals and crossings"),
      ("6", "Lukaya, A2", "+11.9 truck min · weighbridge"),
      ("2", "Magamaga, A1", "+12.3 truck min · weighbridge, police post"),
      ("5", "Elegu border", "+4.0 truck min · police posts")]
y = 2.75
for n, place, d in hs:
    circle_num(s, x0, y + 0.05, 0.5, n, fill=DARK, size=15)
    text(s, x0 + 0.7, y, 4.4, 0.35, place, size=16, bold=True)
    text(s, x0 + 0.7, y + 0.36, 4.4, 0.4, d, size=13, color=MUTED)
    y += 0.9
text(s, x0, 6.4, 5.1, 0.7, "Eight of the ten worst stretches are led by weighbridges, police posts or signals; the other two are in Hoima town.",
     size=14, italic=True, color=LAT)
s.notes_slide.notes_text_frame.text = (
    "Numbers come from outputs/hotspots_mapped.csv. Close-ups of each hotspot are in figures/m03_hotspots.png and figures/hotspots/, "
    "and one atlas sheet per corridor in figures/m05_atlas_*.png.")

# ---------------------------------------------------------------- 11 growth
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Result 4 · The roadside filled in fast, between towns", "Built-up land within 300 m of the road, 2000–2020 (GHSL)")
cd = CategoryChartData()
cd.categories = ["Elegu (A6)", "Hoima (A9)", "Katuna (A2)", "Malaba (A1)"]
cd.add_series("Roadside settlement", (103, 92, 68, 45))
cd.add_series("Town", (20, 17, 16, 13))
cd.add_series("Whole corridor", (68, 57, 43, 27))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.85), Inches(4.5), Inches(5.0), cd)
ch = gf.chart
style_chart(ch, [SAND, LAT, DARK], size=12)
pl = ch.plots[0]; pl.gap_width = 45; pl.overlap = -5
pl.has_data_labels = True
pl.data_labels.number_format = '"+"0"%"'; pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.data_labels.font.size = Pt(11); pl.data_labels.font.color.rgb = INK
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
picture(s, f"{S}/m04_grid.png", 5.25, 1.85, h=5.0)
text(s, 9.95, 1.95, 2.8, 4.9, [
    [("+27% to +68%", {"bold": True, "size": 30, "color": LAT, "font": HEAD})],
    "roadside built-up land in 20 years, fastest on the Elegu and Hoima roads.",
    [("Settlements between towns roughly doubled on the A6 and A9; towns grew only 13–20%.", {"color": MUTED})],
    [("New friction is appearing on what used to be open road.", {"color": MUTED})],
], size=15, space_after=10)
source(s, "Maps: each corridor's fastest-growing 5 km; grey built by 2000, orange built 2000–2020. Open-road growth (150–225%) is from a very small base and not charted.")
s.notes_slide.notes_text_frame.text = (
    "Hectares within 300 m, 2000 to 2020: Elegu 855 to 1,437; Hoima 477 to 748; Katuna 1,188 to 1,704; Malaba 1,078 to 1,370. "
    "GHSL's projection gives only +5–9% for 2020–2026, far slower than the observed trend, so it probably understates recent building.")

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

# ---------------------------------------------------------------- 12a fixes
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Result 5 · Controls are the quickest wins", "Truck minutes saved per trip leaving Kampala, by fix (central estimate)")
cd = CategoryChartData()
cd.categories = CLAB
fixes = [("wim", "Weigh-in-motion", GRN), ("no_police", "No police stops", RGBColor(0x4E, 0x7C, 0x8A)),
         ("bypass_2", "Bypass 2 worst towns", SAND), ("service_all", "Service roads, all settlements", LAT)]
for key, lab, _ in fixes:
    d = SC[(SC.vehicle == "truck") & (SC.scenario == key)].set_index("corridor").reindex(CORR)
    cd.add_series(lab, [round(float(v), 1) for v in d.minutes_saved])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.9), Inches(8.2), Inches(5.0), cd)
ch = gf.chart
style_chart(ch, [c for _, _, c in fixes], size=12)
pl = ch.plots[0]; pl.gap_width = 60; pl.overlap = -5
pl.has_data_labels = True
pl.data_labels.number_format = '0'; pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.data_labels.font.size = Pt(11); pl.data_labels.font.color.rgb = INK
tc = COST[COST.vehicle == "truck"].cost_per_year_usd_m.sum()
text(s, 9.1, 2.05, 3.6, 4.8, [
    [(f"US${tc:.0f} M a year", {"bold": True, "size": 28, "color": LAT, "font": HEAD})],
    "is what delay costs heavy trucks on the four roads at central values (range several times wider: truck counts are assumed off the A1).",
    [("Weigh-in-motion and ending police stops save more per trip than bypasses in light traffic. "
      "Service roads help everywhere but need 125–270 km each.", {"color": MUTED})],
], size=14, space_after=10)
source(s, "outputs/scenarios.csv, outputs/costs.csv (scripts 16, 17). Congestion relief from bypasses is not captured by the light-traffic model.")

# ---------------------------------------------------------------- 12b safety and reliability
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Result 6 · Settlements carry most of the risk", "Roadside settlements: share of people within 300 m vs share of exposure (people × trucks × speed⁴)")
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
text(s, 8.8, 4.7, 3.7, 2.0, [
    [(f"{tr.buffer_index.min():.0%}–{tr.buffer_index.max():.0%} slower", {"bold": True, "size": 22, "color": DARK, "font": HEAD})],
    "on a bad-rain day (95th percentile, 2006–2025) than on a typical day. The Malaba road is slowed on about 87 days a year.",
], size=13, space_after=6)
source(s, "outputs/safety_by_type.csv, outputs/reliability.csv (scripts 18, 19). Exposure is not a crash rate; floods that close roads are not modelled.")

# ---------------------------------------------------------------- 12c rail
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
picture(s, os.path.join(S, "f12.png"), 0.4, 0.35, h=6.8)
x0 = 7.0
text(s, x0, 0.45, 5.8, 1.3, "Rail along the bottlenecks", size=30, font=HEAD, bold=True)
text(s, x0, 1.35, 5.8, 0.6, "Least-cost screening alignments and the existing metre-gauge railway", size=14, color=MUTED)
near = RP[(RP.corridor == "kampala_malaba") & (RP.railway == "in use")].share_of_truck_delay.iloc[0]
g = lambda line, var, m: RE[(RE.line == line) & (RE.variant == var) & (RE.measure == m)].iloc[0]  # noqa: E731
be = g("Eastern", "through from Mombasa", "freight needed to break even")
bc = g("Eastern", "through from Mombasa", "benefit / cost")
rt = g("Eastern", "domestic", "door-to-door time by rail")
items = [(f"{near:.0%}", "of the Malaba road's truck delay lies within 10 km of the railway the SGR follows; "
                         "on the other roads, 16% or less."),
         (f"{rt.central:.0f} h", "door to door by rail for domestic freight on the eastern line, against about 5 h by truck: "
                                 "terminals, not line-haul, set the time."),
         (f"{bc.central:.2f}", f"benefit/cost for the eastern SGR even with through traffic from Mombasa (up to {bc.p95:.2f}); "
                               f"about {be.central:.0f} Mt a year needed to break even."),
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
    "Kenya's Naivasha-Malaba SGR link is not built, which the through-traffic case needs.")

# ---------------------------------------------------------------- 12 discussion
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Discussion", "What the results suggest for corridor policy")
pts = [
    ("Settlement is the chronic problem", LAT,
     "Roadside activity costs the most time on three of four roads and is growing fastest where it is newest. "
     "Access management, service roads and planned trading centres off the carriageway address the cause, not the symptom."),
    ("Controls are the cheap wins", DARK,
     "Weighbridges and police posts produce the worst single stretches. Weigh-in-motion screening saves 8–16 truck "
     "minutes per trip and ending police stops 4–15; bypasses save 2–5 in light traffic."),
    ("Kampala's problem is congestion", GRN,
     "The gap between modelled and observed Kampala–Jinja trips is congestion. The expressway and urban traffic "
     "management matter there more than roadside fixes."),
    ("Growth outpaces the road", SAND,
     "At 27–68% in 20 years, today's open road is tomorrow's settlement. Land-use control along the corridors is time-critical."),
]
for i, (h, col, d) in enumerate(pts):
    cx = 0.6 + (i % 2) * 6.15
    cy = 1.95 + (i // 2) * 2.5
    box(s, cx, cy, 5.95, 2.3, TINT)
    circle_num(s, cx + 0.3, cy + 0.3, 0.5, str(i + 1), fill=col, size=15)
    text(s, cx + 1.0, cy + 0.33, 4.7, 0.45, h, size=19, bold=True, font=HEAD)
    text(s, cx + 1.0, cy + 0.85, 4.7, 1.4, d, size=14, color=MUTED)
s.notes_slide.notes_text_frame.text = (
    "These are implications from a light-traffic model, not project appraisals. The weighbridge saving assumes about ten minutes per stop, "
    "which is itself an assumption with a wide range.")

# ---------------------------------------------------------------- 13 limits
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Limitations and next steps")
lims = [
    ("Congestion is not modelled", "Results describe light traffic; peak-hour delay near Kampala is larger."),
    ("Speed humps are under-mapped", "OSM holds < 60 on all four roads; one per town piece is assumed (range 0–2)."),
    ("Stop times are assumptions", "Police posts 0–5 min, weighbridges ~10 min; rankings on the A1 depend on them."),
    ("Growth data end in 2020", "GHSL's projection to 2026 is slower than the observed trend; Open Buildings Temporal would extend it."),
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
    "Report cause rankings with their Monte Carlo shares",
    "Swap GLO-30 for FABDEM terrain",
    "Observe post-2020 growth with Open Buildings 2.5D Temporal",
    "Replace assumed truck counts with UNRA counts",
    "Write up the paper",
], size=15, color=PALE, space_after=12)

# ---------------------------------------------------------------- 14 close
s = prs.slides.add_slide(BLANK); bg(s, DARK)
text(s, 0.7, 1.2, 11.9, 0.5, "CONCLUSION", size=13, bold=True, color=SAND)
text(s, 0.7, 1.75, 11.9, 1.5, "Uganda's corridors are becoming high streets faster than they are being managed as highways.",
     size=34, font=HEAD, bold=True, color=WHITE)
cl = [("1", "Open data alone reproduce trip times within a few percent, outside Kampala."),
      ("2", "Roadside activity is the largest steady delay; weighbridges are the worst single points."),
      ("3", "Roadside building grew 27–68% in 2000–2020, mostly between towns."),
      ("4", "Cheap fixes at controls beat bypasses; rail pays only with far more freight than today.")]
y = 3.55
for n, t in cl:
    circle_num(s, 0.7, y, 0.55, n, fill=LAT, size=16)
    text(s, 1.55, y + 0.02, 11.0, 0.55, t, size=19, color=PALE, anchor=MSO_ANCHOR.MIDDLE)
    y += 0.72
text(s, 0.7, 6.55, 11.9, 0.4, "Code, outputs, maps and animations: uganda-trade-corridors repository", size=13, color=PALE)

prs.save(OUT)
print("saved", OUT)
