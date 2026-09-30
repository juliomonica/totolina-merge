## Animation

For any task involving animation, character rigs, merge effects, UI motion,
background/environment animation, particles/VFX, or animation tooling, read and
follow:

`docs/ANIMATION_GUIDELINES.md`

## Photoshop operator requests

Use the configured `photoshop_process_image` MCP tool directly for these short
requests; no preliminary `photoshop_ping`, manual `core.server`, or UDT launch.
See `tools/LUNITORA_COMMANDS.md` for daily commands and
`tools/lunitora_mcp/README.md` for technical setup and limits.

For a bare PNG filename, use exactly that file under `source_art/_inbox/`.
Default destinations below are under `source_art/_staging/`:

| Request | Destination | Parameters |
| --- | --- | --- |
| Remove the background from cat.png | `cat_nobg.png` | `mode:preserve_size`, `remove_background:true`; read the source PNG dimensions and use them as `width_px` / `height_px`. |
| Resize cat.png to 384x384 | `cat_384x384.png` | `width_px:384`, `height_px:384`, `mode:fit`, `resample:bicubic`, `remove_background:false`. |
| Remove the background and resize cat.png to 384x384 | `cat_nobg_384x384.png` | Same resize parameters with `remove_background:true`. |

Apply the same naming rule to other requested filenames and dimensions. Preserve
explicit user choices within the tool's constraints. Fit never upscales or crops;
it centers the artwork with transparent padding. Use nearest only when explicitly
requested (for example pixel art). Do not guess missing source dimensions.

Never overwrite staging candidates. If the default destination exists, explain
the collision and obtain a new filename; never delete/replace the existing file
or silently process another source. Never promote a candidate to runtime assets.
For character/fine-detail work recommend background removal → human visual review
→ copy the approved candidate back to `_inbox` → resize. A combined request is
still authorized as one candidate operation. Technical validation does not replace
human visual approval. Never print, log or put pairing tokens in chat or Git.
