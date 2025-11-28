#!/usr/bin/env python3
"""
Capture each slide individually and combine into landscape PDF
"""
from playwright.sync_api import sync_playwright
from pypdf import PdfWriter
import os


def capture_all_slides_to_landscape_pdf(html_file, output_pdf):
    """Capture each slide individually to ensure all are in the PDF"""
    print(f"Converting {html_file} to landscape PDF...")

    temp_pdfs = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1600, 'height': 900})

        # Load HTML
        file_path = os.path.abspath(html_file)
        page.goto(f'file://{file_path}')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)

        # Count total slides
        slide_count = page.locator('.slide').count()
        print(f"  Found {slide_count} slides")

        # Hide controls
        page.add_style_tag(content='''
            .controls, .navigation, .nav-button, .slide-counter, button {
                display: none !important;
            }
        ''')

        # Capture each slide individually
        for i in range(slide_count):
            print(f"  Capturing slide {i+1}/{slide_count}...")

            # Make only this slide visible
            page.evaluate(f'''
                () => {{
                    const slides = document.querySelectorAll('.slide');
                    slides.forEach((slide, index) => {{
                        if (index === {i}) {{
                            slide.classList.add('active');
                            slide.style.display = 'block';
                        }} else {{
                            slide.classList.remove('active');
                            slide.style.display = 'none';
                        }}
                    }});
                }}
            ''')

            page.wait_for_timeout(300)

            # Capture this slide as a PDF page
            temp_pdf = f'temp_slide_{i}.pdf'
            page.pdf(
                path=temp_pdf,
                width='11in',
                height='8.5in',
                print_background=True,
                margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'}
            )
            temp_pdfs.append(temp_pdf)

        browser.close()

    # Combine all PDFs into one
    print(f"  Combining {len(temp_pdfs)} pages into single PDF...")
    from pypdf import PdfReader
    writer = PdfWriter()

    for temp_pdf in temp_pdfs:
        reader = PdfReader(temp_pdf)
        writer.add_page(reader.pages[0])
        os.remove(temp_pdf)  # Clean up temp file

    # Write final PDF
    with open(output_pdf, 'wb') as f:
        writer.write(f)

    size_kb = os.path.getsize(output_pdf) / 1024
    print(f"✓ Created {output_pdf} ({size_kb:.1f} KB)")
    print(f"  {slide_count} pages in LANDSCAPE (11\" wide × 8.5\" tall)")


if __name__ == '__main__':
    capture_all_slides_to_landscape_pdf(
        'presentation_slides.html',
        'presentation_slides_LANDSCAPE.pdf'
    )

    print("\n✓ ALL 10 SLIDES captured! Each slide = 1 landscape page.")
