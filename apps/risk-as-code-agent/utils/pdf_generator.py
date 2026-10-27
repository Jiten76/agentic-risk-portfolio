"""
PDF one-pager generator.
Produces a clean, audit-ready risk evidence one-pager per domain.
Uses reportlab (pure Python, no LaTeX dependency).
"""

import os
from datetime import datetime, timezone
from typing import Dict, Any, List

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor, black, white, gray
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


RAG_COLORS = {
    "red":   "#C0392B",
    "amber": "#E67E22",
    "green": "#27AE60",
}

RAG_LABELS = {
    "red":   "RED — Exceeds Appetite",
    "amber": "AMBER — Approaching Threshold",
    "green": "GREEN — Within Appetite",
}

HEADER_BLUE = "#1A3A5C"
LIGHT_GRAY  = "#F4F6F8"
MID_GRAY    = "#BDC3C7"


def _rag_badge(rag: str) -> str:
    color = RAG_COLORS.get(rag, "#95A5A6")
    label = rag.upper()
    return f'<font color="{color}"><b>● {label}</b></font>'


def generate_domain_onepager(domain_report: Dict[str, Any], output_path: str) -> str:
    """
    Generate a PDF one-pager for a single domain.
    Returns the output path.
    """
    if not REPORTLAB_AVAILABLE:
        # Fallback: write a plain text version
        txt_path = output_path.replace(".pdf", ".txt")
        with open(txt_path, "w") as f:
            f.write(_plain_text_onepager(domain_report))
        return txt_path

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Header ───────────────────────────────────────────────────────────────
    header_style = ParagraphStyle(
        "Header", parent=styles["Normal"],
        fontSize=16, textColor=HexColor(HEADER_BLUE),
        spaceAfter=4, fontName="Helvetica-Bold",
    )
    sub_style = ParagraphStyle(
        "Sub", parent=styles["Normal"],
        fontSize=10, textColor=HexColor("#555555"),
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=9, leading=14, textColor=black,
        spaceAfter=6,
    )
    label_style = ParagraphStyle(
        "Label", parent=styles["Normal"],
        fontSize=8, textColor=HexColor("#777777"),
        spaceAfter=2, fontName="Helvetica-Bold",
    )

    domain_name = domain_report.get("domain_name", domain_report.get("domain_id", "Unknown"))
    period = domain_report.get("period", "—")
    overall_rag = domain_report.get("overall_rag", "green")
    rag_color = HexColor(RAG_COLORS.get(overall_rag, "#95A5A6"))

    story.append(Paragraph("RISK-AS-CODE AGENT FRAMEWORK", ParagraphStyle(
        "Tiny", parent=styles["Normal"], fontSize=7,
        textColor=HexColor("#999999"), spaceAfter=2, fontName="Helvetica",
    )))
    story.append(Paragraph(f"Technology Risk Evidence — {domain_name}", header_style))
    story.append(Paragraph(
        f"Period: {period}  ·  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ·  "
        f"Tier {domain_report.get('tier', '—')} Domain",
        sub_style,
    ))

    # RAG banner
    banner_data = [[
        Paragraph(f"Overall Posture: {RAG_LABELS.get(overall_rag, overall_rag.upper())}",
                  ParagraphStyle("Banner", parent=styles["Normal"], fontSize=11,
                                 textColor=white, fontName="Helvetica-Bold")),
        Paragraph(
            f"Findings: {domain_report.get('red_findings', 0)} Red  /  "
            f"{domain_report.get('amber_findings', 0)} Amber  /  "
            f"{domain_report.get('patterns_assessed', 12)} Patterns Assessed",
            ParagraphStyle("BannerRight", parent=styles["Normal"], fontSize=9,
                           textColor=white, alignment=TA_RIGHT)),
    ]]
    banner = Table(banner_data, colWidths=[4 * inch, 3 * inch])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), rag_color),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(Spacer(1, 8))
    story.append(banner)
    story.append(Spacer(1, 10))

    # Executive Summary
    story.append(Paragraph("EXECUTIVE SUMMARY", label_style))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(MID_GRAY)))
    story.append(Spacer(1, 4))
    exec_summary = domain_report.get("executive_summary", "—")
    story.append(Paragraph(exec_summary, body_style))
    story.append(Spacer(1, 8))

    # Findings table
    findings = domain_report.get("findings", [])
    if findings:
        story.append(Paragraph("RISK PATTERN FINDINGS", label_style))
        story.append(HRFlowable(width="100%", thickness=1, color=HexColor(MID_GRAY)))
        story.append(Spacer(1, 4))

        table_data = [[
            Paragraph("<b>Pattern</b>", ParagraphStyle("TH", parent=styles["Normal"], fontSize=8, fontName="Helvetica-Bold")),
            Paragraph("<b>RAG</b>", ParagraphStyle("TH", parent=styles["Normal"], fontSize=8, fontName="Helvetica-Bold")),
            Paragraph("<b>Key Signals</b>", ParagraphStyle("TH", parent=styles["Normal"], fontSize=8, fontName="Helvetica-Bold")),
            Paragraph("<b>Evidence Summary</b>", ParagraphStyle("TH", parent=styles["Normal"], fontSize=8, fontName="Helvetica-Bold")),
        ]]

        for finding in findings:
            rag = finding.get("overall_rag", "green")
            row_color = HexColor("#FDECEA") if rag == "red" else (HexColor("#FEF9E7") if rag == "amber" else HexColor("#EAFAF1"))
            narrative = finding.get("evidence_narrative", "—")
            if len(narrative) > 200:
                narrative = narrative[:197] + "..."

            table_data.append([
                Paragraph(f"<b>{finding.get('pattern_id', '—')}</b><br/><font size='7'>{finding.get('pattern_name', '')}</font>",
                          ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8)),
                Paragraph(f'<font color="{RAG_COLORS.get(rag, "#000")}"><b>{rag.upper()}</b></font>',
                          ParagraphStyle("RAG", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold")),
                Paragraph(f"<font size='7'>{finding.get('signal_summary', '—')}</font>",
                          ParagraphStyle("Cell", parent=styles["Normal"], fontSize=7)),
                Paragraph(f"<font size='7'>{narrative}</font>",
                          ParagraphStyle("Cell", parent=styles["Normal"], fontSize=7, leading=10)),
            ])

        findings_table = Table(table_data, colWidths=[1.1*inch, 0.6*inch, 1.8*inch, 3.2*inch])
        findings_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor(HEADER_BLUE)),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor(LIGHT_GRAY), white]),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor(MID_GRAY)),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(findings_table)
        story.append(Spacer(1, 10))

    # Attestation
    story.append(Paragraph("ATTESTATION", label_style))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(MID_GRAY)))
    story.append(Spacer(1, 4))
    attestation = domain_report.get("attestation_statement", "—")
    story.append(Paragraph(attestation, body_style))
    story.append(Spacer(1, 16))

    # Signature block
    sig_data = [[
        Paragraph("2LoD Reviewer: _______________________", ParagraphStyle("Sig", parent=styles["Normal"], fontSize=8)),
        Paragraph("Domain Owner: _______________________", ParagraphStyle("Sig", parent=styles["Normal"], fontSize=8)),
        Paragraph(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}", ParagraphStyle("Sig", parent=styles["Normal"], fontSize=8)),
    ]]
    sig_table = Table(sig_data, colWidths=[2.5*inch, 2.5*inch, 2*inch])
    sig_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(sig_table)

    # Footer note
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Generated by Risk-as-Code Agent Framework · Evidence source: telemetry-auto · "
        "Framework alignment: NIST CSF 2.0, ISO 31000, DORA · "
        "github.com/Jiten76/risk-as-code-agent",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7,
                       textColor=HexColor("#AAAAAA"), alignment=TA_CENTER),
    ))

    doc.build(story)
    return output_path


def _plain_text_onepager(domain_report: Dict[str, Any]) -> str:
    lines = [
        "=" * 70,
        "RISK-AS-CODE AGENT FRAMEWORK — EVIDENCE ONE-PAGER",
        "=" * 70,
        f"Domain: {domain_report.get('domain_name', domain_report.get('domain_id', '?'))}",
        f"Period: {domain_report.get('period', '?')}",
        f"Overall RAG: {domain_report.get('overall_rag', '?').upper()}",
        f"Findings: {domain_report.get('red_findings', 0)} Red / {domain_report.get('amber_findings', 0)} Amber",
        "",
        "EXECUTIVE SUMMARY",
        "-" * 40,
        domain_report.get("executive_summary", "—"),
        "",
        "FINDINGS",
        "-" * 40,
    ]
    for f in domain_report.get("findings", []):
        lines.append(f"[{f.get('overall_rag','?').upper()}] {f.get('pattern_id')} — {f.get('pattern_name')}")
        lines.append(f"  Signals: {f.get('signal_summary', '—')}")
        lines.append(f"  {f.get('evidence_narrative', '—')}")
        lines.append("")
    lines += [
        "ATTESTATION",
        "-" * 40,
        domain_report.get("attestation_statement", "—"),
        "",
        "2LoD Reviewer: _______________________  Date: ___________",
        "Domain Owner:  _______________________",
        "=" * 70,
    ]
    return "\n".join(lines)


def generate_all_onepagers(report: Dict[str, Any], output_dir: str = "outputs") -> List[str]:
    """Generate one PDF per domain from a full attestation report."""
    paths = []
    for domain_id, domain_report in report.get("domain_reports", {}).items():
        filename = f"{report.get('period', 'report')}_{domain_id}_evidence.pdf"
        output_path = os.path.join(output_dir, filename)
        path = generate_domain_onepager(domain_report, output_path)
        paths.append(path)
        print(f"  Generated: {path}")
    return paths


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from graph.risk_graph import run_risk_assessment

    print("Running demo assessment...")
    report = run_risk_assessment(demo=True)
    print("Generating one-pagers...")
    paths = generate_all_onepagers(report, "outputs")
    print(f"Done. {len(paths)} documents generated.")
