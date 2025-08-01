# Meeting Transcription & Summary Pipeline

An automated pipeline that processes meeting recordings (.webm files) into professional transcripts and AI-generated summaries. The system batch processes files from your Windows Downloads folder, transcribes them using SpeechText.AI, generates meeting summaries with Claude AI, and outputs professional PDF documents.

## Features

- **Batch Processing**: Automatically finds and processes all .webm files from Windows Downloads
- **Professional Transcription**: Uses SpeechText.AI for high-quality transcription with speaker identification and timestamps
- **AI-Powered Summaries**: Generates structured meeting summaries using Claude AI with customizable prompts
- **Professional PDF Output**: Creates beautifully formatted PDFs for both transcripts and summaries
- **Smart File Management**: Moves processed files and tracks completion status
- **Detailed Logging**: Comprehensive logging with progress tracking and API usage monitoring

## What It Does

1. **File Discovery**: Scans your Windows Downloads folder for .webm meeting recordings
2. **File Management**: Moves recordings to a dedicated `meeting_outputs` folder
3. **Transcription**: Sends audio to SpeechText.AI for transcription with speaker identification
4. **Enhanced Processing**: Captures word-level timestamps, confidence scores, and speaker data
5. **AI Summary**: Uses Claude AI to generate structured meeting summaries
6. **PDF Generation**: Creates professional PDFs for both transcripts and summaries
7. **Progress Tracking**: Only processes files that haven't been transcribed yet

## Output Files

For each meeting recording, the pipeline generates:

- `filename_transcript.pdf` - Professional transcript with speaker identification
- `filename_summary.pdf` - AI-generated meeting summary with action items
- `filename_full_transcript.txt` - Complete transcript with timestamps and metadata

## Prerequisites

- Python 3.7+
- SpeechText.AI API key
- Anthropic (Claude) API key
- Windows system with WSL (for Downloads folder access)

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd speechtext-audio-to-pdf-summary-pipeline
```

2. Set up your environment variables by creating a `.env` file:
```bash
SPEECHTEXT_API_KEY=your_speechtext_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Quick Start (Recommended)

Use the provided shell script that handles virtual environment setup automatically:

```bash
./run_meeting_pipeline.sh
```

This script will:
- Create a virtual environment if needed
- Install/update dependencies
- Run the pipeline
- Show completion status
- Optionally open the output directory

### Manual Execution

If you prefer to manage the environment yourself:

```bash
python meeting_pipeline.py
```

### First Run Setup

On first run, the pipeline will:
- Create a `meeting_outputs` directory
- Generate a default `claude_prompt_template.txt` file
- Set up logging and file structure

## Configuration

### Customizing Meeting Summaries

Edit `claude_prompt_template.txt` to customize how Claude generates your meeting summaries. The default template creates:

- **Executive Summary**: Main purpose and outcomes
- **Key Decisions Made**: Decisions reached with rationale
- **Action Items**: Tasks with owners and due dates
- **Technical Discussion Points**: Technical topics and details
- **Blockers & Risks**: Issues needing resolution
- **Next Steps**: Immediate actions and follow-ups

### File Locations

- **Input**: `/mnt/c/Users/[Username]/Downloads/*.webm` (Windows Downloads via WSL)
- **Output**: `./meeting_outputs/` (all generated files)
- **Config**: `./claude_prompt_template.txt` (summary template)

## API Usage & Costs

### SpeechText.AI
- Charges based on audio duration
- Provides speaker identification and timestamps
- Shows remaining API time after processing

### Anthropic Claude
- Uses Claude-3-Haiku model for cost efficiency
- Charges based on token usage
- Generates structured meeting summaries

## File Processing Logic

The pipeline intelligently handles file processing:

1. **Discovery**: Finds all .webm files in Downloads
2. **Movement**: Moves files to `meeting_outputs` folder
3. **Skip Logic**: Only processes files without existing transcript PDFs
4. **Error Handling**: Continues processing other files if one fails
5. **Status Tracking**: Reports success/failure for each file

## Output Examples

### Transcript PDF Features
- Professional corporate styling
- Speaker identification (when available)
- Timestamp references
- Clean paragraph formatting
- Metadata and generation info

### Summary PDF Features
- Executive summary format
- Structured sections with clear headers
- Action items with ownership
- Technical discussion points
- Professional business formatting

## Troubleshooting

### Common Issues

**No .webm files found**
- Check that files are in the correct Downloads directory
- Verify WSL path mapping is correct

**API key errors**
- Ensure `.env` file exists with correct API keys
- Check that environment variables are loaded

**Permission errors**
- Ensure write permissions for `meeting_outputs` directory
- Check file access permissions for Downloads folder

**Transcription failures**
- Verify audio file format is supported
- Check SpeechText.AI API quota and status
- Ensure stable internet connection

### Logging

The pipeline provides detailed logging:
- File discovery and movement status
- Transcription progress and completion
- API usage and remaining quotas
- PDF generation status
- Error details and troubleshooting info

## Development

### Project Structure
```
├── meeting_pipeline.py          # Main pipeline script
├── requirements.txt             # Python dependencies
├── run_meeting_pipeline.sh      # Automated runner script
├── claude_prompt_template.txt   # Claude summary template
├── .env                        # API keys (create this)
└── meeting_outputs/            # Generated files (auto-created)
```

### Key Classes
- `SpeechTextClient`: Handles audio transcription
- `ClaudeClient`: Manages AI summary generation
- `PDFGenerator`: Creates professional PDF documents
- `BatchProcessor`: Orchestrates the complete pipeline

## License

This project is provided as-is for meeting transcription and summary automation. 
