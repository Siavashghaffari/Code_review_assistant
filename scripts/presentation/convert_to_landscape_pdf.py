#!/usr/bin/env python3
"""
Convert HTML presentations to landscape PDF using Playwright
"""
from playwright.sync_api import sync_playwright
import os


def convert_to_landscape_pdf(html_file, pdf_file):
    """Convert HTML to landscape PDF"""
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
        page.wait_for_timeout(2000)  # Extra wait for animations

        # Generate PDF with landscape orientation
        page.pdf(
            path=pdf_file,
            format='Letter',  # 11x8.5 inches
            landscape=True,
            print_background=True,
            margin={
                'top': '0',
                'right': '0',
                'bottom': '0',
                'left': '0'
            },
            prefer_css_page_size=False
        )

        browser.close()

    # Get file size
    size_kb = os.path.getsize(pdf_file) / 1024
    print(f"✓ Created {pdf_file} ({size_kb:.1f} KB)")


if __name__ == '__main__':
    conversions = [
        ('presentation_slides.html', 'presentation_slides_landscape.pdf'),
        ('presentation.html', 'presentation_landscape.pdf')
    ]

    for html_file, pdf_file in conversions:
        if os.path.exists(html_file):
            convert_to_landscape_pdf(html_file, pdf_file)
        else:
            print(f"Warning: {html_file} not found")

    print("\n✓ All conversions complete! All pages are in LANDSCAPE orientation.")
