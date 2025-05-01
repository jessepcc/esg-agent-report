# @title Helper Functions

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Dict, List

from google.genai import types

from rich import print as rich_print
from termcolor import colored


report_structure_prompt = {
    1: {
        "title": "Introduction",
        "content": {
            "subsections": [
                {"title": "Purpose of the Report", "content": "Define the objective of the ESG report, aligning with ISSB standards and HKEX ESG Code."},
                {"title": "Reporting Frameworks", "content": "Specify adherence to IFRS S1 (General Sustainability Disclosure) and IFRS S2 (Climate-related Disclosures), as well as HKEX's ESG Code."},
                {"title": "Scope and Reporting Period", "content": "State the coverage of the report, ensuring alignment with the financial reporting period."}
            ],
            "quality_assurance": [
                "Ensure alignment with ISSB and HKEX frameworks explicitly stated in the introduction.",
                "Verify consistency in defining reporting scope across all sections.",
                "Conduct peer reviews to confirm clarity and completeness of purpose.",
                "Use stakeholder feedback to validate relevance of objectives.",
                "Ensure timely publication within HKEX's required timeframe (four months after fiscal year-end)."
            ]
        }
    },
    2: {
        "title": "Governance",
        "content": {
            "subsections": [
                {"title": "Board Oversight", "content": "Describe the board’s role in overseeing ESG strategies, policies, and material issues."},
                {"title": "Management Structure", "content": "Outline the governance structure for implementing ESG initiatives."},
                {"title": "Accountability", "content": "Detail processes for tracking progress against ESG goals."}
            ],
            "quality_assurance": [
                "Confirm board statements on ESG oversight are detailed and accurate.",
                "Validate governance structures align with HKEX mandatory disclosure requirements.",
                "Ensure material issues are prioritized based on stakeholder engagement results.",
                "Audit tracking mechanisms for ESG goals to verify reliability.",
                "Cross-check disclosures against HKEX Appendix 27 requirements."
            ]
        }
    },
    3 : {
        "title": "Materiality Assessment",
        "content": {
            "subsections": [
                {"title": "Identification Process", "content": "Explain how material ESG factors are identified, including stakeholder engagement methods."},
                {"title": "Criteria for Selection", "content": "Provide clear criteria used to determine materiality."}
            ],
            "quality_assurance": [
                "Verify materiality assessment processes comply with ISSB standards for sustainability-related risks and opportunities.",
                "Ensure stakeholder engagement results are transparently documented.",
                "Confirm consistency in criteria application across reporting periods.",
                "Validate assumptions and methodologies used in materiality determination.",
                "Conduct external assurance reviews to ensure impartiality."
            ]
        }
    },
    4: {
        "title": "Environmental Disclosures",
        "content": {
            "subsections": [
                {"title": "Climate-related Risks and Opportunities", "content": "Report Scope 1, Scope 2, and Scope 3 emissions (mandatory for HKEX starting 2025)."},
                {"title": "Resource Management", "content": "Include data on energy consumption, water usage, and waste management."}
            ],
            "quality_assurance": [
                "Ensure compliance with IFRS S2 for climate-related disclosures.",
                "Validate emission calculations using standardized methodologies (e.g., GHG Protocol).",
                "Confirm data sources and conversion factors used for resource metrics are reliable.",
                "Audit consistency in environmental KPIs across reporting periods.",
                "Conduct independent verification of climate-related risk disclosures."
            ]
        }
    },
    5: {
        "title": "Social Disclosures",
        "content": {
            "subsections": [
                {"title": "Employee Welfare", "content": "Report on labor rights, diversity, training programs, and health/safety metrics."},
                {"title": "Community Engagement", "content": "Highlight initiatives that benefit local communities."}
            ],
            "quality_assurance": [
                "Confirm accuracy of metrics related to employee welfare (e.g., turnover rates, training hours).",
                "Verify alignment of social disclosures with HKEX's 'comply or explain' provisions.",
                "Ensure community engagement data is supported by documented evidence.",
                "Conduct internal audits to validate social KPIs against stated goals.",
                "Review stakeholder feedback to ensure disclosures meet expectations."
            ]
        }
    },
    6 : {
        "title": "Governance Disclosures",
        "content": {
            "subsections": [
                {"title": "Anti-Corruption Measures", "content": "Detail policies and practices to prevent unethical behavior."},
                {"title": "Product Responsibility", "content": "Include metrics on quality assurance and customer satisfaction."}
            ],
            "quality_assurance": [
                "Validate anti-corruption policies against industry best practices and HKEX requirements.",
                "Ensure product responsibility disclosures are backed by measurable KPIs.",
                "Conduct external audits of governance practices to ensure compliance.",
                "Verify consistency in governance disclosures across reporting periods.",
                "Cross-check alignment with ISSB standards for governance-related risks."
            ]
        }
    },
    7:{
        "title": "Metrics and Targets",
        "content": {
            "subsections": [
                {"title": "Performance Indicators", "content": "Present quantitative data on ESG performance using consistent methodologies."},
                {"title": "Future Goals", "content": "Provide targets aligned with international benchmarks (e.g., Paris Agreement)."}
            ],
            "quality_assurance": [
                "Validate performance indicators using recognized standards (e.g., SASB metrics).",
                "Ensure targets are realistic, measurable, and time-bound.",
                "Confirm alignment of goals with global sustainability frameworks like TCFD or ISSB S2.",
                "Audit historical data trends for accuracy in comparisons over time.",
                "Conduct scenario analysis to test robustness of targets under different conditions."
            ]
        }
    },
    8: {
        "title": "Reporting Principles",
        "content": {
            "subsections": [
                {"title": "Materiality, Quantitative Data, Consistency", "content": "Describe how these principles were applied during report preparation."}
            ],
            "quality_assurance": [
                "Confirm materiality processes align with ISSB S1 requirements for financial relevance.",
                "Validate quantitative data methodologies for transparency and comparability.",
                "Ensure consistency in reporting methods across periods or explain deviations clearly.",
                "Conduct independent reviews of reporting principles application for impartiality.",
                "Verify stakeholder engagement results support materiality decisions."
            ]
        }
    },
    9: {
        "title": "Conclusion",
        "content": {
            "subsections": [
                {"title": "Summary of Findings", "content": "Recap key insights from the report regarding sustainability performance and future plans."}
            ],
            "quality_assurance": [
                "Ensure conclusions are supported by evidence throughout the report sections.",
                "Validate alignment between summary findings and disclosed metrics/targets.",
                "Confirm clarity and conciseness in presenting final insights to stakeholders.",
                "Cross-check consistency between conclusions and governance disclosures on progress tracking.",
                "Conduct final review by an external auditor for unbiased assurance."
            ]
        }
    }
}


@dataclass
class ReportSection:
    """Represents a section of the ESG report"""
    title: str
    content: str
    sources: List[Dict[str, str]]

@dataclass
class GeneratedReport:
    """Complete generated ESG report with all sections"""
    company: str
    stock_symbol: str
    industry: str
    reporting_period: str
    timestamp: datetime
    sections: List[ReportSection]
    
    @property
    def text(self) -> str:
        """Returns the full report text with all sections properly formatted"""
        report_text = []
        
        # Add report header
        report_text.append(f"# ESG REPORT: {self.company} ({self.stock_symbol})")
        report_text.append(f"Industry: {self.industry}")
        report_text.append(f"Reporting Period: {self.reporting_period}")
        report_text.append(f"Generated on: {self.timestamp.strftime('%B %d, %Y')}")
        report_text.append("\n")
        
        # Add each section with its title and content
        for section in self.sections:
            report_text.append(f"## {section.title}")
            report_text.append(f"{section.content}")
            
            # Add sources if available
            if section.sources:
                report_text.append("\n**Sources:**")
                for source in section.sources:
                    source_text = source.get("source_name", "Unknown Source")
                    if source.get("source_url"):
                        source_text += f" - {source.get('source_url')}"
                    if source.get("source_date"):
                        source_text += f" ({source.get('source_date')})"
                    report_text.append(f"- {source_text}")
            
            report_text.append("\n")
            
        return "\n\n".join(report_text)
class ReportAgent:
    def __init__(
        self, client, model_name: str, debug: bool = False
    ):
        self.client = client
        self.model_name = model_name
        self.debug = debug

        if not self.debug:
            rich_print(
                "[bold yellow]ℹ️ Warning: Assembling the pieces of the puzzle!  It's like a jigsaw, but with more numbers and less chance of losing pieces under the couch.  Want a sneak peek at the final picture? debug=True is your magnifying glass! (And if you want to see the output of each agent stage, set stage_output=True!) 🧩🔍 [/bold yellow]"
            )

    def log_info(self, msg: str):
        print(colored(f"INFO: {msg}", "green", attrs=["bold"]))

    def log_debug(self, msg: str):
        print(colored(f"DEBUG: {msg}", "yellow", attrs=["bold"]))

    def log_process(self, msg: str):
        print(colored(f"🔄 {msg}", "cyan", attrs=["bold"]))

    def log_error(self, msg: str):
        print(colored(f"ERROR: {msg}", "red", attrs=["bold"]))
        
    def _extract_section_from_structure(self, section_number: int) -> Dict:
        """Extract a specific section from the report structure prompt"""
        if section_number not in report_structure_prompt:
            return {"title": "Unknown Section", "content": ""}
            
        section = report_structure_prompt[section_number]
        
        # Format content for use in prompts
        formatted_content = ""
        
        # Add subsections
        for subsection in section["content"]["subsections"]:
            formatted_content += f"- **{subsection['title']}**: {subsection['content']}\n"
        
        # Add quality assurance requirements
        formatted_content += "\n#### Quality Assurance Requirements:\n"
        for i, qa in enumerate(section["content"]["quality_assurance"], 1):
            formatted_content += f"{i}. {qa}\n"
        
        return {
            "title": section["title"],
            "content": formatted_content
        }
    
    def _extract_relevant_data_for_section(self, section_number: int, framework_output, info_gather_output):
        """Extract relevant data from agent outputs for a specific report section"""
        try:
            relevant_data = {
                "framework": {},
                "esg_data": {},
                "metrics": {}
            }
            
            # Map sections to disclosure areas in framework and info gather outputs
            section_mapping = {
                1: ["Introduction", "General Requirements"],  # Introduction
                2: ["Governance"],  # Governance
                3: ["Materiality Assessment", "Materiality"],  # Materiality Assessment
                4: ["Environmental Disclosures", "Climate", "Environment"],  # Environmental Disclosures
                5: ["Social Disclosures", "Social", "Employee", "Community"],  # Social Disclosures
                6: ["Governance Disclosures", "Anti-Corruption", "Ethics"],  # Governance Disclosures
                7: ["Metrics and Targets", "Performance Indicators"],  # Metrics and Targets
                8: ["Reporting Principles", "Methodology"],  # Reporting Principles
                9: ["Conclusion", "Summary"]  # Conclusion
            }
            
            # Extract framework information
            if framework_output and hasattr(framework_output, 'framework'):
                framework = framework_output.framework
                
                # Extract disclosure areas that match the section
                if section_number in section_mapping:
                    section_keywords = section_mapping[section_number]
                    
                    # Find matching disclosure areas
                    matching_areas = []
                    for area in framework.disclosure_areas:
                        for keyword in section_keywords:
                            if keyword.lower() in area.name.lower():
                                matching_areas.append(area)
                                break
                    
                    relevant_data["framework"]["disclosure_areas"] = matching_areas
                    
                # Add general framework information
                relevant_data["framework"]["company"] = framework.company
                relevant_data["framework"]["stock_symbol"] = framework.stock_symbol
                relevant_data["framework"]["industry"] = framework.industry
                relevant_data["framework"]["summary"] = framework.summary
                
                # For metrics section, include all applicable metrics
                if section_number == 7:  # Metrics and Targets
                    relevant_data["framework"]["applicable_metrics"] = framework.applicable_metrics
            
            # Extract ESG data
            if info_gather_output and hasattr(info_gather_output, 'esg_data'):
                esg_data = info_gather_output.esg_data
                
                # Extract disclosure data that match the section
                if section_number in section_mapping:
                    section_keywords = section_mapping[section_number]
                    
                    # Find matching disclosure areas
                    matching_areas = []
                    for area in esg_data.disclosure_data:
                        for keyword in section_keywords:
                            if keyword.lower() in area.area_name.lower():
                                matching_areas.append(area)
                                break
                    
                    relevant_data["esg_data"]["disclosure_data"] = matching_areas
                
                # Add general ESG data information
                relevant_data["esg_data"]["company"] = esg_data.company
                relevant_data["esg_data"]["stock_symbol"] = esg_data.stock_symbol
                relevant_data["esg_data"]["industry"] = esg_data.industry
                
                # For metrics section, include all metrics data
                if section_number == 7:  # Metrics and Targets
                    relevant_data["metrics"] = esg_data.metrics_data
                    
            return relevant_data
            
        except Exception as e:
            if self.debug:
                self.log_error(f"Error extracting relevant data: {str(e)}")
            return {"framework": {}, "esg_data": {}, "metrics": {}}

    def _extract_sources_from_data_points(self, data_points):
        """Extract sources from data points for citation"""
        sources = []
        
        if not data_points:
            return sources
            
        for point in data_points:
            if hasattr(point, 'sources') and point.sources:
                for source in point.sources:
                    source_dict = {
                        "source_type": source.source_type if hasattr(source, 'source_type') else "Unknown",
                        "source_name": source.source_name if hasattr(source, 'source_name') else "Unknown",
                        "source_url": source.source_url if hasattr(source, 'source_url') else None,
                        "source_date": source.source_date if hasattr(source, 'source_date') else None
                    }
                    if source_dict not in sources:
                        sources.append(source_dict)
                        
            # Also check for grounded content sources
            if hasattr(point, 'content') and hasattr(point.content, 'sources'):
                for grounded_source in point.content.sources:
                    source_dict = {
                        "source_type": "web" if hasattr(grounded_source, 'uri') and grounded_source.uri.startswith('http') else "report",
                        "source_name": grounded_source.title if hasattr(grounded_source, 'title') else "Unknown",
                        "source_url": grounded_source.uri if hasattr(grounded_source, 'uri') else None,
                    }
                    if source_dict not in sources:
                        sources.append(source_dict)
                        
        return sources

    def generate_report_section(self, section_number: int, framework_output, info_gather_output):
        """Generate a specific section of the ESG report"""
        try:
            section_info = self._extract_section_from_structure(section_number)
            section_title = section_info["title"]
            section_guidelines = section_info["content"]
            
            # Extract relevant data for this section
            relevant_data = self._extract_relevant_data_for_section(
                section_number, framework_output, info_gather_output
            )
            
            # Extract company information
            company = relevant_data["esg_data"].get("company", "")
            if not company and "framework" in relevant_data:
                company = relevant_data["framework"].get("company", "")
                
            stock_symbol = relevant_data["esg_data"].get("stock_symbol", "")
            industry = relevant_data["esg_data"].get("industry", "")
            
            # Collect data points for this section
            data_points = []
            for area in relevant_data["esg_data"].get("disclosure_data", []):
                if hasattr(area, 'data_points'):
                    data_points.extend(area.data_points)
            
            # Extract sources from data points
            sources = self._extract_sources_from_data_points(data_points)
            
            # Prepare metrics information if this is the metrics section
            metrics_info = ""
            if section_number == 7 and relevant_data["metrics"]:
                metrics_info = json.dumps(relevant_data["metrics"], indent=2)
            
            # Construct the prompt for generating this section
            prompt = f"""
            You are an expert ESG report writer. Your task is to draft Section {section_number}: {section_title} of the ESG report for {company} ({stock_symbol}), a company in the {industry} industry.

            SECTION GUIDELINES:
            {section_guidelines}
            
            RELEVANT DATA:
            """
            
            # Add data points content
            if data_points:
                prompt += "DATA POINTS:\n"
                for i, point in enumerate(data_points):
                    if hasattr(point, 'requirement_id'):
                        prompt += f"Requirement ID: {point.requirement_id}\n"
                    
                    # Extract content text
                    if hasattr(point, 'content'):
                        if isinstance(point.content, str):
                            prompt += f"Content: {point.content}\n\n"
                        elif hasattr(point.content, 'text'):
                            prompt += f"Content: {point.content.text}\n\n"
            else:
                prompt += "No specific data points available for this section.\n\n"
                
            # Add metrics information for metrics section
            if metrics_info:
                prompt += f"METRICS DATA:\n{metrics_info}\n\n"
                
            # Add framework requirements
            if "disclosure_areas" in relevant_data["framework"]:
                prompt += "FRAMEWORK REQUIREMENTS:\n"
                for area in relevant_data["framework"]["disclosure_areas"]:
                    if hasattr(area, 'name') and hasattr(area, 'description'):
                        prompt += f"{area.name}: {area.description}\n"
                    if hasattr(area, 'requirements'):
                        for req in area.requirements:
                            if hasattr(req, 'id') and hasattr(req, 'description'):
                                prompt += f"- {req.id}: {req.description}\n"
                                if hasattr(req, 'guidance_notes') and req.guidance_notes:
                                    prompt += f"  Guidance: {req.guidance_notes}\n"
                    prompt += "\n"
            
            # Finalize the prompt with instructions
            prompt += f"""
            YOUR TASK:
            1. Draft a comprehensive and coherent Section {section_number}: {section_title} for the ESG report.
            2. Format your response as a long paragraph or series of paragraphs that flow naturally.
            3. Use only the information provided above, do not fabricate data or statistics.
            4. Maintain a professional and objective tone suitable for an official ESG report.
            5. Ensure the content meets the quality assurance requirements mentioned in the guidelines.
            
            Your response must contain only the draft content for this section, without section titles or headings.
            """
            
            if self.debug:
                self.log_process(f"Generating Section {section_number}: {section_title}")
                
            # Generate the section content
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config = types.GenerateContentConfig(
                    temperature = 1.3,
                    top_p = 1,
                    seed = 0,
                    max_output_tokens = 8192,
                    response_mime_type="application/json",
                    safety_settings = [
                        types.SafetySetting(
                            category="HARM_CATEGORY_HATE_SPEECH",
                            threshold="OFF"
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_DANGEROUS_CONTENT",
                            threshold="OFF"
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            threshold="OFF"
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_HARASSMENT",
                            threshold="OFF"
                    )],
                )
            )

            
            # Create the section
            section = ReportSection(
                title=section_title,
                content=response.text,
                sources=sources
            )
            
            return section
            
        except Exception as e:
            if self.debug:
                self.log_error(f"Error generating section {section_number}: {str(e)}")
            
            return ReportSection(
                title=f"Section {section_number}",
                content=f"Error generating this section: {str(e)}",
                sources=[]
            )

    def generate_report(self, framework_output, info_gather_output, start_month_year, end_month_year):
        """Generate a complete ESG report based on outputs from Framework and InfoGather agents"""
        try:
            if self.debug:
                self.log_info(f"Starting ESG report generation")
                
            # Extract company information
            company = "Unknown"
            stock_symbol = "Unknown"
            industry = "Unknown"
            
            if framework_output and hasattr(framework_output, 'framework'):
                company = framework_output.framework.company
                stock_symbol = framework_output.framework.stock_symbol
                industry = framework_output.framework.industry
            elif info_gather_output and hasattr(info_gather_output, 'esg_data'):
                company = info_gather_output.esg_data.company
                stock_symbol = info_gather_output.esg_data.stock_symbol
                industry = info_gather_output.esg_data.industry
                
            reporting_period = f"{start_month_year} - {end_month_year}"
            
            # Generate all sections (9 sections in report_structure_prompt)
            sections = []
            for i in range(1, 10):  # Sections 1 through 9
                section = self.generate_report_section(i, framework_output, info_gather_output)
                sections.append(section)
                
                if self.debug:
                    self.log_info(f"Generated section: {section.title}")
                    
            # Create the complete report
            report = GeneratedReport(
                company=company,
                stock_symbol=stock_symbol,
                industry=industry,
                reporting_period=reporting_period,
                timestamp=datetime.now(),
                sections=sections
            )
            
            if self.debug:
                self.log_info(f"Completed ESG report generation for {company}")
                
            return report
            
        except Exception as e:
            if self.debug:
                self.log_error(f"Error generating report: {str(e)}")
            
            # Return partial report if available
            return GeneratedReport(
                company=company if company else "Unknown",
                stock_symbol=stock_symbol if stock_symbol else "Unknown",
                industry=industry if industry else "Unknown",
                reporting_period=f"{start_month_year} - {end_month_year}",
                timestamp=datetime.now(),
                sections=sections if locals().get('sections') else []
            )

