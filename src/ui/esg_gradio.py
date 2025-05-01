import gradio as gr
import asyncio
import os
import logging
import json
import traceback
from datetime import datetime
from io import StringIO
from google import genai
from esg_agent.agent_handler.agent_01_ExecutionAgent import ExecutionAgent

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LogCapture:
    def __init__(self):
        self.logs = StringIO()
        self.handler = logging.StreamHandler(self.logs)
        self.handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
    def start_capture(self):
        root_logger = logging.getLogger()
        root_logger.addHandler(self.handler)
        
    def stop_capture(self):
        root_logger = logging.getLogger()  # Fixed: define root_logger
        root_logger.removeHandler(self.handler)
        
    def get_logs(self):
        return self.logs.getvalue()

# Async function needs a wrapper to ensure it's properly executed in Gradio
def generate_report_wrapper(*args):
    """Wrapper to run async function in event loop"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # If no event loop exists, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(generate_report(*args))

async def generate_report(api_key, company, symbol, start_date, end_date, pdf_url, debug_mode):
    # Set up progress tracking
    log_capture = LogCapture()
    log_capture.start_capture()
    
    try:
        # Configure the client
        if api_key and api_key.strip():
            client = genai.Client(api_key=api_key)
        else:
            client = genai.Client(vertexai=True)
        
        # Log setup success
        logger.info("AI client successfully initialized")
        
        # Construct the query
        query = f"Please generate an ESG report for {company}, {symbol} for the period {start_date} to {end_date}"
        if pdf_url and pdf_url.strip():
            query += f". Analyze the PDF document at this URL: {pdf_url}"
        
        # Create the execution agent
        agent = ExecutionAgent.create(
            client=client,
            model_name="gemini-2.0-flash-001",
            model_search="gemini-1.5-flash-002",
            api_key=api_key,
            debug=debug_mode,
            stage_output=debug_mode,
            info_gather_timeout=600,
            max_iterations=3,
            min_qa_score=80.0,
            pdf_url=pdf_url if pdf_url and pdf_url.strip() else None
        )
        
        # Execute the agent
        logger.info(f"Starting agent execution with query: {query}")
        results = await agent.execute(query)
        
        # Extract report
        if "report" in results and hasattr(results["report"], "text"):
            report_text = results["report"].text
            logs = log_capture.get_logs()
            
            # Create output directory if it doesn't exist
            os.makedirs("reports", exist_ok=True)
            
            # Save report to file
            filename = f"reports/ESG_Report_{company}_{datetime.now().strftime('%Y%m%d')}.md"
            with open(filename, "w") as f:
                f.write(report_text)
                
            # Save logs to file
            logs_filename = f"reports/ESG_Report_Logs_{company}_{datetime.now().strftime('%Y%m%d')}.txt"
            with open(logs_filename, "w") as f:
                f.write(logs)
                
            return report_text, logs, filename, logs_filename
        else:
            error_msg = "Could not extract report from results"
            logger.error(error_msg)
            return None, log_capture.get_logs(), None, None
            
    except Exception as e:
        error_msg = f"Error during execution: {str(e)}"
        logger.error(f"Exception: {error_msg}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None, log_capture.get_logs() + f"\n\nERROR: {str(e)}\n{traceback.format_exc()}", None, None
    finally:
        log_capture.stop_capture()

def download_file(filename):
    """Improved download function that handles missing files gracefully"""
    try:
        if filename and os.path.exists(filename):
            with open(filename, "r") as f:
                return f.read()
        else:
            return "File not found or not specified"
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {str(e)}")
        return f"Error downloading file: {str(e)}"

# Create the interface
with gr.Blocks() as demo:
    gr.Markdown("# ESG Report Generator")
    gr.Markdown("Generate comprehensive ESG reports using AI agents")
    
    with gr.Row():
        with gr.Column(scale=1):
            # Input components
            api_key = gr.Textbox(label="Google AI API Key (optional if using Vertex AI)", type="password")
            company = gr.Textbox(label="Company Name", value="HSBC")
            symbol = gr.Textbox(label="Stock Symbol", value="0005.HK")
            start_date = gr.Textbox(label="Start Date", value="Apr 2023")
            end_date = gr.Textbox(label="End Date", value="Mar 2024")
            pdf_url = gr.Textbox(label="PDF URL", placeholder="Enter URL to PDF for additional analysis")
            debug_mode = gr.Checkbox(label="Debug Mode", value=True)
            
            # Button to start generation
            generate_btn = gr.Button("Generate ESG Report")
            
            # Status display and progress indicator
            status = gr.Markdown("Ready to generate report")
            progress = gr.Markdown("")
            
        with gr.Column(scale=2):
            # Output components
            report_md = gr.Markdown("Report output will appear here")
            
            with gr.Accordion("Debug Logs", open=False):
                logs_output = gr.Code(language="markdown")
            
            download_report_btn = gr.Button("Download Report", visible=False)
            download_logs_btn = gr.Button("Download Logs", visible=False)
    
    # Define state variables for filenames
    report_file = gr.State("")
    logs_file = gr.State("")
    
    def start_generation(*args):
        return "Generating report... Please wait.", gr.update(interactive=False), "This may take several minutes..."
    
    def handle_output(report, logs, report_filename, logs_filename):
        
        if report:
            return (
                "Report generation complete!",
                gr.update(interactive=True),
                "",  # Clear progress message
                report,
                logs,
                gr.update(visible=True),
                gr.update(visible=True),
                report_filename,
                logs_filename
            )
        else:
            return (
                "Error generating report. See logs for details.",
                gr.update(interactive=True),
                "",  # Clear progress message
                "Failed to generate report",
                logs,
                gr.update(visible=False),
                gr.update(visible=True),
                None,
                logs_filename
            )
    
    # Set up event handling
    generate_btn.click(
        fn=start_generation,
        inputs=[],
        outputs=[status, generate_btn, progress]
    ).then(
        fn=generate_report_wrapper,  # Use the wrapper instead of the async function directly
        inputs=[api_key, company, symbol, start_date, end_date, pdf_url, debug_mode],
        outputs=[report_md, logs_output, report_file, logs_file]
    ).then(
        fn=handle_output,
        inputs=[report_md, logs_output, report_file, logs_file],
        outputs=[
            status, generate_btn, progress, report_md, logs_output, 
            download_report_btn, download_logs_btn, report_file, logs_file
        ]
    )
    
    # Download handlers with improved error handling
    download_report_btn.click(
        fn=lambda filename: gr.update(value=filename) if filename else None,
        inputs=[report_file],
        outputs=[gr.File(interactive=True, visible=False, elem_id="download_report")]
    )

    download_logs_btn.click(
        fn=lambda filename: gr.update(value=filename) if filename else None,
        inputs=[logs_file],
        outputs=[gr.File(interactive=True, visible=False, elem_id="download_logs")]
    )

# Launch the app
if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 7860))
        demo.launch(server_name="0.0.0.0", server_port=port, share=True)
        print("Gradio app launched successfully.")
    except Exception as e:
        print(f"Error launching Gradio app: {str(e)}")
        traceback.print_exc()