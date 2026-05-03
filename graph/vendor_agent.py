from langchain_anthropic import ChatAnthropic                                                                                  
from langgraph.prebuilt import create_react_agent                                                                              
from dotenv import load_dotenv                                                                                                                                                                                                                                  
from tools.inventory import get_supplier_quotes, get_best_supplier                                                             
from skills.reorder import calculate_reorder_quantity
from skills.rag import search_inventory                                                                                        
                                                                                                                                 
load_dotenv()

llm = ChatAnthropic(model="claude-haiku-4-5-20251001")
                                                                                                                                 
tools = [                                                                                                                      
      get_supplier_quotes,                                                                                                       
      get_best_supplier,                                                                                                         
      calculate_reorder_quantity,                                                                                                
      search_inventory,
  ]    


system_prompt = """
  You are a vendor advisor for a warehouse procurement team.
                                                                                                                                 
  You will be given an item_id and urgency level from the inventory monitor.
                                                                                                                                 
  Your job:       
  1. Call get_supplier_quotes to see all available vendors for the item                                                          
  2. Call get_best_supplier to get the top recommendation                                                                        
  3. Call calculate_reorder_quantity using the best supplier's lead_time_days
  4. Present a complete procurement recommendation with:                                                                         
     - Item name and SKU                                                                                                         
     - Recommended supplier, price per unit, and lead time                                                                       
     - Exact quantity to order                                                                                                   
     - Total cost estimate
     - Reasoning behind the recommendation                                                                                       
                  
  Rules:
  - If urgency is CRITICAL, flag if lead_time_days > days_to_stockout                                                            
  - Always show the total cost: quantity × price_per_unit                                                                        
  - Be specific and actionable — give exact numbers, not ranges                                                                  
  - If no suppliers are found, clearly state that and suggest searching alternatives                                             
  """      

agent = create_react_agent(llm, tools, prompt=system_prompt)
                                                                                                                                 
                                                                                                                                 
def run_vendor_advisor(item_id: int, urgency: str, days_to_stockout: float) -> str:                                            
    result = agent.invoke(                                                                                                     
          {                                                                                                                      
              "messages": [{
                  "role": "user",
                  "content": (                                                                                                   
                      f"item_id: {item_id}, "
                      f"urgency: {urgency}, "                                                                                    
                      f"days_to_stockout: {days_to_stockout}. "
                      f"Provide a complete procurement recommendation."                                                          
                  )
              }]                                                                                                                 
          },      
          config={"recursion_limit": 20},
      )
    return result["messages"][-1].content