#!/usr/bin/env python3
"""
Convert ALL HTML presentation slides to landscape PDF
"""
from playwright.sync_api import sync_playwright
import os


def convert_all_slides_to_landscape_pdf(html_file, pdf_file):
    """Convert all HTML slides to landscape PDF"""
    print(f"Converting {html_file} to landscape PDF...")

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch()
        page = browser.new_page()

        # Load the HTML file
        file_path = os.path.abspath(html_file)
        page.goto(f'file://{file_path}')

        # Wait for page to fully load
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)

        # Inject CSS to show all slides and format for PDF printing
        page.add_style_tag(content='''
            @media print {
                @page {
                    size: 11in 8.5in;
                    margin: 0;
                }
            }

            /* Show all slides */
            .slide {
                display: block !important;
                page-break-after: always;
                page-break-inside: avoid;
                width: 100vw;
                height: 100vh;
                position: relative;
                overflow: hidden;
            }

            /* Hide navigation and controls for PDF */
            .controls,
            .navigation,
            .slide-counter,
            .nav-button,
            button {
                display: none !important;
            }

            /* Ensure proper sizing */
            body {
                margin: 0;
                padding: 0;
            }

            .slide-container,
            .presentation-container {
                width: 100%;
                height: 100%;
            }
        ''')

        # Wait a moment for styles to apply
        page.wait_for_timeout(500)

        # Count slides
        slide_count = page.locator('.slide').count()
        print(f"  Found {slide_count} slides")

        # Generate PDF with landscape orientation
        page.pdf(
            path=pdf_file,
            format='Letter',
            landscape=True,
            print_background=True,
            margin={
                'top': '0',
                'right': '0',
                'bottom': '0',
                'left': '0'
            },
            prefer_css_page_size=False,
            page_ranges='1-' + str(slide_count)
        )

        browser.close()

    # Get file size
    size_kb = os.path.getsize(pdf_file) / 1024
    print(f"✓ Created {pdf_file} ({size_kb:.1f} KB) with {slide_count} pages")


if __name__ == '__main__':
    conversions = [
        ('presentation_slides.html', 'presentation_slides_landscape.pdf'),
        ('presentation.html', 'presentation_landscape.pdf')
    ]

    print("Converting HTML presentations to landscape PDF...")
    print("=" * 60)

    for html_file, pdf_file in conversions:
        if os.path.exists(html_file):
            try:
                convert_all_slides_to_landscape_pdf(html_file, pdf_file)
            except Exception as e:
                print(f"Error converting {html_file}: {e}")
        else:
            print(f"Warning: {html_file} not found")

    print("=" * 60)
    print("✓ All conversions complete! All pages are LANDSCAPE.")
