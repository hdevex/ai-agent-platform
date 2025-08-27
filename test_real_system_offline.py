#!/usr/bin/env python3
"""
Test REAL system data retrieval without LM Studio
"""

from real_excel_chat_system import IntelligentQueryAnalyzer, TokenEfficientDataRetriever

def test_query_analysis():
    """Test the intelligent query analyzer."""
    analyzer = IntelligentQueryAnalyzer()
    
    test_queries = [
        "What companies are mentioned in TURN-COS-GP_RM?",
        "Find revenue figures greater than 1 million",
        "List all the worksheets in the Excel files",
        "Show me financial data from PNL sheet",
        "Which construction companies are in GROUP-BS_RM?",
        "Calculate total assets above 500 thousand"
    ]
    
    print("🔍 QUERY ANALYSIS TEST (No hardcoding)")
    print("=" * 50)
    
    for query in test_queries:
        analysis = analyzer.analyze_query(query)
        print(f"\nQuery: {query}")
        print(f"Intent scores: {analysis['intent_scores']}")
        print(f"Target sheets: {analysis['target_sheets']}")
        print(f"Data types needed: {analysis['data_types_needed']}")
        print(f"Filters required: {analysis['filters_required']}")
        print("-" * 30)

def test_data_retrieval():
    """Test data retrieval from real Excel database."""
    retriever = TokenEfficientDataRetriever()
    analyzer = IntelligentQueryAnalyzer()
    
    test_queries = [
        "What companies are in TURN-COS-GP_RM?",
        "Find numbers greater than 1000000"
    ]
    
    print("\n📊 DATA RETRIEVAL TEST (Real Excel data)")
    print("=" * 50)
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        analysis = analyzer.analyze_query(query)
        data = retriever.get_relevant_data(analysis)
        
        print(f"Found {len(data)} relevant data points:")
        for i, item in enumerate(data[:5], 1):
            print(f"  {i}. [{item['type']}] {item.get('data', item.get('value', 'N/A'))} (from {item.get('sheet', 'unknown')})")
        
        if len(data) > 5:
            print(f"  ... and {len(data) - 5} more items")
        print("-" * 30)

if __name__ == "__main__":
    test_query_analysis()
    test_data_retrieval()