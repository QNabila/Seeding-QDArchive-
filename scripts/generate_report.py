"""
Part 2 Step 4d: Generate PDF Classification Report
Student: Nabila Kader | ID: 23079506
"""

import sqlite3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import io
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

DB_PATH = "23079506-sq26-classification.db"

def get_data(conn):
    """Get all classification data organized by repository."""
    data = {}
    repos = conn.execute("SELECT id, name FROM REPOSITORIES ORDER BY id").fetchall()
    for repo_id, repo_name in repos:
        # Project type counts
        type_counts = {}
        for row in conn.execute("""
            SELECT type, COUNT(*) FROM PROJECTS
            WHERE repository_id=? GROUP BY type
        """, (repo_id,)):
            type_counts[row[0] or "UNKNOWN"] = row[1]

        # Primary class distribution
        class_counts = {}
        for row in conn.execute("""
            SELECT primary_class, COUNT(*) as cnt FROM PROJECTS
            WHERE repository_id=? AND primary_class IS NOT NULL
            GROUP BY primary_class ORDER BY cnt DESC
        """, (repo_id,)):
            class_counts[row[0]] = row[1]

        # Total projects
        total = conn.execute("SELECT COUNT(*) FROM PROJECTS WHERE repository_id=?", (repo_id,)).fetchone()[0]

        data[repo_name] = {
            "id": repo_id,
            "total": total,
            "type_counts": type_counts,
            "class_counts": class_counts,
        }
    return data

def make_histogram(class_counts, repo_name, top_n=20):
    """Create a horizontal bar chart as SVG-quality vector image."""
    items = sorted(class_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
    if not items:
        return None

    labels = [item[0].split(": ", 1)[1] if ": " in item[0] else item[0] for item in items]
    values = [item[1] for item in items]

    # Truncate long labels
    labels = [l[:45] + "..." if len(l) > 45 else l for l in labels]

    fig, ax = plt.subplots(figsize=(12, max(6, len(labels) * 0.45)))
    bars = ax.barh(range(len(labels)), values,
                   color='#2E5B8A', edgecolor='white', linewidth=0.5)

    # Add count labels on bars
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + max(values) * 0.01, bar.get_y() + bar.get_height()/2,
                str(val), va='center', ha='left', fontsize=9, fontweight='bold')

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Number of Projects", fontsize=10)
    ax.set_title(f"Primary ISIC Classes — {repo_name.title()} Repository",
                 fontsize=12, fontweight='bold', pad=10)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_xlim(0, max(values) * 1.15)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight', dpi=150)
    plt.close()
    buf.seek(0)
    return buf

def make_project_type_chart(type_counts, repo_name):
    """Create pie chart for project types."""
    labels = list(type_counts.keys())
    values = list(type_counts.values())
    colors_list = ['#2E5B8A', '#4CAF50', '#FF9800', '#9E9E9E']

    fig, ax = plt.subplots(figsize=(7, 5))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct='%1.1f%%',
        colors=colors_list[:len(labels)],
        startangle=90, pctdistance=0.8
    )
    for text in texts:
        text.set_fontsize(9)
    for autotext in autotexts:
        autotext.set_fontsize(8)
        autotext.set_fontweight('bold')
    ax.set_title(f"Project Type Distribution — {repo_name.title()}", fontsize=11, fontweight='bold')
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight', dpi=150)
    plt.close()
    buf.seek(0)
    return buf

def build_report(data, output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'],
        fontSize=20, spaceAfter=8, textColor=colors.HexColor('#1A3A5C'))
    h1_style = ParagraphStyle('H1', parent=styles['Heading1'],
        fontSize=16, spaceAfter=6, spaceBefore=12,
        textColor=colors.HexColor('#2E5B8A'))
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'],
        fontSize=13, spaceAfter=4, spaceBefore=8,
        textColor=colors.HexColor('#2E5B8A'))
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
        fontSize=10, spaceAfter=6, leading=14, alignment=TA_JUSTIFY)
    caption_style = ParagraphStyle('Caption', parent=styles['Normal'],
        fontSize=8, spaceAfter=4, textColor=colors.grey, alignment=TA_CENTER)

    story = []

    # Cover page
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph("QDArchive — Part 2: Data Classification Report", title_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#2E5B8A')))
    story.append(Spacer(1, 0.5*cm))

    meta = [
        ["Student", "Nabila Kader"],
        ["Student ID", "23079506"],
        ["Course", "Seeding QDArchive (SQ26)"],
        ["University", "FAU Erlangen-Nürnberg"],
        ["Professor", "Dirk Riehle"],
        ["Classification Standard", "ISIC Rev. 5 (two levels: sections and divisions)"],
    ]
    t = Table(meta, colWidths=[4*cm, 12*cm])
    t.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 1*cm))

    # Summary
    story.append(Paragraph("Executive Summary", h1_style))
    total_all = sum(d["total"] for d in data.values())
    story.append(Paragraph(
        f"This report presents the classification results of <b>{total_all:,} research projects</b> "
        f"collected from two assigned repositories: DataFirst UCT (repository #8) and "
        f"Harvard Murray Archive / Harvard Dataverse (repository #18). "
        f"Each project was classified using the <b>ISIC Rev. 5</b> international standard "
        f"for economic activities, going down to the division level (two-digit codes). "
        f"Classification was performed using keyword-based analysis of project titles, "
        f"descriptions, and metadata.", body_style))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Classification Methodology", h2_style))
    story.append(Paragraph(
        "Projects were first classified by type based on their downloaded file extensions: "
        "<b>QDA_PROJECT</b> if a QDA file (e.g. .qdpx, .nvp) was present; "
        "<b>QD_PROJECT</b> if primary data files (PDF, DOCX, TXT, etc.) were found; "
        "<b>OTHER_PROJECT</b> for other file types; "
        "<b>NOT_A_PROJECT</b> if no usable files were found. "
        "ISIC classification was then assigned based on keyword matching against project titles "
        "and descriptions, mapping research subjects to the most appropriate economic sector.",
        body_style))

    story.append(PageBreak())

    # Per-repository sections
    repo_display = {"datafirst": "DataFirst UCT", "harvard": "Harvard Murray Archive / Dataverse"}

    for repo_name, repo_data in data.items():
        display_name = repo_display.get(repo_name, repo_name.title())
        story.append(Paragraph(f"Repository: {display_name}", h1_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#AAAAAA')))
        story.append(Spacer(1, 0.3*cm))

        story.append(Paragraph(
            f"Total projects: <b>{repo_data['total']:,}</b>", body_style))

        # Project type table
        story.append(Paragraph("Project Type Distribution", h2_style))
        type_data = [["Project Type", "Count", "Percentage"]]
        total = repo_data["total"]
        for ptype, cnt in sorted(repo_data["type_counts"].items()):
            pct = f"{cnt/total*100:.1f}%"
            type_data.append([ptype or "UNKNOWN", str(cnt), pct])

        t = Table(type_data, colWidths=[7*cm, 3*cm, 3*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2E5B8A')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#EEF2F7')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC')),
            ('ALIGN', (1,0), (-1,-1), 'CENTER'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))

        # Project type pie chart
        pie_buf = make_project_type_chart(repo_data["type_counts"], display_name)
        if pie_buf:
            img = Image(pie_buf, width=12*cm, height=8*cm)
            story.append(img)
            story.append(Paragraph(
                f"Figure: Project type distribution for {display_name}", caption_style))
        story.append(Spacer(1, 0.5*cm))

        # ISIC Histogram
        story.append(Paragraph("Primary ISIC Class Distribution (Top 20)", h2_style))
        hist_buf = make_histogram(repo_data["class_counts"], display_name)
        if hist_buf:
            n_classes = min(len(repo_data["class_counts"]), 20)
            img_height = max(8*cm, n_classes * 0.6*cm)
            img = Image(hist_buf, width=16*cm, height=img_height)
            story.append(img)
            story.append(Paragraph(
                f"Figure: Top {n_classes} primary ISIC divisions identified in {display_name}",
                caption_style))
        story.append(Spacer(1, 0.5*cm))

        # Top 20 class table
        story.append(Paragraph("Rank-Ordered List of Classes (Top 20)", h2_style))
        table_data = [["Rank", "ISIC Code", "Division Name", "Count"]]
        items = sorted(repo_data["class_counts"].items(), key=lambda x: x[1], reverse=True)[:20]
        for rank, (cls, cnt) in enumerate(items, 1):
            parts = cls.split(": ", 1)
            code = parts[0] if len(parts) > 1 else "-"
            name = parts[1] if len(parts) > 1 else cls
            table_data.append([str(rank), code, name[:50], str(cnt)])

        t = Table(table_data, colWidths=[1.5*cm, 2.5*cm, 10*cm, 2*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2E5B8A')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#EEF2F7')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC')),
            ('ALIGN', (0,0), (1,-1), 'CENTER'),
            ('ALIGN', (3,0), (3,-1), 'CENTER'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))

        # Comments
        story.append(Paragraph("Comments on Findings", h2_style))

        if repo_name == "datafirst":
            dominant = items[0][0].split(": ", 1)[1] if items else "N/A"
            story.append(Paragraph(
                f"The DataFirst UCT repository is a South African survey/statistics archive. "
                f"The dominant class is <b>{dominant}</b>, reflecting the repository's strong "
                f"focus on HIV/AIDS surveillance, demographic health surveys, and mortality studies "
                f"primarily from sub-Saharan Africa. "
                f"The second most common class is Scientific Research, covering OER studies and "
                f"academic research projects. Financial services rank third due to the many "
                f"household income and expenditure surveys. "
                f"All 596 projects in this repository were classified as QD_PROJECT (no QDA files "
                f"found), which is expected as DataFirst is a quantitative/statistical data repository "
                f"rather than a qualitative data analysis repository.",
                body_style))
        else:
            dominant = items[0][0].split(": ", 1)[1] if items else "N/A"
            story.append(Paragraph(
                f"The Harvard Murray Archive / Harvard Dataverse collection contains longitudinal "
                f"social science studies. The dominant class is <b>{dominant}</b>, consistent with "
                f"the Murray Archive's focus on long-term human development and psychology research. "
                f"Notably, 3 projects were classified as QDA_PROJECT, indicating the presence of "
                f"actual qualitative data analysis files in the Harvard collection. "
                f"The diversity of ISIC classes in this repository reflects the broad scope of "
                f"Harvard's social science research, spanning education, health, employment, "
                f"and community studies.",
                body_style))

        story.append(PageBreak())

    # Overall summary
    story.append(Paragraph("Overall Summary", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#AAAAAA')))
    story.append(Spacer(1, 0.3*cm))

    all_classes = {}
    for repo_data in data.values():
        for cls, cnt in repo_data["class_counts"].items():
            all_classes[cls] = all_classes.get(cls, 0) + cnt

    story.append(Paragraph("Combined Top 15 Classes (Both Repositories)", h2_style))
    combined_data = [["Rank", "ISIC Code", "Division Name", "Count", "% of Total"]]
    items = sorted(all_classes.items(), key=lambda x: x[1], reverse=True)[:15]
    for rank, (cls, cnt) in enumerate(items, 1):
        parts = cls.split(": ", 1)
        code = parts[0] if len(parts) > 1 else "-"
        name = parts[1] if len(parts) > 1 else cls
        pct = f"{cnt/total_all*100:.1f}%"
        combined_data.append([str(rank), code, name[:45], str(cnt), pct])

    t = Table(combined_data, colWidths=[1.5*cm, 2.5*cm, 9*cm, 2*cm, 2*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2E5B8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#EEF2F7')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC')),
        ('ALIGN', (0,0), (1,-1), 'CENTER'),
        ('ALIGN', (3,0), (-1,-1), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Overall Observations", h2_style))
    story.append(Paragraph(
        "Across both repositories, <b>Human Health Activities (ISIC 86)</b> is the dominant "
        "class with 430 projects (28%), reflecting the African health research focus of DataFirst "
        "and the longitudinal health studies in the Harvard collection. "
        "<b>Scientific Research and Development (ISIC 72)</b> is second with 287 projects (19%), "
        "capturing academic and social science research projects. "
        "The two repositories are complementary: DataFirst is primarily a quantitative African "
        "survey archive (all QD_PROJECT), while Harvard Dataverse contains more diverse longitudinal "
        "social science data including the only QDA_PROJECT entries found in this dataset. "
        "No QDA files (e.g. .qdpx, .nvp) were found in DataFirst, confirming it is not a "
        "qualitative data analysis repository. The 3 QDA files found in Harvard Dataverse "
        "represent a small but significant finding for the QDArchive project.",
        body_style))

    doc.build(story)
    print(f"Report saved: {output_path}")

if __name__ == "__main__":
    import os
    os.chdir("/Users/Nabila/AI Projects/Seeding-QDArchive-")
    conn = sqlite3.connect(DB_PATH)
    data = get_data(conn)
    conn.close()
    build_report(data, "23079506-classification-report.pdf")
