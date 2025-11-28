#!/usr/bin/env python3
"""
Convert HTML presentations to landscape PDF
"""
import subprocess
import sys
import os


def install_package(package):
    """Install a Python package"""
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])


def create_landscape_pdf_weasyprint(html_file, pdf_file):
    """Convert HTML to landscape PDF using WeasyPrint"""
    try:
        from weasyprint import HTML, CSS
        print(f"Converting {html_file} to {pdf_file}...")

        # Create custom CSS for landscape orientation
        landscape_css = CSS(string='''
            @page {
                size: A4 landscape;
                margin: 0;
            }
            body {
                margin: 0;
                padding: 0;
            }
        ''')

        # Convert to PDF
        HTML(filename=html_file).write_pdf(
            pdf_file,
            stylesheets=[landscape_css]
        )

        print(f"✓ Created {pdf_file}")
        return True

    except Exception as e:
        print(f"WeasyPrint method failed: {e}")
        return False


def create_landscape_pdf_playwright(html_file, pdf_file):
    """Convert HTML to landscape PDF using Playwright"""
    try:
        from playwright.sync_api import sync_playwright

        print(f"Converting {html_file} to {pdf_file} using Playwright...")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            # Load the HTML file
            page.goto(f'file://{os.path.abspath(html_file)}')

            # Wait for page to load
            page.wait_for_load_state('networkidle')

            # Generate PDF with landscape orientation
            page.pdf(
                path=pdf_file,
                format='A4',
                landscape=True,
                print_background=True,
                margin={
                    'top': '0mm',
                    'right': '0mm',
                    'bottom': '0mm',
                    'left': '0mm'
                }
            )

            browser.close()

        print(f"✓ Created {pdf_file}")
        return True

    except Exception as e:
        print(f"Playwright method failed: {e}")
        return False


def main():
    files_to_convert = [
        ('presentation_slides.html', 'presentation_slides_landscape.pdf'),
        ('presentation.html', 'presentation_landscape.pdf')
    ]

    # Try WeasyPrint first
    print("Attempting conversion with WeasyPrint...")
    try:
        from weasyprint import HTML
        method = 'weasyprint'
    except ImportError:
        print("Installing WeasyPrint...")
        try:
            install_package('weasyprint')
            method = 'weasyprint'
        except:
            print("WeasyPrint installation failed, trying Playwright...")
            method = 'playwright'

    if method == 'playwright':
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("Installing Playwright...")
            install_package('playwright')
            subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])

    # Convert files
    for html_file, pdf_file in files_to_convert:
        if not os.path.exists(html_file):
            print(f"Warning: {html_file} not found, skipping...")
            continue

        success = False

        if method == 'weasyprint':
            success = create_landscape_pdf_weasyprint(html_file, pdf_file)

        if not success and method == 'playwright':
            success = create_landscape_pdf_playwright(html_file, pdf_file)

        if not success:
            print(f"Failed to convert {html_file}")

    print("\n✓ Conversion complete!")


if __name__ == '__main__':
    main()
