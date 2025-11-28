#!/usr/bin/env python3
"""
Properly convert HTML slides to landscape PDF
Pages are WIDER than tall, content oriented correctly
"""
from playwright.sync_api import sync_playwright
import os


def convert_html_to_proper_landscape_pdf(html_file, pdf_file):
    """Convert HTML to proper landscape PDF (wide pages, not rotated)"""
    print(f"Converting {html_file} to proper landscape PDF...")

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Set viewport to landscape dimensions
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})

        # Load HTML file
        file_path = os.path.abspath(html_file)
        page.goto(f'file://{file_path}')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)

        # Inject CSS to display all slides for PDF
        page.add_style_tag(content='''
            @page {
                size: 11in 8.5in;  /* Landscape: width > height */
                margin: 0;
            }

            /* Show ALL slides */
            .slide {
                display: block !important;
                page-break-after: always;
                page-break-inside: avoid;
                width: 100vw;
                height: 100vh;
                min-height: 8.5in;
            }

            /* Remove last page break */
            .slide:last-child {
                page-break-after: avoid;
            }

            /* Hide controls */
            .controls,
            .navigation,
            .nav-button,
            .slide-counter,
            button {
                display: none !important;
            }
        ''')

        page.wait_for_timeout(500)

        # Count slides
        slide_count = page.locator('.slide').count()
        print(f"  Found {slide_count} slides")

        # Generate PDF - LANDSCAPE orientation
        page.pdf(
            path=pdf_file,
            width='11in',      # Width = 11 inches (WIDE)
            height='8.5in',    # Height = 8.5 inches (TALL)
            print_background=True,
            margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'}
        )

        browser.close()

    size_kb = os.path.getsize(pdf_file) / 1024
    print(f"✓ Created {pdf_file} ({size_kb:.1f} KB)")
    print(f"  {slide_count} pages in LANDSCAPE (11\" wide × 8.5\" tall)")


if __name__ == '__main__':
    convert_html_to_proper_landscape_pdf(
        'presentation_slides.html',
        'presentation_slides_LANDSCAPE.pdf'
    )

    print("\n✓ Done! Pages are LANDSCAPE (wider than tall) with content oriented correctly.")
