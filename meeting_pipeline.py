#!/usr/bin/env python3
"""
Enhanced Meeting Transcription Pipeline
Batch processes .webm files from Windows Downloads → SpeechText.AI → Claude API → PDF summaries

Usage: python meeting_pipeline.py
"""

import requests
import time
import json
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import Color, black, white
import logging
from dotenv import load_dotenv
import anthropic

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SpeechTextClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.speechtext.ai"
        self.remaining_seconds = None
    
    def transcribe_file(self, file_path):
        """Upload file to SpeechText.AI and get complete transcription with speakers/timestamps"""
        logger.info(f"🎤 Starting transcription for: {Path(file_path).name}")
        
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
            "format": file_format,
            "speakers": True,  # Enable speaker identification
            "summary": True,   # Enable summary generation
            "summary_size": 15  # 15% summary size
        }
        
        logger.info("📤 Uploading file to SpeechText.AI...")
        response = requests.post(endpoint, headers=headers, params=config, data=post_body)
        
        if response.status_code != 200:
            raise Exception(f"Upload failed: {response.text}")
        
        result = response.json()
        task_id = result["id"]
        logger.info(f"✅ Upload successful. Task ID: {task_id}")
        
        # Step 2: Poll for results and collect all data
        return self._get_complete_transcription_results(task_id, Path(file_path).stem)
    
    def _get_complete_transcription_results(self, task_id, base_filename):
        """Poll for transcription results and save complete transcript"""
        endpoint = f"{self.base_url}/results"
        
        config = {
            "key": self.api_key,
            "task": task_id
        }
        
        logger.info("⏳ Waiting for transcription to complete...")
        
        # Create text file to collect all transcript data
        transcript_file = Path(f"meeting_outputs/{base_filename}_full_transcript.txt")
        transcript_file.parent.mkdir(exist_ok=True)
        
        poll_count = 0
        
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(f"FULL TRANSCRIPT - {base_filename}\n")
            f.write(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n")
            f.write("=" * 80 + "\n\n")
        
        while True:
            response = requests.get(endpoint, params=config)
            results = response.json()
            
            poll_count += 1
            
            if "status" not in results:
                break
            
            status = results["status"]
            logger.info(f"📊 Task status: {status} (Poll #{poll_count})")
            
            # Save this polling result to file
            with open(transcript_file, 'a', encoding='utf-8') as f:
                f.write(f"POLL #{poll_count} - Status: {status}\n")
                f.write(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}\n")
                
                if "results" in results:
                    # Check for remaining seconds
                    if "remaining seconds" in results:
                        self.remaining_seconds = results["remaining seconds"]
                        f.write(f"Remaining seconds: {self.remaining_seconds}\n")
                    
                    # Write transcript data if available
                    if "transcript" in results["results"]:
                        f.write(f"TRANSCRIPT CONTENT:\n")
                        f.write(results["results"]["transcript"])
                        f.write("\n")
                    
                    # Write word-level timestamps if available
                    if "word_time_offsets" in results["results"]:
                        f.write(f"\nWORD-LEVEL TIMESTAMPS:\n")
                        for word_data in results["results"]["word_time_offsets"]:
                            start_time = word_data.get("start_time", 0)
                            end_time = word_data.get("end_time", 0)
                            word = word_data.get("word", "")
                            confidence = word_data.get("confidence", 0)
                            f.write(f"[{start_time:.2f}s-{end_time:.2f}s] {word} (conf: {confidence:.3f})\n")
                    
                    # Write speaker information if available
                    if "speakers" in results["results"]:
                        f.write(f"\nSPEAKER INFORMATION:\n")
                        for speaker_data in results["results"]["speakers"]:
                            f.write(f"Speaker: {json.dumps(speaker_data, indent=2)}\n")
                    
                    # Write summary if available
                    if "summary" in results["results"]:
                        f.write(f"\nAUTO-GENERATED SUMMARY:\n")
                        f.write(results["results"]["summary"])
                        f.write("\n")
                
                f.write("\n" + "-" * 60 + "\n\n")
            
            if status == 'failed':
                raise Exception(f"Transcription failed: {results}")
            
            if status == 'finished':
                logger.info("🎉 Transcription completed!")
                
                # Write final results
                with open(transcript_file, 'a', encoding='utf-8') as f:
                    f.write("FINAL TRANSCRIPTION COMPLETE\n")
                    f.write("=" * 80 + "\n")
                    
                    if "results" in results:
                        final_transcript = results["results"].get("transcript", "")
                        f.write("FINAL COMPLETE TRANSCRIPT:\n")
                        f.write(final_transcript)
                        f.write("\n\n")
                        
                        # Check for remaining seconds one more time
                        if "remaining seconds" in results:
                            self.remaining_seconds = results["remaining seconds"]
                
                # Return the complete transcript for PDF processing
                if "results" in results and "transcript" in results["results"]:
                    return results["results"]["transcript"], str(transcript_file)
                else:
                    raise Exception("No transcript found in final results")
            
            # Sleep for 15 seconds if still processing
            time.sleep(15)
        
        raise Exception("Unexpected response format")
    
    def get_remaining_minutes(self):
        """Convert remaining seconds to minutes for user display"""
        if self.remaining_seconds is not None:
            minutes = self.remaining_seconds / 60.0
            return minutes
        return None

class ClaudeClient:
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.prompt_template = self._load_prompt_template()
    
    def _load_prompt_template(self):
        """Load prompt template from file"""
        prompt_file = Path("claude_prompt_template.txt")
        
        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            # Create default template if file doesn't exist
            default_prompt = """Please create a professional IT meeting summary from this transcript. Format it with:

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
            
            # Save default template for future editing
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(default_prompt)
            
            logger.info(f"📝 Created default prompt template: {prompt_file}")
            return default_prompt
    
    def create_summary(self, transcript):
        """Generate meeting summary using Claude API"""
        logger.info("🤖 Generating summary with Claude...")
        
        prompt = self.prompt_template.format(transcript=transcript)
        
        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",  # Using Haiku for cost efficiency
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            summary = response.content[0].text
            logger.info("✅ Summary generated successfully")
            return summary
            
        except Exception as e:
            logger.error(f"❌ Claude API error: {e}")
            raise

class PDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        
        # Corporate Professional Color Scheme
        self.primary_blue = Color(0.18, 0.31, 0.67)      # Corporate blue
        self.accent_blue = Color(0.25, 0.45, 0.85)       # Lighter blue
        self.dark_grey = Color(0.2, 0.2, 0.2)            # Dark grey
        self.light_grey = Color(0.95, 0.95, 0.95)        # Light grey background
        self.medium_grey = Color(0.6, 0.6, 0.6)          # Medium grey
        self.timestamp_color = Color(0.4, 0.4, 0.8)      # Purple for timestamps
        
        # Professional Typography Styles
        self.title_style = ParagraphStyle(
            'CorporateTitle',
            fontName='Helvetica-Bold',
            fontSize=24,
            textColor=self.primary_blue,
            spaceAfter=20,
            spaceBefore=10,
            alignment=0,  # Left aligned
        )
        
        self.section_header_style = ParagraphStyle(
            'SectionHeader',
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=self.primary_blue,
            spaceAfter=12,
            spaceBefore=16,
            leftIndent=0,
        )
        
        self.subsection_header_style = ParagraphStyle(
            'SubsectionHeader',
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=self.dark_grey,
            spaceAfter=8,
            spaceBefore=12,
            leftIndent=10,
        )
        
        self.body_style = ParagraphStyle(
            'CorporateBody',
            fontName='Helvetica',
            fontSize=11,
            textColor=black,
            leading=16,  # Line height
            spaceAfter=8,
            spaceBefore=2,
            leftIndent=0,
            rightIndent=0,
            alignment=0,  # Left aligned
        )
        
        self.timestamp_style = ParagraphStyle(
            'TimestampStyle',
            fontName='Courier',
            fontSize=9,
            textColor=self.timestamp_color,
            leading=12,
            spaceAfter=4,
            spaceBefore=2,
            leftIndent=10,
        )
        
        self.speaker_style = ParagraphStyle(
            'SpeakerStyle',
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=self.primary_blue,
            leading=14,
            spaceAfter=6,
            spaceBefore=8,
            leftIndent=0,
        )
        
        self.bullet_style = ParagraphStyle(
            'CorporateBullet',
            fontName='Helvetica',
            fontSize=11,
            textColor=black,
            leading=15,
            spaceAfter=6,
            spaceBefore=2,
            leftIndent=20,
        )
        
        self.metadata_style = ParagraphStyle(
            'Metadata',
            fontName='Helvetica',
            fontSize=9,
            textColor=self.medium_grey,
            spaceAfter=20,
            spaceBefore=5,
            alignment=0,
        )
    
    def create_transcript_pdf(self, transcript_text, output_path, filename, transcript_file_path=None):
        """Create professionally formatted PDF from transcript with speaker/timestamp data"""
        logger.info(f"📄 Creating enhanced transcript PDF: {Path(output_path).name}")
        
        doc = SimpleDocTemplate(
            str(output_path), 
            pagesize=letter,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch
        )
        content = []
        
        # Professional header
        title = Paragraph("Meeting Transcript", self.title_style)
        content.append(title)
        
        # Subtitle with filename
        subtitle = Paragraph(f"Source: {filename}", self.subsection_header_style)
        content.append(subtitle)
        content.append(Spacer(1, 0.2*inch))
        
        # Metadata in professional format
        timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        meta_text = f"Generated on {timestamp} | Processed by SpeechText.AI"
        meta = Paragraph(meta_text, self.metadata_style)
        content.append(meta)
        
        # Add note about full transcript file
        if transcript_file_path:
            note_text = f"Complete transcript with timestamps: {Path(transcript_file_path).name}"
            note = Paragraph(note_text, self.metadata_style)
            content.append(note)
        
        # Separator line
        content.append(HRFlowable(width="100%", thickness=1, color=self.accent_blue))
        content.append(Spacer(1, 0.3*inch))
        
        # If we have the detailed transcript file, use it for enhanced formatting
        if transcript_file_path and Path(transcript_file_path).exists():
            content.extend(self._format_detailed_transcript(transcript_file_path))
        else:
            # Fallback to simple paragraph formatting
            paragraphs = self._split_transcript_into_paragraphs(transcript_text)
            for i, para in enumerate(paragraphs):
                if para.strip():
                    content.append(Paragraph(para.strip(), self.body_style))
                    if i < len(paragraphs) - 1:
                        content.append(Spacer(1, 0.12*inch))
        
        doc.build(content)
        logger.info("✅ Enhanced transcript PDF created successfully")
    
    def _format_detailed_transcript(self, transcript_file_path):
        """Format transcript with speaker identification and timestamps"""
        content = []
        
        try:
            with open(transcript_file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            # Look for the final complete transcript
            sections = file_content.split("FINAL COMPLETE TRANSCRIPT:")
            if len(sections) > 1:
                transcript_text = sections[1].strip()
            else:
                # Fallback to first transcript found
                sections = file_content.split("TRANSCRIPT CONTENT:")
                if len(sections) > 1:
                    transcript_text = sections[1].split("WORD-LEVEL TIMESTAMPS:")[0].strip()
                else:
                    transcript_text = "Transcript processing error - please check the full transcript file."
            
            # Format the transcript with better paragraph breaks
            paragraphs = self._split_transcript_into_paragraphs(transcript_text)
            
            for para in paragraphs:
                if para.strip():
                    content.append(Paragraph(para.strip(), self.body_style))
                    content.append(Spacer(1, 0.1*inch))
            
            # Add section for timestamp information
            content.append(Spacer(1, 0.2*inch))
            content.append(Paragraph("Detailed Analysis Available", self.section_header_style))
            note = Paragraph(
                f"Complete word-level timestamps, speaker identification, and confidence scores "
                f"are available in the full transcript file: {Path(transcript_file_path).name}",
                self.metadata_style
            )
            content.append(note)
            
        except Exception as e:
            logger.warning(f"⚠️ Could not format detailed transcript: {e}")
            content.append(Paragraph("Error reading detailed transcript file", self.body_style))
        
        return content
    
    def _split_transcript_into_paragraphs(self, text):
        """Intelligently split transcript into readable paragraphs"""
        paragraphs = text.split('\n\n')
        
        if len(paragraphs) == 1:
            sentences = text.split('. ')
            paragraphs = []
            current_para = ""
            sentence_count = 0
            
            for sentence in sentences:
                current_para += sentence.strip()
                if not sentence.endswith('.'):
                    current_para += ". "
                sentence_count += 1
                
                if (sentence_count >= 3 and len(current_para) > 200) or sentence_count >= 5:
                    paragraphs.append(current_para.strip())
                    current_para = ""
                    sentence_count = 0
                elif sentence_count < 5:
                    current_para += " "
            
            if current_para.strip():
                paragraphs.append(current_para.strip())
        
        return [p for p in paragraphs if p.strip()]
    
    def create_summary_pdf(self, summary_text, output_path, filename):
        """Create professionally formatted PDF from Claude summary"""
        logger.info(f"📄 Creating summary PDF: {Path(output_path).name}")
        
        doc = SimpleDocTemplate(
            str(output_path), 
            pagesize=letter,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch
        )
        content = []
        
        # Professional header
        title = Paragraph("Meeting Summary", self.title_style)
        content.append(title)
        
        # Subtitle
        subtitle = Paragraph(f"Meeting: {filename}", self.subsection_header_style)
        content.append(subtitle)
        content.append(Spacer(1, 0.2*inch))
        
        # Metadata
        timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        meta_text = f"Generated on {timestamp} | Summarized by Claude AI"
        meta = Paragraph(meta_text, self.metadata_style)
        content.append(meta)
        
        # Separator line
        content.append(HRFlowable(width="100%", thickness=1, color=self.accent_blue))
        content.append(Spacer(1, 0.3*inch))
        
        # Format summary content
        formatted_content = self._format_summary_content(summary_text)
        content.extend(formatted_content)
        
        doc.build(content)
        logger.info("✅ Professional summary PDF created successfully")
    
    def _format_summary_content(self, text):
        """Format summary content with professional styling"""
        content = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                content.append(Spacer(1, 0.1*inch))
                continue
            
            # Check for section headers (lines with **text**)
            if line.startswith('**') and line.endswith('**'):
                header_text = line.strip('*').strip()
                content.append(Paragraph(header_text, self.section_header_style))
                
            # Check for bullet points (lines starting with -)
            elif line.startswith('- '):
                bullet_text = line[2:].strip()
                content.append(Paragraph(f"• {bullet_text}", self.bullet_style))
                
            # Regular paragraph
            else:
                content.append(Paragraph(line, self.body_style))
        
        return content

class BatchProcessor:
    def __init__(self, speech_client, claude_client, pdf_generator):
        self.speech_client = speech_client
        self.claude_client = claude_client
        self.pdf_generator = pdf_generator
        
        # Windows Downloads directory via WSL
        self.downloads_dir = Path("/mnt/c/Users/MelvinJones/Downloads")
        self.output_dir = Path("meeting_outputs")
        self.output_dir.mkdir(exist_ok=True)
    
    def find_webm_files(self):
        """Find all .webm files in downloads directory"""
        if not self.downloads_dir.exists():
            logger.warning(f"⚠️ Downloads directory not found: {self.downloads_dir}")
            return []
        
        webm_files = list(self.downloads_dir.glob("*.webm"))
        logger.info(f"📁 Found {len(webm_files)} .webm files in downloads")
        return webm_files
    
    def move_webm_files(self, webm_files):
        """Move .webm files from downloads to meeting_outputs"""
        moved_files = []
        
        for webm_file in webm_files:
            destination = self.output_dir / webm_file.name
            
            # Skip if file already exists in output directory
            if destination.exists():
                logger.info(f"📄 File already exists: {webm_file.name}")
                moved_files.append(destination)
                continue
            
            try:
                shutil.move(str(webm_file), str(destination))
                logger.info(f"📦 Moved: {webm_file.name}")
                moved_files.append(destination)
            except Exception as e:
                logger.error(f"❌ Failed to move {webm_file.name}: {e}")
        
        return moved_files
    
    def get_files_needing_transcription(self, webm_files):
        """Find .webm files that don't have corresponding transcript PDFs"""
        files_to_process = []
        
        for webm_file in webm_files:
            base_name = webm_file.stem
            transcript_pdf = self.output_dir / f"{base_name}_transcript.pdf"
            
            if not transcript_pdf.exists():
                files_to_process.append(webm_file)
                logger.info(f"📝 Needs transcription: {webm_file.name}")
            else:
                logger.info(f"✅ Already transcribed: {webm_file.name}")
        
        return files_to_process
    
    def process_file(self, webm_file):
        """Process a single .webm file through the complete pipeline"""
        base_name = webm_file.stem
        
        transcript_pdf_path = self.output_dir / f"{base_name}_transcript.pdf"
        summary_pdf_path = self.output_dir / f"{base_name}_summary.pdf"
        
        try:
            # Step 1: Transcribe audio (gets full transcript + detailed file)
            transcript, transcript_file_path = self.speech_client.transcribe_file(webm_file)
            
            # Step 2: Create enhanced transcript PDF
            self.pdf_generator.create_transcript_pdf(
                transcript, transcript_pdf_path, base_name, transcript_file_path
            )
            
            # Step 3: Generate summary with Claude
            summary = self.claude_client.create_summary(transcript)
            
            # Step 4: Create summary PDF
            self.pdf_generator.create_summary_pdf(
                summary, summary_pdf_path, base_name
            )
            
            logger.info(f"🎉 Completed processing: {webm_file.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to process {webm_file.name}: {e}")
            return False
    
    def run_batch_processing(self):
        """Main batch processing workflow"""
        logger.info("🚀 Starting batch processing...")
        
        # Step 1: Find .webm files in downloads
        webm_files = self.find_webm_files()
        if not webm_files:
            logger.info("📭 No .webm files found in downloads directory")
            return
        
        # Step 2: Move files to output directory
        moved_files = self.move_webm_files(webm_files)
        
        # Step 3: Find files that need transcription
        files_to_process = self.get_files_needing_transcription(moved_files)
        
        if not files_to_process:
            logger.info("✅ All files already have transcripts")
            return
        
        logger.info(f"🎯 Processing {len(files_to_process)} files...")
        
        # Step 4: Process each file
        success_count = 0
        for webm_file in files_to_process:
            logger.info(f"\n📁 Processing: {webm_file.name}")
            if self.process_file(webm_file):
                success_count += 1
        
        # Step 5: Display remaining API time
        remaining_minutes = self.speech_client.get_remaining_minutes()
        if remaining_minutes is not None:
            logger.info(f"\n⏰ SpeechText.AI remaining time: {remaining_minutes:.1f} minutes")
        else:
            logger.warning("⚠️ Could not determine remaining API time")
        
        # Final summary
        logger.info(f"\n🎉 Batch processing complete!")
        logger.info(f"✅ Successfully processed: {success_count}/{len(files_to_process)} files")

def check_environment():
    """Check that all required environment variables are set"""
    required_vars = ['SPEECHTEXT_API_KEY', 'ANTHROPIC_API_KEY']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error("❌ Missing required environment variables:")
        for var in missing_vars:
            logger.error(f"   - {var}")
        logger.error("\nPlease set these in your .env file:")
        for var in missing_vars:
            logger.error(f"   {var}=your_api_key_here")
        return False
    
    return True

def main():
    """Main application entry point"""
    print("🚀 Enhanced Meeting Transcription Pipeline")
    print("Batch processing .webm files from Windows Downloads")
    print("Complete transcripts with speakers, timestamps, and summaries")
    print("=" * 70)
    
    # Check environment variables
    if not check_environment():
        return 1
    
    try:
        # Initialize clients
        speech_api_key = os.getenv('SPEECHTEXT_API_KEY')
        claude_api_key = os.getenv('ANTHROPIC_API_KEY')
        
        speech_client = SpeechTextClient(speech_api_key)
        claude_client = ClaudeClient(claude_api_key)
        pdf_generator = PDFGenerator()
        
        # Run batch processor
        processor = BatchProcessor(speech_client, claude_client, pdf_generator)
        processor.run_batch_processing()
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())