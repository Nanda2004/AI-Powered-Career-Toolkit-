import streamlit as st
from google.generativeai import GenerativeModel, configure
import pdfplumber
from docx import Document
import os
from dotenv import load_dotenv
import tempfile
import json
import pandas as pd
import plotly.express as px
from datetime import datetime
import base64

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("❌ Gemini API key not found. Add it to your `.env` file.")
    st.stop()

# Initialize Gemini
try:
    configure(api_key=GEMINI_API_KEY)
    gemini_model = GenerativeModel('gemini-2.0-flash')
except Exception as e:
    st.error(f"Failed to initialize Gemini: {e}")
    st.stop()

# Initialize session state
if 'job_tracker' not in st.session_state:
    st.session_state.job_tracker = {
        'applications': [],
        'resume_versions': {}
    }
if 'resume_history' not in st.session_state:
    st.session_state.resume_history = []
if 'analysis' not in st.session_state:
    st.session_state.analysis = None
if 'interview_prep' not in st.session_state:
    st.session_state.interview_prep = ""
if 'improved_resume' not in st.session_state:
    st.session_state.improved_resume = ""
if 'course_search' not in st.session_state:
    st.session_state.course_search = {}
if 'interview_questions' not in st.session_state:
    st.session_state.interview_questions = []
if 'current_question' not in st.session_state:
    st.session_state.current_question = 0
if 'interview_responses' not in st.session_state:
    st.session_state.interview_responses = []
if 'interview_started' not in st.session_state:
    st.session_state.interview_started = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Resume Analyzer"
# Handle pending reroutes
if 'pending_redirect' in st.session_state:
    st.session_state.current_page = st.session_state.pending_redirect
    del st.session_state.pending_redirect
    st.rerun()


def extract_text_from_file(uploaded_file):
    """Extract text from PDF, DOCX, or TXT files."""
    text = ""
    file_extension = uploaded_file.name.split('.')[-1].lower()
    
    if file_extension == 'pdf':
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    elif file_extension == 'docx':
        doc = Document(uploaded_file)
        for para in doc.paragraphs:
            text += para.text + "\n"
    elif file_extension == 'txt':
        text = uploaded_file.read().decode("utf-8")
    
    return text

def analyze_resume(resume_text, job_desc):
    """Analyze resume against job description with robust JSON parsing."""
    prompt = f"""
    Analyze this resume against the job description and provide detailed feedback in this exact JSON format:
    {{
        "ats_score": (0-100),
        "screening_chance": ("Low"/"Medium"/"High"),
        "strengths": ["list", "of", "strengths"],
        "weaknesses": ["list", "of", "weaknesses"],
        "missing_keywords": ["keywords", "from", "jd"],
        "improvements": ["specific", "actionable", "improvements"],
        "skill_coverage": {{
            "Technical Skills": 0-100,
            "Soft Skills": 0-100,
            "Tools": 0-100,
            "Frameworks": 0-100
        }},
        "learning_suggestions": [
            {{
                "skill": "skill name",
                "resources": "learning resources",
                "roadmap": "learning path",
                "project_idea": "project suggestion",
                "courses": "specific course recommendations"
            }}
        ]
    }}

    Be extremely consistent with scoring for the same resume and job description.
    Return ONLY the JSON object, no additional text or explanations.

    Resume: {resume_text[:8000]}
    Job Description: {job_desc[:5000]}
    """
    
    try:
        response = gemini_model.generate_content(prompt)
        if response.text:
            # Clean the response to ensure valid JSON
            json_str = response.text.strip()
            if json_str.startswith('```json'):
                json_str = json_str[7:-3].strip()
            elif json_str.startswith('```'):
                json_str = json_str[3:-3].strip()
            
            data = json.loads(json_str)
            
            # Validate the response structure
            required_keys = ['ats_score', 'screening_chance', 'strengths', 
                           'weaknesses', 'missing_keywords', 'improvements',
                           'skill_coverage', 'learning_suggestions']
            if all(key in data for key in required_keys):
                return data
            
    except Exception as e:
        st.error(f"Analysis error: {str(e)}")
    
    # Default response if parsing fails
    return {
        'ats_score': 50,
        'screening_chance': 'Medium',
        'strengths': ["Strong technical foundation", "Relevant work experience"],
        'weaknesses': ["Could highlight achievements more", "Missing some keywords"],
        'missing_keywords': [],
        'improvements': [
            "Quantify achievements with metrics",
            "Add more action verbs",
            "Tailor skills to job description"
        ],
        'skill_coverage': {
            "Technical Skills": 70,
            "Soft Skills": 65,
            "Tools": 60,
            "Frameworks": 55
        },
        'learning_suggestions': []
    }

def generate_enhanced_resume(resume_text, improvements, job_desc=""):
    """Generate an improved version of the resume."""
    prompt = f"""
    Rewrite this resume incorporating these improvements:
    {improvements}
    
    Maintain the original format while enhancing content.
    Focus on making the resume more ATS-friendly.
    Include relevant keywords from this job description: {job_desc[:2000]}
    
    Return ONLY the improved resume text, no additional explanations.
    
    Original Resume:
    {resume_text[:8000]}
    """
    response = gemini_model.generate_content(prompt)
    return response.text

def generate_cover_letter(resume_text, job_desc, company_info=""):
    """Generate a professional cover letter."""
    prompt = f"""
    Write a professional cover letter for this candidate:
    Resume: {resume_text[:4000]}
    Job Description: {job_desc[:2000]}
    Company Info: {company_info}
    
    Format guidelines:
    - 3-4 paragraphs
    - Professional tone
    - Highlight relevant skills
    - Tailored to the job
    """
    response = gemini_model.generate_content(prompt)
    return response.text

def generate_interview_questions(resume_text, job_desc):
    """Generate interview questions with robust error handling."""
    prompt = f"""
    Generate 5 technical and 3 behavioral interview questions based on:
    Resume: {resume_text[:4000]}
    Job Description: {job_desc[:2000]}
    
    Return as a JSON object with this exact structure:
    {{
        "questions": [
            "Question 1 text",
            "Question 2 text"
        ]
    }}
    """
    
    try:
        response = gemini_model.generate_content(prompt)
        if response.text:
            # Clean the response
            json_str = response.text.strip()
            if json_str.startswith('```json'):
                json_str = json_str[7:-3].strip()
            elif json_str.startswith('```'):
                json_str = json_str[3:-3].strip()
            
            data = json.loads(json_str)
            if 'questions' in data and isinstance(data['questions'], list):
                return data['questions']
    except Exception as e:
        st.error(f"Question generation error: {str(e)}")
    
    # Default questions if generation fails
    return [
        "Tell me about yourself",
        "What interests you about this position?",
        "Describe a challenging project you worked on",
        "How do you handle conflicts in a team?",
        "What relevant skills do you bring to this role?"
    ]

def evaluate_interview_response(question, response):
    """Evaluate user's interview response."""
    prompt = f"""
    Evaluate this interview response:
    Question: {question}
    Response: {response}
    
    Provide feedback in this JSON format:
    {{
        "technical_score": (1-5),
        "clarity_score": (1-5),
        "confidence_score": (1-5),
        "feedback": "detailed suggestions"
    }}
    """
    try:
        evaluation = gemini_model.generate_content(prompt)
        if evaluation.text:
            json_str = evaluation.text.strip()
            if json_str.startswith('```json'):
                json_str = json_str[7:-3].strip()
            elif json_str.startswith('```'):
                json_str = json_str[3:-3].strip()
            
            return json.loads(json_str)
    except Exception as e:
        st.error(f"Evaluation error: {str(e)}")
    
    return {
        'technical_score': 3,
        'clarity_score': 3,
        'confidence_score': 3,
        'feedback': "Evaluation failed - please try again"
    }

def track_application(company, position, jd, resume_version):
    """Track job application in dashboard."""
    application = {
        'company': company,
        'position': position,
        'date': datetime.now().strftime("%Y-%m-%d"),
        'status': 'Applied',
        'jd': jd,
        'resume_version': resume_version
    }
    st.session_state.job_tracker['applications'].append(application)

def create_download_link(content, filename, filetype="txt"):
    """Create a download link for the content."""
    b64 = base64.b64encode(content.encode()).decode()
    return f'<a href="data:file/{filetype};base64,{b64}" download="{filename}">Download {filename}</a>'

def main():
    st.set_page_config(layout="wide", page_title="Career Toolkit Pro")
    st.title("🚀 Career Toolkit Pro: Resume Analyzer & Interview Coach")
    
    # Navigation options
    nav_options = [
        "Resume Analyzer", 
        "Job Tracker", 
        "Mock Interview",
        "Resume Builder",
        "Interview Prep Guide"
    ]
    
    # Navigation sidebar with persistent selection
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Resume Analyzer"
        
    # Create radio with the current selection
    page = st.sidebar.radio(
        "Navigation", 
        nav_options,
        index=nav_options.index(st.session_state.current_page)
    )
    
    # Update current page in session state
    if page != st.session_state.current_page:
        st.session_state.current_page = page

    if st.session_state.current_page == "Resume Analyzer":
        st.header("📄 Resume Analysis & Optimization")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            resume_file = st.file_uploader("Upload Resume (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"])
            if resume_file:
                resume_text = extract_text_from_file(resume_file)
                st.session_state.resume_text = resume_text
                if len(st.session_state.resume_history) == 0:
                    st.session_state.resume_history.append(resume_text)
                
        with col2:
            job_desc = st.text_area("Paste Job Description", height=200,
                                 placeholder="Copy-paste the job description here...")
            role = st.text_input("Target Role", placeholder="E.g., Data Scientist, UX Designer")
            company = st.text_input("Company (Optional)")
            
        if st.button("Analyze Resume") and st.session_state.resume_text and job_desc:
            with st.spinner("Analyzing your resume..."):
                analysis = analyze_resume(st.session_state.resume_text, job_desc)
                st.session_state.analysis = analysis
                st.session_state.job_desc = job_desc
                
                if company and role:
                    track_application(company, role, job_desc, f"v{len(st.session_state.resume_history)}")
                
                st.success("Analysis complete!")
                
                # Display ATS Score with color coding
                score = analysis['ats_score']
                if score >= 80:
                    score_color = "green"
                    score_emoji = "✅"
                elif score >= 60:
                    score_color = "orange"
                    score_emoji = "⚠️"
                else:
                    score_color = "red"
                    score_emoji = "❌"
                
                st.markdown(
                    f"### <span style='color:{score_color}'>ATS Score: {score}/100 {score_emoji}</span> "
                    f"(Screening chance: {analysis['screening_chance']})",
                    unsafe_allow_html=True
                )
                
                # Tabbed interface for results
                tab1, tab2 = st.tabs(["Improvements", "Learning Path"])
                
                with tab1:
                    st.subheader("🚀 Recommended Improvements")
                    for i, imp in enumerate(analysis['improvements'], 1):
                        st.markdown(f"{i}. {imp}")
                    
                    # if st.button("Apply All Improvements"):
                    #     with st.spinner("Applying improvements..."):
                    #         improved = generate_enhanced_resume(
                    #             st.session_state.resume_text,
                    #             analysis['improvements'],
                    #             job_desc
                    #         )
                    #         st.session_state.improved_resume = improved
                    #         st.session_state.resume_history.append(improved)
                    #         st.session_state.resume_text = improved
                            
                    #         # Redirect to Resume Builder
                    #         st.session_state.pending_redirect = "Resume Builder"
                    #         st.write("🔁 Redirecting to Resume Builder...")

                            # st.rerun()
                
                with tab2:
                    if analysis.get('learning_suggestions'):
                        st.subheader("📚 Learning Recommendations")
                        for rec in analysis['learning_suggestions']:
                            with st.expander(f"🎯 {rec.get('skill', 'Skill Development')}"):
                                st.markdown(f"**Resources:** {rec.get('resources', 'Not specified')}")
                                st.markdown(f"**Learning Path:** {rec.get('roadmap', 'Not specified')}")
                                st.markdown(f"**Project Idea:** {rec.get('project_idea', 'Not specified')}")
                                
                                # Generate course recommendations when clicked
                                # if st.button(f"Find Courses for {rec.get('skill')}", key=f"courses_{rec.get('skill')}"):
                                #     with st.spinner(f"Finding courses for {rec.get('skill')}..."):
                                #         prompt = f"""
                                #         Recommend specific online courses to learn {rec.get('skill')}.
                                #         Include course names, platforms (like Coursera, Udemy), and URLs if possible.
                                #         """
                                #         response = gemini_model.generate_content(prompt)
                                #         st.session_state.course_search[rec.get('skill')] = response.text
                                
                                # Display course recommendations if available
                                # if rec.get('skill') in st.session_state.course_search:
                                #     st.markdown("**Recommended Courses:**")
                                #     st.write(st.session_state.course_search[rec.get('skill')])
                    else:
                        st.info("No major skill gaps identified!")

    elif st.session_state.current_page == "Job Tracker":
        st.header("📊 Job Application Tracker")
        
        # Add new application
        with st.expander("➕ Add New Application", expanded=False):
            with st.form("add_application"):
                company = st.text_input("Company Name*")
                position = st.text_input("Position Title*")
                jd = st.text_area("Job Description")
                resume_ver = st.text_input("Resume Version Used")
                status = st.selectbox("Status", ["Applied", "Interview", "Offer", "Rejected"])
                
                if st.form_submit_button("Track Application"):
                    if company and position:
                        application = {
                            'company': company,
                            'position': position,
                            'date': datetime.now().strftime("%Y-%m-%d"),
                            'status': status,
                            'jd': jd,
                            'resume_version': resume_ver
                        }
                        st.session_state.job_tracker['applications'].append(application)
                        st.success("Application tracked!")
                    else:
                        st.error("Company and Position are required")
        
        # Display applications
        if st.session_state.job_tracker['applications']:
            st.subheader("Your Applications")
            apps_df = pd.DataFrame(st.session_state.job_tracker['applications'])
            
            # Show statistics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Applications", len(apps_df))
            col2.metric("Active", len(apps_df[apps_df['status'] == "Applied"]))
            col3.metric("Interviews", len(apps_df[apps_df['status'] == "Interview"]))
            col4.metric("Offers", len(apps_df[apps_df['status'] == "Offer"]))
            
            # Display editable table
            edited_df = st.data_editor(
                apps_df.sort_values('date', ascending=False),
                column_config={
                    "date": "Date",
                    "company": "Company",
                    "position": "Position",
                    "status": st.column_config.SelectboxColumn(
                        "Status",
                        options=["Applied", "Interview", "Offer", "Rejected"]
                    )
                },
                use_container_width=True,
                hide_index=True
            )
            
            # Save changes
            if st.button("Save Changes"):
                st.session_state.job_tracker['applications'] = edited_df.to_dict('records')
                st.success("Changes saved!")
        else:
            st.info("No applications tracked yet.")

    elif st.session_state.current_page == "Mock Interview":
        st.header("🎤 Mock Interview Simulator")
        
        if 'resume_text' not in st.session_state:
            st.warning("Upload your resume first in the Resume Analyzer section")
            st.stop()
            
        job_desc = st.text_area("Enter Job Description", height=150,
                              value=st.session_state.get('job_desc', ''))
        
        if st.button("Start Mock Interview") and job_desc:
            with st.spinner("Generating interview questions..."):
                questions = generate_interview_questions(st.session_state.resume_text, job_desc)
                st.session_state.interview_questions = questions
                st.session_state.current_question = 0
                st.session_state.interview_responses = []
                st.session_state.interview_started = True
                st.success("Interview ready! First question loaded.")
        
        if st.session_state.get('interview_started'):
            st.divider()
            progress = (st.session_state.current_question + 1) / len(st.session_state.interview_questions)
            st.progress(progress, text=f"Question {st.session_state.current_question + 1} of {len(st.session_state.interview_questions)}")
            
            current_q = st.session_state.interview_questions[st.session_state.current_question]
            st.subheader(f"❔ {current_q}")
            
            response = st.text_area("Your Answer", height=150, key=f"response_{st.session_state.current_question}")
            
            if st.button("Submit Answer"):
                with st.spinner("Evaluating your response..."):
                    evaluation = evaluate_interview_response(current_q, response)
                    st.session_state.interview_responses.append({
                        'question': current_q,
                        'response': response,
                        'evaluation': evaluation
                    })
                    
                    with st.expander("💬 Feedback", expanded=True):
                        cols = st.columns(3)
                        cols[0].metric("Technical", f"{evaluation['technical_score']}/5")
                        cols[1].metric("Clarity", f"{evaluation['clarity_score']}/5")
                        cols[2].metric("Confidence", f"{evaluation['confidence_score']}/5")
                        
                        st.markdown("**Detailed Feedback:**")
                        st.write(evaluation['feedback'])
                    
                    st.session_state.current_question += 1
                    if st.session_state.current_question >= len(st.session_state.interview_questions):
                        st.session_state.interview_started = False
                        st.balloons()
                        st.success("🎉 Interview completed!")
                        
                        # Show summary
                        st.subheader("📊 Interview Performance Summary")
                        tech_scores = [r['evaluation']['technical_score'] for r in st.session_state.interview_responses]
                        clarity_scores = [r['evaluation']['clarity_score'] for r in st.session_state.interview_responses]
                        conf_scores = [r['evaluation']['confidence_score'] for r in st.session_state.interview_responses]
                        
                        avg_scores = pd.DataFrame({
                            'Category': ['Technical', 'Clarity', 'Confidence'],
                            'Average Score': [
                                sum(tech_scores)/len(tech_scores),
                                sum(clarity_scores)/len(clarity_scores),
                                sum(conf_scores)/len(conf_scores)
                            ]
                        })
                        
                        fig = px.bar(avg_scores, x='Category', y='Average Score', 
                                    range_y=[0,5], title="Your Average Scores")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.rerun()

    elif st.session_state.current_page == "Resume Builder":
        st.header("🛠️ Smart Resume Builder")
        
        if 'resume_text' not in st.session_state:
            st.warning("Upload your resume first in the Resume Analyzer section")
            st.stop()
            
        if len(st.session_state.resume_history) == 0:
            st.session_state.resume_history.append(st.session_state.resume_text)
        
        st.subheader("📝 Resume Editor")
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # Version selector
            selected_version = st.selectbox(
                "Select Version",
                options=[f"Version {i+1}" for i in range(len(st.session_state.resume_history))],
                index=len(st.session_state.resume_history)-1
            )
            version_index = int(selected_version.split()[1])-1
            
            # Resume editor
            current_resume = st.text_area(
                "Edit your resume",
                st.session_state.resume_history[version_index],
                height=500,
                key=f"resume_editor_{version_index}"
            )
            
            # Action buttons
            col1a, col1b = st.columns(2)
            with col1a:
                if st.button("💾 Save Changes"):
                    st.session_state.resume_history[version_index] = current_resume
                    st.session_state.resume_text = current_resume
                    st.success("Changes saved!")
            with col1b:
                if st.button("🆕 New Version"):
                    st.session_state.resume_history.append(current_resume)
                    st.success("New version created!")
        
        with col2:
            # Improvement suggestions from analysis
            if 'analysis' in st.session_state and st.session_state.analysis.get('improvements'):
                st.subheader("✨ Suggested Improvements")
                for i, imp in enumerate(st.session_state.analysis['improvements'], 1):
                    st.markdown(f"{i}. {imp}")
                
                if st.button("🚀 Apply All Suggestions"):
                    with st.spinner("Generating enhanced resume..."):
                        improved = generate_enhanced_resume(
                            current_resume,
                            st.session_state.analysis['improvements'],
                            st.session_state.get('job_desc', "")
                        )
                        st.session_state.resume_history.append(improved)
                        st.session_state.resume_text = improved
                        st.success("Improvements applied! Select the new version.")
                        st.rerun()
            
            # Export options
            st.subheader("📤 Export Options")
            export_format = st.selectbox("Format", ["TXT", "PDF"])
            
            if st.button(f"Export as {export_format}"):
                if export_format == "TXT":
                    st.download_button(
                        label="⬇️ Download TXT",
                        data=current_resume,
                        file_name="resume.txt",
                        mime="text/plain"
                    )
                elif export_format == "PDF":
                    # Note: In production, implement actual PDF generation
                    st.warning("PDF export requires additional libraries. Downloading as TXT for now.")
                    st.download_button(
                        label="⬇️ Download TXT",
                        data=current_resume,
                        file_name="resume.txt",
                        mime="text/plain"
                    )

    elif st.session_state.current_page == "Interview Prep Guide":
        st.header("📚 Comprehensive Interview Preparation")
        
        if 'resume_text' not in st.session_state:
            st.warning("Upload your resume first in the Resume Analyzer section")
            st.stop()
            
        job_desc = st.text_area("Paste Job Description", height=150,
                              value=st.session_state.get('job_desc', ''))
        
        if st.button("Generate Prep Guide") and job_desc:
            with st.spinner("Creating personalized preparation plan..."):
                prompt = f"""
                Create a detailed interview preparation guide for:
                Resume: {st.session_state.resume_text[:4000]}
                Job Description: {job_desc[:2000]}
                
                Include:
                1. Technical Topics (categorized by priority)
                2. Behavioral Questions (with STAR examples)
                3. Company Research Points
                4. Industry Trends
                5. Questions to Ask Interviewers
                6. Presentation Tips
                
                Format with clear headings and bullet points.
                """
                response = gemini_model.generate_content(prompt)
                st.session_state.interview_prep = response.text
                st.success("Preparation guide generated!")
        
        if 'interview_prep' in st.session_state:
            st.markdown(st.session_state.interview_prep)
            
            # Study plan generator
            st.subheader("📅 Create Study Plan")
            study_days = st.slider("Days until interview", 1, 30, 7)
            
            if st.button("Generate Study Plan"):
                with st.spinner("Creating customized schedule..."):
                    prompt = f"""
                    Create a {study_days}-day study plan based on:
                    {st.session_state.interview_prep[:3000]}
                    
                    Include for each day:
                    - Focus areas
                    - Time allocation
                    - Resources
                    - Practice activities
                    """
                    study_plan = gemini_model.generate_content(prompt)
                    
                    st.subheader("🗓️ Your Study Plan")
                    st.markdown(study_plan.text)
                    
                    # Download option
                    st.download_button(
                        label="⬇️ Download Study Plan",
                        data=study_plan.text,
                        file_name="interview_study_plan.txt",
                        mime="text/plain"
                    )

if __name__ == "__main__":
    main()