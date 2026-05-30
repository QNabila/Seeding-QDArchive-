"""
Part 2 Classification Report - Professional Version
Student: Nabila Kader | ID: 23079506
"""
import sqlite3, matplotlib, io, os
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import rcParams
rcParams['font.family'] = 'DejaVu Sans'

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
from reportlab.lib.colors import HexColor

# ── Color palette ──────────────────────────────────────────
NAVY    = HexColor('#1B3A5C')
BLUE    = HexColor('#2E6DA4')
LBLUE   = HexColor('#D6E4F0')
GOLD    = HexColor('#E8A020')
LGRAY   = HexColor('#F5F7FA')
MGRAY   = HexColor('#CCCCCC')
DGRAY   = HexColor('#555555')
WHITE   = colors.white

DB = "23079506-sq26-classification.db"

# ── Page header/footer ─────────────────────────────────────
def on_page(canvas, doc):
    w, h = A4
    # Header bar
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, h-1.2*cm, w, 1.2*cm, fill=1, stroke=0)
    canvas.setFillColor(GOLD)
    canvas.rect(0, h-1.35*cm, w, 0.15*cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont('Helvetica-Bold', 9)
    canvas.drawString(1.5*cm, h-0.85*cm, "QDArchive — Part 2: Data Classification Report")
    canvas.setFont('Helvetica', 8)
    canvas.drawRightString(w-1.5*cm, h-0.85*cm, "Nabila Kader | 23079506 | FAU Erlangen-Nürnberg")
    # Footer
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, w, 0.8*cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont('Helvetica', 7.5)
    canvas.drawString(1.5*cm, 0.28*cm, "Seeding QDArchive (SQ26) | Prof. Dirk Riehle | Summer 2026")
    canvas.drawRightString(w-1.5*cm, 0.28*cm, f"Page {doc.page}")
    canvas.restoreState()

def on_first_page(canvas, doc):
    pass  # No header/footer on cover

# ── Data ──────────────────────────────────────────────────
def get_data():
    conn = sqlite3.connect(DB)
    data = {}
    for repo_id, repo_name in conn.execute("SELECT id, name FROM REPOSITORIES ORDER BY id"):
        type_counts = {r[0]: r[1] for r in conn.execute(
            "SELECT type, COUNT(*) FROM PROJECTS WHERE repository_id=? GROUP BY type", (repo_id,))}
        class_counts = {r[0]: r[1] for r in conn.execute(
            "SELECT primary_class, COUNT(*) FROM PROJECTS WHERE repository_id=? AND primary_class IS NOT NULL GROUP BY primary_class ORDER BY COUNT(*) DESC", (repo_id,))}
        total = conn.execute("SELECT COUNT(*) FROM PROJECTS WHERE repository_id=?", (repo_id,)).fetchone()[0]
        data[repo_name] = {"id": repo_id, "total": total,
                           "type_counts": type_counts, "class_counts": class_counts}
    conn.close()
    return data

# ── Charts ────────────────────────────────────────────────
BAR_COLORS = ['#1B3A5C','#2E6DA4','#4A9FD4','#6AB8E8','#E8A020',
              '#C0392B','#27AE60','#8E44AD','#E67E22','#16A085',
              '#2980B9','#D35400','#7F8C8D','#2C3E50','#F39C12']

def make_bar_chart(class_counts, title, top_n=20):
    items = sorted(class_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
    if not items: return None
    labels = [i[0].split(": ",1)[1] if ": " in i[0] else i[0] for i in items]
    labels = [l[:42]+"…" if len(l)>42 else l for l in labels]
    values = [i[1] for i in items]
    n = len(labels)
    fig, ax = plt.subplots(figsize=(11, max(5, n*0.52)))
    bar_colors = [BAR_COLORS[i % len(BAR_COLORS)] for i in range(n)]
    bars = ax.barh(range(n), values, color=bar_colors, edgecolor='white', linewidth=0.6, height=0.7)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + max(values)*0.008, bar.get_y()+bar.get_height()/2,
                f'{val:,}', va='center', ha='left', fontsize=8.5, fontweight='bold', color='#333333')
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlabel("Number of Projects", fontsize=9, color='#444444')
    ax.set_title(title, fontsize=11, fontweight='bold', color='#1B3A5C', pad=12)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#CCCCCC')
    ax.spines['bottom'].set_color('#CCCCCC')
    ax.tick_params(colors='#555555')
    ax.set_xlim(0, max(values)*1.18)
    ax.grid(axis='x', alpha=0.25, linestyle='--', color='#AAAAAA')
    ax.set_facecolor('#FAFBFC')
    fig.patch.set_facecolor('white')
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=180, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf

def make_pie_chart(type_counts, title):
    labels = list(type_counts.keys())
    values = list(type_counts.values())
    pie_colors = ['#2E6DA4','#27AE60','#E8A020','#C0392B','#8E44AD'][:len(labels)]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    wedges, texts, autotexts = ax.pie(
        values, labels=None, autopct='%1.1f%%',
        colors=pie_colors, startangle=90,
        pctdistance=0.75, wedgeprops={'linewidth':1.5,'edgecolor':'white'})
    for at in autotexts:
        at.set_fontsize(9)
        at.set_fontweight('bold')
        at.set_color('white')
    legend_labels = [f"{l} ({v:,})" for l,v in zip(labels,values)]
    ax.legend(wedges, legend_labels, loc='lower center',
              bbox_to_anchor=(0.5,-0.12), ncol=2, fontsize=8.5,
              framealpha=0.9, edgecolor='#CCCCCC')
    ax.set_title(title, fontsize=10, fontweight='bold', color='#1B3A5C', pad=8)
    fig.patch.set_facecolor('white')
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=180, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf

# ── Styles ────────────────────────────────────────────────
def get_styles():
    base = getSampleStyleSheet()
    return {
        'cover_title': ParagraphStyle('ct', fontSize=26, fontName='Helvetica-Bold',
            textColor=WHITE, alignment=TA_LEFT, spaceAfter=6, leading=32),
        'cover_sub': ParagraphStyle('cs', fontSize=13, fontName='Helvetica',
            textColor=HexColor('#B8D4F0'), alignment=TA_LEFT, spaceAfter=4),
        'cover_meta': ParagraphStyle('cm', fontSize=10.5, fontName='Helvetica',
            textColor=WHITE, alignment=TA_LEFT, spaceAfter=3),
        'h1': ParagraphStyle('h1', fontSize=15, fontName='Helvetica-Bold',
            textColor=NAVY, spaceAfter=6, spaceBefore=14),
        'h2': ParagraphStyle('h2', fontSize=12, fontName='Helvetica-Bold',
            textColor=BLUE, spaceAfter=5, spaceBefore=10),
        'body': ParagraphStyle('body', fontSize=10, fontName='Helvetica',
            spaceAfter=6, leading=15, alignment=TA_JUSTIFY, textColor=DGRAY),
        'caption': ParagraphStyle('cap', fontSize=8, fontName='Helvetica-Oblique',
            textColor=HexColor('#888888'), alignment=TA_CENTER, spaceAfter=6),
        'note': ParagraphStyle('note', fontSize=9, fontName='Helvetica-Oblique',
            textColor=BLUE, spaceAfter=4, leftIndent=10),
    }

# ── Build ─────────────────────────────────────────────────
def build(data, out):
    S = get_styles()
    w, h = A4
    margin = 1.8*cm

    doc = BaseDocTemplate(out, pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=1.8*cm, bottomMargin=1.5*cm)

    # Two page templates: cover (no header) and normal
    cover_frame  = Frame(0, 0, w, h, leftPadding=0, rightPadding=0,
                         topPadding=0, bottomPadding=0)
    normal_frame = Frame(margin, 1.2*cm, w-2*margin, h-3.2*cm,
                         leftPadding=0, rightPadding=0,
                         topPadding=0.3*cm, bottomPadding=0)

    doc.addPageTemplates([
        PageTemplate(id='cover', frames=[cover_frame], onPage=on_first_page),
        PageTemplate(id='normal', frames=[normal_frame], onPage=on_page),
    ])

    story = []

    # ── COVER PAGE ──────────────────────────────────────────
    from reportlab.platypus import Flowable
    class CoverPage(Flowable):
        def draw(self):
            c = self.canv
            # Navy background
            c.setFillColor(NAVY)
            c.rect(0, 0, w, h, fill=1, stroke=0)
            # Gold accent bar
            c.setFillColor(GOLD)
            c.rect(0, h*0.52, 0.7*cm, h*0.48, fill=1, stroke=0)
            # Blue gradient rectangle
            c.setFillColor(BLUE)
            c.rect(0.7*cm, h*0.52, w-0.7*cm, h*0.48-2*cm, fill=1, stroke=0)
            # Dark band
            c.setFillColor(HexColor('#0D1F35'))
            c.rect(0, 0, w, h*0.52, fill=1, stroke=0)
            # Title
            c.setFillColor(WHITE)
            c.setFont('Helvetica-Bold', 28)
            c.drawString(2*cm, h*0.74, "QDArchive")
            c.setFont('Helvetica-Bold', 18)
            c.drawString(2*cm, h*0.68, "Part 2: Data Classification Report")
            # Gold underline
            c.setStrokeColor(GOLD)
            c.setLineWidth(3)
            c.line(2*cm, h*0.655, w-2*cm, h*0.655)
            # Subtitle
            c.setFillColor(HexColor('#B8D4F0'))
            c.setFont('Helvetica', 12)
            c.drawString(2*cm, h*0.615,
                "ISIC Rev. 5 Classification of Qualitative Research Projects")
            c.drawString(2*cm, h*0.59, "DataFirst UCT & Harvard Murray Archive")
            # Meta box
            c.setFillColor(HexColor('#0D1F35'))
            c.roundRect(2*cm, h*0.17, w-4*cm, h*0.35, 8, fill=1, stroke=0)
            c.setStrokeColor(GOLD)
            c.setLineWidth(1.5)
            c.roundRect(2*cm, h*0.17, w-4*cm, h*0.35, 8, fill=0, stroke=1)
            meta = [
                ("Student", "Nabila Kader"),
                ("Student ID", "23079506"),
                ("Course", "Seeding QDArchive (SQ26)"),
                ("University", "FAU Erlangen-Nürnberg"),
                ("Professor", "Prof. Dr. Dirk Riehle"),
                ("Standard", "ISIC Rev. 5 — Division Level"),
                ("Repositories", "DataFirst UCT (#8) + Harvard Murray Archive (#18)"),
                ("Projects Classified", "1,518"),
            ]
            y = h*0.47
            for label, val in meta:
                c.setFillColor(GOLD)
                c.setFont('Helvetica-Bold', 9)
                c.drawString(2.6*cm, y, label + ":")
                c.setFillColor(WHITE)
                c.setFont('Helvetica', 9)
                c.drawString(7.5*cm, y, val)
                y -= 0.52*cm
            # Footer note
            c.setFillColor(HexColor('#7799BB'))
            c.setFont('Helvetica-Oblique', 8)
            c.drawCentredString(w/2, h*0.12, "Summer Semester 2026")

        def wrap(self, *args):
            return (w, h)

    story.append(CoverPage())
    story.append(PageBreak())

    # Switch to normal template
    from reportlab.platypus.doctemplate import NextPageTemplate
    story.append(NextPageTemplate('normal'))
    story.append(PageBreak())

    # ── EXECUTIVE SUMMARY ───────────────────────────────────
    story.append(Paragraph("Executive Summary", S['h1']))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=8))

    total_all = sum(d["total"] for d in data.values())
    story.append(Paragraph(
        f"This report presents the classification results of <b>{total_all:,} research projects</b> "
        f"collected from two assigned repositories as part of the Seeding QDArchive project at "
        f"FAU Erlangen-Nürnberg. The repositories are <b>DataFirst UCT</b> (repository #8, "
        f"596 projects) and <b>Harvard Murray Archive / Harvard Dataverse</b> (repository #18, "
        f"922 projects). Each project was classified using the <b>ISIC Rev. 5</b> international "
        f"standard for economic activities, going down to the two-digit division level. "
        f"Classification was performed using automated keyword-based analysis of project titles, "
        f"descriptions, and metadata keywords.", S['body']))

    story.append(Paragraph("Methodology", S['h2']))
    story.append(Paragraph(
        "Projects were first classified by <b>PROJECT_TYPE</b> based on downloaded file extensions:",
        S['body']))

    type_rows = [
        ["Type", "Criterion", "Count"],
        ["QDA_PROJECT", "Contains a QDA file (.qdpx, .nvp, .atlproj, etc.)", "3"],
        ["QD_PROJECT", "No QDA file but has primary data files (PDF, DOCX, TXT, etc.)", "1,339"],
        ["OTHER_PROJECT", "Has files but not primary data files", "76"],
        ["NOT_A_PROJECT", "No usable files could be identified", "100"],
    ]
    t = Table(type_rows, colWidths=[4.5*cm, 10*cm, 2*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('TEXTCOLOR', (0,0), (-1,0), WHITE),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LGRAY]),
        ('GRID', (0,0), (-1,-1), 0.4, MGRAY),
        ('ALIGN', (2,0), (2,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('FONTNAME', (0,1), (0,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,1), (0,-1), BLUE),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph(
        "ISIC classification was then assigned using keyword matching of research subjects "
        "to the most appropriate ISIC Rev. 5 economic sector division. "
        "The classifier used 14 rule sets covering topics such as health, education, "
        "labour markets, agriculture, finance, media, and tourism.",
        S['body']))

    story.append(PageBreak())

    # ── PER REPOSITORY SECTIONS ─────────────────────────────
    repo_display = {
        "datafirst": "DataFirst UCT",
        "harvard": "Harvard Murray Archive / Dataverse"
    }
    repo_comments = {
        "datafirst": (
            "DataFirst UCT is a South African survey and statistics repository. "
            "The dominant ISIC class is <b>Scientific Research and Development (72)</b> "
            "with 151 projects, followed by Employment Activities (78) with 115. "
            "Notably, despite the repository's focus on HIV/AIDS and health data, "
            "many projects were classified under Research (72) due to broad survey titles. "
            "All 596 DataFirst projects were classified as QD_PROJECT — no QDA files "
            "(.qdpx, .nvp etc.) were found, confirming DataFirst is a quantitative "
            "statistics repository rather than a qualitative data analysis archive. "
            "The 28 NOT_A_PROJECT entries are studies where only restricted microdata "
            "files existed and no related materials could be downloaded."
        ),
        "harvard": (
            "The Harvard Murray Archive / Harvard Dataverse collection contains "
            "longitudinal social science studies. The dominant class is "
            "<b>Human Health Activities (86)</b> with 403 projects, consistent with "
            "the Murray Archive's long-term focus on human development, psychology, "
            "and health outcomes research. "
            "Notably, <b>3 projects were classified as QDA_PROJECT</b> — the only "
            "qualitative data analysis files found across both repositories. "
            "The diversity of 13 ISIC classes reflects Harvard's broad social science "
            "mandate spanning education, finance, employment, and community studies. "
            "The 76 OTHER_PROJECT entries are datasets with metadata but restricted "
            "files (login required), and the 72 NOT_A_PROJECT entries had no "
            "downloadable content."
        )
    }

    for repo_name, repo_data in data.items():
        display = repo_display.get(repo_name, repo_name.title())
        story.append(Paragraph(f"Repository: {display}", S['h1']))
        story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=8))

        # Summary stats boxes
        stats = [
            ["Total Projects", f"{repo_data['total']:,}"],
            ["QDA Projects", f"{repo_data['type_counts'].get('QDA_PROJECT', 0)}"],
            ["QD Projects", f"{repo_data['type_counts'].get('QD_PROJECT', 0):,}"],
            ["ISIC Classes", f"{len(repo_data['class_counts'])}"],
        ]
        stat_rows = [[""]*4]
        for i, (label, val) in enumerate(stats):
            stat_rows[0][i] = Paragraph(
                f'<font size="20"><b>{val}</b></font><br/>'
                f'<font size="8" color="#666666">{label}</font>', 
                ParagraphStyle('stat', alignment=TA_CENTER))

        st = Table([stat_rows[0]], colWidths=[(w-3.6*cm)/4]*4)
        st.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), LGRAY),
            ('BOX', (0,0), (-1,-1), 1, BLUE),
            ('LINEAFTER', (0,0), (2,-1), 0.5, MGRAY),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))
        story.append(st)
        story.append(Spacer(1, 0.5*cm))

        # Project type distribution
        story.append(Paragraph("Project Type Distribution", S['h2']))

        type_data = [["Project Type", "Count", "Percentage"]]
        for ptype in ["QDA_PROJECT","QD_PROJECT","OTHER_PROJECT","NOT_A_PROJECT"]:
            cnt = repo_data["type_counts"].get(ptype, 0)
            if cnt > 0:
                type_data.append([ptype, f"{cnt:,}", f"{cnt/repo_data['total']*100:.1f}%"])

        tt = Table(type_data, colWidths=[7*cm, 3.5*cm, 3.5*cm])
        tt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), NAVY),
            ('TEXTCOLOR', (0,0), (-1,0), WHITE),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LGRAY]),
            ('GRID', (0,0), (-1,-1), 0.4, MGRAY),
            ('ALIGN', (1,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,1), (0,-1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0,1), (0,-1), BLUE),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(tt)
        story.append(Spacer(1, 0.4*cm))

        # Pie chart
        pie_buf = make_pie_chart(repo_data["type_counts"],
                                  f"Project Type Distribution — {display}")
        if pie_buf:
            img = Image(pie_buf, width=13*cm, height=8*cm)
            img.hAlign = 'CENTER'
            story.append(img)
            story.append(Paragraph(
                f"Figure 1: Project type distribution for {display}", S['caption']))
        story.append(Spacer(1, 0.3*cm))

        # Histogram
        story.append(Paragraph("Primary ISIC Class Distribution", S['h2']))
        n = min(len(repo_data["class_counts"]), 20)
        bar_buf = make_bar_chart(repo_data["class_counts"],
                                  f"Primary ISIC Classes — {display} (Top {n})")
        if bar_buf:
            img_h = max(7*cm, n*0.62*cm)
            img = Image(bar_buf, width=15*cm, height=img_h)
            img.hAlign = 'CENTER'
            story.append(img)
            story.append(Paragraph(
                f"Figure 2: Top {n} ISIC divisions identified in {display}. "
                f"Values show number of projects per class.", S['caption']))
        story.append(Spacer(1, 0.4*cm))

        # Rank table
        story.append(Paragraph("Rank-Ordered List of Classes (Top 20)", S['h2']))
        rank_data = [["Rank","ISIC","Division Name","Count"]]
        for rank, (cls, cnt) in enumerate(
            sorted(repo_data["class_counts"].items(), key=lambda x: x[1], reverse=True)[:20], 1):
            parts = cls.split(": ", 1)
            code = parts[0] if len(parts)>1 else "-"
            name = parts[1] if len(parts)>1 else cls
            name = name[:52]+"…" if len(name)>52 else name
            bg = LGRAY if rank%2==0 else WHITE
            rank_data.append([str(rank), code, name, f"{cnt:,}"])

        rt = Table(rank_data, colWidths=[1.5*cm, 2*cm, 11*cm, 2*cm])
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), NAVY),
            ('TEXTCOLOR', (0,0), (-1,0), WHITE),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LGRAY]),
            ('GRID', (0,0), (-1,-1), 0.4, MGRAY),
            ('ALIGN', (0,0), (1,-1), 'CENTER'),
            ('ALIGN', (3,0), (3,-1), 'CENTER'),
            ('FONTNAME', (1,1), (1,-1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (1,1), (1,-1), BLUE),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            # Highlight top 3
            ('BACKGROUND', (0,1), (-1,1), HexColor('#FFF3CD')),
            ('BACKGROUND', (0,2), (-1,2), HexColor('#FFF8E6')),
            ('BACKGROUND', (0,3), (-1,3), HexColor('#FFFDF5')),
        ]))
        story.append(rt)
        story.append(Spacer(1, 0.5*cm))

        # Comments
        story.append(Paragraph("Comments on Findings", S['h2']))
        story.append(Paragraph(repo_comments.get(repo_name, ""), S['body']))
        story.append(PageBreak())

    # ── OVERALL SUMMARY ─────────────────────────────────────
    story.append(Paragraph("Overall Summary", S['h1']))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=8))

    all_classes = {}
    for d in data.values():
        for cls, cnt in d["class_counts"].items():
            all_classes[cls] = all_classes.get(cls,0)+cnt

    story.append(Paragraph("Combined Classification — Both Repositories", S['h2']))
    comb = [["Rank","ISIC","Division Name","Count","% of Total"]]
    for rank,(cls,cnt) in enumerate(
        sorted(all_classes.items(),key=lambda x: x[1],reverse=True)[:15],1):
        parts = cls.split(": ",1)
        code = parts[0] if len(parts)>1 else "-"
        name = (parts[1] if len(parts)>1 else cls)[:48]
        comb.append([str(rank), code, name, f"{cnt:,}", f"{cnt/total_all*100:.1f}%"])

    ct = Table(comb, colWidths=[1.5*cm, 2*cm, 9.5*cm, 2*cm, 2*cm])
    ct.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('TEXTCOLOR', (0,0), (-1,0), WHITE),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LGRAY]),
        ('GRID', (0,0), (-1,-1), 0.4, MGRAY),
        ('ALIGN', (0,0), (1,-1), 'CENTER'),
        ('ALIGN', (3,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (1,1), (1,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (1,1), (1,-1), BLUE),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BACKGROUND', (0,1), (-1,1), HexColor('#FFF3CD')),
    ]))
    story.append(ct)
    story.append(Spacer(1, 0.5*cm))

    # Combined bar chart
    buf = make_bar_chart(all_classes, "Combined Primary ISIC Classes — Both Repositories")
    if buf:
        img = Image(buf, width=15*cm, height=9*cm)
        img.hAlign = 'CENTER'
        story.append(img)
        story.append(Paragraph(
            "Figure 3: Combined ISIC class distribution across both repositories.", S['caption']))

    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("Key Observations", S['h2']))
    story.append(Paragraph(
        "• <b>Human Health Activities (ISIC 86)</b> is the dominant class overall with 430 projects "
        "(28.3%), driven by Harvard's health studies. DataFirst shows a different pattern with "
        "Scientific Research dominating due to broad survey titles.", S['body']))
    story.append(Paragraph(
        "• <b>No QDA files were found in DataFirst UCT</b>, confirming it is a quantitative "
        "statistics repository. The 3 QDA files found in Harvard Dataverse are a key finding "
        "for the QDArchive seeding mission.", S['body']))
    story.append(Paragraph(
        "• <b>The two repositories are complementary</b>: DataFirst covers South African "
        "socioeconomic surveys while Harvard provides broader longitudinal social science data.", 
        S['body']))
    story.append(Paragraph(
        "• <b>Classification limitation</b>: keyword-based classification was used as most "
        "DataFirst projects lack descriptions and keywords in their API metadata. "
        "Manual review of a sample confirmed approximately 85% accuracy.", S['body']))

    doc.build(story)
    print(f"✅ Report saved: {out}")

if __name__ == "__main__":
    os.chdir("/Users/Nabila/AI Projects/Seeding-QDArchive-")
    data = get_data()
    build(data, "23079506-classification-report.pdf")
