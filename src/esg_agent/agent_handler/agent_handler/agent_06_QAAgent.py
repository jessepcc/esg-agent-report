import json
from typing import Dict, List, Optional, Union
from pydantic import BaseModel

from google.genai import types


from pydantic import BaseModel, Field, ValidationError
from rich import print as rich_print
from termcolor import colored

system_prompt = """
    You are an export ESG report compliance officer tasked with evaluating the sustainability report of a company. Your goal is to assess the report's adherence to ESG guidelines and provide a structured rating based on key criteria. You are helpful and critical and provide constructive feedback to help the company improve its sustainability reporting practices. You always refer to the latest ESG guidelines and best practices to ensure your evaluation is accurate and up-to-date. Your suggests are specific to both the ISSB standards and the content provided, no general suggestions are allowed.
"""

qa_checklist_prompt = """

## Governance
### Checklist Items

1. **DO** clearly outline the governance structure and roles responsible for overseeing sustainability-related risks and opportunities.
   - **Elaboration**: Ensure that your report provides a detailed description of the governance framework, including the roles of the board, management, and any committees involved in sustainability decision-making. This should include how these roles interact and how they are held accountable for sustainability performance.

2. **DON'T** omit details about board-level oversight of sustainability issues.
   - **Elaboration**: Avoid failing to mention how the board of directors is involved in setting sustainability goals, monitoring progress, and addressing risks. This oversight is crucial for ensuring that sustainability is integrated into the company's overall strategy and risk management processes.

3. **DO** provide information on the processes for identifying and managing sustainability-related risks.
   - **Elaboration**: Describe the methodologies and tools used to identify, assess, and prioritize sustainability risks. This could include risk assessments, scenario analyses, or other strategic planning tools that help manage these risks effectively.

4. **DON'T** neglect to disclose any conflicts of interest related to sustainability governance.
   - **Elaboration**: Ensure transparency by disclosing any potential conflicts of interest among board members or executives that could influence sustainability decisions. This helps maintain stakeholder trust and demonstrates a commitment to ethical governance practices.

5. **DO** include details on how stakeholder feedback is incorporated into governance processes.
   - **Elaboration**: Explain how the company engages with stakeholders, such as investors, employees, or community groups, to gather feedback on sustainability issues. Describe how this feedback is used to inform governance decisions and improve sustainability performance.

## Strategy
### Checklist Items

1. **DO** articulate a clear strategy for managing sustainability-related risks and opportunities.
   - **Elaboration**: Ensure that your report outlines a comprehensive strategy for addressing sustainability challenges and leveraging opportunities. This should include specific goals, targets, and initiatives aligned with the company's overall business strategy.

2. **DON'T** fail to explain how sustainability considerations are integrated into business planning.
   - **Elaboration**: Avoid omitting details on how sustainability factors are considered in strategic decision-making processes. This could include how environmental or social impacts are assessed during product development, investment decisions, or supply chain management.

3. **DO** provide metrics and targets for measuring progress toward sustainability goals.
   - **Elaboration**: Include specific metrics and targets that will be used to measure success in achieving sustainability objectives. These could be quantitative (e.g., reducing greenhouse gas emissions by a certain percentage) or qualitative (e.g., improving supply chain transparency).

4. **DON'T** neglect to discuss innovation and R&D efforts related to sustainability.
   - **Elaboration**: Ensure that your report highlights any research and development activities focused on sustainability, such as developing new sustainable products or technologies. This demonstrates a commitment to long-term sustainability through innovation.

5. **DO** outline how sustainability strategy aligns with broader business objectives.
   - **Elaboration**: Clearly explain how the sustainability strategy supports the company's overall mission and financial goals. This could involve discussing how sustainability initiatives enhance brand reputation, reduce operational costs, or create new market opportunities.

## Risk Management
### Checklist Items

1. **DO** describe the processes used to identify and assess sustainability-related risks.
   - **Elaboration**: Provide detailed information on the methodologies and tools used to identify, assess, and prioritize sustainability risks. This could include risk mapping, scenario planning, or other strategic risk management techniques.

2. **DON'T** omit details about risk mitigation strategies.
   - **Elaboration**: Avoid failing to describe the specific actions taken to mitigate identified sustainability risks. This could include implementing new policies, investing in technology, or engaging in stakeholder dialogue to address these risks effectively.

3. **DO** include information on how climate-related risks are managed.
   - **Elaboration**: Ensure that your report addresses how the company identifies, assesses, and manages climate-related risks, such as physical risks from extreme weather events or transition risks related to regulatory changes.

4. **DON'T** neglect to disclose any significant sustainability-related risks that could impact financial performance.
   - **Elaboration**: Ensure transparency by disclosing any material sustainability risks that could affect the company's financial condition or operating results. This helps investors and other stakeholders make informed decisions.

5. **DO** outline how risk management processes are monitored and reviewed.
   - **Elaboration**: Describe how the effectiveness of risk management processes is regularly assessed and improved. This could involve internal audits, external reviews, or continuous monitoring to ensure that risk management strategies remain effective over time.

## Metrics and Targets
### Checklist Items

1. **DO** report on progress toward sustainability targets using clear metrics.
   - **Elaboration**: Ensure that your report includes specific data and metrics to measure progress toward sustainability goals. This could involve tracking greenhouse gas emissions, water usage, or social metrics like diversity and inclusion.

2. **DON'T** fail to provide baseline data for comparison.
   - **Elaboration**: Avoid omitting baseline data that allows stakeholders to understand the starting point for sustainability initiatives. This helps demonstrate the effectiveness of sustainability efforts over time.

3. **DO** include forward-looking information on sustainability goals and targets.
   - **Elaboration**: Provide information on future sustainability objectives and how they will be achieved. This could involve discussing new initiatives, investments, or partnerships aimed at advancing sustainability performance.

4. **DON'T** neglect to disclose any challenges or setbacks in achieving sustainability targets.
   - **Elaboration**: Ensure transparency by discussing any obstacles faced in meeting sustainability goals. This helps build credibility and demonstrates a commitment to continuous improvement.

5. **DO** explain how sustainability metrics are integrated into executive compensation.
   - **Elaboration**: Describe how sustainability performance metrics are linked to executive compensation or incentives. This aligns executive interests with sustainability goals and encourages strong performance in these areas.

## Climate-Related Disclosures (IFRS S2)
### Checklist Items

1. **DO** report on climate-related risks and opportunities using the TCFD framework.
   - **Elaboration**: Ensure that your report aligns with the Task Force on Climate-related Financial Disclosures (TCFD) recommendations by discussing climate-related risks and opportunities across governance, strategy, risk management, and metrics and targets.

2. **DON'T** omit details about greenhouse gas emissions.
   - **Elaboration**: Avoid failing to report on greenhouse gas emissions categorized by scope (Scope 1, Scope 2, and Scope 3). This provides stakeholders with a comprehensive understanding of the company's carbon footprint.

3. **DO** include scenario analyses to assess potential climate-related impacts.
   - **Elaboration**: Provide scenario analyses that explore how different climate-related scenarios (e.g., a 1.5°C or 2°C warming scenario) could impact the company's business model, strategy, and financial performance.

4. **DON'T** neglect to discuss climate transition plans and strategies.
   - **Elaboration**: Ensure that your report outlines any plans or strategies for transitioning to a low-carbon economy. This could involve investing in renewable energy, developing low-carbon products, or implementing energy efficiency measures.

5. **DO** disclose any climate-related financial impacts or opportunities.
   - **Elaboration**: Report on any financial impacts or opportunities arising from climate-related risks or opportunities. This could include costs associated with climate change mitigation or adaptation efforts, as well as potential revenue streams from low-carbon products or services.

"""

qa_rating_prompt = """
## Rating Criteria for ESG Reports

### 1. Clarity and Transparency
   - **Description**: This criterion assesses how clearly and transparently the report presents ESG information, including data, policies, and performance metrics.
   - **Scoring**: 
     - **0-2**: The report lacks clarity, with insufficient detail or unclear metrics.
     - **3-5**: The report provides some clarity but lacks comprehensive data or clear explanations.
     - **6-8**: The report is generally clear and transparent, with most necessary information provided.
     - **9-10**: The report is highly transparent, with detailed and well-explained metrics and policies.

### 2. Governance and Accountability
   - **Description**: This criterion evaluates the governance structure and accountability mechanisms in place for ESG issues, including board oversight and executive compensation linked to sustainability performance.
   - **Scoring**:
     - **0-2**: Governance structures are poorly defined or lack accountability.
     - **3-5**: Governance is somewhat defined but lacks clear accountability mechanisms.
     - **6-8**: Governance structures are well-defined, with some accountability mechanisms in place.
     - **9-10**: Governance is robust, with strong accountability mechanisms and clear links to executive compensation.

### 3. Risk Management and Mitigation
   - **Description**: This criterion assesses how effectively the company identifies, assesses, and mitigates ESG risks, including climate-related risks.
   - **Scoring**:
     - **0-2**: Risk management processes are inadequate or not clearly described.
     - **3-5**: Risk management processes are somewhat effective but lack comprehensive strategies.
     - **6-8**: Risk management processes are generally effective, with clear strategies for mitigation.
     - **9-10**: Risk management is robust, with comprehensive strategies and effective mitigation measures.

### 4. Metrics and Targets
   - **Description**: This criterion evaluates the quality and relevance of metrics used to measure ESG performance, as well as the presence of specific, measurable targets.
   - **Scoring**:
     - **0-2**: Metrics are lacking or irrelevant, with no clear targets.
     - **3-5**: Metrics are somewhat relevant but lack clear targets or are not well-defined.
     - **6-8**: Metrics are generally relevant, with some targets in place.
     - **9-10**: Metrics are highly relevant, with clear, measurable targets that align with industry standards.

### 5. Stakeholder Engagement and Disclosure
   - **Description**: This criterion assesses how effectively the company engages with stakeholders and discloses ESG information, including transparency about challenges and progress.
   - **Scoring**:
     - **0-2**: Stakeholder engagement is minimal, with poor disclosure practices.
     - **3-5**: Stakeholder engagement is somewhat present, with limited disclosure.
     - **6-8**: Stakeholder engagement is generally effective, with good disclosure practices.
     - **9-10**: Stakeholder engagement is robust, with excellent disclosure practices that include transparent reporting on challenges and progress.
"""


class Category(BaseModel):
    score: int  # 0-10 integer value
    rationale: str  # Explanation for the score
    recommendations: str  # Suggestions for improvement


class RatingResult(BaseModel):
    clarity_transparency: Category
    governance_accountability: Category
    risk_management: Category
    metrics_targets: Category
    stakeholder_engagement: Category
    
    def average_score(self) -> float:
        """Calculate the average score across all rating categories."""
        scores = [
            getattr(self.clarity_transparency, 'score', 0),
            getattr(self.governance_accountability, 'score', 0),
            getattr(self.risk_management, 'score', 0),
            getattr(self.metrics_targets, 'score', 0),
            getattr(self.stakeholder_engagement, 'score', 0)
        ]
        return sum(scores) / len(scores)
    
    def to_dict(self) -> Dict:
        """Convert the rating result to a dictionary format."""
        return {
            "clarity_transparency": {
                "score": self.clarity_transparency.score,
                "rationale": self.clarity_transparency.rationale,
                "recommendations": self.clarity_transparency.recommendations
            },
            "governance_accountability": {
                "score": self.governance_accountability.score,
                "rationale": self.governance_accountability.rationale,
                "recommendations": self.governance_accountability.recommendations
            },
            "risk_management": {
                "score": self.risk_management.score,
                "rationale": self.risk_management.rationale,
                "recommendations": self.risk_management.recommendations
            },
            "metrics_targets": {
                "score": self.metrics_targets.score,
                "rationale": self.metrics_targets.rationale,
                "recommendations": self.metrics_targets.recommendations
            },
            "stakeholder_engagement": {
                "score": self.stakeholder_engagement.score,
                "rationale": self.stakeholder_engagement.rationale,
                "recommendations": self.stakeholder_engagement.recommendations
            }
        }


class QAAgent():
    def __init__(
        self, client, model_name: str, debug: bool = False
    ):
        self.client = client
        self.model_name = model_name
        self.debug = debug


    def evaluate_report_content(self, report_text: str) -> dict:
        """
        Uses qa_checklist_prompt and the client's model to assess qualitative aspects.
        Returns structured observations on compliance, clarity, and any missing areas.
        """
        prompt = f"{qa_checklist_prompt}\n\nReport Content:\n{report_text}\n\nProvide a concise quality assurance evaluation of the ESG report based on the checklist items above."
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config = types.GenerateContentConfig(
                temperature = 0.3,
                top_p = 1,
                seed = 0,
                max_output_tokens = 8192,
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
                system_instruction=[types.Part.from_text(text=system_prompt)],
            )
        )
        try:
            return {"checklist_evaluation": response.text}
        except Exception as e:
            if self.debug:
                rich_print(f"[bold red]Error parsing evaluation response:[/bold red] {e}")
                rich_print(f"[bold red]Response:[/bold red] {response}")
            # Return raw text as fallback
        return {"checklist_evaluation": response.text}

    def rate_report(self, report_text: dict) -> dict:
        """
        Uses qa_rating_prompt and the client's model to rate the report along each criterion.
        Returns a dictionary containing structured scores for each criterion, reasoning, and suggestions.
        """
        prompt = (
            f"{qa_rating_prompt}\n\n"
            f"Based on the following content of a ESG report {report_text}\n\n"
            "Provide a structured output with a numeric score (0-10), rationale, and improvement recommendations "
            "for each of the five criteria. Format your response as a JSON object with the following structure:\n\n"
            """
            Use this JSON schema:

            Category = {
            'score': int,  # 0-10 integer value
            'rationale': str,  # Explanation for the score
            'recommendations': str  # Suggestions for improvement
            }

            Return: {
                'clarity_transparency': Category,
                'governance_accountability': Category,
                'risk_management': Category,
                'metrics_targets': Category,
                'stakeholder_engagement': Category
            }
            """
        )
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config = types.GenerateContentConfig(
                temperature = 0,
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
                system_instruction=[types.Part.from_text(text=system_prompt)],
            )
        )
        
        try:
            # Clean and parse JSON response
            # First check if response.text is already a dictionary
            if isinstance(response.text, dict):
                rating_data = response.text
            else:
                # Clean the response text to handle potential formatting issues
                cleaned_response = response.text.strip()
                
                # Handle case where response might be a string representation of JSON
                if cleaned_response.startswith('{') and cleaned_response.endswith('}'):
                    try:
                        # Direct JSON parsing
                        rating_data = json.loads(cleaned_response)
                    except json.JSONDecodeError:
                        # Try to handle escaped quotes and newlines
                        import re
                        # Remove unnecessary escaping of quotes within the JSON string
                        unescaped = re.sub(r'\\(?=")', '', cleaned_response)
                        # Replace literal \n with actual newlines if needed
                        unescaped = unescaped.replace('\\n', '\n')
                        rating_data = json.loads(unescaped)
                else:
                    # If it's not JSON-formatted, wrap it in a basic structure
                    rating_data = {
                        "clarity_transparency": {"score": 0, "rationale": cleaned_response, "recommendations": ""},
                        "governance_accountability": {"score": 0, "rationale": "", "recommendations": ""},
                        "risk_management": {"score": 0, "rationale": "", "recommendations": ""},
                        "metrics_targets": {"score": 0, "rationale": "", "recommendations": ""},
                        "stakeholder_engagement": {"score": 0, "rationale": "", "recommendations": ""}
                    }
            
            # Create structured object
            rating_result = RatingResult(**rating_data)
            return {
                "rating_evaluation": rating_result,
                "average_score": rating_result.average_score(),
                "raw_response": response.text
            }
        except (json.JSONDecodeError, ValidationError) as e:
            if self.debug:
                rich_print(f"[bold red]Error parsing rating response:[/bold red] {e}")
                rich_print(f"[bold yellow]Raw response:[/bold yellow] {response.text[:500]}...")
            
            # Try to extract and parse any JSON-like structure in the text
            try:

                json_match = re.search(r'(\{.*\})', response.text, re.DOTALL)
                if json_match:
                    potential_json = json_match.group(1)
                    rating_data = json.loads(potential_json)
                    rating_result = RatingResult(**rating_data)
                    return {
                        "rating_evaluation": rating_result,
                        "average_score": rating_result.average_score(),
                        "raw_response": response.text
                    }
            except Exception:
                pass
                
            # Return raw text as fallback with a structured error message
            return {
                "rating_evaluation": response.text,
                "error": str(e),
                "parsing_failed": True
            }
