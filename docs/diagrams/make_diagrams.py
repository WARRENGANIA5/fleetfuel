"""Builds the four CRISP-DM thesis diagrams of the FleetFuel system as SVG.

    python docs/diagrams/make_diagrams.py

Clean documentation style: few words per shape, standard notations
(stage pipeline, star schema, CRISP-DM cycle, 3-tier architecture),
one page each. Numbers come from model/metrics.json and the data files.
"""
import math
import os

from svgkit import F, GOLD, GREEN, INK, MAROON, MUTED, NAVY, TEAL, R, SVG

OUT = os.path.dirname(os.path.abspath(__file__))


def step(s, x, y, n):
    """Numbered circle used for the inference steps."""
    r = 14 * F
    s.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{MAROON}"/>')
    s.text(x, y + 6 * F, str(n), 15, "bold", "#ffffff", "middle")


# ======================================================================
# Figure 1. Data Pipeline Diagram
# ======================================================================
def data_pipeline():
    W = 1000
    s = SVG(W, "Data Pipeline Diagram", "From the collected records to the trained model")
    rows = [
        ("Data Sources", "Data Understanding",
         [("GSO Trip Records", "93 trips + completed requests", "maroon"), ("Vehicle Records", "9 vehicles", "maroon"),
          ("Online Trip Records", "7,496 EEA van trips", "gold"), ("Other Online Records", "92,402 records", "gold")]),
        ("Storage", "Data Understanding",
         [("Firebase Firestore", "trips, vehicles, requests", "teal"), ("CSV Files", "online trips, supplementary", "gold")]),
        ("Export to Colab", "Data Preparation",
         [("Trip Records", "CSV file", "navy"), ("Vehicle Records", "CSV file", "navy"),
          ("Supplementary Data", "CSV file", "navy")]),
        ("Integration", "Data Preparation",
         [("Join trips and vehicles", "by plate number", "navy"), ("Merge online data", "tag the data source", "navy")]),
        ("Cleaning", "Data Preparation",
         [("Remove missing and zero distance", None, "maroon"), ("Remove outliers", "IQR per engine power, residual |z| > 3", "maroon"),
          ("Keep fleet range", "Diesel, 30–400 km, 51–177 kW", "maroon")]),
        ("Feature Engineering", "Data Preparation",
         [("Distance (c)", "X1, km", "navy"), ("Engine Power (c)", "X2, kW", "navy"), ("Fuel Type", "X3, 0 = Diesel", "navy"),
          ("Distance × Power", "X4", "navy")]),
        ("Data Split", "Modeling",
         [("Training Set", "80% · 27,288", "green"), ("Test Set", "20% · 6,823", "green"),
          ("Cross-Validation", "5 folds", "green")]),
        ("Model Output", "Modeling",
         [("Linear Regression", "weighted least squares", "green"), ("Saved Files", ".joblib + metrics", "green"),
          ("Results", "R² 0.9008 · MAE 1.87 L", "green")]),
    ]
    LX, CX0, CX1, GAP = 20, 255, W - 22, 16
    y = 128
    prev = None
    for i, (name, phase, chips) in enumerate(rows):
        n = len(chips)
        cw = (CX1 - CX0 - GAP * (n - 1)) / n
        h = max(s.box_h(cw, t, b) for t, b, _ in chips)
        s.rect(LX - 8 + 8, y - 14, W - 2 * LX, h + 28, "#f5f7fa" if i % 2 == 0 else "#ffffff", "#d6dde6", 10, 1.2)
        s.add(f'<circle cx="{LX + 30:.1f}" cy="{y + h / 2:.1f}" r="{18 * F:.1f}" fill="{NAVY}"/>')
        s.text(LX + 30, y + h / 2 + 7 * F, str(i + 1), 17, "bold", "#ffffff", "middle")
        nm = name.split(" ", 1) if len(name) > 14 else [name]
        ny = y + h / 2 - 2 - (len(nm) - 1) * 11
        end = s.lines(LX + 62, ny, nm, 17, "bold", NAVY)
        s.text(LX + 62, end + 2, phase, 13, "normal", MAROON, italic=True)
        for j, (t, b, tone) in enumerate(chips):
            s.box(CX0 + j * (cw + GAP), y, cw, t, b, tone, h, center=True)
        if prev:
            mid = (CX0 + CX1) / 2
            s.path([(mid, prev - 14), (mid, y - 15)], INK, 2.4)
        prev = y + h + 14
        if name == "Cleaning":
            prev_label = y + h + 14
        y += h + 28 + 44
    s.label((CX0 + CX1) / 2 + 150, prev_label + 28, "34,111 clean records", GREEN, 14)
    s.save(os.path.join(OUT, "fig1_data_pipeline.svg"), y - 20)


# ======================================================================
# Figure 2. Analytical Data Model Schema (star schema)
# ======================================================================
def data_model():
    W = 1020
    s = SVG(W, "Analytical Data Model Schema", "Star schema: trips and fuel requests (facts) with their dimensions")
    TW = 310
    C = [20, 355, 690]

    def lab(x, y, t):
        s.text(x, y, t, 14, "bold", MAROON, "middle")

    mv, mvy = s.table(C[0], 130, TW, "Model Input View", [
        ("", "X1 distance_km", "km"), ("", "X2 engine_power_kw", "kW"), ("", "X3 fuel_type", "0 = Diesel"),
        ("", "X4 distance × power", "X1·X2"), ("", "Y actual_fuel", "L")], tone="green", note="34,111 clean records")
    dd, ddy = s.table(C[1], 130, TW, "Dim Date", [
        ("PK", "trip_date", "date"), ("", "month", "int"), ("", "year", "int")], tone="gold",
        note="from the trip date")
    # legend top-right
    lg = R(C[2], 130, TW, 200)
    s.rect(lg.x, lg.y, lg.w, lg.h, "#ffffff", "#cfd7e2", 8, 1.2)
    s.text(lg.x + 16, lg.y + 32, "Legend", 17, "bold", NAVY)
    for i, (k, c, t) in enumerate([("PK", MAROON, "primary key"), ("FK", NAVY, "foreign key")]):
        s.text(lg.x + 16, lg.y + 66 + i * 32, k, 13, "bold", c)
        s.text(lg.x + 64, lg.y + 66 + i * 32, t, 15)
    s.rect(lg.x + 16, lg.y + 116, 30, 18, "#1f3a5f", "#1f3a5f", 3, 0)
    s.text(lg.x + 64, lg.y + 131, "fact table", 15)
    s.rect(lg.x + 16, lg.y + 150, 30, 18, GOLD, GOLD, 3, 0)
    s.text(lg.x + 64, lg.y + 165, "dimension table", 15)

    Y2 = max(mv.b, dd.b, lg.b) + 70
    dv, dvy = s.table(C[0], Y2, TW, "Dim Vehicle", [
        ("PK", "vehicle_id", "int"), ("", "plate_number", "text"), ("", "brand_model", "text"),
        ("", "fuel_type", "X3"), ("", "engine_power_kw", "X2")], tone="gold")
    ft, fty = s.table(C[1], Y2, TW, "Fact Trip", [
        ("PK", "trip_id", "int"), ("FK", "vehicle_id", "int"), ("FK", "trip_date", "date"),
        ("FK", "data_source", "text"), ("", "distance_km", "X1"), ("", "actual_fuel_consumption", "Y")], tone="navy",
        note="one row per trip (trip_records)")
    ds, dsy = s.table(C[2], Y2, TW, "Dim Data Source", [
        ("PK", "data_source", "text"), ("", "dataset", "text")], tone="gold",
        note="local · online trips · supplementary")

    Y3 = max(dv.b, ft.b, ds.b) + 70
    fp, fpy = s.table(C[1], Y3, TW, "Fact Prediction", [
        ("PK", "prediction_id", "int"), ("FK", "vehicle_id", "int"), ("FK", "user_id", "int"),
        ("FK", "trip_record_id", "int"), ("", "distance_km", "km"), ("", "predicted_fuel", "ŷ (L)"),
        ("", "approval_status", "text"), ("", "approved_fuel", "L"), ("", "actual_fuel", "L"),
        ("", "created_at", "time")], tone="navy",
        note="one row per fuel request (predictions)")
    du, duy = s.table(C[2], Y3, TW, "Dim User", [
        ("PK", "user_id", "int"), ("", "username", "text"), ("", "full_name", "text"), ("", "role", "admin / staff")],
        tone="gold")

    # relationships (1 : N)
    s.path([(dv.r, dvy[0]), (ft.l, fty[1])], INK, 2, head=False)
    lab(dv.r + 10, dvy[0] - 8, "1")
    lab(ft.l - 10, fty[1] - 8, "N")
    s.path([(ds.l, dsy[0]), (ft.r, fty[3])], INK, 2, head=False)
    lab(ds.l - 10, dsy[0] - 8, "1")
    lab(ft.r + 10, fty[3] - 8, "N")
    s.path([(dd.cx, dd.b), (ft.cx, ft.t)], INK, 2, head=False)
    lab(dd.cx + 12, dd.b + 20, "1")
    lab(ft.cx + 12, ft.t - 8, "N")
    s.path([(ft.cx, ft.b), (fp.cx, fp.t)], INK, 2, head=False)
    lab(ft.cx + 12, ft.b + 20, "1")
    lab(fp.cx + 18, fp.t - 8, "0..1")
    s.path([(du.l, duy[0]), (fp.r, fpy[2])], INK, 2, head=False)
    lab(du.l - 10, duy[0] - 8, "1")
    lab(fp.r + 10, fpy[2] - 8, "N")
    s.path([(dv.cx, dv.b), (dv.cx, fpy[1]), (fp.l, fpy[1])], INK, 2, head=False)
    lab(dv.cx + 12, dv.b + 20, "1")
    lab(fp.l - 10, fpy[1] - 8, "N")
    # derived model view
    s.path([(dv.cx, dv.t), (dv.cx, mv.b + 2)], GREEN, 2.4, dash="7 5")
    s.label(dv.cx + 66, (dv.t + mv.b) / 2 + 5, "derived", GREEN, 13)
    s.save(os.path.join(OUT, "fig2_analytical_data_model.svg"), fp.b + 30)


# ======================================================================
# Figure 3. ML Lifecycle and Decision Flow
# ======================================================================
def lifecycle():
    W = 1000
    s = SVG(W, "ML Lifecycle and Decision Flow", "CRISP-DM cycle of the project and the decisions in it")
    phases = [("1. Business Understanding", "predict fuel per trip", "maroon"),
              ("2. Data Understanding", "93 GSO + 99,898 online", "gold"),
              ("3. Data Preparation", "34,111 clean records", "navy"),
              ("4. Modeling", "Linear Regression", "teal"),
              ("5. Evaluation", "R² 0.9008, 5-fold CV", "green"),
              ("6. Deployment", "Flask web system", "maroon")]
    pw = 270
    xs = [40, W / 2 - pw / 2, W - 40 - pw]
    h = max(s.box_h(pw, t_, b_) for t_, b_, _ in phases)
    r1, r2 = 130, 130 + h + 150
    pos = [(xs[0], r1), (xs[1], r1), (xs[2], r1), (xs[2], r2), (xs[1], r2), (xs[0], r2)]
    boxes = [s.box(x, y, pw, t_, b_, tone, h, center=True) for (x, y), (t_, b_, tone) in zip(pos, phases)]
    bu, du, dp, mo, ev, de = boxes
    s.path([(bu.r, bu.cy), (du.l - 1, du.cy)], NAVY, 2.6, both=True)
    s.path([(du.r, du.cy), (dp.l - 1, dp.cy)], NAVY, 2.6)
    s.path([(dp.cx, dp.b), (mo.cx, mo.t - 1)], NAVY, 2.6, both=True)
    s.path([(mo.l, mo.cy), (ev.r + 1, ev.cy)], NAVY, 2.6)
    s.path([(ev.l, ev.cy), (de.r + 1, de.cy)], NAVY, 2.6)
    s.path([(de.cx, de.t), (bu.cx, bu.b + 1)], NAVY, 2.6)
    mid = (bu.b + ev.t) / 2
    s.path([(ev.cx, ev.t), (ev.cx, mid), (bu.cx + 70, mid), (bu.cx + 70, bu.b + 1)], MAROON, 2, dash="7 5")
    s.label((ev.cx + bu.cx + 70) / 2, mid - 10, "not good enough: revise", MAROON, 13)
    boxes = [ev, de]

    # ---- decision flow
    y0 = max(b.b for b in boxes) + 60
    s.text(30, y0 + 24, "A. Building the model", 17, "bold", NAVY)
    ya = y0 + 50
    nw, dw = 165, 230
    hA = max(s.node_h(nw, "Export training data"), 64)
    d1h = s.diamond_h(dw, "Accurate? VIF ≤ 5?")
    n1 = s.node(110, ya + 20 + (d1h - hA) / 2, nw, "Export training data", "navy", h=hA)
    n2 = s.node(320, n1.t, nw, "Train in Google Colab", "navy", h=hA)
    d1 = s.diamond(560, n1.cy - d1h / 2, dw, "Accurate? VIF ≤ 5?")
    n3 = s.node(850, n1.t, nw + 20, "Upload and check model", "green", h=hA)
    s.right(n1, n2, INK)
    s.path([(n2.r, n2.cy), (d1.l - 1, n2.cy)], INK, 2)
    s.path([(d1.r, d1.cy), (n3.l - 1, n3.cy)], INK, 2)
    s.label((d1.r + n3.l) / 2, d1.cy - 10, "Yes", GREEN, 13)
    s.path([(d1.cx, d1.b), (d1.cx, d1.b + 26), (n1.cx, d1.b + 26), (n1.cx, n1.b + 1)], MAROON, 2, dash="7 5")
    s.label((d1.cx + n1.cx) / 2, d1.b + 31, "No: revise the data", MAROON, 13)

    yb = d1.b + 70
    s.text(30, yb + 24, "B. Using the model", 17, "bold", NAVY)
    yb += 50
    hB = max(s.node_h(150, "Record the actual fuel"), 64)
    d3h = s.diamond_h(210, "Admin approves?")
    m1 = s.node(90, yb + 20 + (d3h - hB) / 2, 140, "Fuel request", "navy", h=hB)
    d2h = s.diamond_h(180, "Valid input?")
    d2 = s.diamond(265, m1.cy - d2h / 2, 180, "Valid input?")
    m2 = s.node(450, m1.t, 150, "Predict and warn", "navy", h=hB)
    d3 = s.diamond(650, m1.cy - d3h / 2, 210, "Admin approves?")
    m3 = s.node(880, m1.t, 170, "Record the actual fuel", "green", h=hB)
    s.path([(m1.r, m1.cy), (d2.l - 1, m1.cy)], INK, 2)
    s.path([(d2.r, m1.cy), (m2.l - 1, m1.cy)], INK, 2)
    s.label((d2.r + m2.l) / 2, m1.cy - 10, "Yes", GREEN, 13)
    s.path([(m2.r, m1.cy), (d3.l - 1, m1.cy)], INK, 2)
    s.path([(d3.r, m1.cy), (m3.l - 1, m1.cy)], INK, 2)
    s.label((d3.r + m3.l) / 2, m1.cy - 10, "Yes", GREEN, 13)
    low = max(d2.b, d3.b) + 34
    e1 = s.node(d2.cx, low, 150, "Show error", "maroon", 15)
    e2 = s.node(d3.cx, low, 190, "Rejected, trip removed", "maroon", 15)
    s.path([(d2.cx, d2.b), (d2.cx, e1.t - 1)], MAROON, 2)
    s.label(d2.cx + 24, (d2.b + e1.t) / 2 + 5, "No", MAROON, 13)
    s.path([(d3.cx, d3.b), (d3.cx, e2.t - 1)], MAROON, 2)
    s.label(d3.cx + 24, (d3.b + e2.t) / 2 + 5, "No", MAROON, 13)
    s.path([(e1.l, e1.cy), (m1.cx, e1.cy), (m1.cx, m1.b + 1)], MAROON, 2, dash="7 5")
    d4 = s.diamond(m3.cx, m3.b + 34, 190, "Retrain needed?")
    s.path([(m3.cx, m3.b), (m3.cx, d4.t - 1)], INK, 2)
    s.path([(d4.r, d4.cy), (W - 14, d4.cy), (W - 14, d1.t - 18), (n1.cx, d1.t - 18), (n1.cx, n1.t - 1)], MAROON, 2,
           dash="7 5")
    s.label(W - 50, d4.cy - 10, "Yes", MAROON, 13)
    en = s.pill(d4.cx, d4.b + 34, 120, "End")
    s.path([(d4.cx, d4.b), (d4.cx, en.t - 1)], INK, 2)
    s.label(d4.cx + 24, (d4.b + en.t) / 2 + 5, "No", MAROON, 13)
    s.save(os.path.join(OUT, "fig3_ml_lifecycle_decision_flow.svg"), en.b + 30)


# ======================================================================
# Figure 4. Inference and Integration Architecture
# ======================================================================
def architecture():
    W = 1000
    s = SVG(W, "Inference and Integration Architecture", "Three tiers, the steps of one prediction, and how a new model is added")
    cols = [(20, 250, "CLIENT"), (290, 700, "APPLICATION SERVER"), (740, 980, "DATA AND MODEL")]
    top, bot = 130, 760
    for x0, x1, t in cols:
        s.rect(x0, top, x1 - x0, bot - top, "#f5f7fa", "#d6dde6", 10, 1.2)
        s.text((x0 + x1) / 2, top + 30, t, 15, "bold", MUTED, "middle")

    users = s.box(40, 190, 190, "Users", "GSO staff, administrator", "maroon", center=True)
    br = s.box(40, 400, 190, "Web Browser", "HTML, Bootstrap, Chart.js", "navy", center=True)
    s.path([(users.cx, users.b), (users.cx, br.t - 1)], INK, 2)

    app = R(310, 175, 370, 565)
    s.rect(app.x, app.y, app.w, app.h, "#ffffff", NAVY, 10, 1.8)
    s.text(app.cx, app.y + 32, "Flask Web Application", 18, "bold", NAVY, "middle")
    s.text(app.cx, app.y + 58, "office server (Waitress) · online link (Vercel)", 13, "normal", MUTED, "middle",
           italic=True)
    rt = s.box(340, 260, 310, "Pages and Routes", "app.py: forms, pages, JSON API", "navy", center=True)
    pm = s.box(340, 420, 310, "Prediction Module", "validate input, predict, warn", "maroon", center=True)
    da = s.box(340, 590, 310, "Data Access", "db.py, trip_dataset.py", "teal", center=True)

    csv = s.cyl(760, 230, 200, "CSV Datasets", "online trips", "gold")
    md = s.cyl(760, pm.cy - 75, 200, "Trained Model", ".joblib + metrics.json", "maroon")
    fs = s.cyl(760, da.cy - 75, 200, "Firebase Firestore", "users, vehicles, trips, requests", "teal")

    s.path([(br.r, br.cy - 22), (rt.l - 1, rt.cy)], INK, 2)
    step(s, (br.r + rt.l) / 2 - 8, (br.cy - 22 + rt.cy) / 2 - 22, 1)
    s.path([(rt.l, rt.cy + 30), (br.r + 1, br.cy + 22)], INK, 2)
    step(s, (br.r + rt.l) / 2 + 8, (br.cy + 22 + rt.cy + 30) / 2 + 26, 5)
    s.path([(rt.cx, rt.b), (pm.cx, pm.t - 1)], INK, 2)
    step(s, rt.cx + 26, (rt.b + pm.t) / 2, 2)
    s.path([(pm.r, pm.cy), (md.l - 1, pm.cy)], INK, 2, both=True)
    step(s, (pm.r + md.l) / 2, pm.cy - 24, 3)
    s.path([(pm.cx, pm.b), (da.cx, da.t - 1)], INK, 2)
    step(s, pm.cx + 26, (pm.b + da.t) / 2, 4)
    s.path([(da.r, da.cy), (fs.l - 1, da.cy)], TEAL, 2, both=True)
    s.path([(rt.r, csv.cy), (csv.l - 1, csv.cy)], GOLD, 2, both=True)

    ty = bot + 40
    s.text(30, ty + 22, "Adding a new model", 17, "bold", NAVY)
    ty += 40
    th = max(s.box_h(230, "Upload Model", "admin, Model Performance"), s.box_h(230, "Upload Check", "same terms, same results"))
    t1 = s.box(40, ty, 230, "Google Colab", "exported CSVs: train, evaluate", "gold", h=th, center=True)
    t2 = s.box(330, ty, 230, "Upload Model", "admin, Model Performance", "gold", h=th, center=True)
    t3 = s.box(620, ty, 230, "Upload Check", "same terms, same results", "gold", h=th, center=True)
    s.right(t1, t2, GOLD)
    s.right(t2, t3, GOLD)
    s.path([(t3.r, t3.cy), (W - 8, t3.cy), (W - 8, md.cy), (md.r + 1, md.cy)], GOLD, 2.4)
    s.label(W - 50, t3.cy - 12, "replace", GOLD, 13)

    ly = t1.b + 44
    s.text(30, ly, "Steps of one prediction", 17, "bold", NAVY)
    items = ["Staff sends the vehicle and the planned distance.",
             "The route checks the input and gets the vehicle's engine power and fuel type.",
             "The trained model predicts the fuel in liters.",
             "The request and a pending trip are saved in Firestore.",
             "The result is shown; the administrator approves or rejects it."]
    for i, t in enumerate(items):
        yy = ly + 38 + i * 34
        step(s, 48, yy - 6, i + 1)
        s.text(76, yy, t, 15)
    s.save(os.path.join(OUT, "fig4_inference_integration_architecture.svg"), ly + 38 + 5 * 34)


if __name__ == "__main__":
    data_pipeline()
    data_model()
    lifecycle()
    architecture()
    print("SVG diagrams written to", OUT)
