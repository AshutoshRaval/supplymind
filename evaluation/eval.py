"""
Agent evaluation using DeepEval — industry standard LLM evaluation framework.

Uses GEval (LLM-as-a-Judge) pattern:
  Claude evaluates Claude's output against defined criteria.

3 GEval metrics:
  1. Answer Relevancy   — is the report relevant to the inventory question?
  2. Faithfulness       — does the report stick to the DB data?
  3. Business Rules     — does the report follow our domain rules?
"""

from dotenv import load_dotenv
from deepeval import evaluate
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.models import DeepEvalBaseLLM
from anthropic import Anthropic

load_dotenv()


class ClaudeJudge(DeepEvalBaseLLM):
    """
    Wraps Claude Haiku as the judge model for DeepEval.
    DeepEval uses this to score the agent's output.
    """

    def __init__(self):
        self.client = Anthropic()
        self.model_name = "claude-haiku-4-5-20251001"

    def load_model(self):
        return self.client

    def generate(self, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return self.model_name


def build_retrieval_context() -> list[str]:
    """Pull actual DB data as context for faithfulness check."""
    from sqlalchemy.orm import Session
    from db.models import Item, Supplier, SupplierItem, engine

    context = []
    with Session(engine) as session:
        items = session.query(Item).filter(
            Item.current_stock <= Item.threshold
        ).all()
        for item in items:
            context.append(
                f"{item.name} (SKU: {item.sku}): "
                f"stock={item.current_stock}, threshold={item.threshold}"
            )

        results = (
            session.query(SupplierItem, Supplier)
            .join(Supplier, SupplierItem.supplier_id == Supplier.id)
            .all()
        )
        for si, supplier in results:
            context.append(
                f"{supplier.name}: rating={supplier.rating}, "
                f"lead_time={supplier.lead_time_days} days, "
                f"price={si.price_per_unit}"
            )

    return context


def run_evaluation(agent_output: str) -> None:
    """
    Run DeepEval GEval evaluation on agent output.
    Claude Haiku acts as judge for all 3 metrics.
    """
    input_query = (
        "Check the inventory and report any items that need restocking. "
        "For each urgent item, recommend the best supplier and quantity to order."
    )

    retrieval_context = build_retrieval_context()
    judge = ClaudeJudge()

    test_case = LLMTestCase(
        input=input_query,
        actual_output=agent_output,
        retrieval_context=retrieval_context,
    )

    # Metric 1: Answer Relevancy
    relevancy = GEval(
        name="Answer Relevancy",
        model=judge,
        criteria="""
        Does the output directly answer the question about inventory restocking?
        A good answer:
        - Identifies which items need restocking
        - Provides supplier recommendations
        - Gives actionable next steps
        Score low if the output is off-topic or vague.
        """,
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        threshold=0.7,
    )

    # Metric 2: Faithfulness
    faithfulness = GEval(
        name="Faithfulness",
        model=judge,
        criteria="""
        Does the output stick to facts from the retrieval context?
        Check:
        - Supplier names match the context
        - Prices mentioned are consistent with context
        - Stock levels mentioned are accurate
        Score low if the output contains made-up supplier names or prices
        not present in the context.
        """,
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.RETRIEVAL_CONTEXT,
        ],
        threshold=0.7,
    )

    # Metric 3: Business Rules (domain-specific)
    business_rules = GEval(
        name="Business Rules Compliance",
        model=judge,
        criteria="""
        Evaluate the inventory report against these business rules:

        1. CRITICAL items (<=3 days to stockout) must be clearly marked urgent.

        2. If a supplier lead time exceeds the days to stockout for a CRITICAL
           item, the report must explicitly warn about this risk.

        3. Every flagged item must include:
           - Specific supplier name
           - Price per unit
           - Quantity to order
           - Lead time

        4. Items sorted CRITICAL first, then HIGH priority.

        Score 0 if rules are ignored. Score 1 if all rules followed perfectly.
        """,
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.7,
    )

    print("\n" + "=" * 60)
    print("DEEPEVAL EVALUATION — Claude as Judge")
    print("=" * 60)
    print("Metrics: Answer Relevancy | Faithfulness | Business Rules")
    print("Threshold: 0.7 (pass/fail)\n")

    evaluate(
        test_cases=[test_case],
        metrics=[relevancy, faithfulness, business_rules],
    )
