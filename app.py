from flask import Flask, render_template, request, redirect, session, url_for, make_response
import json
import math
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import Color, white, black
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import io
import requests
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True
)

# Load quiz data
with open("data/quiz_structure.json", "r", encoding="utf-8") as f:
    quiz_data = json.load(f)

# Create mappings from your JSON structure
fc_map = {}
for question in quiz_data['forced_choice']:
    qid = question['block_id']  # FC1, FC2, etc.
    fc_map[qid] = {k: v["subtype"] for k, v in question["options"].items()}

sc_map = {}
for question in quiz_data['scenario_choice']:
    qid = question['block_id']  # SC1, SC2, etc.
    sc_map[qid] = {k: v["subtype"] for k, v in question["options"].items()}

likert_map = {}
for question in quiz_data['likert']:
    qid = question['item_id']  # L1, L2, etc.
    likert_map[qid] = question['subtype']

# Subtype names from your JSON
SUBTYPES = ["SECURE", "REMADE SECURE", "ETHICAL AVOIDANT", "MANIPULATIVE AVOIDANT", 
           "NURTURING ANXIOUS", "TOXIC ANXIOUS", "QUIET DISORGANIZED", "LOUD DISORGANIZED"]

# Maximum possible scores (calculated from your JSON structure)
def calculate_max_scores():
    max_scores = {}
    
    for subtype in SUBTYPES:
        fc_count = 0
        sc_count = 0
        likert_count = 0
        
        # Count FC appearances
        for qid, mapping in fc_map.items():
            for option, sub in mapping.items():
                if sub == subtype:
                    fc_count += 1
        
        # Count SC appearances  
        for qid, mapping in sc_map.items():
            for option, sub in mapping.items():
                if sub == subtype:
                    sc_count += 1
                    
        # Count Likert appearances
        for qid, sub in likert_map.items():
            if sub == subtype:
                likert_count += 1
        
        # Calculate max possible score
        max_scores[subtype] = (fc_count * 3) + (sc_count * 3) + (likert_count * 5)
    
    return max_scores

MAX_SCORES = calculate_max_scores()
print("Calculated max scores:", MAX_SCORES)  # For debugging

# Global variable to cache results
result_cache = None

@app.route('/')
def index():
    # Initialize session data
    if 'fc_responses' not in session:
        session['fc_responses'] = {}
    if 'sc_responses' not in session:
        session['sc_responses'] = {}
    if 'likert_responses' not in session:
        session['likert_responses'] = {}
    
    return redirect(url_for('fc_question', question_index=0))

# FORCED CHOICE SECTION - One question at a time
@app.route('/quiz/fc/<int:question_index>', methods=['GET', 'POST'])
def fc_question(question_index):
    fc_questions = quiz_data['forced_choice']
    
    if question_index >= len(fc_questions):
        return redirect(url_for('sc_question', question_index=0))
    
    if request.method == 'POST':
        # Save the current question's responses
        current_question = fc_questions[question_index]
        question_id = current_question['block_id']  # FC1, FC2, etc.
        
        fc_data = {}
        for label in current_question['options'].keys():
            field_name = f"{current_question['block_id']}_{label}"
            if field_name in request.form:
                fc_data[label] = int(request.form[field_name])
        
        # Store in session
        if 'fc_responses' not in session:
            session['fc_responses'] = {}
        session['fc_responses'][question_id] = fc_data
        session.modified = True
        
        # Go to next question
        return redirect(url_for('fc_question', question_index=question_index + 1))
    
    current_question = fc_questions[question_index]
    total_fc_questions = len(fc_questions)
    question_id = current_question['block_id']
    
    # Calculate progress percentage
    progress_percent = round(((question_index + 1) / total_fc_questions) * 100, 1)
    
    # Check if there's a saved response for this question
    saved_response = None
    if 'fc_responses' in session and question_id in session['fc_responses']:
        saved_response = session['fc_responses'][question_id]
    
    return render_template('fc_question.html', 
                         question=current_question,
                         question_index=question_index,
                         total_questions=total_fc_questions,
                         saved_response=saved_response,
                         section="Forced Choice",
                         progress_percent=progress_percent)

# SCENARIO CHOICE SECTION - One question at a time
@app.route('/quiz/sc/<int:question_index>', methods=['GET', 'POST'])
def sc_question(question_index):
    sc_questions = quiz_data['scenario_choice']
    
    if question_index >= len(sc_questions):
        return redirect(url_for('likert_question', question_index=0))
    
    if request.method == 'POST':
        # Save the current question's response
        current_question = sc_questions[question_index]
        question_id = current_question['block_id']  # SC1, SC2, etc.
        
        if 'sc_responses' not in session:
            session['sc_responses'] = {}
        session['sc_responses'][question_id] = request.form['answer']
        session.modified = True
        
        # Go to next question
        return redirect(url_for('sc_question', question_index=question_index + 1))
    
    current_question = sc_questions[question_index]
    total_sc_questions = len(sc_questions)
    question_id = current_question['block_id']
    
    # Calculate progress percentage
    progress_percent = round(((question_index + 1) / total_sc_questions) * 100, 1)
    
    # Check if there's a saved response for this question
    saved_response = None
    if 'sc_responses' in session and question_id in session['sc_responses']:
        saved_response = session['sc_responses'][question_id]
    
    return render_template('sc_question.html', 
                         question=current_question,
                         question_index=question_index,
                         total_questions=total_sc_questions,
                         saved_response=saved_response,
                         section="Scenario Choice",
                         progress_percent=progress_percent)

# LIKERT SECTION - One question at a time
@app.route('/quiz/likert/<int:question_index>', methods=['GET', 'POST'])
def likert_question(question_index):
    likert_questions = quiz_data['likert']
    
    if question_index >= len(likert_questions):
        return redirect(url_for('results'))
    
    if request.method == 'POST':
        # Save the current question's response
        current_question = likert_questions[question_index]
        question_id = current_question['item_id']  # L1, L2, etc.
        
        if 'likert_responses' not in session:
            session['likert_responses'] = {}
        session['likert_responses'][question_id] = int(request.form['rating'])
        session.modified = True
        
        # Go to next question
        return redirect(url_for('likert_question', question_index=question_index + 1))
    
    current_question = likert_questions[question_index]
    total_likert_questions = len(likert_questions)
    question_id = current_question['item_id']
    
    # Calculate progress percentage
    progress_percent = round(((question_index + 1) / total_likert_questions) * 100, 1)
    
    # Check if there's a saved response for this question
    saved_response = None
    if 'likert_responses' in session and question_id in session['likert_responses']:
        saved_response = session['likert_responses'][question_id]
    
    return render_template('likert_question.html', 
                         question=current_question,
                         question_index=question_index,
                         total_questions=total_likert_questions,
                         saved_response=saved_response,
                         section="Likert Scale",
                         progress_percent=progress_percent)

@app.route('/results')
def results():
    fc_raw = session.get('fc_responses', {})
    sc_raw = session.get('sc_responses', {})
    likert_raw = session.get('likert_responses', {})

    # Convert to proper format
    likert_responses = {k: int(v) for k, v in likert_raw.items()}

    # Score using your JSON structure
    final_totals, breakdown = score_responses(fc_raw, sc_raw, likert_responses)
    result = determine_alignment(final_totals, breakdown)

    global result_cache
    result_cache = result

    # Send results to WordPress
    user_name = session.get('user_name')
    user_email = session.get('user_email')
    send_to_wordpress(user_name, user_email, result)

    return render_template('results.html', result=result)

# Custom colors to match the web design
DARK_GREEN = Color(44/255, 85/255, 48/255, 1)  # #2c5530
LIGHT_GREEN = Color(76/255, 175/255, 80/255, 1)  # #4CAF50
ORANGE = Color(255/255, 107/255, 53/255, 1)  # #FF6B35
LIGHT_ORANGE = Color(247/255, 147/255, 30/255, 1)  # #F7931E
BLUE = Color(33/255, 150/255, 243/255, 1)  # #2196F3
GRAY = Color(102/255, 102/255, 102/255, 1)  # #666666
LIGHT_GRAY = Color(248/255, 249/255, 250/255, 1)  # #f8f9fa

def create_enhanced_pdf(result_data):
    """Create a visually stunning PDF that matches the web design."""
    
    # Create a BytesIO buffer
    buffer = io.BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=60,
        bottomMargin=60,
        title="Attachment Profile Results"
    )
    
    # Get styles and create custom ones
    styles = getSampleStyleSheet()
    
    # Custom styles matching the web design
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=DARK_GREEN,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=20,
        textColor=GRAY,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )
    
    header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=18,
        spaceAfter=15,
        textColor=DARK_GREEN,
        fontName='Helvetica-Bold',
        leftIndent=0
    )
    
    dominant_style = ParagraphStyle(
        'DominantType',
        parent=styles['Normal'],
        fontSize=20,
        spaceAfter=20,
        textColor=ORANGE,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=12,
        textColor=black,
        fontName='Helvetica'
    )
    
    # Build the story (content)
    story = []
    
    # Title section with emoji
    story.append(Paragraph("🎯 Your Attachment Profile Results", title_style))
    story.append(Paragraph("Discover the key to building unforgettable relationships", subtitle_style))
    story.append(Spacer(1, 30))
    
    # Dominant type section with colored background effect
    story.append(Paragraph(f"<b>{result_data['dominant']}</b>", dominant_style))
    story.append(Paragraph(f"<b>Primary Score: {result_data['totals'][result_data['dominant']]}</b>", 
                          ParagraphStyle('ScoreStyle', parent=normal_style, alignment=TA_CENTER, fontSize=16, textColor=LIGHT_GREEN)))
    story.append(Spacer(1, 30))
    
    # Key Statistics Section
    story.append(Paragraph("📊 Key Statistics", header_style))
    
    # Create a beautiful stats table
    stats_data = [
        ['Metric', 'Value', 'Details'],
        ['Primary Type', result_data['dominant'], 'Your strongest attachment pattern'],
        ['Primary Score', str(result_data['totals'][result_data['dominant']]), 'Points earned for dominant type'],
        ['Runner-Up', result_data['runner_up'], 'Second strongest pattern'],
        ['Runner-Up Score', str(result_data['totals'][result_data['runner_up']]), 'Points for second place'],
        ['Score Gap', f"{result_data['gap']} points", 'Lead over runner-up'],
        ['Alignment Strength', result_data['strength'], get_strength_description(result_data['strength'])]
    ]
    
    stats_table = Table(stats_data, colWidths=[2*inch, 1.5*inch, 2.5*inch])
    stats_table.setStyle(TableStyle([
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT_GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        
        # Data rows styling
        ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
        ('TEXTCOLOR', (0, 1), (-1, -1), black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        
        # Smaller font for Runner-Up row (row 4, index 3)
        ('FONTSIZE', (0, 4), (-1, 4), 8),
        ('FONTSIZE', (0, 5), (-1, 5), 8),  # Runner-Up Score row
        
        # Borders and spacing
        ('GRID', (0, 0), (-1, -1), 1, Color(0.8, 0.8, 0.8)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, Color(0.98, 0.98, 0.98)]),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    story.append(stats_table)
    story.append(Spacer(1, 30))
    
    # Alignment Strength with colored indicator
    story.append(Paragraph("🎯 Alignment Strength Analysis", header_style))
    
    strength_color = get_strength_color(result_data['strength'])
    strength_text = f"<b><font color='{strength_color}'>{result_data['strength'].upper()} ALIGNMENT</font></b>"
    
    story.append(Paragraph(strength_text, ParagraphStyle('StrengthStyle', parent=normal_style, alignment=TA_CENTER, fontSize=16)))
    story.append(Paragraph(get_strength_explanation(result_data['strength']), normal_style))
    story.append(Spacer(1, 25))
    
    # Complete Score Breakdown
    story.append(Paragraph("📈 Complete Score Breakdown", header_style))
    
    # Sort scores for better presentation
    sorted_scores = sorted(result_data['totals'].items(), key=lambda x: x[1], reverse=True)
    
    # Create breakdown table with visual scoring
    breakdown_data = [['Attachment Subtype', 'Score', 'Visual Bar', 'Percentage']]
    
    max_score = max(result_data['totals'].values())
    
    for subtype, score in sorted_scores:
        percentage = f"{(score/max_score)*100:.1f}%" if max_score > 0 else "0%"
        
        # FIXED: Create a visual bar that properly reflects the percentage
        # Use 15 characters total for a more compact bar
        bar_length = int((score/max_score) * 15) if max_score > 0 else 0
        # Using alternatives that render better in PDF
        visual_bar = "█" * bar_length + " " * (15 - bar_length)
        
        breakdown_data.append([subtype, str(score), visual_bar, percentage])
    
    breakdown_table = Table(breakdown_data, colWidths=[2.2*inch, 0.8*inch, 1.8*inch, 1.2*inch])
    breakdown_table.setStyle(TableStyle([
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), ORANGE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        
        # Data styling
        ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
        ('TEXTCOLOR', (0, 1), (-1, -1), black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        
        # Special formatting for top score
        ('BACKGROUND', (0, 1), (-1, 1), Color(0.9, 1, 0.9)),  # Light green for winner
        ('TEXTCOLOR', (0, 1), (-1, 1), DARK_GREEN),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        
        # Borders and alignment
        ('GRID', (0, 0), (-1, -1), 1, Color(0.7, 0.7, 0.7)),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),  # Score column
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),  # Visual bar column
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),  # Percentage column
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (2, 1), (2, -1), 'Courier'),  # Monospace for bars
        
        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    story.append(breakdown_table)
    story.append(Spacer(1, 25))
    
    # Understanding Your Results Section
    story.append(Paragraph("🧠 Understanding Your Results", header_style))
    
    understanding_text = f"""
    <b>Your Dominant Pattern:</b> {result_data['dominant']}<br/>
    This represents your primary attachment style based on your responses across all assessment sections.
    
    <br/><br/><b>Score Interpretation:</b><br/>
    • <b>Forced Choice:</b> {result_data['breakdown']['FC'][result_data['dominant']]} points from ranking preferences<br/>
    • <b>Scenario Choice:</b> {result_data['breakdown']['SC'][result_data['dominant']]} points from situational responses<br/>
    • <b>Likert Scale:</b> {result_data['breakdown']['Likert'][result_data['dominant']]} points from agreement ratings<br/>
    
    <br/><br/><b>What This Means:</b><br/>
    Your {result_data['strength'].lower()} alignment indicates {get_alignment_meaning(result_data['strength'])}
    """
    
    story.append(Paragraph(understanding_text, normal_style))
    story.append(Spacer(1, 20))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=10,
        textColor=GRAY,
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique'
    )
    
    story.append(Spacer(1, 30))
    story.append(Paragraph("Generated by Adam Lane Smith's Attachment Assessment System", footer_style))
    story.append(Paragraph("Understanding attachment patterns for better relationships", footer_style))
    
    # Build the PDF
    doc.build(story)
    
    # Get the PDF data
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data

def get_strength_description(strength):
    """Get description for strength level."""
    descriptions = {
        'High': 'Clear and confident results',
        'Medium': 'Good confidence in results',
        'Low': 'Mixed patterns detected'
    }
    return descriptions.get(strength, 'Results analyzed')

def get_strength_color(strength):
    """Get color code for strength level."""
    colors = {
        'High': '#4CAF50',
        'Medium': '#FF6B35', 
        'Low': '#f44336'
    }
    return colors.get(strength, '#666666')

def get_strength_explanation(strength):
    """Get detailed explanation for strength level."""
    explanations = {
        'High': 'Your responses show a strong and clear attachment pattern with high confidence in the results. This indicates a well-defined attachment style.',
        'Medium': 'Your responses show a moderate attachment pattern with good confidence in the results. There may be some secondary patterns present.',
        'Low': 'Your responses show mixed attachment patterns. Consider retaking the assessment or exploring multiple attachment styles that may apply to you.'
    }
    return explanations.get(strength, 'Your attachment pattern has been analyzed.')

def get_alignment_meaning(strength):
    """Get meaning text for alignment strength."""
    meanings = {
        'High': 'you have a clearly defined attachment pattern with consistent responses across all assessment areas.',
        'Medium': 'you have a generally consistent pattern with some variation in specific areas.',
        'Low': 'you may have multiple attachment patterns or be in a period of transition between styles.'
    }
    return meanings.get(strength, 'your responses have been carefully analyzed.')

@app.route('/download', methods=['POST'])
def download():
    global result_cache
    if not result_cache:
        return redirect(url_for('results'))
    
    pdf_data = create_enhanced_pdf(result_cache)
    
    response = make_response(pdf_data)
    response.headers.set('Content-Disposition', 'attachment', filename='attachment_profile_results.pdf')
    response.headers.set('Content-Type', 'application/pdf')
    return response

# SCORING FUNCTIONS COMPATIBLE WITH YOUR JSON
def score_responses(fc_responses, sc_responses, likert_responses):
    """Calculate final totals and subtotals for each subtype using your JSON structure."""
    # Initialize subtotals
    fc_total = {sub: 0 for sub in SUBTYPES}
    sc_total = {sub: 0 for sub in SUBTYPES}
    likert_total = {sub: 0 for sub in SUBTYPES}

    # 1) Score Forced-Choice blocks
    for qid, ranking in fc_responses.items():
        if qid in fc_map:
            mapping = fc_map[qid]
            for option_letter, rank in ranking.items():
                if option_letter in mapping:
                    subtype = mapping[option_letter]
                    if rank == 1:
                        fc_total[subtype] += 3
                    elif rank == 2:
                        fc_total[subtype] += 2
                    elif rank == 3:
                        fc_total[subtype] += 1
                    # rank == 4 → +0

    # 2) Score Scenario items
    for qid, choice in sc_responses.items():
        if qid in sc_map and choice in sc_map[qid]:
            subtype = sc_map[qid][choice]
            sc_total[subtype] += 3

    # 3) Score Likert items
    for qid, rating in likert_responses.items():
        if qid in likert_map:
            subtype = likert_map[qid]
            likert_total[subtype] += rating

    # 4) Compute final totals
    final_totals = {
        sub: fc_total[sub] + sc_total[sub] + likert_total[sub]
        for sub in SUBTYPES
    }

    breakdown = {
        "FC": fc_total,
        "SC": sc_total,
        "Likert": likert_total,
    }

    return final_totals, breakdown

def determine_alignment(final_totals, breakdown):
    """Determine dominant subtype and alignment with proper tie-breaking."""
    # Build a sortable list: (subtype, total, fc_points, lik_points, sc_points)
    score_list = []
    for sub in SUBTYPES:
        total = final_totals[sub]
        fc_pts = breakdown["FC"][sub]
        lik_pts = breakdown["Likert"][sub]
        sc_pts = breakdown["SC"][sub]
        score_list.append((sub, total, fc_pts, lik_pts, sc_pts))

    # Sort by: total desc, fc desc, lik desc, sc desc, subtype asc (tie-breaking)
    score_list.sort(key=lambda x: (-x[1], -x[2], -x[3], -x[4], x[0]))

    dominant, dom_total, dom_fc, dom_lik, dom_sc = score_list[0]
    runner_up, run_total, run_fc, run_lik, run_sc = score_list[1]
    gap = dom_total - run_total
    
    attachment_pages = {
    "SECURE": "https://adamlanesmith.com/secure/",
    "REMADE SECURE": "https://adamlanesmith.com/remade-secure/",
    "ETHICAL AVOIDANT": "https://adamlanesmith.com/ethical-avoidant/",
    "MANIPULATIVE AVOIDANT": "https://adamlanesmith.com/manipulative-avoidant/",
    "NURTURING ANXIOUS": "https://adamlanesmith.com/nurturing-anxious/",
    "TOXIC ANXIOUS": "https://adamlanesmith.com/toxic-anxious/",
    "QUIET DISORGANIZED": "https://adamlanesmith.com/quiet-disorganized/",
    "LOUD DISORGANIZED": "https://adamlanesmith.com/loud-disorganized/"
    }

    # Determine thresholds
    max_val = MAX_SCORES[dominant]
    pct70 = math.ceil(0.70 * max_val)
    pct50 = math.ceil(0.50 * max_val)

    if dom_total >= pct70 and gap >= 8:
        strength = "High"
    elif dom_total >= pct50 and gap >= 5:
        strength = "Medium"
    else:
        strength = "Low"

    return {
        "dominant": dominant,
        "runner_up": runner_up,
        "gap": gap,
        "strength": strength,
        "totals": final_totals,
        "breakdown": breakdown,
        "page_link": attachment_pages[dominant],
    }

@app.route('/start', methods=['GET', 'POST'])
def start():
    if request.method == 'POST':
        session['user_name'] = request.form['name']
        session['user_email'] = request.form['email']
        return redirect(url_for('fc_question', question_index=0))
    return render_template('start.html')

# Function to send quiz results to WordPress
# Call this after scoring in your /results route

# import requests


def send_to_wordpress(name, email, result):
    print(name, email)
    # print(session.get('user_name'))
    url = "https://adamlanesmith.com/wp-json/custom/v1/submit-quiz"
    data = {
        "name": name,
        "email": email,
        "result": result['dominant']  # assume result is just a string
    }
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',  # Add this
        'User-Agent': 'Mozilla/5.0'
    }

    try:
        response = requests.post(url, data=json.dumps(data), headers=headers, timeout=5, verify=False)
        response.raise_for_status()
        print("✅ Success:", response.status_code)
        print("📦 Response:", response.text)
    except Exception as e:
        print(data)
        print("❌ Failed to send result to WordPress:", e)

# Call with flat string result
# send_to_wordpress("Umar", "umar@example.com", "Secure")