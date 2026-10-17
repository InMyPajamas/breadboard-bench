"""Build a public, static copy of bench-hub.html for redding.digital.

    python cad/publish_site.py            # -> ../redding-digital/public/bench*
    python cad/publish_site.py --out DIR  # somewhere else

The hub as served on the LAN is 150 kB of HTML and 268 MB of PNG renders, and
its Checks tab talks to a server that only exists at home. Neither survives a
static host, so this makes a copy that does:

  * every referenced PNG re-encoded as WEBP. These are flat-shaded renders with
    large uniform areas, so they land at about 2% of the PNG size -- 268 MB
    becomes roughly 5 MB, which is what makes the whole idea viable.
  * the Checks tab rewritten as READ-ONLY results. On a static host there is no
    /save and no /data, so the live progress bars and the "open the sheet"
    buttons would simply be broken. Instead the recorded answers and the
    constants they settled are baked in as plain cards, which is the part a
    visitor actually wants to see.
  * a banner saying this is a snapshot of a workshop tool, with the date.

Nothing here is destructive: it only writes into the output directory. It does
not commit, push or deploy.
"""
import argparse
import json
import os
import re
import shutil
from datetime import date

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DEFAULT_OUT = os.path.abspath(os.path.join(ROOT, "..", "redding-digital", "public"))
QUALITY = 82

SHEETS = [
    ("Plate 01 - TPU", "PLATE 01", os.path.join(ROOT, "out", "plate1_tpu", "measurements.json"),
     "Caliper readings for the TPU pads and the control block, spoken rather than typed so both "
     "hands stay on the caliper. Settles FOOT_FIT and how much TPU over-prints on this machine."),
    ("Plate 02 - fits", "PLATES 02, 02B, 02C, 02D", os.path.join(ROOT, "out", "plate2_pla", "fit_results.json"),
     "Push each printed gauge into its slot and tap what happened. Settles the rail slot, the round "
     "sockets, the foot pocket, the pilot screws, the gasket and the magnet caps."),
    ("Cleat gauges", "PLATES 02E-02I", os.path.join(ROOT, "out", "plate2_pla", "cleat_results.json"),
     "The board retention rework: drop a breadboard onto each gauge by its own dovetail cleats. "
     "Settles the rail gap and the station span that replace the indexing teeth."),
]


def convert(src_rel, out_dir, seen):
    """PNG -> WEBP inside the output tree. Returns the new relative path."""
    src = os.path.join(ROOT, src_rel)
    if not os.path.exists(src):
        return None
    # every source extension, not just .png -- writing WEBP bytes into a .jpg
    # name leaves the file unreachable once the HTML asks for .webp
    new_rel = re.sub(r"\.(png|jpe?g)$", ".webp", src_rel, flags=re.I)
    dst = os.path.join(out_dir, new_rel)
    if new_rel in seen:
        return new_rel
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im = Image.open(src)
    im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") and "A" in im.getbands() else "RGB")
    im.save(dst, "WEBP", quality=QUALITY, method=5)
    seen[new_rel] = (os.path.getsize(src), os.path.getsize(dst))
    return new_rel


def read_sheet(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def checks_panel():
    """The Checks tab, as static results rather than a live tool."""
    cards = []
    for title, plates, path, blurb in SHEETS:
        d = read_sheet(path) or {}
        vals = d.get("values") or {}
        answered = d.get("answered", len(vals))
        required = d.get("required")
        derived = {k: v for k, v in (d.get("derived") or {}).items()
                   if v is not None and not isinstance(v, (dict, list))}
        rows = "".join(
            f'<li><span>{k}</span><b>{v}</b></li>' for k, v in list(derived.items())[:8])
        count = (f"<b>{answered}</b>" + (f" of <b>{required}</b>" if required else "") + " answered"
                 if answered else "not started")
        if d.get("complete"):
            count += ' &middot; <span class="done">complete</span>'
        cards.append(f"""
      <div class="check">
        <h3>{title}</h3>
        <div class="plates">{plates}</div>
        <p>{blurb}</p>
        <div class="stat">{count}</div>
        {'<ul class="derived">' + rows + '</ul>' if rows else ''}
      </div>""")
    return f"""<section id="checks" role="tabpanel">
  <div class="eyebrow">Result sheets &middot; tapped at the printer &middot; what they settled</div>
  <h2>Checks</h2>
  <p style="color:var(--bone-dim); max-width:78ch; margin:-4px 0 18px; font-size:13.5px">
    Every printed gauge exists to settle a number, and a number that stays in your head is a number
    the CAD never gets. On the workshop LAN these are tap-through sheets on an iPad that save to disk
    as you go and work the constant out for you. Here they are the results: what was answered, and
    the constants that went back into the CAD.</p>
  <div class="checks">{''.join(cards)}
  </div>
</section>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()
    out_dir = os.path.join(args.out, "bench")
    os.makedirs(out_dir, exist_ok=True)

    html = open(os.path.join(ROOT, "bench-hub.html"), encoding="utf-8").read()

    # 1. Assets. The page builds most image paths at runtime -- `renders/
    # ${stem}_${ang}.png` -- so there is no list of them to walk. What IS
    # constant is the extension, so convert every image in the asset trees and
    # swap the extension globally in the HTML.
    seen = {}
    for tree in ("renders", os.path.join("checklist", "img")):
        base = os.path.join(ROOT, tree)
        for dp, dirs, files in os.walk(base):
            # a film's PNG frame sequence (renders/*_frames/, 4 GB by
            # 2026-10-17) is the film's source, not a page asset
            dirs[:] = [d for d in dirs if not d.endswith("_frames")]
            for f in files:
                rel = os.path.relpath(os.path.join(dp, f), ROOT)
                low = f.lower()
                if low.endswith((".png", ".jpg", ".jpeg")):
                    convert(rel, out_dir, seen)
                elif low.endswith((".mp4", ".webm", ".svg")):
                    dst = os.path.join(out_dir, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(os.path.join(ROOT, rel), dst)

    # the viewers and the data the catalogue reads, plus only those STLs the
    # page actually names -- out/ holds 114 MB of geometry and the site wants
    # about 5 MB of it
    wanted = set(re.findall(r'["\'`](out/[^"\'`]+)["\'`]', html))
    wanted |= {"out/catalog.json"}
    for rel in sorted(wanted):
        src = os.path.join(ROOT, rel.split("?")[0])
        if os.path.isfile(src):
            dst = os.path.join(out_dir, rel.split("?")[0])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

    # 2. the Checks tab becomes static results
    start = html.index('<section id="checks" role="tabpanel">')
    end = html.index('<section id="plan" role="tabpanel">')
    html = html[:start] + checks_panel() + "\n\n" + html[end:]
    # and its script, which only talks to the sheet server, goes with it
    html = re.sub(r"<script>\n// ---- Checks tab .*?</script>", "", html, flags=re.S)

    # 3. say plainly what this is
    banner = (f'<div style="background:var(--graphite);border-bottom:1px solid var(--line);'
              f'padding:10px 16px;font:12px/1.5 var(--mono);color:var(--bone-dim)">'
              f'A published snapshot of a workshop tool, {date.today():%d %B %Y}. '
              f'The live version runs on the shop LAN, where the result sheets save to disk and the '
              f'3D viewer talks to the printer.</div>')
    html = html.replace("<body>", "<body>\n" + banner, 1)

    # 4. Point the page at the converted assets. The extension swap is global
    # because dynamic paths end in a literal ".png" even when the stem is
    # interpolated; every .png/.jpg this page names is one of its own renders.
    html = re.sub(r"\.(png|jpe?g)\b", ".webp", html, flags=re.I)
    # the page sits one level above its assets, so prefix the trees
    html = re.sub(r'(["\'`])(renders|out|checklist)/', r"\1bench/\2/", html)

    dst_html = os.path.join(args.out, "bench-hub.html")
    open(dst_html, "w", encoding="utf-8").write(html)

    png, webp = sum(a for a, _ in seen.values()), sum(b for _, b in seen.values())
    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fs in os.walk(out_dir) for f in fs) + os.path.getsize(dst_html)
    print(f"  wrote {dst_html}")
    print(f"  {len(seen)} images: {png/1e6:.1f} MB PNG -> {webp/1e6:.1f} MB WEBP "
          f"({100*webp/max(png,1):.0f}%)")
    print(f"  bundle total: {total/1e6:.1f} MB")


if __name__ == "__main__":
    main()
