#!/usr/bin/env python3
"""
Convert presentation HTML to PDF with ALL pages in landscape
Using headless Chrome print-to-PDF
"""
from playwright.sync_api import sync_playwright
import os


def convert_presentation_to_landscape_pdf(html_file, pdf_file):
    """Convert HTML presentation to landscape PDF with all slides"""

    print(f"Converting {html_file} to landscape PDF...")

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        # Load HTML file
        file_path = os.path.abspath(html_file)
        page.goto(f'file://{file_path}')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1500)

        # Force ALL slides to be visible and each on its own page
        page.evaluate('''
            () => {
                // Remove all controls
                const controls = document.querySelectorAll('.controls, .navigation, .slide-counter, button');
                controls.forEach(el => el.remove());

                // Get all slides
                const slides = document.querySelectorAll('.slide');

                // Make ALL slides visible
                slides.forEach((slide, index) => {
                    slide.style.display = 'block';
                    slide.style.position = 'relative';
                    slide.style.pageBreakAfter = 'always';
                    slide.style.pageBreakInside = 'avoid';
                    slide.style.width = '100vw';
                    slide.style.height = '100vh';
                    slide.style.minHeight = '8.5in';
                    slide.classList.add('active');
                });

                // Remove page break from last slide
                if (slides.length > 0) {
                    slides[slides.length - 1].style.pageBreakAfter = 'auto';
                }
            }
        ''')

        page.wait_for_timeout(1000)

        # Count slides
        slide_count = page.locator('.slide').count()
        print(f"Found {slide_count} slides")

        # Generate PDF in landscape
        page.pdf(
            path=pdf_file,
            format='Letter',
            landscape=True,  # THIS MAKES IT LANDSCAPE
            print_background=True,
            margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'},
            prefer_css_page_size=False
        )

        browser.close()

    # Verify
    from pypdf import PdfReader
    reader = PdfReader(pdf_file)
    num_pages = len(reader.pages)
    size_kb = os.path.getsize(pdf_file) / 1024

    print(f"✓ SUCCESS: {pdf_file}")
    print(f"  {num_pages} PAGES")
    print(f"  {size_kb:.1f} KB")
    print(f"  LANDSCAPE orientation (11\" × 8.5\")")

    return num_pages


if __name__ == '__main__':
    num_pages = convert_presentation_to_landscape_pdf(
        'presentation_slides.html',
        'presentation_slides_LANDSCAPE.pdf'
    )

    if num_pages == 10:
        print("\n✓✓✓ PERFECT! All 10 slides captured in LANDSCAPE ✓✓✓")
    else:
        print(f"\n⚠ Warning: Expected 10 pages but got {num_pages}")
