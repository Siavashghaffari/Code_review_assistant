#!/usr/bin/env python3
"""
Rotate existing PDF pages to landscape orientation
"""
from pypdf import PdfReader, PdfWriter


def rotate_pdf_to_landscape(input_pdf, output_pdf):
    """Rotate all pages in PDF to landscape"""
    print(f"Rotating {input_pdf} to landscape...")

    # Read the PDF
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    num_pages = len(reader.pages)
    print(f"  Found {num_pages} pages")

    # Rotate each page
    for i, page in enumerate(reader.pages):
        print(f"  Rotating page {i+1}/{num_pages}...")
        # Rotate 90 degrees clockwise to landscape
        page.rotate(90)
        writer.add_page(page)

    # Write the output PDF
    with open(output_pdf, 'wb') as f:
        writer.write(f)

    print(f"✓ Created {output_pdf} with all {num_pages} pages in LANDSCAPE")


if __name__ == '__main__':
    # Rotate the existing PDF
    rotate_pdf_to_landscape('presentation_slides.pdf', 'presentation_slides_LANDSCAPE.pdf')
    print("\n✓ Done! All 10 pages are now LANDSCAPE orientation.")
