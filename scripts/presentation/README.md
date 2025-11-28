# Presentation Generation Scripts

This folder contains Python scripts for converting HTML presentations to various formats.

## Scripts

### PowerPoint Conversion
- **match_html_design.py** - Main script to convert HTML to PowerPoint (RECOMMENDED)
  - Matches HTML design with gradient backgrounds and white content boxes  
  - Preserves layouts, colors, and styling
  - Includes stats cards, impact cards, and feature lists
  - Usage: `python match_html_design.py`

- **html_to_pptx_with_design.py** - Alternative PowerPoint converter
- **html_to_pptx.py** - Basic PowerPoint converter (older version)

### PDF Conversion
- **capture_each_slide.py** - Captures each HTML slide individually to PDF (RECOMMENDED for PDF)
  - Creates landscape PDFs with all slides
  - Each slide becomes one page
  - Usage: `python capture_each_slide.py`

- **convert_all_slides_to_pdf.py** - Alternative PDF conversion method
- **final_landscape_pdf.py** - Landscape PDF generator
- **html_to_landscape_pdf.py** - HTML to landscape PDF converter
- **convert_to_landscape_pdf.py** - Simple landscape PDF converter
- **proper_landscape_pdf.py** - Proper landscape orientation PDF
- **rotate_pdf_to_landscape.py** - Rotates existing PDF pages to landscape

## Requirements

Install required packages:
```bash
pip install python-pptx beautifulsoup4 playwright pypdf
python -m playwright install chromium
```

## Usage Examples

### Generate PowerPoint from HTML
```bash
cd presentations
python ../scripts/match_html_design.py
```

### Generate Landscape PDF from HTML
```bash
cd presentations
python ../scripts/capture_each_slide.py
```

## Notes
- All scripts expect to run from the presentations/ folder
- Scripts use presentation_slides.html as the default input
- Output files are created in the same directory as the input file
