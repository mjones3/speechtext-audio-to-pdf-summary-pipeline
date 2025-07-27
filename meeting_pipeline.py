#!/usr/bin/env python3
"""
Meeting Transcription Pipeline
.webm → SpeechText.AI → PDF transcript → Claude → PDF summary

Usage: python meeting_pipeline.py
"""

import requests
import time
import json
import os
import sys
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import pyperclip
import logging
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SpeechTextClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.speechtext.ai"
    
    def transcribe_file(self, file_path):
        """Upload file to SpeechText.AI and get transcription"""
        logger.info(f"🎤 Starting transcription for: {file_path}")
        
        # Step 1: Upload file
        endpoint = f"{self.base_url}/recognize"
        
        with open(file_path, "rb") as file:
            post_body = file.read()
        
        headers = {'Content-Type': "application/octet-stream"}
        
        # Get file extension for format
        file_format = Path(file_path).suffix[1:].lower()  # Remove the dot
        
        config = {
            "key": self.api_key,
            "language": "en-US",
            "punctuation": True,
            "format": file_format
        }
        
        logger.info("📤 Uploading file to SpeechText.AI...")
        response = requests.post(endpoint, headers=headers, params=config, data=post_body)
        
        if response.status_code != 200:
            raise Exception(f"Upload failed: {response.text}")
        
        result = response.json()
        task_id = result["id"]
        logger.info(f"✅ Upload successful. Task ID: {task_id}")
        
        # Step 2: Poll for results
        return self._get_transcription_results(task_id)
    
    def _get_transcription_results(self, task_id):
        """Poll for transcription results"""
        endpoint = f"{self.base_url}/results"
        
        config = {
            "key": self.api_key,
            "task": task_id
        }
        
        logger.info("⏳ Waiting for transcription to complete...")
        
        while True:
            response = requests.get(endpoint, params=config)
            results = response.json()
            
            if "status" not in results:
                break
            
            status = results["status"]
            logger.info(f"📊 Task status: {status}")
            
            if status == 'failed':
                raise Exception(f"Transcription failed: {results}")
            
            if status == 'finished':
                logger.info("🎉 Transcription completed!")
                return results["results"]["transcript"]
            
            # Sleep for 15 seconds if still processing
            time.sleep(15)
        
        raise Exception("Unexpected response format")

class PDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        
        # Custom styles
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            textColor='#2E86AB'
        )
        
        self.body_style = ParagraphStyle(
            'CustomBody',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=14,
            spaceAfter=12
        )
    
    def create_transcript_pdf(self, transcript_text, output_path):
        """Create PDF from transcript text"""
        logger.info(f"📄 Creating transcript PDF: {output_path}")
        
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        content = []
        
        # Title
        title = Paragraph("Meeting Transcript", self.title_style)
        content.append(title)
        content.append(Spacer(1, 0.2*inch))
        
        # Metadata
        timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        meta = Paragraph(f"Generated on: {timestamp}", self.styles['Normal'])
        content.append(meta)
        content.append(Spacer(1, 0.3*inch))
        
        # Transcript content
        # Split into paragraphs for better formatting
        paragraphs = transcript_text.split('\n\n')
        if len(paragraphs) == 1:
            # If no double newlines, split on single newlines every few sentences
            sentences = transcript_text.split('. ')
            paragraphs = []
            current_para = ""
            for i, sentence in enumerate(sentences):
                current_para += sentence + ". "
                if (i + 1) % 3 == 0:  # Every 3 sentences
                    paragraphs.append(current_para.strip())
                    current_para = ""
            if current_para:
                paragraphs.append(current_para.strip())
        
        for para in paragraphs:
            if para.strip():
                content.append(Paragraph(para.strip(), self.body_style))
                content.append(Spacer(1, 0.1*inch))
        
        doc.build(content)
        logger.info("✅ Transcript PDF created successfully")
    
    def create_summary_pdf(self, summary_text, output_path):
        """Create PDF from Claude summary"""
        logger.info(f"📄 Creating summary PDF: {output_path}")
        
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        content = []
        
        # Title
        title = Paragraph("Meeting Summary", self.title_style)
        content.append(title)
        content.append(Spacer(1, 0.2*inch))
        
        # Metadata
        timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        meta = Paragraph(f"Generated on: {timestamp}", self.styles['Normal'])
        content.append(meta)
        content.append(Spacer(1, 0.3*inch))
        
        # Summary content
        paragraphs = summary_text.split('\n\n')
        for para in paragraphs:
            if para.strip():
                content.append(Paragraph(para.strip(), self.body_style))
                content.append(Spacer(1, 0.1*inch))
        
        doc.build(content)
        logger.info("✅ Summary PDF created successfully")

class ClaudeIntegration:
    def __init__(self):
        self.prompt_template = """Please create a professional IT meeting summary from this transcript. Format it with:

**EXECUTIVE SUMMARY** (2-3 sentences highlighting the main purpose and outcomes)

**KEY DECISIONS MADE**
- List all decisions reached during the meeting
- Include rationale where mentioned

**ACTION ITEMS**
- Item description (Owner: Name, Due: Date if mentioned)
- Be specific about who is responsible

**TECHNICAL DISCUSSION POINTS**
- Main technical topics covered
- Any architectural or implementation details discussed

**BLOCKERS & RISKS**
- Issues that need resolution
- Potential risks identified

**NEXT STEPS**
- Immediate next steps
- Follow-up meetings needed

Make it concise, scannable, and suitable for stakeholders. Focus on actionable information.

TRANSCRIPT:
{transcript}"""
    
    def prepare_claude_prompt(self, transcript):
        """Prepare the prompt for Claude"""
        return self.prompt_template.format(transcript=transcript)
    
    def copy_prompt_to_clipboard(self, transcript):
        """Copy the formatted prompt to clipboard for manual Claude interaction"""
        prompt = self.prepare_claude_prompt(transcript)
        pyperclip.copy(prompt)
        logger.info("📋 Prompt copied to clipboard!")
        return prompt

def select_file():
    """Open file dialog to select audio file"""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    file_types = [
        ("Audio files", "*.webm *.mp4 *.mp3 *.wav *.m4a *.flac"),
        ("All files", "*.*")
    ]
    
    file_path = filedialog.askopenfilename(
        title="Select audio file to transcribe",
        filetypes=file_types
    )
    
    return file_path

def get_output_paths(input_file):
    """Generate output file paths based on input file"""
    input_path = Path(input_file)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"meeting_{timestamp}"
    
    output_dir = input_path.parent / "meeting_outputs"
    output_dir.mkdir(exist_ok=True)
    
    transcript_pdf = output_dir / f"{base_name}_transcript.pdf"
    summary_pdf = output_dir / f"{base_name}_summary.pdf"
    
    return transcript_pdf, summary_pdf

def main():
    """Main pipeline execution"""
    print("🚀 Meeting Transcription Pipeline")
    print("=" * 50)
    
    # Check for API key
    api_key = os.getenv('SPEECHTEXT_API_KEY')
    if not api_key:
        print("❌ Error: SPEECHTEXT_API_KEY environment variable not set")
        print("Please set your SpeechText.AI API key:")
        print("export SPEECHTEXT_API_KEY='your_api_key_here'")
        return 1
    
    try:
        # Step 1: Select file
        print("📁 Select your audio file...")
        input_file = select_file()
        
        if not input_file:
            print("❌ No file selected. Exiting.")
            return 1
        
        print(f"✅ Selected: {Path(input_file).name}")
        
        # Get output paths
        transcript_pdf_path, summary_pdf_path = get_output_paths(input_file)
        
        # Step 2: Transcribe with SpeechText.AI
        speech_client = SpeechTextClient(api_key)
        transcript = speech_client.transcribe_file(input_file)
        
        # Step 3: Create transcript PDF
        pdf_generator = PDFGenerator()
        pdf_generator.create_transcript_pdf(transcript, transcript_pdf_path)
        
        # Step 4: Prepare Claude prompt
        claude = ClaudeIntegration()
        prompt = claude.copy_prompt_to_clipboard(transcript)
        
        print("\n" + "="*50)
        print("📋 PROMPT COPIED TO CLIPBOARD!")
        print("="*50)
        print("Next steps:")
        print("1. Go to Claude (web interface)")
        print("2. Paste the prompt (Ctrl+V / Cmd+V)")
        print("3. Wait for Claude's response")
        print("4. Copy Claude's summary")
        print("5. Come back here and paste it")
        print("="*50)
        
        # Step 5: Get Claude response from user
        print("\n📝 Paste Claude's summary here (press Enter twice when done):")
        summary_lines = []
        while True:
            try:
                line = input()
                if line == "" and summary_lines and summary_lines[-1] == "":
                    break
                summary_lines.append(line)
            except KeyboardInterrupt:
                print("\n❌ Operation cancelled.")
                return 1
        
        summary_text = '\n'.join(summary_lines).strip()
        
        if not summary_text:
            print("❌ No summary provided. Exiting.")
            return 1
        
        # Step 6: Create summary PDF
        pdf_generator.create_summary_pdf(summary_text, summary_pdf_path)
        
        # Final output
        print("\n🎉 Pipeline completed successfully!")
        print(f"📄 Transcript PDF: {transcript_pdf_path}")
        print(f"📊 Summary PDF: {summary_pdf_path}")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())