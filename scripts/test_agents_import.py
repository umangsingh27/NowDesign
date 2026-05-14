"""Day 4 — verify all four agents import cleanly and register their skills."""
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

# Test all skill files import
from backend.core.skills.creator_skills import (
    GenerateBackground, ValidateBackgroundLuminance, RenderGlassEffect,
    RenderTextElement, PlaceLogo, CompositeFinal,
)
print('creator_skills: OK (6 skills)')

from backend.core.skills.critic_skills import (
    AnalyzeVisualCompliance, CheckTextLegibility, CheckLuminanceZones,
    ScoreAndReport, WriteCorrectsBrief, LogCompliancePattern,
)
print('critic_skills: OK (6 skills)')

from backend.core.skills.learning_skills import (
    ReadSessionConversation, ClassifyKnowledge, WriteBrandKnowledge,
    WriteAgentMemory, ExtractDesignPatterns, LogSessionOutcome,
)
print('learning_skills: OK (6 skills)')

# Test all agent files import
from backend.core.agents import PlannerAgent, CreatorAgent, CriticAgent, LearningAgent
print('agents: OK (4 agents)')

import openai, os, json
client = openai.OpenAI(
    base_url=os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'),
    api_key=os.getenv('OPENROUTER_API_KEY', 'sk-fake-key-for-import-test'),
)

class MockLogger:
    def log_skill_invocation(self, **kwargs): pass
    def log_kb_operation(self, **kwargs): pass
    def log_session_update(self, *args, **kwargs): pass
    def log_session_create(self, *args, **kwargs): pass
    def log_conversation_message(self, **kwargs): pass
    def get_session(self, sid): return {}
    def get_conversations(self, sid): return []

config = json.load(open('brand_config.json'))
logger = MockLogger()

planner = PlannerAgent(logger, client, config)
print(f'PlannerAgent skills: {list(planner.skill_registry.keys())}')

creator = CreatorAgent(logger, client, config)
print(f'CreatorAgent skills: {list(creator.skill_registry.keys())}')

critic = CriticAgent(logger, client, config)
print(f'CriticAgent skills: {list(critic.skill_registry.keys())}')

learner = LearningAgent(logger, client, config)
print(f'LearningAgent skills: {list(learner.skill_registry.keys())}')

print()
print('ALL FOUR AGENTS READY')
