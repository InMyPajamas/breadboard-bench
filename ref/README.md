# Reference files

The CAD reads two vendor models when they are here and skips the parts that use them when they
are not, so the bench still builds without them. They are not in this repo because they are the
vendors' files. Download them into these folders:

| Folder | File | Where from | Used for |
|---|---|---|---|
| `ref/crowpanel7_p4/` | `crowpanel7_p4.stp` | Elecrow's CrowPanel Advanced 7" ESP32-P4 repository on GitHub | the screen prop, the backplate's clearances |
| `ref/respeaker_xvf3800/` | `respeaker_mic_array_xvf3800_1_with-xiao-0820.stp` | Seeed Studio wiki, reSpeaker XVF3800 USB 4-Mic Array | the mic board prop on the crown |

`ref/templates/h2s_petg_hf_pla_basic.3mf` is a two-filament Bambu Studio project saved from the
GUI (PETG HF in slot 1, PLA Basic in slot 2, H2S 0.4). `cad/plates.py` copies its settings into
every PETG + PLA plate and every multi-plate project, because Studio's GUI rejects a
two-filament config written from scratch.
