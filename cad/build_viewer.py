"""Splice the packed geometry into the viewer shell to make one standalone file.

The result has no external requests at all -- no CDN, no loader library, no
sidecar mesh file -- so it opens straight off disk, off a phone, or out of a
published artifact with identical behaviour.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")


# Per-variant identity: the shell's subtitle and stat block are the frame's;
# the console build swaps them. Plain string replacement against the exact
# shell text, asserted so a shell edit cannot silently ship frame numbers
# under a console title.
CONSOLE_SWAPS = [
    ("<p>Skeletal frame with a printed DIN rail</p>",
     "<p>Moulded console with a printed DIN rail</p>"),
    # the envelope itself is no longer typed: __ENV__ is filled from each
    # variant's own data (2026-10-17, the frame's read 154 high for a month
    # after the screen went on)
    ('<div class="rev">__ENV__ MM &middot; 18 RIGID + 18 TPU</div>',
     '<div class="rev">__ENV__ MM &middot; ONE MOULDING + RAIL</div>'),
    ('<div><span class="k">filament  </span><b>347</b> cm&sup3; &rarr; '
     "<b>~320</b> g</div>",
     '<div><span class="k">filament  </span><b>412</b> cm&sup3; &rarr; '
     "<b>~310</b> g</div>"),
    ('<div><span class="k">rail held </span><b>4</b> supports &middot; '
     "<b>8</b> screws</div>",
     '<div><span class="k">rail held </span><b>4</b> panel pilots &middot; '
     "<b>4</b> screws</div>"),
]


def main():
    with open(os.path.join(HERE, "viewer_shell.html"), encoding="utf-8") as f:
        shell = f.read()

    builds = [("viewer_data.json", [], "bench-viewer")]
    if os.path.exists(os.path.join(OUT, "viewer_data_console.json")):
        builds.append(("viewer_data_console.json", CONSOLE_SWAPS,
                       "console-viewer"))
    # v2 (two posts) is now the shipped mount, so it needs no variant of its
    # own -- the base build IS it. What needs one is the v1 H-frame it
    # replaced, staged by cad/display_mount_v1.py.
    if os.path.exists(os.path.join(OUT, "viewer_data_mountv1.json")):
        builds.append(("viewer_data_mountv1.json", [
            ("<p>Skeletal frame with a printed DIN rail</p>",
             "<p>Skeletal frame &mdash; previous display mount, spine + "
             "uprights + crossbars (superseded)</p>"),
        ], "mountv1-viewer"))
    # The superseded tie joint, kept selectable so the change can be judged
    # rather than taken on trust. Staged by scratchpad/stage_tievee.py --
    # frame.py no longer contains this geometry.
    if os.path.exists(os.path.join(OUT, "viewer_data_tievee.json")):
        builds.append(("viewer_data_tievee.json", [
            ("<p>Skeletal frame with a printed DIN rail</p>",
             "<p>Skeletal frame &mdash; previous tie joint, V-notched "
             "tails (superseded)</p>"),
        ], "tievee-viewer"))
    # The proposed recessed-ledge deck (PLAN.md, 2026-09-23), staged on the
    # Mac by cad/ledge_ladder.py from the plan's numbers until frame.py
    # exports it for real. Proposed, not built: the subtitle says so.
    if os.path.exists(os.path.join(OUT, "viewer_data_ledge.json")):
        builds.append(("viewer_data_ledge.json", [
            ("<p>Skeletal frame with a printed DIN rail</p>",
             "<p>Skeletal frame &mdash; PROPOSED deck: teeth and stops gone, "
             "the boards recessed 1.2 mm into the ledges (to confirm)</p>"),
        ], "ledge-viewer"))

    for data_name, swaps, stem in builds:
        with open(os.path.join(OUT, data_name), encoding="utf-8") as f:
            data = f.read()

        # Base64 and ASCII labels cannot contain "<", but escaping it anyway
        # means a future label with a stray "</script>" can never break out
        # of the tag.
        data = data.replace("<", "\\u003c")

        assert "__DATA__" in shell, "shell lost its data placeholder"
        page = shell
        for old, new in swaps:
            assert old in page, f"shell drifted; swap not found: {old[:40]}"
            page = page.replace(old, new)
        w, d, h = json.loads(data)["size"]
        page = page.replace("__ENV__", f"{w:.0f} &times; {d:.0f} &times; {h:.0f}")
        assert "__ENV__" not in page
        page = page.replace("__DATA__", data)

        # Two builds off one shell. The artifact host wraps the file in its
        # own <!doctype html><head>...<body> skeleton, so the published copy
        # must not carry a doctype -- but a file opened straight off disk
        # without one lands in quirks mode, where layout is subtly wrong.
        for name, prefix in ((f"{stem}.html", "<!doctype html>\n"),
                             (f"{stem}.artifact.html", "")):
            path = os.path.join(OUT, name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(prefix + page)
            print(f"  {os.path.getsize(path) / 1048576:.2f} MB -> "
                  f"{os.path.normpath(path)}")


if __name__ == "__main__":
    main()
