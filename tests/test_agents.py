import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the src directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the agent classes
from src.esg_agent.agent_handler.agent_01_ExecutionAgent import ExecutionAgent
from src.esg_agent.agent_handler.agent_02_PlanningAgent import PlanningAgent
from src.esg_agent.agent_handler.agent_03_FrameworkAgent import FrameworkAgent

class TestAgentSetup(unittest.TestCase):
    """Test basic agent setup and initialization"""
    
    def test_execution_agent_creation(self):
        """Test that ExecutionAgent can be properly instantiated"""
        mock_client = MagicMock()
        
        agent = ExecutionAgent.create(
            client=mock_client,
            model_name="gemini-pro",
            model_search="gemini-pro",
            pdf_url="https://example.com/report.pdf",
            debug=True
        )
        
        self.assertIsInstance(agent, ExecutionAgent)
        self.assertEqual(agent.model_name, "gemini-pro")
        self.assertTrue(agent.debug)
        self.assertEqual(agent.pdf_url, "https://example.com/report.pdf")
    
    @patch('src.esg_agent.agent_handler.agent_02_PlanningAgent.PlanningAgent.create_plan')
    def test_planning_agent(self, mock_create_plan):
        """Test PlanningAgent with mocked create_plan method"""
        # Setup the mock return value
        mock_plan = MagicMock()
        mock_plan.validated_query.is_valid = True
        mock_plan.validated_query.company = "Test Company"
        mock_plan.validated_query.stock_symbol = "TEST"
        mock_create_plan.return_value = mock_plan
        
        # Create the agent
        mock_client = MagicMock()
        planning_agent = PlanningAgent(
            query="Create an ESG report for Test Company (TEST)",
            client=mock_client,
            model_name="gemini-pro",
            debug=True
        )
        
        # Call the create_plan method
        plan = planning_agent.create_plan()
        
        # Assertions
        self.assertEqual(plan.validated_query.company, "Test Company")
        self.assertEqual(plan.validated_query.stock_symbol, "TEST")
        self.assertTrue(plan.validated_query.is_valid)
        
    def test_framework_agent(self):
        """Test FrameworkAgent basic initialization"""
        mock_client = MagicMock()
        
        framework_agent = FrameworkAgent(
            client=mock_client,
            model_name="gemini-pro",
            debug=True
        )
        
        self.assertIsInstance(framework_agent, FrameworkAgent)
        
if __name__ == '__main__':
    unittest.main()
