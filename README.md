# ESG Reporting Agent System

## Overview

This project demonstrates an advanced LLM-based agent system that generates professional ESG (Environmental, Social, and Governance) reports. The system leverages Google's Gemini models to create comprehensive reports that comply with industry frameworks like IFRS standards and HKEX ESG Code.

> **Note:**  
> This project is built **without any LLM orchestration frameworks** (e.g., LangChain, LlamaIndex).  
> All agent logic, prompt engineering, and data pipelines are implemented from scratch using standard Python and direct API calls to Google Gemini.

### Key Features

-   **Multi-Agent Architecture**: Specialized agents work together to create comprehensive reports
-   **Framework Compliance**: Ensures reports comply with IFRS S1, IFRS S2, and HKEX ESG Code
-   **Intelligent Information Gathering**: Analyzes PDF reports and extracts relevant ESG information
-   **Quality Assurance**: Built-in QA agent ensures report quality with iterative refinement
-   **Interactive UI**: User-friendly interface for report generation with Gradio

## System Architecture

The system implements a coordinated multi-agent architecture where specialized AI agents handle different aspects of ESG report generation:

![ESG Agent System](/images/system_architecture.png)

### Agent Components

1. **ExecutionAgent**: Orchestrates the entire workflow and manages agent interactions
2. **PlanningAgent**: Creates structured plan based on user query and validates inputs
3. **FrameworkAgent**: Identifies and applies relevant ESG reporting frameworks
4. **InfoGatherAgent**: Extracts ESG information from company documentation and reports
5. **ReportAgent**: Generates comprehensive ESG reports based on gathered information
6. **QAAgent**: Evaluates report quality and suggests improvements

For more details on the system architecture, see the [architecture documentation](docs/architecture.md).

## Installation & Setup

### Prerequisites

-   Python 3.9+
-   Google Gemini API key

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/esg-reporting-agent.git
cd esg-reporting-agent

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Launch the Gradio UI
python src/ui/esg_gradio.py
```

### Using Docker

```bash
# Build the Docker image for the Gradio interface
docker build -f docker/Dockerfile.gradio -t esg-agent-gradio .

# Run the container
docker run -p 7860:7860 -e GOOGLE_API_KEY=your_api_key esg-agent-gradio
```

## Usage

1. Enter your Google API key (or use Vertex AI authentication)
2. Specify the company name and stock symbol
3. Define the reporting period
4. Provide a PDF URL with ESG information
5. Click "Generate ESG Report" and wait for the system to create your report

## Technical Details

### Multi-Agent Architecture

This system demonstrates an advanced application of LLM agents with specialized roles:

-   Each agent has a specific focus area and prompt engineering
-   Agents communicate through a structured data pipeline
-   The ExecutionAgent orchestrates the workflow and handles refinement

### Prompt Engineering Techniques

The project showcases several advanced prompt engineering approaches:

-   Task-specific context and instructions for each agent
-   Structured output formats to ensure consistent processing
-   Few-shot examples to guide model outputs
-   System messages that define agent roles and responsibilities

### Iterative Refinement Process

The system implements an iterative refinement process:

1. Generate initial ESG report based on gathered information
2. Evaluate quality using the QA agent
3. Identify specific areas for improvement
4. Target refinement to specific aspects of the report
5. Repeat until quality thresholds are met

## Project Structure

```text
esg-agent-portfolio/
├── README.md                     # Comprehensive project overview
├── LICENSE                       # Open source license
├── requirements.txt              # Dependencies
├── docs/                         # Documentation
│   ├── architecture.md           # System architecture details
│   ├── agent_design.md           # Agent design specifications
│   ├── images/                   # Diagrams and screenshots
│   └── examples/                 # Example reports
├── src/                          # Source code
│   ├── esg_agent/                # Core agent implementation
│   │   └── agent_handler/        # Agent implementations
│   ├── ui/                       # User interfaces
│   │   └── esg_gradio.py         # Gradio UI
│   └── utils/                    # Utility functions
├── tests/                        # Test cases
└── docker/                       # Docker configurations
    ├── Dockerfile.gradio         # Gradio interface Dockerfile
    └── Dockerfile.streamlit      # Streamlit interface Dockerfile
```

## Example Reports

See the [examples folder](docs/examples/) for sample reports generated by the system.

## Agent Design

For detailed information on the agent design and interactions, see the [agent design documentation](docs/agent_design.md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Future Enhancements

-   Integration with company financial databases for automated data gathering
-   Support for additional ESG frameworks and standards
-   Enhanced visualization of ESG metrics and performance
-   Comparative analysis against industry benchmarks
-   Multi-language support for international reporting requirements
