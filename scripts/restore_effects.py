#!/usr/bin/env python3
"""Restore CSS visual effects that were disabled during debugging."""
import re
import glob
import os

site_dir = os.path.join(os.path.dirname(__file__), "..", "site", "foundation")

for path in sorted(glob.glob(os.path.join(site_dir, "*.html"))):
    if "test_nav" in path:
        continue

    with open(path, "r") as f:
        content = f.read()

    original = content

    # 1. Restore body::before grid lines
    content = content.replace(
        'body::before { content: ""; display: none; }',
        '''body::before {
      content: "";
      position: fixed; inset: 0; z-index: 0;
      background-image:
        linear-gradient(rgba(var(--f-rgb),.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(var(--f-rgb),.02) 1px, transparent 1px);
      background-size: 64px 64px;
      mask-image: radial-gradient(ellipse 70% 60% at 50% 30%, black 20%, transparent 100%);
      pointer-events: none;
    }'''
    )

    # 2. Restore body::after ambient glow
    content = content.replace(
        'body::after { content: ""; display: none; }',
        '''body::after {
      content: "";
      position: fixed; inset: 0; z-index: 0;
      background:
        radial-gradient(900px 600px at 20% -10%, rgba(var(--f-rgb),.06), transparent 60%),
        radial-gradient(700px 500px at 85% 10%, rgba(239,187,95,.04), transparent 55%),
        radial-gradient(800px 500px at 50% 110%, rgba(115,184,255,.04), transparent 50%);
      pointer-events: none;
    }'''
    )

    # 3. Restore scanlines CSS
    content = content.replace(
        '.scanlines { display: none; }',
        '''.scanlines {
      position: fixed; inset: 0; z-index: 9997; pointer-events: none;
      background: repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.025) 2px,rgba(0,0,0,.025) 4px);
    }'''
    )

    # 4. Restore backdrop-filter
    content = content.replace(
        '/* backdrop-filter removed for performance */',
        'backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);'
    )

    # 5. Restore scanlines div
    content = content.replace(
        '<!-- scanlines removed for performance -->',
        '<div class="scanlines" aria-hidden="true"></div>'
    )

    # 6. Keep grain SVG disabled (genuinely heavy) but restore the comment
    # grain SVG was replaced with a comment by fix_perf.py -- leave as is

    if content != original:
        with open(path, "w") as f:
            f.write(content)
        print(f"Restored effects: {os.path.basename(path)}")
    else:
        print(f"No changes: {os.path.basename(path)}")
