"""Tool to fetch a news article URL and generate a PDF of its content."""


def fetch_article_as_pdf(url: str, output_path: str) -> dict:
    """Fetch a news article URL and save it as a plain-text PDF.

    Args:
        url: The article URL to fetch.
        output_path: Full path where the PDF should be saved.

    Returns:
        dict with 'success' (bool), 'path' (str), and 'message' (str).
    """
    try:
        from fpdf import FPDF
    except ImportError:
        return {"success": False, "path": "", "message": "fpdf2 not installed. Run: pip install fpdf2"}

    # Fetch and extract clean article text
    try:
        import requests
        import trafilatura

        _HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-AU,en;q=0.9",
        }
        r = requests.get(url, headers=_HEADERS, timeout=15)
        text = trafilatura.extract(r.text) if r.status_code == 200 else None
        if not text:
            text = "(Could not extract article text)"
    except Exception as e:
        return {"success": False, "path": "", "message": f"Failed to fetch URL: {e}"}

    def _safe(s: str) -> str:
        """Strip non-latin-1 characters so FPDF core fonts don't choke."""
        return s.encode("latin-1", errors="replace").decode("latin-1")

    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # URL header
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(pdf.epw, 7, _safe(url[:120]))
        pdf.ln(4)

        # Article body
        pdf.set_font("Helvetica", "", 10)
        for line in text.splitlines():
            safe_line = _safe(line.strip())
            if safe_line:
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(pdf.epw, 5, safe_line)

        pdf.output(output_path)
        return {"success": True, "path": output_path, "message": "PDF created"}
    except Exception as e:
        return {"success": False, "path": "", "message": f"PDF generation failed: {e}"}
