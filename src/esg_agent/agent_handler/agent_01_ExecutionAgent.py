# @title Helper Functions

from typing import Any, Dict, Optional, Union
import time
import asyncio
import os
import httpx

from esg_agent.agent_handler.agent_02_PlanningAgent import PlanningAgent
from esg_agent.agent_handler.agent_03_FrameworkAgent import FrameworkAgent, print_debug
from esg_agent.agent_handler.agent_04_InfoGatherAgent import InfoGatherAgent
from esg_agent.agent_handler.agent_05_ReportAgent import ReportAgent
from esg_agent.agent_handler.agent_06_QAAgent import QAAgent
from pydantic import BaseModel
from rich import print as rich_print
from termcolor import colored


class ExecutionAgent(BaseModel):
    """🤖 The conductor of our ESG reporting orchestra!
    Coordinates planning and execution of the analysis pipeline."""

    client: Any
    model_name: str
    model_search: str
    api_key: Optional[str] = None
    debug: bool = False
    stage_output: bool = False
    output_type: Optional[str] = None
    info_gather_timeout: int = 600  # 10 minute default timeout for info gathering
    max_iterations: int = 3  # Maximum number of refinement iterations
    min_qa_score: float = 80.0  # Minimum QA score to consider the report satisfactory
    pdf_url: str  # URL to a PDF file for ESG report analysis

    def _debug_print(self, message: str, color: str = "blue") -> None:
        """Print colorful debug messages when debug is enabled"""
        if self.debug:
            try:
                print(colored(f"🔍 Debug: {message}", color))
            except:
                # Fallback if termcolor fails
                print(f"🔍 Debug: {message}")

    def _handle_error(self, step: str, error: Exception) -> None:
        """Handle errors with style and grace"""
        error_msg = f"💥 Error in {step}: {str(error)}"
        print(colored(error_msg, "red"))
        if self.debug:
            import traceback
            print(colored(f"📚 Traceback:\n{traceback.format_exc()}", "yellow"))
        raise Exception(error_msg)
        
    def _determine_next_agent(self, qa_output: Dict, framework_output: Dict, info_output: Dict) -> str:
        """
        Determine which agent to call next based on QA results.
        
        This function analyzes the QA output to identify the weakest areas and 
        determines which agent should be called to address those issues.
        
        Returns:
            str: The name of the agent to call next ('framework', 'info', or 'report')
        """
        try:
            # Extract scores from QA output
            rating_eval = qa_output.get("report_rating", {})
            
            # Check if we have a structured rating result
            if hasattr(rating_eval, "clarity_transparency"):
                # Get scores for each category
                clarity_score = rating_eval.clarity_transparency.get("score", 0)
                governance_score = rating_eval.governance_accountability.get("score", 0)
                risk_score = rating_eval.risk_management.get("score", 0)
                metrics_score = rating_eval.metrics_targets.get("score", 0)
                stakeholder_score = rating_eval.stakeholder_engagement.get("score", 0)
                
                # Determine the weakest areas
                scores = {
                    "clarity": clarity_score,
                    "governance": governance_score,
                    "risk": risk_score,
                    "metrics": metrics_score,
                    "stakeholder": stakeholder_score
                }
                
                weakest_area = min(scores, key=scores.get)
                self._debug_print(f"Weakest area identified: {weakest_area} with score {scores[weakest_area]}", "yellow")
                
                # Map weakest areas to agents
                if weakest_area in ["governance", "risk"]:
                    return "framework"  # Framework issues - call FrameworkAgent
                elif weakest_area in ["metrics", "stakeholder"]:
                    return "info"  # Information issues - call InfoGatherAgent
                else:
                    return "report"  # Clarity issues - call ReportAgent
            
            # If we don't have structured data, analyze the content evaluation
            content_eval = qa_output.get("content_evaluation", "")
            if isinstance(content_eval, str):
                # Simple keyword analysis
                framework_keywords = ["governance", "board", "oversight", "structure", "accountability"]
                info_keywords = ["data", "metrics", "information", "evidence", "sources", "stakeholder"]
                report_keywords = ["clarity", "structure", "presentation", "organization", "format"]
                
                # Count keyword occurrences
                framework_count = sum(1 for keyword in framework_keywords if keyword.lower() in content_eval.lower())
                info_count = sum(1 for keyword in info_keywords if keyword.lower() in content_eval.lower())
                report_count = sum(1 for keyword in report_keywords if keyword.lower() in content_eval.lower())
                
                # Determine which area has the most mentions (likely the most problematic)
                counts = {"framework": framework_count, "info": info_count, "report": report_count}
                return max(counts, key=counts.get)
            
            # Default to report agent if we can't determine
            return "report"
            
        except Exception as e:
            self._debug_print(f"Error determining next agent: {str(e)}. Defaulting to report agent.", "red")
            return "report"

    async def execute(self, query: str) -> Union[Dict, str, tuple]:
        """🎭 The main show! Execute the analysis pipeline with agentic refinement"""
        try:
            start_time = time.time()
            self._debug_print("🎯 Starting ESG Report Generation...", "cyan")
            
            # Check PDF URL file size
            try:
                self._debug_print(f"Checking PDF file size for URL: {self.pdf_url}", "cyan")
                response = httpx.head(self.pdf_url, follow_redirects=True)
                
                # Check if the request was successful
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"Failed to access PDF URL. Status code: {response.status_code}",
                    }
                
                # Get content length from headers
                content_length = int(response.headers.get('content-length', 0))
                size_mb = content_length / (1024 * 1024)  # Convert to MB
                
                # Check if file size exceeds limit (20MB)
                if size_mb > 20:
                    return {
                        "status": "error",
                        "message": f"PDF file size ({size_mb:.2f}MB) exceeds the 20MB limit",
                    }
                
                self._debug_print(f"PDF file size: {size_mb:.2f}MB (within limit)", "green")
            except Exception as e:
                self._handle_error("PDF URL validation", e)
                return {
                    "status": "error",
                    "message": f"Failed to validate PDF URL: {str(e)}",
                }
            
            if self.stage_output:
                print("self.stage_output", self.stage_output)
                print("self.debug", self.debug)
            
            # 🎬 Act 1: Planning Phase
            self._debug_print("🎯 Starting Planning Phase...", "cyan")
            planning_agent = PlanningAgent(
                query=query,
                client=self.client,
                model_name=self.model_name,
                debug=self.debug,
                api_key=self.api_key,
            )
            plan = planning_agent.create_plan()
            
            if not plan.validated_query.is_valid:
                return {
                    "status": "error",
                    "message": "Invalid query",
                    "suggestions": plan.validated_query.suggestions,
                }
            
            if self.stage_output:
                rich_print(plan)
                
            # 🎭 Act 2: Execution Phase with Refinement Loop
            results = {"plan": plan}
            
            # Process company and stock symbol
            company = plan.validated_query.company
            stock_symbol = plan.validated_query.stock_symbol
            
            if not company or not stock_symbol:
                return {
                    "status": "error",
                    "message": "Missing company or stock symbol",
                    "suggestions": "Please provide a valid company and stock symbol"
                }
                
            self._debug_print(f"Processing for {company} ({stock_symbol})...", "green")
            
            # Initialize variables for the refinement loop
            current_iteration = 0
            best_qa_score = 0
            best_results = {}
            next_agent = "framework"  # Start with framework agent in the first iteration
            
            # Start the refinement loop
            while current_iteration < self.max_iterations:
                current_iteration += 1
                self._debug_print(f"🔄 Starting iteration {current_iteration} of {self.max_iterations}", "cyan")
                
                # Scene 1: Framework Gathering
                if current_iteration == 1 or next_agent == "framework":
                    self._debug_print("📘 Gathering IFRS Framework Requirements...", "green")
                    framework_agent = FrameworkAgent(
                        client=self.client,
                        model_name=self.model_name,
                        debug=self.debug
                    )
                    
                    framework_output = framework_agent.process(company, stock_symbol)
                    
                    if framework_output.status == "error":
                        self._handle_error("framework gathering", Exception(framework_output.error))
                        
                    results["framework"] = framework_output
                    
                    if self.stage_output:
                        rich_print(framework_output)
                
                # Scene 2: Information Gathering
                if current_iteration == 1 or next_agent == "info":
                    self._debug_print("📊 Gathering ESG Information...", "green")
                    report_paths = []
                    
                    # Check if report_paths are provided in the query
                    if hasattr(plan, "report_paths") and plan.report_paths:
                        report_paths = plan.report_paths
                    
                    # Add the PDF URL to report_paths
                    if not report_paths:
                        report_paths = [self.pdf_url]
                        self._debug_print(f"Using PDF URL for analysis: {self.pdf_url}", "cyan")
                    
                    # Create InfoGatherAgent with improved handling
                    info_agent = InfoGatherAgent(
                        client=self.client,
                        model_name=self.model_name,
                        debug=self.debug,
                        report_paths=report_paths
                    )
                    
                    # Set custom timeout if needed based on report size/complexity
                    info_agent.set_timeout(self.info_gather_timeout)
                    
                    try:
                        # Use asyncio.wait_for to set a global timeout on the entire process
                        info_gather_start = time.time()
                        self._debug_print(f"Starting InfoGatherAgent process with {len(report_paths)} report files...", "cyan")
                        
                        info_output = info_agent.process(
                            framework_output=results["framework"],
                            validated_query=plan.validated_query,
                            report_paths=report_paths
                        )
                        
                        info_gather_duration = time.time() - info_gather_start
                        self._debug_print(f"InfoGatherAgent completed in {info_gather_duration:.1f}s", "green")
                        
                        if info_output.status == "error":
                            self._handle_error("info gathering", Exception(info_output.error))
                            
                        results["info"] = info_output
                        
                        if self.stage_output:
                            rich_print(info_output)
                    except Exception as e:
                        self._handle_error("info gathering", e)
                
                # Scene 3: Report Generation
                self._debug_print("📝 Generating ESG Report...", "green")
                report_agent = ReportAgent(
                    client=self.client,
                    model_name=self.model_name,
                    debug=self.debug
                )
                
                # Determine reporting period from query
                start_month_year = None
                end_month_year = None
                if hasattr(plan.validated_query, "reporting_period") and plan.validated_query.reporting_period:
                    period = plan.validated_query.reporting_period
                    if isinstance(period, dict) and "start" in period and "end" in period:
                        start_month_year = period["start"]
                        end_month_year = period["end"]
                
                # Generate the report
                try:
                    report_output = report_agent.generate_report(
                        framework_output=results["framework"],
                        info_gather_output=results["info"],
                        start_month_year=start_month_year,
                        end_month_year=end_month_year
                    )
                    
                    results["report"] = report_output
                    
                    if self.stage_output:
                        rich_print(report_output)
                except Exception as e:
                    self._handle_error("report generation", e)
                
                # Scene 4: Quality Assurance
                self._debug_print("🔍 Performing Quality Assurance Check...", "green")
                qa_agent = QAAgent(
                    client=self.client,
                    model_name=self.model_name,
                    debug=self.debug
                )
                
                try:
                    # Extract report text from the generated report
                    report_text = report_output.text if hasattr(report_output, "text") else str(report_output)
                    
                    # Evaluate the report
                    qa_output = qa_agent.rate_report(report_text)
                    
                    results["qa"] = qa_output
                    
                    if self.stage_output:
                        rich_print(qa_output)
                        
                    # Check if we've reached the target score
                    current_score = 0
                   

                    if "rating_evaluation" in qa_output and "average_score" in qa_output:
                        current_score = qa_output["average_score"] * 10  # Convert 0-10 to 0-100
                    elif "rating_evaluation" in qa_output and hasattr(qa_output["rating_evaluation"], "average_score"):
                        current_score = qa_output["rating_evaluation"].average_score() * 10
                    else:
                        raise ValueError("Invalid QA output format")
                    
                    self._debug_print(f"Current QA score: {current_score:.2f}/100", "yellow")
                    
                    # Keep track of the best results so far
                    if current_score > best_qa_score:
                        best_qa_score = current_score
                        best_results = results.copy()
                        self._debug_print(f"New best score: {best_qa_score:.2f}/100", "green")
                    
                    # Check if we've reached the target score
                    if current_score >= self.min_qa_score:
                        self._debug_print(f"🎉 Target QA score reached: {current_score:.2f}/100", "green")
                        break
                        
                    # Determine which agent to call next based on QA results
                    next_agent = self._determine_next_agent(qa_output, results["framework"], results["info"])
                    self._debug_print(f"Next agent to call: {next_agent}", "cyan")
                    
                except Exception as e:
                    self._handle_error("quality assurance", e)
                    next_agent = "report"  # Default to report agent if QA fails
            
            # Use the best results if we've gone through multiple iterations
            if best_qa_score > 0:
                results = best_results
                self._debug_print(f"Using best results with QA score: {best_qa_score:.2f}/100", "green")
            
            # Add refinement metadata to results
            results["refinement_metadata"] = {
                "iterations": current_iteration,
                "best_score": best_qa_score,
                "target_score": self.min_qa_score,
                "max_iterations": self.max_iterations
            }
            
            # 🎬 Final Act: Return Results
            total_duration = time.time() - start_time
            self._debug_print(f"🎉 Execution Complete in {total_duration:.1f}s!", "cyan")
            return results

        except Exception as e:
            self._handle_error("execution", e)
            
    @classmethod
    def create(
        cls,
        client: Any,
        model_name: str,
        model_search: str,
        pdf_url: str,
        api_key: Optional[str] = None,
        debug: bool = False,
        stage_output: bool = False,
        output_type: Optional[str] = None,
        info_gather_timeout: int = 600,
        max_iterations: int = 3,
        min_qa_score: float = 80.0,
    ) -> "ExecutionAgent":
        """Factory method for creating an ExecutionAgent"""
        return cls(
            client=client,
            model_name=model_name,
            model_search=model_search,
            api_key=api_key,
            debug=debug,
            stage_output=stage_output,
            output_type=output_type,
            info_gather_timeout=info_gather_timeout,
            max_iterations=max_iterations,
            min_qa_score=min_qa_score,
            pdf_url=pdf_url,
        )
