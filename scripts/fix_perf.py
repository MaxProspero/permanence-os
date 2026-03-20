#!/usr/bin/env python3
"""Strip GPU-heavy effects from Foundation Site pages for performance."""
import sys
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

    # 1. Disable body::before grid lines (mask-image is GPU heavy)
    content = re.sub(
        r'body::before\s*\{\s*content:\s*"";\s*position:\s*fixed;[^}]*mask-image:[^}]*\}',
        'body::before { content: ""; display: none; }',
        content
    )

    # 2. Disable body::after ambient glow (multiple radial-gradients)
    content = re.sub(
        r'body::after\s*\{\s*content:\s*"";\s*position:\s*fixed;[^}]*radial-gradient[^}]*\}',
        'body::after { content: ""; display: none; }',
        content
    )

    # 3. Disable scanlines
    content = re.sub(
        r'\.scanlines\s*\{[^}]*repeating-linear-gradient[^}]*\}',
        '.scanlines { display: none; }',
        content
    )

    # 4. Remove backdrop-filter (GPU intensive)
    content = re.sub(
        r'backdrop-filter:\s*blur\([^)]*\);\s*-webkit-backdrop-filter:\s*blur\([^)]*\);',
        '/* backdrop-filter removed for performance */',
        content
    )

    # 5. Hide SVG grain element
    content = re.sub(
        r'<svg id="grain"[^>]*>.*?</svg>',
        '<!-- grain SVG removed for performance -->',
        content,
        flags=re.DOTALL
    )

    # 6. Hide scanlines div
    content = content.replace(
        '<div class="scanlines" aria-hidden="true"></div>',
        '<!-- scanlines removed for performance -->'
    )

    if content != original:
        with open(path, "w") as f:
            f.write(content)
        print(f"Optimized: {os.path.basename(path)}")
    else:
        print(f"No changes: {os.path.basename(path)}")
