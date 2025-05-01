# @title Helper Functions

from enum import Enum
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from dataclasses import dataclass, field

from google.genai import types
from pydantic import BaseModel
from rich import print as rich_print

# Debug Print Functions with both light and dark theme friendly colors
def print_planning(msg: str):
    rich_print(f"[bold cyan]🤔 PLANNING:[/bold cyan] {msg}")


def print_executing(msg: str):
    rich_print(f"[bold green]⚡ EXECUTING:[/bold green] {msg}")

def print_debug(msg: str):
    rich_print(f"[bold magenta]🔍 DEBUG:[/bold magenta] {msg}")

def print_info(msg: str):
    rich_print(f"[bold yellow]ℹ️ INFO:[/bold yellow] {msg}")

class IFRSStandard(str, Enum):
    S1 = "IFRS S1"  # General Requirements
    S2 = "IFRS S2"  # Climate-related Disclosures

@dataclass
class IFRSRequirement:
    """Individual requirement or disclosure from IFRS Sustainability Standards"""
    id: str  # Identifier like "S1.10" or "S2.21(a)"
    description: str
    guidance_notes: Optional[str] = None
    examples: Optional[List[str]] = None
    
    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "guidance_notes": self.guidance_notes,
            "examples": self.examples
        }

@dataclass
class IFRSDisclosureArea:
    """Major disclosure area in IFRS Standards (e.g., Governance, Strategy, etc.)"""
    name: str
    description: str
    requirements: List[IFRSRequirement] = field(default_factory=list)
    
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "requirements": [req.to_dict() for req in self.requirements]
        }


@dataclass
class IFRSFramework:
    """Complete IFRS Sustainability framework relevant to the query"""
    standard: IFRSStandard
    industry: str
    company: str
    stock_symbol: str
    summary: str
    disclosure_areas: List[IFRSDisclosureArea] = field(default_factory=list)
    applicable_metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self):
        return {
            "standard": self.standard,
            "industry": self.industry,
            "company": self.company,
            "stock_symbol": self.stock_symbol,
            "summary": self.summary,
            "disclosure_areas": [area.to_dict() for area in self.disclosure_areas],
            "applicable_metrics": self.applicable_metrics,
            "error": self.error
        }


@dataclass
class FrameworkAgentOutput:
    """Output from the Framework Agent with IFRS Standards guidance"""
    timestamp: datetime
    framework: IFRSFramework
    status: str = "success"
    error: Optional[str] = None

    def to_dict(self):
        return {
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "error": self.error,
            "framework": self.framework.to_dict() if self.framework else None,
        }

class FrameworkAgent:
    def __init__(self, client, model_name: str, debug: bool = False):
        self.client = client
        self.model_name = model_name
        self.debug = False
        
    def set_debug(self, debug: bool):
        self.debug = debug
        
    def _determine_industry(self, company: str, stock_symbol: str) -> str:
        """Determine the industry classification of the company"""
        try:
            prompt = f"""
            Determine the primary industry sector of {company} (ticker: {stock_symbol}).
            Return only the industry name following the Global Industry Classification Standard (GICS).
            Example industries: Technology, Healthcare, Energy, Finance, Consumer Discretionary, etc.
            """
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            industry = response.text.strip()
            if self.debug:
                print_debug(f"Determined industry for {company}: {industry}")
            return industry
            
        except Exception as e:
            if self.debug:
                print_debug(f"Error determining industry: {str(e)}")
            return "Unknown"
    
    def _extract_ifrs_requirements(self, company: str, stock_symbol: str, industry: str) -> IFRSFramework:
        """Extract IFRS requirements specific to company's industry"""
        try:
            prompt = f"""
            Generate a comprehensive IFRS Sustainability Disclosure Standards framework specifically for {company} ({stock_symbol}) in the {industry} industry.
            
            Focus on both IFRS S1 (General Requirements) and IFRS S2 (Climate-related Disclosures) standards that are most relevant.
            
            Return your response as a structured JSON with the following format:
            {{
                "standard": "IFRS S1" or "IFRS S2" (whichever is more relevant to the company),
                "company": "{company}",
                "stock_symbol": "{stock_symbol}",
                "summary": "Brief summary of key IFRS requirements for this company",
                "disclosure_areas": [
                    {{
                        "name": "Name of disclosure area (e.g. Governance, Strategy, Risk Management, Metrics)",
                        "description": "Description of this disclosure area",
                        "requirements": [
                            {{
                                "id": "Specific IFRS identifier like S1.10 or S2.21(a)",
                                "description": "Description of the requirement",
                                "guidance_notes": "Specific guidance for implementing this requirement for {company}",
                                "examples": ["Example 1 for {company}", "Example 2 for {company}"]
                            }}
                        ]
                    }}
                ],
                "applicable_metrics": {{
                    "metric1": "Description of metric relevance to {company}",
                    "metric2": "Description of metric relevance to {company}"
                }}
            }}
            
            Include industry-specific requirements and metrics that are particularly relevant to {industry} companies.
            """
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
             # Add debugging to see the raw response
            if self.debug:
                print_debug(f"Raw response text: {response.text[:200]}...")
            
            # Handle potential list or invalid JSON
            response_json = json.loads(response.text)
            
            # Check if response is a list and extract the first item if it is
            if isinstance(response_json, list):
                if self.debug:
                    print_debug("Response is a list, taking first item")
                if response_json:  # Check if list is not empty
                    response_json = response_json[0]
                else:
                    raise ValueError("Empty JSON array received from LLM")
                    
            # Check if we now have a valid dict
            if not isinstance(response_json, dict):
                raise ValueError(f"Expected JSON object, got {type(response_json).__name__}")
            
            if self.debug:
                print_debug(f"Extracted IFRS framework for {company}")
            
            # Convert JSON to IFRSFramework object
            standard = IFRSStandard.S1 if response_json.get("standard") == "IFRS S1" else IFRSStandard.S2
            
            disclosure_areas = []
            for area in response_json.get("disclosure_areas", []):
                requirements = []
                for req in area.get("requirements", []):
                    requirements.append(IFRSRequirement(
                        id=req.get("id", ""),
                        description=req.get("description", ""),
                        guidance_notes=req.get("guidance_notes", None),
                        examples=req.get("examples", None)
                    ))
                    
                disclosure_areas.append(IFRSDisclosureArea(
                    name=area.get("name", ""),
                    description=area.get("description", ""),
                    requirements=requirements
                ))
            
            return IFRSFramework(
                standard=standard,
                industry=industry,
                company=company,
                stock_symbol=stock_symbol,
                summary=response_json.get("summary", ""),
                disclosure_areas=disclosure_areas,
                applicable_metrics=response_json.get("applicable_metrics", {})
            )
            
        except Exception as e:
            if self.debug:
                print_debug(f"Error extracting IFRS requirements: {str(e)}")
            return IFRSFramework(
                standard=IFRSStandard.S1,
                industry=industry,
                company=company,
                stock_symbol=stock_symbol,
                summary="",
                error=f"Failed to extract IFRS requirements: {str(e)}"
            )
    
    def process(self, company: str, stock_symbol: str) -> FrameworkAgentOutput:
        """Process a query to extract relevant IFRS framework guidance"""
        try:
            if self.debug:
                print_executing(f"Framework Agent processing query for {company}")
                
            # Determine company industry
            industry = self._determine_industry(company, stock_symbol)
            
            # Extract IFRS requirements for this company/industry
            framework = self._extract_ifrs_requirements(company, stock_symbol, industry)
            
            return FrameworkAgentOutput(
                timestamp=datetime.now(),
                framework=framework,
                status="success"
            )
            
        except Exception as e:
            if self.debug:
                print_debug(f"Error in Framework Agent: {str(e)}")
            return FrameworkAgentOutput(
                timestamp=datetime.now(),
                framework=IFRSFramework(
                    standard=IFRSStandard.S1,
                    company=company,
                    stock_symbol=stock_symbol,
                    summary="",
                    error=f"Framework agent error: {str(e)}"
                ),
                status="error",
                error=str(e)
            )