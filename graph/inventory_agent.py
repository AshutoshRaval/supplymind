import time
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from dotenv import load_dotenv   
from tools.inventory import (                                                                                                                   
      check_stock_levels,
      get_consumption_velocity,                                                                                                                   
      get_supplier_quotes,
      get_low_stock_summary,
      get_best_supplier,                                                                                                                          
)
from skills.rag import search_inventory                                                                                                         
                  
load_dotenv()

llm = ChatAnthropic(model="claude-haiku-4-5-20251001")                                                                                          

tools = [                                                                                                                                       
      check_stock_levels,
      get_consumption_velocity,
      get_supplier_quotes,
      get_low_stock_summary,
      get_best_supplier,
      search_inventory,
  ]

system_prompt = """
  You are an inventory monitor for a warehouse.                                                                                                   
                                                                                                                                                  
  Your job:                                                                                                                                       
  1. Call get_low_stock_summary to get all items that need attention                                                                              
  2. For each CRITICAL or HIGH urgency item, call get_best_supplier                                                                               
  3. Present a clear alert report with:                                                                                                           
     - Item name and SKU                                                                                                                          
     - Current stock and days to stockout                                                                                                         
     - Urgency level                                                                                                                              
     - Best supplier name, price, and lead time
                                                                                                                                                  
  Rules:          
  - Never recommend a supplier whose lead_time_days > days_to_stockout                                                                            
  - Always sort your report: CRITICAL items first, then HIGH                                                                                      
  - Be concise and actionable                                                                                                                     
  """  


agent = create_react_agent(llm, tools, prompt=system_prompt)


def run_inventory_monitor(retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            result = agent.invoke(
                {
                    "messages": [{
                        "role": "user",
                        "content": "Check the inventory and report any items that need restocking."
                    }]
                },
                config={"recursion_limit": 20},  # max 20 steps before force-stop
            )
            return result["messages"][-1].content
        except Exception as e:
            if attempt < retries - 1:
                print(f"[Attempt {attempt + 1} failed] {e}. Retrying in 2s...")
                time.sleep(2)
            else:
                return f"Agent failed after {retries} attempts: {str(e)}"