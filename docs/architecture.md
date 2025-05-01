# ESG Agent System Architecture

## Overview

The ESG Agent system is built around a multi-agent architecture that coordinates specialized LLM-based agents to produce comprehensive ESG reports. Each agent is responsible for a specific aspect of the reporting process, communicating with other agents through a well-defined pipeline orchestrated by the ExecutionAgent.

## Architecture Diagram

```
┌───────────────┐                  ┌───────────────────────┐
│  User Interface  │                 │     Google Gemini API    │
│   (Gradio UI)    │◄───────────────►│    (LLM Provider)       │
└───────┬─────────┘                 └───────────────────────┘
        │                                       ▲
        ▼                                       │
┌───────────────┐                               │
│  ExecutionAgent  │                             │
│  (Orchestrator)  │──────────────────────────────┘
└───────┬─────────┘
        │
        ├─────────────┬─────────────┬─────────────┬─────────────┐
        │             │             │             │             │
        ▼             ▼             ▼             ▼             ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  PlanningAgent  │ │ FrameworkAgent │ │  InfoGatherAgent │ │  ReportAgent   │ │    QAAgent     │
└───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘
```

## Component Descriptions

### 1. User Interface (Gradio)

-   Provides an interactive web interface for users to input company information, reporting period, and upload documents
-   Displays the generated ESG reports and progress updates
-   Allows users to provide API keys and configuration options

### 2. ExecutionAgent

-   Serves as the orchestration layer for the entire system
-   Manages the flow of information between specialized agents
-   Implements the iterative refinement process based on QA feedback
-   Handles error recovery and timeout management

### 3. PlanningAgent

-   Analyzes the user's query to understand report requirements
-   Validates input parameters (company name, stock symbol, reporting period)
-   Creates a structured plan for ESG report generation
-   Sets up constraints and guidelines for other agents

### 4. FrameworkAgent

-   Identifies relevant ESG frameworks (IFRS S1, IFRS S2, HKEX ESG Code)
-   Extracts framework-specific requirements for the report
-   Ensures compliance with standard reporting practices
-   Provides structure guidance based on regulatory requirements

### 5. InfoGatherAgent

-   Extracts relevant ESG information from company reports and documents
-   Processes PDF documents for sustainability-related data
-   Organizes extracted information according to framework requirements
-   Validates information quality and relevance

### 6. ReportAgent

-   Generates comprehensive ESG reports based on gathered information
-   Structures content according to standard ESG reporting practices
-   Ensures narrative coherence and completeness
-   Formats output for readability and professional presentation

### 7. QAAgent

-   Evaluates the quality of generated reports against framework requirements
-   Identifies areas for improvement in report content and structure
-   Provides feedback for iterative refinement
-   Assigns quality scores to guide the refinement process

## Data Flow

1. User inputs company information and uploads documents
2. ExecutionAgent triggers PlanningAgent to validate and structure the request
3. FrameworkAgent identifies relevant ESG frameworks and requirements
4. InfoGatherAgent analyzes company documents for relevant ESG information
5. ReportAgent generates an initial ESG report based on gathered information
6. QAAgent evaluates the report quality and identifies areas for improvement
7. ExecutionAgent coordinates refinement iterations until quality thresholds are met
8. Final ESG report is presented to the user through the UI

## Technologies Used

-   **Google Gemini**: Advanced language models for specialized agent functions
-   **Python**: Core programming language for the system
-   **Gradio**: UI framework for interactive interfaces
-   **PDF Processing**: Tools for extracting information from documents
-   **Pydantic**: Data validation and serialization
