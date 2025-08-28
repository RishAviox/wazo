"""
Demo script for player_postmatch_intelligence function calling

This script follows the exact pattern of your weather example
but implements post-match intelligence analysis.
"""

import json
from .conversation_runner import run_conversation


def demo_postmatch_intelligence():
    """
    Demo function that mimics your weather example usage
    """
    
    print("🏈 Player Post-Match Intelligence Demo")
    print("=" * 50)
    
    # Example 1: Performance Summary (like your Paris weather example)
    print("\n📊 Example 1: Performance Summary")
    print("-" * 30)
    
    question1 = """
    Generate a performance summary for player_123 from match_789. 
    I'm a Coach and need to understand the player's overall performance.
    The player showed excellent work rate but seemed to fade after 70 minutes.
    """
    
    print(f"Question: {question1}")
    print("\n🤖 AI Response:")
    
    response1 = run_conversation(question1)
    for chunk in response1:
        print(chunk.choices[0].delta.content or "", end='', flush=True)
    
    print("\n\n")
    
    # Example 2: Comparison Analysis (like your Paris and SF example)
    print("📈 Example 2: Performance Comparison")
    print("-" * 35)
    
    question2 = """
    Compare player_456's performance in match_abc with their previous match match_xyz.
    I'm a Coach and need to identify performance trends and areas of improvement.
    """
    
    print(f"Question: {question2}")
    print("\n🤖 AI Response:")
    
    response2 = run_conversation(question2)
    for chunk in response2:
        print(chunk.choices[0].delta.content or "", end='', flush=True)
    
    print("\n\n")
    
    # Example 3: Multiple players analysis
    print("👥 Example 3: Multiple Players Analysis")
    print("-" * 38)
    
    question3 = """
    I need post-match intelligence for player_123 and player_456 from match_789.
    As a Coach, I want to understand both players' performance and create action items.
    Player_123 had good defensive work but poor distribution.
    Player_456 was strong in attack but needs to work on positioning.
    """
    
    print(f"Question: {question3}")
    print("\n🤖 AI Response:")
    
    response3 = run_conversation(question3)
    for chunk in response3:
        print(chunk.choices[0].delta.content or "", end='', flush=True)
    
    print("\n\n")


def demo_direct_function_calls():
    """
    Demo direct function calls (like calling get_current_weather directly)
    """
    from .post_match_intelligence import player_postmatch_intelligence
    
    print("🔧 Direct Function Call Examples")
    print("=" * 35)
    
    # Example 1: Summarize Performance
    print("\n📊 Direct Call: Summarize Performance")
    print("-" * 38)
    
    result1 = player_postmatch_intelligence(
        task="summarize_performance",
        userRole="Coach",
        playerId="player_123",
        matchId="match_789",
        language="en",
        notes="Player showed good work rate but faded after 70 minutes"
    )
    
    print("Function Result:")
    print(json.dumps(json.loads(result1), indent=2))
    
    # Example 2: Emotional Reflection
    print("\n💭 Direct Call: Emotional Reflection")
    print("-" * 36)
    
    result2 = player_postmatch_intelligence(
        task="trigger_emotional_reflection",
        userRole="Coach", 
        playerId="player_456",
        matchId="match_abc",
        language="en",
        notes="Player seems frustrated after a tough loss"
    )
    
    print("Function Result:")
    print(json.dumps(json.loads(result2), indent=2))
    
    # Example 3: Hebrew Language
    print("\n🇮🇱 Direct Call: Hebrew Language")
    print("-" * 33)
    
    result3 = player_postmatch_intelligence(
        task="highlight_strengths",
        userRole="Coach",
        playerId="player_789", 
        matchId="match_def",
        language="he",
        notes="השחקן הראה ביצועים מעולים במחצית השנייה"
    )
    
    print("Function Result:")
    print(json.dumps(json.loads(result3), indent=2))


def demo_api_usage():
    """
    Demo how to use the API endpoint (for testing with curl/Postman)
    """
    
    print("🌐 API Usage Examples")
    print("=" * 25)
    
    # Natural language API call
    natural_language_payload = {
        "message": "Generate a performance summary for player_123 from match_789. I'm a Coach and the player showed good work rate but faded after 70 minutes."
    }
    
    print("\n📝 Natural Language API Call:")
    print("POST /chatbot-features/player-postmatch-intelligence")
    print("Content-Type: application/json")
    print("Authorization: Bearer <your-token>")
    print()
    print(json.dumps(natural_language_payload, indent=2))
    
    # Direct function call API
    function_call_payload = {
        "function_call": {
            "task": "summarize_performance",
            "userRole": "Coach",
            "playerId": "player_123", 
            "matchId": "match_789",
            "language": "en",
            "notes": "Player showed good work rate but faded after 70 minutes"
        }
    }
    
    print("\n🔧 Direct Function Call API:")
    print("POST /chatbot-features/player-postmatch-intelligence")
    print("Content-Type: application/json")
    print("Authorization: Bearer <your-token>")
    print()
    print(json.dumps(function_call_payload, indent=2))
    
    # Curl examples
    print("\n📡 Curl Examples:")
    print()
    print("# Natural language:")
    print('curl -X POST http://localhost:8000/chatbot-features/player-postmatch-intelligence \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -H "Authorization: Bearer <your-token>" \\')
    print('  -d \'{"message": "Analyze player_123 performance in match_789 as a Coach"}\'')
    print()
    print("# Direct function call:")
    print('curl -X POST http://localhost:8000/chatbot-features/player-postmatch-intelligence \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -H "Authorization: Bearer <your-token>" \\')
    print('  -d \'{"function_call": {"task": "summarize_performance", "userRole": "Coach", "playerId": "player_123", "matchId": "match_789"}}\'')


if __name__ == "__main__":
    print("🚀 Starting Player Post-Match Intelligence Demo")
    print("This demo follows the exact pattern of your weather example\n")
    
    try:
        # Run conversation demos (like your weather example)
        demo_postmatch_intelligence()
        
        print("\n" + "=" * 60 + "\n")
        
        # Run direct function call demos
        demo_direct_function_calls()
        
        print("\n" + "=" * 60 + "\n")
        
        # Show API usage examples
        demo_api_usage()
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("\n💡 Make sure you have:")
        print("1. Set OPENAI_API_KEY environment variable")
        print("2. Created test players and matches in Django admin")
        print("3. Django server running")
        
    print("\n✅ Demo completed!")
    print("\n📚 Next steps:")
    print("1. Set up your OpenAI API key")
    print("2. Create test data in Django admin")
    print("3. Test the API endpoints")
    print("4. Integrate with your frontend app")
