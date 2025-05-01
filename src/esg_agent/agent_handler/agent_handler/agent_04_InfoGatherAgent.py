from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
import re
import pathlib
import asyncio
import time
import httpx
import concurrent.futures
from concurrent.futures import TimeoutError as FuturesTimeoutError
from google.genai import types
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, HttpOptions, Part
from urllib.parse import urlparse

from esg_agent.agent_handler.agent_02_PlanningAgent import QueryValidation

from esg_agent.agent_handler.agent_03_FrameworkAgent import (
    FrameworkAgentOutput,
    IFRSRequirement,
    print_debug,
    print_executing,
)

# Constants for timeout and concurrency control
DEFAULT_TIMEOUT = 60  # 60 seconds timeout for model calls
MAX_CONCURRENT_TASKS = 3  # Limit concurrent tasks to prevent rate limiting
PDF_PROCESSING_TIMEOUT = 300  # 5 minutes timeout for PDF processing

@dataclass
class MetricData:
    """Represents a metric extracted from the report"""
    metric_name: str
    value: str
    unit: str
    year: str
    source: str
    source_type: str
    notes: str

@dataclass
class GroundingSource:
    """Represents a source used for grounding"""
    title: str
    uri: str
    index: int
    
@dataclass
class GroundedSegment:
    """Represents a segment of text with its grounding sources"""
    text: str
    source_indices: List[int]
    confidence_scores: List[float]
    
@dataclass
class GroundedContent:
    """Structured representation of content with grounding information"""
    text: str
    grounded_segments: List[GroundedSegment]
    sources: List[GroundingSource]
    search_queries: Optional[List[str]] = None
    raw_grounding_metadata: Optional[Any] = None  # Store the original metadata
    

@dataclass
class InfoSource:
    """Source of ESG information"""
    source_type: str  # "report", "web", "database"
    source_name: str
    source_url: Optional[str] = None
    source_date: Optional[str] = None
    reliability: float = 1.0  # 0.0-1.0 scale
    
    def to_dict(self):
        return {
            "source_type": self.source_type,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "source_date": self.source_date,
            "reliability": self.reliability
        }

@dataclass
class ESGDataPoint:
    """Single data point of ESG information"""
    requirement_id: str  # Maps to IFRS Requirement ID
    content: Union[str, GroundedContent]  # Can be either string or GroundedContent
    sources: List[InfoSource] = field(default_factory=list)
    
    def to_dict(self):
        if isinstance(self.content, GroundedContent):
            content_dict = grounded_content_to_dict(self.content)
        else:
            content_dict = {"text": self.content, "grounded": False}
            
        return {
            "requirement_id": self.requirement_id,
            "content": content_dict,
            "sources": [source.to_dict() for source in self.sources]
        }

@dataclass
class ESGDisclosureData:
    """Collection of ESG data for a disclosure area"""
    area_name: str
    data_points: List[ESGDataPoint] = field(default_factory=list)
    
    def to_dict(self):
        return {
            "area_name": self.area_name,
            "data_points": [point.to_dict() for point in self.data_points]
        }

@dataclass
class CompanyESGData:
    """Complete ESG data collection for a company"""
    company: str
    stock_symbol: str
    industry: str
    disclosure_data: List[ESGDisclosureData] = field(default_factory=list)
    metrics_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        return {
            "company": self.company,
            "stock_symbol": self.stock_symbol,
            "industry": self.industry,
            "disclosure_data": [data.to_dict() for data in self.disclosure_data],
            "metrics_data": self.metrics_data
        }

@dataclass
class InfoGatherAgentOutput:
    """Output from the Information Gathering Agent"""
    timestamp: datetime
    esg_data: CompanyESGData
    status: str = "success"
    error: Optional[str] = None
    
    def to_dict(self):
        return {
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "error": self.error,
            "esg_data": self.esg_data.to_dict() if self.esg_data else None
        }

def parse_grounding_response(response) -> GroundedContent:
    """Parse a Gemini response with grounding into a structured format"""
    
    # Extract the full text from the response
    full_text = response.text
    
    # Extract grounding metadata
    grounding_metadata = response.candidates[0].grounding_metadata
    
    # Create list of sources
    sources = []
    for idx, chunk in enumerate(grounding_metadata.grounding_chunks):
        if hasattr(chunk, 'web') and chunk.web:
            sources.append(GroundingSource(
                title=chunk.web.title,
                uri=chunk.web.uri,
                index=idx
            ))
    
    # Extract grounded segments
    ENCODING = "utf-8"
    text_bytes = full_text.encode(ENCODING)
    grounded_segments = []
    
    prev_index = 0
    
    for support in grounding_metadata.grounding_supports:
        # Get the text segment
        segment_text = text_bytes[prev_index:support.segment.end_index].decode(ENCODING)
        
        # Create grounded segment
        segment = GroundedSegment(
            text=segment_text,
            source_indices=support.grounding_chunk_indices,
            confidence_scores=support.confidence_scores
        )
        grounded_segments.append(segment)
        prev_index = support.segment.end_index
    
    # Add any remaining text
    if prev_index < len(text_bytes):
        remaining_text = text_bytes[prev_index:].decode(ENCODING)
        grounded_segments.append(GroundedSegment(
            text=remaining_text,
            source_indices=[],
            confidence_scores=[]
        ))
    
    # Get search queries if available
    search_queries = None
    if hasattr(grounding_metadata, 'web_search_queries') and grounding_metadata.web_search_queries:
        search_queries = grounding_metadata.web_search_queries
    
    # Create the complete structured content
    grounded_content = GroundedContent(
        text=full_text,
        grounded_segments=grounded_segments,
        sources=sources,
        search_queries=search_queries,
        raw_grounding_metadata=grounding_metadata  # Keep the original for reference
    )
    
    return grounded_content

def grounded_content_to_dict(content: GroundedContent) -> Dict:
    """Convert grounded content to a dictionary format for serialization"""
    return {
        "text": content.text,
        "segments": [
            {
                "text": segment.text,
                "sources": [content.sources[idx].title for idx in segment.source_indices],
                "source_indices": segment.source_indices,
                "confidence_scores": segment.confidence_scores
            }
            for segment in content.grounded_segments
        ],
        "sources": [
            {
                "title": source.title,
                "uri": source.uri,
                "index": source.index
            }
            for source in content.sources
        ],
        "search_queries": content.search_queries
    }



class InfoGatherAgent:
    def __init__(self, client, model_name: str, report_paths: List[str], debug: bool = False):
        self.client = client
        self.model_name = model_name
        self.debug = debug
        self.report_paths = report_paths
        self.timeout = DEFAULT_TIMEOUT
        self.pdf_timeout = PDF_PROCESSING_TIMEOUT
        self.max_retries = 2
        self.semaphore = None  # Will be initialized in process method
        
    def set_debug(self, debug: bool):
        self.debug = debug
        
    def set_timeout(self, timeout: int):
        """Set custom timeout for API calls in seconds"""
        self.timeout = timeout
        
    async def _extract_from_report_with_timeout(self, *args, **kwargs):
        """Wrapper to call _extract_from_report with timeout"""
        loop = asyncio.get_event_loop()
        try:
            # Run the synchronous method in a thread pool with timeout
            return await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self._extract_from_report(*args, **kwargs)), 
                timeout=self.pdf_timeout
            )
        except asyncio.TimeoutError:
            if self.debug:
                print_debug(f"Timeout extracting from report: {kwargs.get('report_path', 'unknown')}")
            return [], {}
    
    def _extract_from_report(
            self, company: str, 
            report_path: str,
            start_month_year: str,
            end_month_year: str,
            requirements: List[IFRSRequirement], 
            applicable_metrics: Dict[str, str] = None) -> tuple[List[ESGDataPoint], Dict[str, Any]]:
        """Extract ESG information and metrics from a provided report file"""
        try:
            start_time = time.time()
            if self.debug:
                print_debug(f"Starting extraction from {report_path}")
            
            doc_data = httpx.get(report_path).content
            
            pdf_file = Part.from_bytes(
                data=doc_data,
                mime_type="application/pdf",
            )
            
            data_points = []
            metrics_data = {}
            
            # For each requirement, extract relevant information
            for i, req in enumerate(requirements):
                if self.debug and i > 0 and i % 5 == 0:
                    print_debug(f"Processed {i}/{len(requirements)} requirements in {time.time() - start_time:.1f}s")
                
                prompt = f"""
                You are an expert in information extraction from various types of documents for ESG reporting.
                Extract information related to the following requirement from IFRS International Sustainability Standards Board (ISSB) from the report text. Extract information only if it relates to {company}'s practices.
                
                Company: {company}
                Requirement ID: {req.id}
                Requirement: {req.description}
                Time Period: {start_month_year} - {end_month_year}
                
                Do not return a list of items. Return a single JSON object with JSON schema:

                {{
                    "requirement_id": int, # "{req.id}"
                    "content": str, # "The extracted information that relates to this requirement"
                    "date": str, # "The date of the report"
                    "found": str # true or false (whether relevant information was found)
                }}
                
                If no date is found, leave date empty. If no relevant information is found, set "found" to false and leave content empty.
                """
                
                try:
                    # Implement retry logic with timeout
                    for retry in range(self.max_retries + 1):
                        try:
                            response = self.client.models.generate_content(
                                model=self.model_name,
                                contents=[pdf_file, prompt],
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",

                                )
                            )
                            break
                        except Exception as e:
                            if retry < self.max_retries:
                                if self.debug:
                                    print_debug(f"Retrying after error: {str(e)}")
                                time.sleep(2 * (retry + 1))  # Exponential backoff
                            else:
                                raise e
                    
                    try:
                        # Add proper error handling for JSON parsing
                        result = json.loads(response.text, strict=False)
                    except json.JSONDecodeError as json_err:
                        if self.debug:
                            print_debug(f"JSON parsing error for {req.id}: {str(json_err)}")
                            print_debug(f"Response text: {response.text[:100]}...")  # Print first 100 chars for debugging
                        
                        # Try to fix common JSON issues like unterminated strings
                        fixed_text = response.text
                        try_to_fix = False
                        
                        # Check for different types of JSON errors and attempt fixes
                        if "Unterminated string" in str(json_err):
                            # Simple fix attempt: add missing quote at the end if that's the issue
                            fixed_text = fixed_text + '"}'
                            try_to_fix = True
                        elif "Invalid control character" in str(json_err):
                            # Replace invalid control characters with spaces
                            fixed_text = re.sub(r'[\x00-\x1F\x7F]', ' ', fixed_text)
                            try_to_fix = True
                        elif "Extra data" in str(json_err):
                            # Try to find the end of the JSON object and truncate
                            match = re.search(r'({.*})', fixed_text)
                            if match:
                                fixed_text = match.group(1)
                                try_to_fix = True
                            
                        if try_to_fix:
                            try:
                                result = json.loads(fixed_text, strict=False)
                                if self.debug:
                                    print_debug(f"Successfully fixed JSON for {req.id}")
                            except Exception as fix_err:
                                # If fix didn't work, try a more generic approach
                                try:
                                    # Try to extract any valid JSON object
                                    potential_json = re.search(r'({[^{}]*(?:{[^{}]*}[^{}]*)*})', fixed_text)
                                    if potential_json and potential_json.group(1):
                                        try:
                                            result = json.loads(potential_json.group(1), strict=False)
                                            if self.debug:
                                                print_debug(f"Successfully fixed JSON for {req.id} with fallback method")
                                        except Exception as json_load_err:
                                            if self.debug:
                                                print_debug(f"Failed to parse extracted JSON: {str(json_load_err)}")
                                            continue
                                    else:
                                        if self.debug:
                                            print_debug(f"Could not find valid JSON pattern for {req.id}, skipping")
                                        continue
                                except Exception as fallback_err:
                                    if self.debug:
                                        print_debug(f"Could not fix JSON for {req.id}, skipping: {str(fallback_err)}")
                                    continue
                            except:
                                # If all fixes failed, skip this extraction
                                if self.debug:
                                    print_debug(f"Could not fix JSON for {req.id}, skipping: {str(fix_err)}")
                                continue
                        else:
                            # For other JSON errors, skip this extraction
                            continue
                    
                    if result.get("found", False):
                        # Create a source
                        is_url = report_path.startswith(('http://', 'https://'))
                        source = InfoSource(
                            source_type="report",
                            source_name=report_path,
                            source_url=report_path if is_url else None,
                            source_date=result.get("date", None)
                        )
                        
                        # Create a GroundedContent object from the extracted text
                        content_text = result.get("content", "")
                        grounded_segment = GroundedSegment(
                            text=content_text,
                            source_indices=[0],  # Reference to the first source
                            confidence_scores=[1.0]  # Full confidence as it's directly from the report
                        )
                        
                        grounded_content = GroundedContent(
                            text=content_text,
                            grounded_segments=[grounded_segment],
                            sources=[GroundingSource(
                                title=source.source_name,
                                uri=report_path,
                                index=0
                            )]
                        )
                        
                        data_points.append(ESGDataPoint(
                            requirement_id=req.id,
                            content=grounded_content,
                            sources=[source]
                        ))
                except Exception as e:
                    if self.debug:
                        print_debug(f"Error parsing report extraction for {req.id}: {str(e)}")
            
            # Extract metrics data if applicable metrics are provided
            if applicable_metrics:
                metrics_prompt = f"""
                You are an expert in extracting ESG metrics from corporate reports.
                Extract the following ESG metrics for {company} from the provided PDF report.
                
                For each metric, extract the most recent value, unit, and year of the data.
                
                Metrics to extract:
                {json.dumps(applicable_metrics, indent=2)}
                
                If a metric is not found in the report, do not include it in the response.
                """
                
                try:
                    # Implement retry logic with timeout
                    for retry in range(self.max_retries + 1):
                        try:
                            metrics_response = self.client.models.generate_content(
                                model=self.model_name,
                                contents=[pdf_file, metrics_prompt],
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",
                                    response_schema=list[MetricData]
                                )
                            )
                            break
                        except Exception as e:
                            if retry < self.max_retries:
                                if self.debug:
                                    print_debug(f"Retrying metrics extraction after error: {str(e)}")
                                time.sleep(2 * (retry + 1))
                            else:
                                raise e
                    
                    try:
                        metrics_result = json.loads(metrics_response.text, strict=False)
                    except json.JSONDecodeError as json_err:
                        if self.debug:
                            print_debug(f"JSON parsing error for metrics: {str(json_err)}")
                            print_debug(f"Response text: {metrics_response.text[:100]}...")
                        
                        # Try to fix common JSON issues
                        fixed_text = metrics_response.text
                        try_to_fix = False
                        
                        # Check for different types of JSON errors and attempt fixes
                        if "Unterminated string" in str(json_err):
                            fixed_text = fixed_text + '"}'
                            try_to_fix = True
                        elif "Invalid control character" in str(json_err):
                            # Replace invalid control characters with spaces
                            fixed_text = re.sub(r'[\x00-\x1F\x7F]', ' ', fixed_text)
                            try_to_fix = True
                        elif "Extra data" in str(json_err):
                            # Try to find the end of the JSON object and truncate
                            match = re.search(r'({.*})', fixed_text)
                            if match:
                                fixed_text = match.group(1)
                                try_to_fix = True                        
                        if try_to_fix:
                            try:
                                metrics_result = json.loads(fixed_text, strict=False)
                                if self.debug:
                                    print_debug(f"Successfully fixed metrics JSON")
                            except Exception as fix_err:
                                # Try a more generic approach
                                try:
                                    # Try to extract any valid JSON object
                                    potential_json = re.search(r'({[^{}]*(?:{[^{}]*}[^{}]*)*})', fixed_text)
                                    if potential_json and potential_json.group(1):
                                        try:
                                            metrics_result = json.loads(potential_json.group(1), strict=False)
                                            if self.debug:
                                                print_debug(f"Successfully fixed metrics JSON with fallback method")
                                        except Exception as json_load_err:
                                            if self.debug:
                                                print_debug(f"Failed to parse extracted JSON: {str(json_load_err)}")
                                            metrics_result = {"metrics": {}}
                                    else:
                                        if self.debug:
                                            print_debug(f"Could not find valid JSON pattern, skipping: {str(fix_err)}")
                                        metrics_result = {"metrics": {}}
                                except Exception:
                                    metrics_result = {"metrics": {}}
                        else:
                            metrics_result = {"metrics": {}}
                    
                    # Check if metrics_result is a list of MetricData objects
                    if isinstance(metrics_result, list):
                        for metric_data in metrics_result:
                            if isinstance(metric_data, dict):
                                if "metric_name" in metric_data:
                                    metric_name = metric_data["metric_name"]
                                    # Add source information
                                    metric_data["source"] = os.path.basename(report_path)
                                    metric_data["source_type"] = "report"
                                    # Add to metrics data
                                    metrics_data[metric_name] = metric_data
                                else:
                                    if self.debug:
                                        print_debug(f"Skipping metric data without metric_name: {metric_data}")
                except Exception as e:
                    if self.debug:
                        print_debug(f"Error extracting metrics from report: {str(e)}")
                        
            if self.debug:
                print_debug(f"Completed extraction from {os.path.basename(report_path)} in {time.time() - start_time:.1f}s")
                        
            return data_points, metrics_data
            
        except Exception as e:
            if self.debug:
                print_debug(f"Error extracting from report: {str(e)}")
            return [], {}
    
    def _extract_report_date(self, text: str) -> Optional[str]:
        """Try to extract the report date from text"""
        # Look for common date patterns in reports
        date_patterns = [
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}',
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{4}-\d{2}-\d{2}'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None
    
    async def _search_web_with_timeout(self, *args, **kwargs):
        """Wrapper to call _search_web with timeout"""
        try:
            # Wait for semaphore to control concurrency
            async with self.semaphore:
                loop = asyncio.get_event_loop()
                # Run the synchronous method in a thread pool with timeout
                return await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: self._search_web(*args, **kwargs)), 
                    timeout=self.timeout
                )
        except asyncio.TimeoutError:
            if self.debug:
                print_debug(f"Timeout searching web for: {kwargs.get('requirement', 'unknown').id}")
            return [], {}
    
    def _search_web(
            self, 
            company: str,
            stock_symbol: str,
            start_month_year: str,
            end_month_year: str,
            requirement: IFRSRequirement,
            applicable_metrics: Dict[str, str] = None) -> tuple[List[ESGDataPoint], Dict[str, Any]]:
        """Search the web for ESG information related to a specific requirement and metrics"""
        try:
            start_time = time.time()
            
            # Construct search query
            search_query = f"{company} {stock_symbol} ESG {requirement.description}"
            
            # Web search for requirement information
            prompt = f"""
            Simulate a web search for: "{search_query}"
            
            Return information about {company}'s ESG practices related to:
            {requirement.description}
            Time Period: {start_month_year} - {end_month_year}
            
            Only return facts about the company within the specified time period. If precise data cannot be found, return empty string. Do not include opinions or speculative information.
            """
            google_search_tool = Tool(
               google_search = GoogleSearch()
            )
            
            # Implement retry logic
            data_points = []
            metrics_data = {}
            
            for retry in range(self.max_retries + 1):
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                        config=GenerateContentConfig(
                            tools=[google_search_tool],
                            response_modalities=["TEXT"],
                        )
                    )
                    break
                except Exception as e:
                    if retry < self.max_retries:
                        if self.debug:
                            print_debug(f"Retrying web search after error: {str(e)}")
                        time.sleep(2 * (retry + 1))
                    else:
                        if self.debug:
                            print_debug(f"Failed web search after {self.max_retries} retries: {str(e)}")
                        return [], {}
            
            try:
                result = parse_grounding_response(response)  
                data_points.append(ESGDataPoint(
                    requirement_id=requirement.id,
                    content=result,
                ))
                    
            except Exception as e:
                if self.debug:
                    print_debug(f"Error parsing web search response: {str(e)}")
            
            # Limit metrics processing to prevent excessive API calls
            if applicable_metrics and len(applicable_metrics) <= 5:
                # We'll search for each metric separately to get more targeted results
                for metric_name, description in applicable_metrics.items():
                    metrics_query = f"{company} {stock_symbol} ESG {metric_name} {description}"
                    
                    metrics_prompt = f"""
                    Simulate a web search for: "{metrics_query}"
                    
                    Find the most recent data point for {company} ({stock_symbol}) regarding this ESG metric:
                    {metric_name}: {description}
                    
                    Return a JSON object with:
                    {{
                        "value": "The metric value (numerical when possible)",
                        "unit": "The unit of measurement",
                        "year": "The year of the data",
                        "source": "The source of this information",
                        "source_url": "URL of the source if available",
                        "notes": "Any contextual notes about this metric"
                    }}
                    
                    If precise data cannot be found, provide the best available estimate and note this in "notes".
                    """
                    
                    try:
                        for retry in range(self.max_retries + 1):
                            try:
                                metrics_response = self.client.models.generate_content(
                                    model=self.model_name,
                                    contents=metrics_prompt,
                                    config=GenerateContentConfig(
                                        tools=[google_search_tool],
                                        response_mime_type="application/json",
                                    )
                                )
                                break
                            except Exception as e:
                                if retry < self.max_retries:
                                    if self.debug:
                                        print_debug(f"Retrying metrics search after error: {str(e)}")
                                    time.sleep(2 * (retry + 1))
                                else:
                                    raise e
                        
                        try:
                            metric_data = json.loads(metrics_response.text, strict=False)
                        except json.JSONDecodeError as json_err:
                            if self.debug:
                                print_debug(f"JSON parsing error for metrics: {str(json_err)}")
                                print_debug(f"Response text: {metrics_response.text[:100]}...")
                            
                            # Try to fix common JSON issues
                            fixed_text = metrics_response.text
                            try_to_fix = False
                            
                            # Check for different types of JSON errors and attempt fixes
                            if "Unterminated string" in str(json_err):
                                fixed_text = fixed_text + '"}'
                                try_to_fix = True
                            elif "Invalid control character" in str(json_err):
                                # Replace invalid control characters with spaces
                                fixed_text = re.sub(r'[\x00-\x1F\x7F]', ' ', fixed_text)
                                try_to_fix = True
                            elif "Extra data" in str(json_err):
                                # Try to find the end of the JSON object and truncate
                                match = re.search(r'({.*})', fixed_text)
                                if match:
                                    fixed_text = match.group(1)
                                    try_to_fix = True                            
                            if try_to_fix:
                                try:
                                    metric_data = json.loads(fixed_text, strict=False)
                                    if self.debug:
                                        print_debug(f"Successfully fixed metrics JSON")
                                except Exception as fix_err:
                                    # Try a more generic approach
                                    try:
                                        # Try to extract any valid JSON object
                                        potential_json = re.search(r'({[^{}]*(?:{[^{}]*}[^{}]*)*})', fixed_text)
                                        if potential_json and potential_json.group(1):
                                            try:
                                                metric_data = json.loads(potential_json.group(1), strict=False)
                                                if self.debug:
                                                    print_debug(f"Successfully fixed metrics JSON with fallback method")
                                            except Exception as json_load_err:
                                                if self.debug:
                                                    print_debug(f"Failed to parse extracted JSON: {str(json_load_err)}")
                                                metric_data = {}
                                        else:
                                            if self.debug:
                                                print_debug(f"Could not find valid JSON pattern, skipping")
                                            metric_data = {}
                                    except Exception as fallback_err:
                                        if self.debug:
                                            print_debug(f"Could not fix metrics JSON, skipping: {str(fallback_err)}")
                                        metric_data = {}
                            else:
                                if self.debug:
                                    print_debug(f"Could not fix metrics JSON, skipping: {str(fix_err)}")
                                metric_data = {}
                        
                        # Handle different possible structures of metric_data
                        if isinstance(metric_data, dict):
                            if "metrics" in metric_data and isinstance(metric_data["metrics"], dict):
                                # Handle nested metrics structure
                                for metric_key, metric_value in metric_data["metrics"].items():
                                    if isinstance(metric_value, dict):
                                        metric_value["source_type"] = "web"
                                        metrics_data[metric_key] = metric_value
                            else:
                                # Handle flat structure
                                metric_data["source_type"] = "web"
                                metrics_data[metric_name] = metric_data
                    except Exception as e:
                        if self.debug:
                            print_debug(f"Error getting metric data for {metric_name}: {str(e)}")
            
            if self.debug:
                print_debug(f"Completed web search for {requirement.id} in {time.time() - start_time:.1f}s")
                
            return data_points, metrics_data
                
        except Exception as e:
            if self.debug:
                print_debug(f"Error searching web: {str(e)}")
            return [], {}
    
    def _consolidate_metrics_data(self, metrics_collections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Consolidate metrics data from multiple sources, keeping the most reliable/recent data"""
        consolidated_metrics = {}
        
        # Simple consolidation: prefer report data over web data, and more recent data over older
        for metrics_dict in metrics_collections:
            for metric_name, metric_data in metrics_dict.items():
                if metric_name not in consolidated_metrics:
                    consolidated_metrics[metric_name] = metric_data
                    continue
                
                # If existing data is from web and new data is from report, prefer report
                if consolidated_metrics[metric_name].get("source_type") == "web" and metric_data.get("source_type") == "report":
                    consolidated_metrics[metric_name] = metric_data
                    continue
                
                # If both are same source type, prefer more recent data
                existing_year_str = consolidated_metrics[metric_name].get("year", "0")
                new_year_str = metric_data.get("year", "0")
                
                # Convert to integers safely, handling non-numeric values like 'N/A'
                try:
                    existing_year = int(existing_year_str)
                except (ValueError, TypeError):
                    existing_year = 0
                    
                try:
                    new_year = int(new_year_str)
                except (ValueError, TypeError):
                    new_year = 0
                
                if new_year > existing_year:
                    consolidated_metrics[metric_name] = metric_data
        
        return consolidated_metrics
    
    async def process_async(self, framework_output: FrameworkAgentOutput, validated_query: QueryValidation) -> InfoGatherAgentOutput:
        """Process framework output to gather ESG information asynchronously"""
        try:
            start_time = time.time()
            if self.debug:
                print_executing(f"InfoGather Agent processing for {framework_output.framework.company}")
            
            # Initialize semaphore for concurrency control
            self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
            
            company = framework_output.framework.company
            stock_symbol = framework_output.framework.stock_symbol
            industry = framework_output.framework.industry
            start_month_year = validated_query.start_month_year
            end_month_year = validated_query.end_month_year
            
            # Initialize ESG data structure
            esg_data = CompanyESGData(
                company=company,
                stock_symbol=stock_symbol,
                industry=industry
            )
            
            # Store all metrics data to consolidate later
            all_metrics_data = []
            
            # Process each disclosure area
            area_tasks = []
            
            # Process report data first if available
            report_data_by_area = {}
            if self.report_paths:
                if self.debug:
                    print_debug(f"Processing {len(self.report_paths)} report files/URLs")
                    
                for i, report_path in enumerate(self.report_paths):
                    if self.debug:
                        # Determine if it's a URL or a local file path
                        is_url = report_path.startswith(('http://', 'https://'))
                        path_type = "URL" if is_url else "file"
                        display_name = urlparse(report_path).path if is_url else os.path.basename(report_path)
                        print_debug(f"Processing report {i+1}/{len(self.report_paths)}: {path_type} {display_name}")
                    
                    for area in framework_output.framework.disclosure_areas:
                        area_key = area.name
                        if area_key not in report_data_by_area:
                            report_data_by_area[area_key] = {}
                        
                        extracted_points, report_metrics = await self._extract_from_report_with_timeout(
                            company, 
                            report_path,
                            start_month_year,
                            end_month_year,
                            area.requirements,
                            framework_output.framework.applicable_metrics
                        )
                        
                        # Group extracted points by requirement ID
                        for point in extracted_points:
                            if point.requirement_id not in report_data_by_area[area_key]:
                                report_data_by_area[area_key][point.requirement_id] = []
                            report_data_by_area[area_key][point.requirement_id].append(point)
                        
                        # Add metrics data to collection
                        if report_metrics:
                            all_metrics_data.append(report_metrics)
            
            # Now process web searches with concurrency control
            for area in framework_output.framework.disclosure_areas:
                area_data = ESGDisclosureData(area_name=area.name)
                
                # Create tasks for web searches
                web_tasks = []
                for req in area.requirements:
                    task = self._search_web_with_timeout(
                        company, 
                        stock_symbol, 
                        start_month_year,
                        end_month_year,
                        req,
                        framework_output.framework.applicable_metrics
                    )
                    web_tasks.append((req.id, task))
                
                # Execute web tasks with concurrency control and gather results
                web_results = {}
                for req_id, task in web_tasks:
                    web_points, web_metrics = await task
                    web_results[req_id] = (web_points, web_metrics)
                    if web_metrics:
                        all_metrics_data.append(web_metrics)
                
                # Now integrate report data with web data
                for req in area.requirements:
                    req_id = req.id
                    
                    # Check if we have report data for this requirement
                    report_points = []
                    if area.name in report_data_by_area and req_id in report_data_by_area[area.name]:
                        report_points = report_data_by_area[area.name][req_id]
                        # Add all points from reports
                        for point in report_points:
                            area_data.data_points.append(point)
                    
                    # Get web data for this requirement
                    if req_id in web_results:
                        web_points, _ = web_results[req_id]
                        
                        if report_points:
                            # We already have data from reports, append web information as supplementary
                            for report_point in report_points:
                                for web_point in web_points:
                                    if web_point.content and (
                                        isinstance(web_point.content, str) and web_point.content.strip() or 
                                        isinstance(web_point.content, GroundedContent) and web_point.content.text.strip()
                                    ):
                                        # Extract the web content text
                                        web_content_text = (
                                            web_point.content if isinstance(web_point.content, str) 
                                            else web_point.content.text
                                        )
                                        
                                        # Integrate based on content type
                                        if isinstance(report_point.content, str):
                                            report_point.content += "\n\nSupplementary information from web sources:\n" + web_content_text
                                        else:
                                            # Integrate with GroundedContent
                                            existing_content = report_point.content
                                            
                                            # Create a new combined text
                                            combined_text = existing_content.text + "\n\nSupplementary information from web sources:\n" + web_content_text
                                            
                                            # Create segment and update content
                                            supp_segment = GroundedSegment(
                                                text="\n\nSupplementary information from web sources:\n" + web_content_text,
                                                source_indices=list(range(
                                                    len(existing_content.sources), 
                                                    len(existing_content.sources) + len(web_point.sources or [1])
                                                )),
                                                confidence_scores=[0.8] * len(web_point.sources or [1])
                                            )
                                            
                                            # Add sources
                                            new_segments = existing_content.grounded_segments + [supp_segment]
                                            new_sources = existing_content.sources + (
                                                web_point.content.sources if isinstance(web_point.content, GroundedContent)
                                                else [GroundingSource(title="Web Search", uri="", index=len(existing_content.sources))]
                                            )
                                            
                                            report_point.content = GroundedContent(
                                                text=combined_text,
                                                grounded_segments=new_segments,
                                                sources=new_sources,
                                                search_queries=existing_content.search_queries
                                            )
                                        
                                        # Add sources
                                        if isinstance(web_point.content, GroundedContent):
                                            for source in web_point.sources or []:
                                                if source not in report_point.sources:
                                                    report_point.sources.append(source)
                        else:
                            # No existing data from reports, add web data as primary source
                            for point in web_points:
                                area_data.data_points.append(point)
                
                # Add this area's data to the company data if it has data points
                if area_data.data_points:
                    esg_data.disclosure_data.append(area_data)
            
            # Consolidate all metrics data
            esg_data.metrics_data = self._consolidate_metrics_data(all_metrics_data)
            
            if self.debug:
                print_debug(f"InfoGather Agent completed processing in {time.time() - start_time:.1f}s")
            
            return InfoGatherAgentOutput(
                timestamp=datetime.now(),
                esg_data=esg_data,
                status="success"
            )
            
        except Exception as e:
            if self.debug:
                print_debug(f"Error in InfoGather Agent: {str(e)}")
            return InfoGatherAgentOutput(
                timestamp=datetime.now(),
                esg_data=CompanyESGData(
                    company=framework_output.framework.company if framework_output and hasattr(framework_output, 'framework') else "Unknown",
                    stock_symbol=framework_output.framework.stock_symbol if framework_output and hasattr(framework_output, 'framework') else "Unknown",
                    industry="Unknown"
                ),
                status="error",
                error=str(e)
            )
    
    def process(self, framework_output: FrameworkAgentOutput, validated_query: QueryValidation, report_paths: List[str] = None) -> InfoGatherAgentOutput:
        """Process framework output to gather ESG information (synchronous wrapper)"""
        try:
            # Use nest_asyncio to allow nested event loops
            import nest_asyncio
            nest_asyncio.apply()
            
            # Now we can safely use asyncio.run even in a running event loop
            try:
                # Use asyncio.run which handles the event loop properly
                return asyncio.run(self.process_async(framework_output, validated_query))
            except RuntimeError as e:
                if "This event loop is already running" in str(e) or "Cannot run the event loop while another loop is running" in str(e):
                    # If we're in a running event loop, use create_task and wait for it
                    loop = asyncio.get_event_loop()
                    return loop.run_until_complete(self.process_async(framework_output, validated_query))
                else:
                    # Re-raise other RuntimeErrors
                    raise
        except Exception as e:
            if self.debug:
                print_debug(f"Error in process wrapper: {str(e)}")
            return InfoGatherAgentOutput(
                timestamp=datetime.now(),
                esg_data=CompanyESGData(
                    company=framework_output.framework.company if framework_output and hasattr(framework_output, 'framework') else "Unknown",
                    stock_symbol=framework_output.framework.stock_symbol if framework_output and hasattr(framework_output, 'framework') else "Unknown",
                    industry="Unknown"
                ),
                status="error",
                error=str(e)
            )
