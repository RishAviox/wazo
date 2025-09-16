import json
from core.llm_provider import client
from .post_match_intelligence import player_postmatch_intelligence
from .openai_schema import PLAYER_POSTMATCH_INTELLIGENCE_SCHEMA


def run_conversation(content):
    """
    Run a conversation with OpenAI that can call player_postmatch_intelligence function
    
    Args:
        content: User message/question
        
    Returns:
        OpenAI response stream or final response
    """

    print(f"\n{'*'*20}User Content: {content}\n{'*'*20}")
    SYSTEM_PROMPT = """
        You are a post-match performance assistant.
        Use the player_postmatch_intelligence tool to generate structured post-match insights for a specific player and match.
        Each request includes a task (e.g., summarize, compare, evaluate), the requester's role, and optional context in notes.
        Always ensure responses are concise, coach-ready, and action-oriented.
        If the task is trigger_emotional_reflection, include an emotional prompt suitable for player introspection.
        For other tasks, generate a structured output with:
        - Performance Summary
        - Strengths
        - Improvement Areas
        - Tactical Fit
        - Suggested Actions
        - Quick Actions
        - (Optional) Emotional Reflection

        If function output is available (`insight_data`), incorporate it directly to generate the final natural-language summary.
        If function needs to be called, extract the parameters and call the tool first.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content}
    ]
    
    # Define available tools (functions)
    tools = [PLAYER_POSTMATCH_INTELLIGENCE_SCHEMA]
    
    try:
        # First API call to see if function calling is needed
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=messages,
            tools=tools,
            tool_choice="auto",  # Let the model decide when to call functions
        )
        
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        
        if tool_calls:
            print(f"Tool calls: {tool_calls}")
            # Function calling was triggered
            messages.append(response_message)
            
            # Available functions mapping
            available_functions = {
                "player_postmatch_intelligence": player_postmatch_intelligence,
            }
            
            # Process each function call
            for tool_call in tool_calls:
                print(f"Function: {tool_call.function.name}")
                print(f"Params: {tool_call.function.arguments}")
                
                function_name = tool_call.function.name
                function_to_call = available_functions[function_name]
                
                try:
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Call the function with the parsed arguments
                    function_response = function_to_call(**function_args)
                    
                    print(f"Function Response: {function_response}")
                    
                    # Add function response to conversation
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool", 
                            "name": function_name,
                            "content": function_response,
                        }
                    )
                except json.JSONDecodeError as e:
                    print(f"Error parsing function arguments: {e}")
                    # Add error response
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps({"error": f"Invalid function arguments: {str(e)}"}),
                        }
                    )
                except Exception as e:
                    print(f"Error calling function {function_name}: {e}")
                    # Add error response
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps({"error": f"Function execution failed: {str(e)}"}),
                        }
                    )
            
            # Second API call to get the final response with function results
            try:
                second_response = client.chat.completions.create(
                    model="gpt-3.5-turbo-0125",
                    messages=messages,
                    stream=True
                )
                return second_response
            except Exception as e:
                print(f"Error in second API call: {e}")
                # Return a fallback response
                return {
                    "choices": [{
                        "message": {
                            "content": f"Analysis completed but there was an error processing the response: {str(e)}"
                        }
                    }]
                }
        
        else:
            return response
            
    except Exception as e:
        print(f"Error in OpenAI API call: {e}")
        # Return a fallback response
        return {
            "choices": [{
                "message": {
                    "content": f"Sorry, I encountered an error while processing your request: {str(e)}"
                }
            }]
        }


def run_conversation_sync(content):
    """
    Synchronous version that returns the complete response as a string
    
    Args:
        content: User message/question
        
    Returns:
        Complete response string
    """
    try:
        response = run_conversation(content)
        
        if hasattr(response, 'choices'):
            # Direct response without streaming
            return response.choices[0].message.content
        else:
            # Streaming response, collect all chunks
            response_text = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    response_text += chunk.choices[0].delta.content
            return response_text
            
    except Exception as e:
        print(f"Error in run_conversation_sync: {e}")
        return f"Error processing conversation: {str(e)}"


# Example usage for testing
if __name__ == "__main__":
    # Example 1: Direct post-match analysis request
    question1 = """
    Generate a performance summary for player_123 from match_789. 
    I'm a Coach and want to understand how the player performed overall.
    The player showed good work rate but seemed to fade after 70 minutes.
    """
    
    print("=" * 50)
    print("Example 1: Performance Summary")
    print("=" * 50)
    print(f"Question: {question1}")
    print("\nResponse:")
    
    response1 = run_conversation(question1)
    if hasattr(response1, 'choices'):
        print(response1.choices[0].message.content)
    else:
        for chunk in response1:
            print(chunk.choices[0].delta.content or "", end='', flush=True)
    
    print("\n\n")
    
    # Example 2: Comparison analysis
    question2 = """
    Compare player_456's performance in match_abc with their previous match match_xyz.
    I'm a Coach looking for trends and improvements.
    """
    
    print("=" * 50) 
    print("Example 2: Performance Comparison")
    print("=" * 50)
    print(f"Question: {question2}")
    print("\nResponse:")
    
    response2 = run_conversation(question2)
    if hasattr(response2, 'choices'):
        print(response2.choices[0].message.content)
    else:
        for chunk in response2:
            print(chunk.choices[0].delta.content or "", end='', flush=True)
    
    print("\n\n")
    
    # Example 3: Emotional reflection
    question3 = """
    Help player_789 process the emotions from a tough loss in match_def.
    I'm a Coach and the player seems frustrated after the match.
    """
    
    print("=" * 50)
    print("Example 3: Emotional Reflection")  
    print("=" * 50)
    print(f"Question: {question3}")
    print("\nResponse:")
    
    response3 = run_conversation(question3)
    if hasattr(response3, 'choices'):
        print(response3.choices[0].message.content)
    else:
        for chunk in response3:
            print(chunk.choices[0].delta.content or "", end='', flush=True)
