"""
Builds the 3-slide deck (PDF, 16:9) from the current reports, so the numbers always match the data.

  python slides/make_slides.py [--team "Team name"] [--demo-url https://...]
Output: slides/smartmess_3slides.pdf (+ slides/smartmess_3slides.html)
"""
import argparse
import asyncio
import base64
import html
import json
from pathlib import Path
import subprocess

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REP = ROOT / "reports"
FIG = REP / "figures"


def img(path):
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def build(team, demo_url):
    eda = json.loads((REP / "eda_summary.json").read_text())
    ms = json.loads((REP / "model_summary.json").read_text())
    wv = json.loads((REP / "wait_validation.json").read_text()) if (REP / "wait_validation.json").exists() else {}
    peaks = pd.read_csv(REP / "eda_peaks.csv")
    pred = pd.read_parquet(REP / "predictions_dashboard.parquet")
    raw = pd.read_parquet(ROOT / "data" / "processed" / "sessions_5min.parquet")
    n_real = int(raw.loc[raw.is_synthetic == 0, "session_id"].nunique())
    n_syn = int(raw.loc[raw.is_synthetic == 1, "session_id"].nunique())
    rows_real = int((raw.is_synthetic == 0).sum())
    best = ms["chosen_model"]
    fw = ms["forward"]
    worst = peaks.sort_values("peak_queue_mean", ascending=False).iloc[0]
    src = " (real data)" if n_real else " (from our observations + facts)"

    # example manager card: first RED in the most congested out-of-sample session
    sid = pred.groupby("session_id").queue_len.max().idxmax()
    g = pred[pred.session_id == sid].sort_values("slot_idx")
    red = g[g.alert == "RED"]
    ex = red.iloc[0] if len(red) else g.loc[g.queue_now.idxmax()]
    hit = g[(g.interval_end > ex.interval_end) & (g.queue_len >= 10)]
    msg = html.escape(ex.manager_message)
    ex_note = (f"{ex.interval_end:%H:%M}: line {ex.queue_now:.0f}; 15 min later it was "
               f"{g[g.interval_end == ex.interval_end + pd.Timedelta(minutes=15)].queue_len.iloc[0]:.0f}"
               if (g.interval_end == ex.interval_end + pd.Timedelta(minutes=15)).any() else "")

    if "real_holdout" in ms:
        rh = ms["real_holdout"]
        res_title = f"Real held-out meals ({n_real})"
        res_line = (f"10-min forecast error: <b>{rh[best]['10']:.1f}</b> people ({best.upper()}) vs "
                    f"{rh['persistence']['10']:.1f} if we assume the line stays the same, and "
                    f"{rh['experimental_formula']['10']:.1f} for our first formula.")
        data_tag = f"{n_real} real meals ({rows_real} rows), labelled"
    else:
        res_title = "Held-out last 5 days"
        res_line = (f"Congested-interval error, 10 min ahead: <b>{fw[best]['10']['mae_congested']:.1f}</b> people "
                    f"({best.upper()}) vs {fw['persistence']['10']['mae_congested']:.1f} (line stays the same) "
                    f"and {fw['experimental_formula']['10']['mae_congested']:.1f} (our first formula).")
        data_tag = f"Meals built from our observations + stated facts; counted meals: in progress"
    wait_line = ""
    if "real" in wv:
        wait_line = (f"Wait formula vs stopwatch ({wv['real']['n']} real people): error "
                     f"{wv['real']['mae_min']:.1f} min.")
    elif "synthetic" in wv:
        wait_line = "Wait formula = queue / service rate; stopwatch check ready for real samples."

    css = """
    @page { size: 1920px 1080px; margin: 0 }
    * { box-sizing: border-box }
    body { margin: 0; font-family: 'Inter', 'DejaVu Sans', Arial, sans-serif; color: #15191e }
    .s { width: 1920px; height: 1080px; padding: 70px 90px; position: relative; page-break-after: always; overflow: hidden }
    .s:last-child { page-break-after: auto }
    .k { color: #d9480f; font-weight: 700; letter-spacing: .12em; font-size: 22px; text-transform: uppercase }
    h1 { font-size: 56px; margin: 10px 0 26px; line-height: 1.05; letter-spacing: -.01em }
    h2 { font-size: 30px; margin: 0 0 12px }
    p, li { font-size: 27px; line-height: 1.4; margin: 0 0 12px }
    ul { padding-left: 28px; margin: 0 }
    .g { display: grid; gap: 40px }
    .box { border: 2px solid #e9ecef; border-radius: 16px; padding: 26px 30px; background: #fff }
    .dark { background: #15191e; color: #fff; border: none }
    .big { font-size: 72px; font-weight: 800; color: #d9480f; line-height: 1 }
    .lbl { font-size: 22px; color: #6c757d }
    .flow { display: flex; gap: 14px; align-items: stretch }
    .step { flex: 1; background: #f1f3f5; border-radius: 12px; padding: 16px 16px; font-size: 22px; line-height: 1.3 }
    .step b { display: block; font-size: 23px; color: #d9480f; margin-bottom: 6px }
    .arrow { align-self: center; font-size: 34px; color: #adb5bd }
    .msg { font-family: 'DejaVu Sans Mono', monospace; font-size: 21px; white-space: pre-wrap; line-height: 1.45 }
    .warn { color: #e67700 }
    .foot { position: absolute; bottom: 36px; left: 90px; right: 90px; font-size: 19px; color: #868e96;
            display: flex; justify-content: space-between }
    img { max-width: 100%; display: block }
    """
    s1 = f"""
    <section class="s">
      <div class="k">Smart Mess &middot; Problem</div>
      <h1>The main-dish line gets long before anyone reacts</h1>
      <div class="g" style="grid-template-columns: 1.05fr 1fr">
        <div>
          <p>In an IIT Guwahati hostel mess, the main-dish counter (dosa, paratha, roti) is the bottleneck.
             Staff only see the line once it is long; students cannot tell when to come.</p>
          <div class="g" style="grid-template-columns: 1fr 1fr; gap: 24px; margin: 18px 0 20px">
            <div class="box"><div class="big">{worst.peak_queue_mean:.0f}</div>
              <div class="lbl">people in line at the worst slot ({worst.meal} {worst.weekday}, {worst.peak_queue_at}){src}</div></div>
            <div class="box"><div class="big">{eda['share_intervals_congested']:.0%}</div>
              <div class="lbl">of 5-min intervals have a line of 10+, so the problem is short and predictable peaks{src}</div></div>
          </div>
          <h2>Users</h2>
          <ul><li><b>Mess manager / counter staff</b>: how fast to serve in the next 15 minutes</li>
              <li><b>Students</b>: go now, or come back in 15 minutes</li></ul>
          <h2 style="margin-top:16px">Our question</h2>
          <p>From door counts and 5-minute counter counts, <b>how long will the line be in 5, 10 and 15 minutes,
             how long is the wait, and what service rate keeps it under 5 minutes?</b></p>
        </div>
        <div><img src="{img(FIG / 'eda_2_queue.png')}"><p class="lbl" style="margin-top:8px">Mean line length by
          meal and weekday. Weekday rushes: breakfast 8:30-9:00, lunch 12:45-1:00 (Wed-Fri), dinner after 9:00; weekend breakfast burst at 9:45.</p>
          <img style="margin-top:14px" src="{img(FIG / 'eda_4_service_and_balance.png')}">
          <p class="lbl" style="margin-top:8px">Left: capacity depends on the dish. Right: line change = people in - people served.</p></div>
      </div>
      <div class="foot"><span>{html.escape(team)} &middot; Granica x IIT Guwahati Hackathon</span><span>Data: {data_tag}</span></div>
    </section>"""

    s2 = f"""
    <section class="s">
      <div class="k">Workflow &middot; Collection &middot; Solution</div>
      <h1>Three phones, two counts, one forecast</h1>
      <div class="flow" style="margin-bottom:30px">
        <div class="step"><b>1 Door</b>IN / OUT tap per person, timestamped</div><div class="arrow">&rarr;</div>
        <div class="step"><b>2 Counter, every 5 min</b>people in line + main-dish units made (= service rate)</div><div class="arrow">&rarr;</div>
        <div class="step"><b>3 Stopwatch</b>~10 people/meal: join to served</div><div class="arrow">&rarr;</div>
        <div class="step"><b>4 Validate</b>gaps, IN/OUT drift, open Parquet</div><div class="arrow">&rarr;</div>
        <div class="step"><b>5 Forecast</b>line in 5/10/15 min + 80% band</div><div class="arrow">&rarr;</div>
        <div class="step"><b>6 Decide</b>wait = line / service rate, then alert + advice</div>
      </div>
      <div class="g" style="grid-template-columns: 1fr 1fr 1fr">
        <div class="box"><h2>Collection</h2><ul>
          <li>Offline phone tap-logger exports the exact schema</li>
          <li>Blank means missed. We never guess</li>
          <li>No cameras, names or roll numbers. Manager approval before any counting</li>
          <li>Units per plate converts "made per minute" into people per minute</li></ul></div>
        <div class="box"><h2>Physics first</h2><ul>
          <li>Line(t) = line(t-1) + people in - people served</li>
          <li>Capacity measured only while a line exists (otherwise "made" = demand)</li>
          <li>Wait = line / service rate, checked by stopwatch</li>
          <li>Our first formula, (in - made)/3, kept as a baseline: it tracks growth, not the line</li></ul></div>
        <div class="box"><h2>Model</h2><ul>
          <li>Predicts the <b>change</b> in line length 5/10/15 min ahead</li>
          <li>Inputs: line now, recent arrivals, service rate, dish speed, same-weekday arrival profile</li>
          <li>XGBoost vs small neural net vs 4 baselines; <b>{best.upper()}</b> chosen</li>
          <li>Tested on days it never saw, incl. each weekday predicted from the weeks before</li></ul></div>
      </div>
      <div class="foot"><span>Data: CSV + Parquet with embedded schema &middot; rebuild: python run_all.py (REPRODUCE.md)</span>
        <span>Observed / inferred tagged on every column</span></div>
    </section>"""

    s3 = f"""
    <section class="s">
      <div class="k">Result &middot; What changes</div>
      <h1>A 15-minute warning the kitchen can act on</h1>
      <div class="g" style="grid-template-columns: 1.15fr 1fr">
        <div>
          <h2>{res_title}</h2>
          <p>{res_line}</p>
          <img src="{img(FIG / 'model_1_mae.png')}">
          <p class="lbl" style="margin-top:8px">{wait_line}</p>
        </div>
        <div>
          <div class="box dark"><div class="lbl" style="color:#adb5bd">Manager card (held-out meal)</div>
            <div class="msg">{msg}</div><div class="lbl" style="color:#adb5bd;margin-top:8px">{ex_note}</div></div>
          <h2 style="margin-top:24px">What changes</h2>
          <ul><li><b>Manager</b>: acts 10-15 minutes earlier with a target service rate, instead of reacting to a long line</li>
              <li><b>Students</b>: "go now" or "come in 15 min"</li>
              <li><b>After each meal</b>: peak, minutes over target, the service rate that was needed</li></ul>
          <h2 style="margin-top:20px">Data Collection Challenges</h2>
          <ul><li>Tried accessing camera recordings but failed due to privacy issues and cameras not working.</li>
              <li>To resolve counting issues, we built an app to record: <b>people in</b> (entering mess and picking thali), <b>people out</b> (completed meal and returned thali), and <b>serving rate</b> (people leaving the queue).</li></ul>
        </div>
      </div>
      <div class="foot"><span>Demo: {html.escape(demo_url)}</span><span>{data_tag}</span></div>
    </section>"""
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{s1}{s2}{s3}</body></html>"


def to_pdf(html_path, pdf_path):
    if pdf_path.exists():
        pdf_path.unlink()                       # never report an old PDF as freshly rendered
    # 1. Try playwright if installed
    try:
        from playwright.async_api import async_playwright
        async def _pw():
            async with async_playwright() as p:
                b = await p.chromium.launch()
                pg = await b.new_page(viewport={"width": 1920, "height": 1080})
                await pg.goto(html_path.as_uri())
                await pg.wait_for_timeout(500)
                await pg.pdf(path=str(pdf_path), width="1920px", height="1080px", print_background=True,
                             margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
                await b.close()
        asyncio.run(_pw())
        return True
    except Exception as e:                      # not installed, or chromium not downloaded
        print(f"slides: playwright unavailable ({type(e).__name__}); trying a local Edge/Chrome")

    # 2. Try Edge or Chrome headless on Windows
    browser_bins = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    for b_bin in browser_bins:
        if b_bin.exists():
            cmd = [
                str(b_bin),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={pdf_path.resolve()}",
                html_path.resolve().as_uri(),
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=30)
                if pdf_path.exists():
                    return True
            except Exception:
                pass
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", default="Team Smart Mess")
    ap.add_argument("--demo-url", default="demo/smartmess_demo.mp4 (recorded) &middot; dashboard: streamlit run dashboard/app.py")
    a = ap.parse_args()
    out = ROOT / "slides"
    h = out / "smartmess_3slides.html"
    pdf = out / "smartmess_3slides.pdf"
    h.write_text(build(a.team, a.demo_url))
    print(f"slides: HTML written to {h}")
    ok = to_pdf(h, pdf)
    if ok:
        print(f"slides: PDF rendered to {pdf}")
    else:
        print("slides: could not render PDF; HTML slides ready at slides/smartmess_3slides.html")


if __name__ == "__main__":
    main()
