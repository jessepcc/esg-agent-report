# @title Helper Functions
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import json

from google.genai import types
from pydantic import BaseModel
from rich import print as rich_print


class QueryValidation(BaseModel):
    """Simplified validation structure focusing on cities and suggestions"""
    company: str
    stock_symbol: str
    start_month_year: str
    end_month_year: str
    is_valid: bool
    missing_elements: List[str]
    suggestions: str


class PlanStepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class BasicInfo:
    company: str
    stock_symbol: str
    start_month_year: str
    end_month_year: str


class PlanStep(BaseModel):
    step_id: int
    agent_name: str
    description: str
    input_requirements: List[str]
    output_format: str
    status: PlanStepStatus = PlanStepStatus.PENDING
    error: Optional[str] = None
    skip_conditions: Optional[Dict[str, str]] = None


class ExecutionPlan(BaseModel):
    query: str
    timestamp: datetime
    validated_query: QueryValidation
    enable_search: bool
    steps: List[PlanStep]
    debug: bool
    max_iterations: int = 3  # Maximum number of refinement iterations
    min_qa_score: float = 80.0  # Minimum QA score to consider the report satisfactory
    refinement_enabled: bool = True  # Whether to enable the refinement loop


def detect_visualization_need(query: str) -> bool:
    """Analyze if query mentions any specific keyword for visualization.

    Look for:
    - Explicit visualization requests: "plot", "chart", "graph", "visualize"

    Args:
        query: User's query about EV infrastructure

    Returns:
        bool: True if visualization asked, False otherwise
    """
    return True  # Model will determine based on above criteria


def detect_search_need(query: str) -> bool:
    """Analyze if query requests or requires enhanced search/grounding.

    Look for:
    - Research keywords: "detailed research", "comprehensive", "grounded", "ground with search", "enhance sections", "cross check citations"

    Args:
        query: User's query about EV infrastructure

    Returns:
        bool: True if enhanced search is asked, False otherwise
    """
    return True  # Model will determine based on above criteria


class PlanningAgent(BaseModel):
    """Main planning agent that creates execution plan"""

    query: str
    client: Any
    model_name: str
    debug: bool = False
    api_key: Optional[str] = None

    def _validate_query(self) -> QueryValidation:
        """Step 0: Validates query for valid company and provides enhancement suggestions"""
        try:

            # validate if query contains ESG keywords
            esg_keywords = ["ESG", "sustainability", "environmental", "social", "governance"]
            if not any(keyword in self.query for keyword in esg_keywords):
                return QueryValidation(
                    company="",
                    stock_symbol="",
                    start_month_year="",
                    end_month_year="",
                    is_valid=False,
                    missing_elements=["ESG keywords"],
                    suggestions=f"""Please specify ESG keywords in your query.
                  
                  Example queries:
                  1. "Analyze Tesla's ESG performance"
                  2. "Compare Apple and Google ESG ratings"
                  3. "Show historical data for Microsoft's sustainability efforts"
                  """,
                )

            
            # Extract potential cities from query
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=f"""Extract information from the query. If any of the fields are missing or it is relevant oto ESG reporting for listed company in Hong Kong, please return empty string for that field.
            
                All fields are required.
                Important: Only return a single piece of valid JSON object.
                Here is the query: {self.query}
                
                """,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BasicInfo,
                    temperature = 0,
                    top_p = 1,
                ),
            )

            response_json = json.loads(response.text)
            print(response_json)
               
            company = response_json.get("company", "")
            stock_symbol = response_json.get("stock_symbol", "")
            start_month_year = response_json.get("start_month_year", "")
            end_month_year = response_json.get("end_month_year", "")


            # Build validation result
            if not company or not stock_symbol:
                return QueryValidation(
                    company=company,
                    stock_symbol=stock_symbol,
                    start_month_year=start_month_year,
                    end_month_year=end_month_year,
                    is_valid=False,
                    missing_elements=["company", "stock_symbol"],
                    suggestions=f"""Please specify a valid company and stock symbol.
                        Example queries:
                        1. "Analyze Tesla's stock performance"
                        2. "Compare Apple and Google stock prices"
                        3. "Show historical data for Microsoft"
                    """,
                )

            return QueryValidation(
                company=company,
                stock_symbol=stock_symbol,
                start_month_year=start_month_year,
                end_month_year=end_month_year,
                is_valid=True,
                missing_elements=[],
                suggestions=f"""Query is valid. Proceed with analysis for {company} ({stock_symbol}) in time period {start_month_year} - {end_month_year}.""",
            )

        except Exception as e:
            if self.debug:
                print(f"Validation error details: {str(e)}")
            return QueryValidation(
                company="",
                stock_symbol="",
                start_month_year="",
                end_month_year="",
                is_valid=False,
                missing_elements=["company", "stock_symbol"],
                suggestions=f"""Unable to process the query. Please try again with a valid company and stock symbol.""",
            )

    def _determine_search_requirement(self) -> bool:
        """Uses function calling to check search/grounding needs"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=f"Return only true or false: Does this query need enhanced search/grounding? '{self.query}'",
                config=types.GenerateContentConfig(tools=[detect_search_need]), # TODO: Add function to detect search need, now set to True
            )
            if self.debug:
                print("Search response: ", response.text)
                print("Search response Bool: ", bool(response.text))

            return response.text

        except Exception as e:
            if self.debug:
                print(f"Search detection error: {str(e)}")
            return False

    def _create_steps(
        self, validated_query: QueryValidation, enable_search: bool
    ) -> List[PlanStep]:
        """Creates appropriate steps based on validation results"""
        steps = []


        # Only create steps if query is valid
        if validated_query.is_valid:
            # Step 1: Always include Framework Gathering
            steps.append(
                PlanStep(
                    step_id=1,
                    agent_name="FrameworkAgent",
                    description="Gather ESG framework requirements",
                    input_requirements=["company", "stock_symbol"],
                    output_format="FrameworkAgentOutput model",
                    skip_conditions=None,
                )
            )

            # Step 2: Information Gathering
            steps.append(
                PlanStep(
                    step_id=2,
                    agent_name="InfoGatherAgent",
                    description="Gather ESG information based on framework",
                    input_requirements=["FrameworkAgent result", "validated_query"],
                    output_format="InfoGatherAgentOutput model",
                    skip_conditions=None,
                )
            )
            
            # Step 3: Report Generation
            steps.append(
                PlanStep(
                    step_id=3,
                    agent_name="ReportAgent",
                    description="Generate ESG report based on framework and gathered information",
                    input_requirements=[
                        "FrameworkAgent result",
                        "InfoGatherAgent result",
                        "reporting_period"
                    ],
                    output_format="Report model",
                    skip_conditions=None,
                )
            )

            # Step 4: Quality Assurance
            steps.append(
                PlanStep(
                    step_id=4,
                    agent_name="QAAgent",
                    description="Evaluate the report quality and provide feedback",
                    input_requirements=["ReportAgent result"],
                    output_format="QA Evaluation model",
                    skip_conditions=None,
                )
            )
            
            # Step 5: Refinement Loop
            steps.append(
                PlanStep(
                    step_id=5,
                    agent_name="RefinementLoop",
                    description="Iteratively refine the report based on QA feedback",
                    input_requirements=[
                        "QAAgent result", 
                        "FrameworkAgent result", 
                        "InfoGatherAgent result", 
                        "ReportAgent result"
                    ],
                    output_format="Refined Report model",
                    skip_conditions={"refinement_enabled": "False"},
                )
            )
           
        return steps

    def create_plan(self) -> ExecutionPlan:
        """Creates execution plan based on query and configuration"""
        # Step 0: Validate query
        if not self.debug:
            rich_print(
                "[bold yellow]ℹ️ Warning: Concocting the perfect plan! It's like a recipe, but with more algorithms and less chance of burning the kitchen down.  Want to see the secret ingredients? debug=True is your cookbook!  (And if you want to see the output of each agent stage, set stage_output=True!) 👨‍🍳🧪 [/bold yellow]"
            )

        validated_query = self._validate_query()

        if not validated_query.is_valid:
            # If query is invalid, create plan with no steps
            return ExecutionPlan(
                query=self.query,
                timestamp=datetime.now(),
                validated_query=validated_query,
                enable_search=False,
                steps=[],
                debug=self.debug,
                refinement_enabled=False
            )

        # Determine if search is needed
        enable_search_toggle = self._determine_search_requirement().strip()
        if self.debug:
            print("Search toggle: ", enable_search_toggle)

        # Create steps based on validation
        steps = self._create_steps(validated_query, enable_search_toggle)

        # Check if refinement should be enabled based on query
        refinement_enabled = True
        if "no refinement" in self.query.lower() or "skip refinement" in self.query.lower():
            refinement_enabled = False
            if self.debug:
                print("Refinement disabled based on query")

        # Create execution plan
        plan = ExecutionPlan(
            query=self.query,
            timestamp=datetime.now(),
            validated_query=validated_query,
            enable_search=enable_search_toggle,
            steps=steps,
            debug=self.debug,
            refinement_enabled=refinement_enabled
        )

        return plan
