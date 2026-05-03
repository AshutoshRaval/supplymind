from datetime import date, timedelta                                                                                                                                    
from langchain_core.tools import tool

@tool                                                                                                                                                        
def generate_po_draft(                                                                                                                                       
      item_name: str,
      sku: str,                                                                                                                                                
      supplier_name: str,
      quantity: int,                                                                                                                                           
      price_per_unit: float,
      lead_time_days: int,                                                                                                                                     
      urgency: str,
  ) -> str:
    """                                                                                                                                                      
      Generate a Purchase Order draft for a single item.                                                                                                       
                                                                                                                                                               
      Args:                                                                                                                                                    
          item_name: Name of the inventory item                                                                                                                
          sku: Stock keeping unit code
          supplier_name: Name of the chosen supplier
          quantity: Number of units to order                                                                                                                   
          price_per_unit: Cost per unit in dollars
          lead_time_days: Expected delivery time in days                                                                                                       
          urgency: CRITICAL or HIGH                                                                                                                            
      """
             
    today = date.today()                                                                                                                                     
    po_number = f"PO-{today.strftime('%Y%m%d')}-{sku}"                                                                                                       
    total_cost = quantity * price_per_unit                                                                                                                   
    

    return f"""                                                                                                                                              
        ========================================                                                                                                                     
        PURCHASE ORDER — {po_number}
        ========================================                                                                                                                     
        Date        : {today}
        Urgency     : {urgency}                                                                                                                                      
                        
        ITEM
            Name      : {item_name}
            SKU       : {sku}                                                                                                                                          
            Quantity  : {quantity} units
                                                                                                                                                                    
        SUPPLIER        
            Name      : {supplier_name}
            Unit Price: ${price_per_unit:.2f}                                                                                                                          
            Total Cost: ${total_cost:.2f}
            Lead Time : {lead_time_days} days                                                                                                                          
            Est. Arrival: {today + timedelta(days=lead_time_days)}                                                                                              
                                                                                                                                                                    
        ========================================                                                                                                                     
        STATUS: DRAFT — Awaiting Approval                                                                                                                            
        ========================================                                                                                                                     
        """